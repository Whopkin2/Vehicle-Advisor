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

if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {}
if "recommendation_made" not in st.session_state:
    st.session_state.recommendation_made = False


def recommend_vehicle_dynamic(profile):
    df = df_vehicle_advisor.copy()
    try:
        user_budget = float(re.findall(r'\d+', profile.get("Budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    score = []
    for _, row in df.iterrows():
        match = sum([1 for k, v in profile.items() if str(v).lower() in str(row.to_dict()).lower()])
        score.append(match)
    df['score'] = score
    df = df.sort_values(by='score', ascending=False)
    return df.head(3).reset_index(drop=True)


def gpt_vehicle_response(user_message):
    profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_profile.items()])
    prompt = (
        f"You are a helpful, friendly AI vehicle advisor helping a user pick the perfect car.\n"
        f"Conversation history:\n{profile_summary}\n"
        f"User just said: {user_message}\n"
        f"Your job is to respond conversationally, infer details, ask smart questions to build a vehicle profile, and suggest specific models that match.\n"
        f"Only ask for relevant follow-ups, and allow the user to change previous answers freely.\n"
        f"Once enough information is gathered (region, budget, use case, size/fuel preferences), stop asking and return top 3 vehicles with reasons.\n"
        f"Then offer to compare them in a table, allow user to reset profile, or update preferences and re-recommend."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a smart, friendly vehicle advisor chatbot."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


def reset_chat():
    st.session_state.chat_log = []
    st.session_state.user_profile = {}
    st.session_state.recommendation_made = False
    st.experimental_rerun()

st.markdown("## 🚘 VehicleAdvisor Chatbot")

st.markdown("### 💬 Chat with VehicleAdvisor")
for message in st.session_state.chat_log:
    st.markdown(message, unsafe_allow_html=True)

with st.form(key="chat_form", clear_on_submit=True):
    user_query = st.text_input("You:")
    submitted = st.form_submit_button("Send")

if submitted and user_query:
    st.session_state.chat_log.append(f"<b>You:</b> {user_query}")

    if user_query.strip().lower() == "reset":
        reset_chat()

    # Extract potential updates from the user message (lightweight keyword mapping)
    profile_keywords = [
        "region", "budget", "family", "mileage", "credit", "garage",
        "hybrid", "suv", "sedan", "eco", "commute", "features"
    ]
    for word in profile_keywords:
        if word in user_query.lower():
            st.session_state.user_profile[word] = user_query  # Naive mapping for now

    reply = gpt_vehicle_response(user_query)
    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")

    if not st.session_state.recommendation_made and len(st.session_state.user_profile) >= 4:
        top_vehicles = recommend_vehicle_dynamic(st.session_state.user_profile)
        st.session_state.chat_log.append("<br><b>✅ I've gathered enough to recommend your top 3 vehicles:</b>")
        for _, row in top_vehicles.iterrows():
            st.session_state.chat_log.append(f"- <b>{row['Brand']} {row['Model']} ({row['Model Year']})</b>: {row['MSRP Range']}")

        st.session_state.chat_log.append("<br>Would you like to compare these cars in a table or by features? Or would you like to change any preferences or start over?")
        st.session_state.recommendation_made = True

    st.rerun()
