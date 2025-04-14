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

questions = [
    ("Region", "Which region(s) are you in?"),
    ("Use Category", "What will you primarily use the vehicle for?"),
    ("Yearly Income", "What is your yearly income?"),
    ("Credit Score", "What is your credit score?"),
    ("Garage Access", "Do you have garage access?"),
    ("Eco-Conscious", "Are you eco-conscious?"),
    ("Charging Access", "Do you have charging access?"),
    ("Neighborhood Type", "What type of neighborhood do you live in? (e.g., city, suburbs, rural)"),
    ("Towing Needs", "Do you have towing needs?"),
    ("Safety Priority", "How important is safety to you?"),
    ("Tech Features", "What level of tech features do you prefer?"),
    ("Car Size", "What car size do you prefer?"),
    ("Ownership Recommendation", "Are you looking to buy, lease, or rent?"),
    ("Employment Status", "What is your employment status?"),
    ("Travel Frequency", "How often do you travel with the car?"),
    ("Annual Mileage", "How many miles will you drive per year?"),
    ("Ownership Duration", "How long do you plan to own or use the vehicle?"),
    ("Budget", "What’s your budget or price range for the vehicle?")
]

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0


def recommend_vehicle_conversational(user_answers, top_n=3):
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


def gpt_vehicle_advice(key, value):
    profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
    prompt = (
        f"User just answered: {key} = {value}\n"
        f"Current profile:\n{profile_summary}\n"
        f"Suggest a vehicle or two that align with this profile so far and explain why they are a fit.\n"
        f"You can also ask clarifying follow-ups if relevant."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You're a helpful, friendly vehicle advisor who suggests cars and builds a profile interactively."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


st.markdown("## 🚘 VehicleAdvisor Chatbot")

st.markdown("### 💬 Chat with VehicleAdvisor")
for message in st.session_state.chat_log:
    st.markdown(message, unsafe_allow_html=True)

index = st.session_state.current_question_index
if index < len(questions):
    key, question = questions[index]
    user_input = st.text_input(question, key="input")
    if st.button("Submit") and user_input:
        st.session_state.user_answers[key] = user_input
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
        gpt_reply = gpt_vehicle_advice(key, user_input)
        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {gpt_reply}")
        st.session_state.current_question_index += 1
        st.rerun()
else:
    st.markdown("### ✅ You've completed the initial profile!")
    st.markdown("### 🚗 Final Vehicle Matches:")
    recommendations = recommend_vehicle_conversational(st.session_state.user_answers)
    for _, row in recommendations.iterrows():
        st.text(f"{row['Brand']} {row['Model']} ({row['Model Year']}) - {row['MSRP Range']}")
    st.markdown("---")
    st.markdown("You can now continue chatting below to go deeper or revise answers.")

    user_query = st.text_input("Ask more, change an answer, or explore deeper:")
    if st.button("Send") and user_query:
        st.session_state.chat_log.append(f"<b>You:</b> {user_query}")
        profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
        gpt_prompt = (
            f"Current profile:\n{profile_summary}\nUser follow-up: {user_query}\n"
            f"Adjust or respond as needed, and suggest 1-2 matching vehicles if relevant."
        )
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're an interactive vehicle advisor chatbot."},
                {"role": "user", "content": gpt_prompt}
            ]
        )
        reply = response.choices[0].message.content
        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
        st.rerun()
