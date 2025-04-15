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
    "Ownership Duration": 0.5, "Budget": 1.5, "Annual Mileage": 0.6
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
st.markdown("## 🚗 VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(f"<div style='font-family:sans-serif;'>{msg}</div>", unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Your reply:")
        submitted = st.form_submit_button("Send")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
       profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
        # Display visual summary if 7 or more preferences collected
        if len(st.session_state.locked_keys) >= 7:
            st.markdown("### 🧾 Your Vehicle Profile")
            st.markdown("<div style='border: 1px solid #ddd; padding: 1rem; border-radius: 10px; background-color: #f9f9f9; font-family: sans-serif;'>" + "<br>".join([f"<b>{k}:</b> {v}" for k, v in st.session_state.user_answers.items()]) + "</div>", unsafe_allow_html=True)
            st.markdown("Would you like to:")
            st.markdown("- 🚗 Proceed with top 3 car recommendations
- ✏️ Edit your profile
- 🔄 Restart your preferences")

        # Update locked keys if new info is added
        for key in st.session_state.user_answers:
            st.session_state.locked_keys.add(key.lower())

        unlocked_questions = [k for k, _ in sorted(score_weights.items(), key=lambda item: item[1], reverse=True)
                              if k.lower() not in st.session_state.locked_keys]

        gpt_prompt = f"""You're a friendly, helpful car expert.
Your job is to build the user's profile and help them find the perfect car.

Here’s what they’ve shared so far:
{profile_summary}

Use this information as an accurate representation of what they’ve already told you. Avoid saying you have no data if some exists.

They just said: {user_input}

Update their profile only if they gave new info. If the budget or any other info has already been shared, do NOT ask about it again or imply that no information is available.
NEVER ask again about these locked preferences: {list(st.session_state.locked_keys)}.

Let’s keep track of how many preferences we’ve collected. So far, we have {len(st.session_state.locked_keys)}.

If fewer than 7 preferences have been collected, ask ONE NEW helpful question from this list: {unlocked_questions}.

If 7 or more preferences have been collected, summarize the profile and ask the user if they would like to:
- Proceed with top 3 car recommendations,
- Edit any part of their profile, or
- Restart the process.

First, based on the updated info, recommend 1 or 2 matching vehicles and explain why they fit.

Then, ask if the user would like to learn more about those cars.
Only after they respond should you decide whether to:
- Provide more info on the cars, or
- Continue asking a new helpful question from the remaining list.
Do NOT ask a new question until the user answers the learn-more prompt.

Allow the user to return to question mode at any time if they lose interest in a vehicle.

Once 7 or more profile preferences are collected, summarize their profile and ask if they want to:
- Proceed with top 3 car recommendations,
- Edit any part of their profile, or
- Restart the process."""

First, based on the updated info, recommend 1 or 2 matching vehicles and explain why they fit.

Then, ask if the user would like to learn more about those cars.
Only after they respond should you decide whether to:
- Provide more info on the cars, or
- Continue asking a new helpful question from the remaining list.
Do NOT ask a new question until the user answers the learn-more prompt.

Allow the user to return to question mode at any time if they lose interest in a vehicle.

Once 7 or more profile preferences are collected, summarize their profile and ask if they want to:
- Proceed with top 3 car recommendations,
- Edit any part of their profile, or
- Restart the process.
"""

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
