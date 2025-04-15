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

        gpt_prompt = f"""You are a professional car advisor having a live conversation with a customer.

Here’s what they’ve told you so far:
{profile_summary}

They just said:
"{user_input}"

Follow these instructions:

1. If they asked about a specific car (e.g., "Tell me more about the Camry"), explain that vehicle’s strengths in a few sentences. If they mentioned other cars before, you can compare — but only if they explicitly ask for it.

2. If you know at least one of the following: budget, region, or use category — suggest 1 or 2 cars that fit what they’ve said. If none of those are known yet, don’t make recommendations.

3. Only ask a follow-up preference question if the user says: "ask another question." If they don’t, follow their lead — they might want to explore a specific brand, compare models, or go deeper into a vehicle.

4. ENDING RULE:
- If you recommended any vehicles, close with:
"Would you like to learn more about one of these cars, or should I ask another question to refine your match?"
- If no vehicles were mentioned, close with:
"Would you like me to suggest a few cars to consider, or should I ask you a question to get started?"
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful, professional car advisor. Speak naturally, avoid repeating preferences, and follow the user's lead."},
                {"role": "user", "content": gpt_prompt}
            ]
        )

        reply = response.choices[0].message.content
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
