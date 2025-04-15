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

# OpenAI setup
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Session state setup
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = pd.DataFrame()
if "locked_keys" not in st.session_state:
    st.session_state.locked_keys = set()
if "vehicle_names_mentioned" not in st.session_state:
    st.session_state.vehicle_names_mentioned = []

score_weights = {
    "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
    "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
    "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
    "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
    "Ownership Duration": 0.5, "Budget": 2.0, "Annual Mileage": 0.6
}

# UI
st.markdown("## 🚗 VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(msg, unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Your reply:")
        submitted = st.form_submit_button("Send")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")

        # Update locked keys if new values detected
        for key in score_weights.keys():
            if key.lower() in user_input.lower():
                st.session_state.user_answers[key] = user_input
                st.session_state.locked_keys.add(key.lower())

        profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
        unlocked_questions = [
            k for k, _ in sorted(score_weights.items(), key=lambda item: item[1], reverse=True)
            if k.lower() not in st.session_state.locked_keys
        ]

        # Decide closing phrase
        prior_vehicles = len(st.session_state.vehicle_names_mentioned) > 0
        closing_phrase = (
            "Would you like me to suggest other cars to consider, or should I ask another question to refine your match?"
            if prior_vehicles else
            "Would you like me to suggest a few cars to consider, or should I ask another question to refine your match?"
        )

        gpt_prompt = f"""You are a professional car advisor having a natural conversation with a customer.

Here’s what they’ve told you so far:
{profile_summary}

They just said:
"{user_input}"

Your job is to do the following:

1. If the user asked about a specific car (e.g., "Tell me more about the Accord"), give a helpful overview of that car’s features and benefits. If they ask for a comparison or mention others, compare only what’s relevant.

2. If you know at least one of: budget, region, or use category — recommend 1–2 matching vehicles. Add their names to the list you’re tracking: {st.session_state.vehicle_names_mentioned}.

3. ONLY ask a follow-up question if the user says: "ask another question." Otherwise, just respond to what they asked or continue the flow.

Always end with:
{closing_phrase}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a conversational, helpful vehicle advisor. Speak naturally, avoid repeating locked preferences, and flow with the user’s intent."},
                {"role": "user", "content": gpt_prompt}
            ]
        )

        reply = response.choices[0].message.content

        # Track cars mentioned
        for name in ["Accord", "Camry", "Outback", "RAV4", "Prius", "X5", "RX 350", "Escape", "CR-V"]:
            if name.lower() in reply.lower() and name not in st.session_state.vehicle_names_mentioned:
                st.session_state.vehicle_names_mentioned.append(name)

        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
        st.session_state.last_recommendations = recommend_vehicles(st.session_state.user_answers)
        st.rerun()

else:
    with st.form(key="initial_chat_form", clear_on_submit=True):
        user_input = st.text_input("Hey there! I’d love to help you find the perfect ride. What brings you in today?")
        submitted = st.form_submit_button("Start Chat")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
        st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Awesome! Let’s get started. Just to begin, what region are you located in?")
        st.rerun()
