import streamlit as st
import pandas as pd
import openai
import re
import os

st.set_page_config(page_title="Vehicle Advisor", layout="centered")

@st.cache_data
def load_data():
    df = pd.read_csv("vehicle_data.csv")
    df['MSRP Min'] = df['MSRP Range'].apply(
        lambda msrp_range: float(re.findall(r'\$([\d,]+)', str(msrp_range))[0].replace(',', ''))
        if re.findall(r'\$([\d,]+)', str(msrp_range)) else None
    )
    return df

df_vehicle_advisor = load_data()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = pd.DataFrame()

def recommend_vehicles(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()
    try:
        user_budget = float(re.findall(r'\d+', user_answers.get("Budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    score_weights = {
        "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
        "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
        "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
        "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
        "Ownership Duration": 0.5, "Budget": 2.0, "Annual Mileage": 0.6
    }

    def compute_score(row):
        return sum(
            weight for key, weight in score_weights.items()
            if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower()
        )

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

def explain_recommendations(recs):
    details = []
    for _, row in recs.iterrows():
        details.append(f"<b>{row['Brand']} {row['Model']} ({row['Model Year']})</b><br>MSRP Range: {row['MSRP Range']}<br>{row.get('Description', 'No additional description available.')}")
    return "<br><br>".join(details)

st.markdown("## 🚗 VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(msg, unsafe_allow_html=True)

    user_input = st.text_input("Your reply:", key="chat")
    if st.button("Send", key="submit_chat") and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")

        if "learn more about those vehicles" in user_input.lower():
            if not st.session_state.last_recommendations.empty:
                reply = explain_recommendations(st.session_state.last_recommendations)
            else:
                reply = "I haven't recommended any vehicles yet. Tell me what you're looking for first!"

        elif "continue refining" in user_input.lower():
            profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
            gpt_prompt = (
                f"You're a vehicle advisor. Here's what the user has shared so far:\n{profile_summary}\n\n"
                f"User just said: {user_input}\n"
                f"Ask the next best profiling question to refine their vehicle needs."
            )
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful vehicle advisor building a user profile through natural conversation."},
                    {"role": "user", "content": gpt_prompt}
                ]
            )
            reply = response.choices[0].message.content

        else:
            profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
            gpt_prompt = (
                f"You're a vehicle advisor. Your goal is to chat casually and build the user's profile.\n\n"
                f"So far, they've shared:\n{profile_summary}\n\n"
                f"User just said: {user_input}\n\n"
                f"Update their profile if you learn something. Suggest a car if you're ready, or ask one question to learn more."
            )
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a friendly car salesman helping users choose a vehicle based on their profile."},
                    {"role": "user", "content": gpt_prompt}
                ]
            )
            reply = response.choices[0].message.content
            st.session_state.last_recommendations = recommend_vehicles(st.session_state.user_answers)

        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
        st.rerun()
else:
    st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Hey there! I’d love to help you find the perfect ride. Just tell me what you're looking for or where you're from, and we'll go from there!")
    st.rerun()

with st.sidebar:
    st.markdown("### Your Vehicle Preferences")
    for k, v in st.session_state.user_answers.items():
        if not any(phrase in v.lower() for phrase in ["learn more", "refine"]):
            st.markdown(f"**{k}**: {v}")
