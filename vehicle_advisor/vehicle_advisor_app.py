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
if "awaiting_vehicle_detail" not in st.session_state:
    st.session_state.awaiting_vehicle_detail = False
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = []

def recommend_vehicles(user_answers, top_n=2):
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

# UI Title
st.markdown("## 🚗 VehicleAdvisor Chat")

# Display chat history
if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(msg, unsafe_allow_html=True)

# Input form (clears after submit)
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Your reply:")
    submitted = st.form_submit_button("Send")

if submitted and user_input:
    st.session_state.chat_log.append(f"<b>You:</b> {user_input}")

    # 1. If user is requesting more info about cars
    if st.session_state.awaiting_vehicle_detail and "learn" in user_input.lower():
        detail_output = ""
        for car in st.session_state.last_recommendations:
            detail_output += f"**{car['Brand']} {car['Model']} ({car['Model Year']})**\n"
            detail_output += f"- MSRP Range: {car['MSRP Range']}\n"
            detail_output += f"- Size: {car.get('Car Size', 'N/A')}\n"
            detail_output += f"- Safety Features: {car.get('Safety Priority', 'N/A')}\n"
            detail_output += f"- Technology Features: {car.get('Tech Features', 'N/A')}\n\n"
        detail_output += "Would you like to continue narrowing your options further?"
        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b><br>{detail_output}")
        st.session_state.awaiting_vehicle_detail = False
        st.rerun()

    # 2. Otherwise: continue conversation and generate recommendations
    profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
    gpt_prompt = (
        f"You are a professional vehicle advisor. You speak in a formal tone and help users choose the best vehicle based on their responses.\n\n"
        f"Current known preferences:\n{profile_summary}\n\n"
        f"The user just said: {user_input}\n\n"
        f"Update the profile as needed. Suggest 1–2 potential vehicle matches based on what you know so far. "
        f"Then ask: 'Would you like to learn more about these vehicles or continue refining your preferences?'"
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional and courteous vehicle advisor helping someone select a car."},
            {"role": "user", "content": gpt_prompt}
        ]
    )

    reply = response.choices[0].message.content
    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")

    # Generate new recs and save them
    recs = recommend_vehicles(st.session_state.user_answers)
    st.session_state.last_recommendations = recs.to_dict(orient="records")
    st.session_state.awaiting_vehicle_detail = True
    st.rerun()

# Initial greeting if starting fresh
if not st.session_state.chat_log:
    st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Welcome. I’m here to help you select a vehicle that suits your needs. To begin, please tell me what you're looking for or where you're located.")
    st.rerun()
