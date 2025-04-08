#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import openai
import re
import os

st.set_page_config(page_title="Vehicle Advisor", layout="centered")

@st.cache_data
def load_data():
    df = pd.read_csv("vehicle_data.csv")
    df['MSRP Min'] = df['MSRP Range'].apply(lambda msrp_range: float(re.findall(r'\$([\d,]+)', str(msrp_range))[0].replace(',', '')) if re.findall(r'\$([\d,]+)', str(msrp_range)) else None)
    return df

df_vehicle_advisor = load_data()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

questions = [
    "Which region(s) are you in?",
    "What will you primarily use the vehicle for?",
    "What is your yearly income?",
    "What is your credit score?",
    "Do you have garage access?",
    "Are you eco-conscious?",
    "Do you have charging access?",
    "What type of neighborhood do you live in? (e.g., city, suburbs, rural)",
    "Do you have towing needs?",
    "How important is safety to you?",
    "What level of tech features do you prefer?",
    "What car size do you prefer?",
    "Are you looking to buy, lease, or rent?",
    "What is your employment status?",
    "How often do you travel with the car?",
    "How long do you plan to own or use the vehicle?",
    "What’s your budget or price range for the vehicle?"
]

keys = [
    "Region", "Use Category", "Yearly Income", "Credit Score", "Garage Access",
    "Eco-Conscious", "Charging Access", "Neighborhood Type", "Towing Needs",
    "Safety Priority", "Tech Features", "Car Size", "Ownership Recommendation",
    "Employment Status", "Travel Frequency", "Ownership Duration", "Budget"
]

if "question_index" not in st.session_state:
    st.session_state.question_index = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

def recommend_vehicle_conversational(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()
    try:
        user_budget = float(re.findall(r'\d+', user_answers.get("Budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[~df['Fuel Type'].str.lower().str.contains("electric|hybrid", na=False)]
    df = df[~df['Vehicle Type'].str.lower().str.contains("sedan|luxury|compact", na=False)]
    df = df[df['Car Size'].str.lower().isin(['midsize', 'full-size', 'truck', 'suv'])]
    df = df[df['MSRP Min'].fillna(99999) <= user_budget]

    score_weights = {
        "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
        "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
        "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
        "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
        "Ownership Duration": 0.5, "Budget": 1.0
    }

    def compute_score(row):
        return sum(weight for key, weight in score_weights.items()
                   if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower())

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

def generate_summary_with_gpt(row, user_answers):
    prompt = (
        f"The user is shopping for a vehicle with a budget of {user_answers.get('Budget', 'unknown')}.\n"
        f"Their preferences: {user_answers}.\n"
        f"Explain why the {row['Brand']} {row['Model']} ({row['Model Year']}) is a good match. "
        f"Highlight its size, simplicity, fuel type, towing ability, tech level, and ownership value. "
        f"Include the MSRP: {row['MSRP Range']}, and how it fits their budget."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You recommend vehicles with helpful, budget-aware summaries."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

st.markdown("## 🚘 VehicleAdvisor Chatbot")
st.markdown("Welcome! Let's find your ideal vehicle. Answer a few quick questions:")

for message in st.session_state.chat_log:
    st.markdown(message, unsafe_allow_html=True)

with st.form("chat_form", clear_on_submit=True):
    if st.session_state.question_index < len(questions):
        user_input = st.text_input(questions[st.session_state.question_index])
        submitted = st.form_submit_button("Send")
        if submitted and user_input:
            key = keys[st.session_state.question_index]
            st.session_state.user_answers[key] = user_input
            st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
            st.session_state.question_index += 1
            if st.session_state.question_index < len(questions):
                next_question = questions[st.session_state.question_index]
                st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {next_question}")
            st.rerun()
    else:
        st.markdown("### ✅ Top Vehicle Recommendations:")
        recommendations = recommend_vehicle_conversational(st.session_state.user_answers)
        for _, row in recommendations.iterrows():
            summary = generate_summary_with_gpt(row, st.session_state.user_answers)
            st.markdown(f"**{row['Brand']} {row['Model']} ({row['Model Year']})**")
            st.markdown(summary)

