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

# Setup API
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Session state init
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
    "Ownership Duration": 0.5, "Budget": 1.5, "Annual Mileage": 0.6, "Drive Type": 1.0
}

def recommend_vehicles(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()
    try:
        budget_value = user_answers.get("Budget", "45000")
        user_budget = float(re.findall(r'\d+', budget_value.replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    def compute_score(row):
        return sum(
            weight for key, weight in score_weights.items()
            if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower()
        )

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

# Chat interface
st.markdown("## \U0001F697 VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(f"<div style='font-family:sans-serif;'>{msg}</div>", unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Your reply:")
        submitted = st.form_submit_button("Send")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")

        profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])

        for key in st.session_state.user_answers:
            st.session_state.locked_keys.add(key.lower())

        unlocked_questions = [k for k, _ in sorted(score_weights.items(), key=lambda item: item[1], reverse=True)
                              if k.lower() not in st.session_state.locked_keys]

        gpt_prompt = f"""You are a car chatbot, that is tasked with helping a person or a car salesman find the best cars that fit the needs specified.
You will look into the the vehicle data csv and ask questions regarding the profile of the individual based off attributes of the cars to find out which car will best suit that individual.
These questions should be based off the score weights — some hold much higher weights than others because they are more important — but that doesn't mean you ignore the lower weighted ones.

Once the user answers a question, HARD LOCK that information — NEVER ask for it again. For example, if they share their budget, that is FINAL. Do not re-ask it. Do not imply it wasn't given.

After each question, mention 2 cars that could fit the individual's preferences so far, based on the latest answer and all prior locked values.
You should ask a total of 8 to 10 thoughtful, dynamic questions before recommending the final vehicles that match best.

You can use charts to visually compare options and highlight matches. Your goal is to be as human and fluid as possible — make the interaction feel natural.

Here’s what they’ve shared so far:
{profile_summary}

They just said: {user_input}

Locked preferences: {list(st.session_state.locked_keys)}
Remaining preference options to ask about: {unlocked_questions}

Start by responding conversationally. Acknowledge their latest message, then update their profile (only if relevant), recommend 1–2 cars, and ask the next best question. NEVER ask about anything that is already locked.
Wait for the user to respond before continuing. You must complete 8–10 total questions unless the user asks to skip ahead."""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a vehicle advisor that helps users build their car preferences step by step, and recommend cars after every step. Do not repeat questions or ask for information already provided."},
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
