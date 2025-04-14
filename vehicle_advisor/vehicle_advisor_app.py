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
    ("Region", "What state or region are you currently residing in?"),
    ("Use Category", "What is the primary purpose of the vehicle?"),
    ("Yearly Income", "What is your approximate annual income?"),
    ("Credit Score", "What is your estimated credit score?"),
    ("Garage Access", "Do you have access to a garage or covered parking?"),
    ("Eco-Conscious", "Do you prefer an environmentally friendly vehicle, such as a hybrid or EV?"),
    ("Charging Access", "Do you have access to an electric vehicle charging station at home or nearby?"),
    ("Neighborhood Type", "Do you live in an urban, suburban, or rural area?"),
    ("Towing Needs", "Will you need the vehicle for towing purposes?"),
    ("Safety Priority", "How important are advanced safety features in your decision?"),
    ("Tech Features", "What level of in-car technology and features do you prefer?"),
    ("Car Size", "What size vehicle are you considering (e.g., compact, midsize, SUV)?"),
    ("Employment Status", "What is your current employment status?"),
    ("Travel Frequency", "How frequently do you plan to drive the vehicle?"),
    ("Annual Mileage", "What is your estimated annual mileage?"),
    ("Ownership Duration", "How long do you plan to own or lease the vehicle?"),
    ("Budget", "What is your vehicle budget or price range?")
]

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []


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


def get_salesman_reply(key, value, user_answers):
    profile = {**user_answers, key: value}
    profile_summary = "\n".join([f"{k}: {v}" for k, v in profile.items()])
    prompt = (
        f"You're a vehicle advisor. You're helping someone find a great vehicle.\n"
        f"So far, they've told you:\n{profile_summary}\n"
        f"They just said: {key} = {value}. Respond like a car salesman, suggest 1-2 vehicles that might fit so far, and ask only the next question — no more than one question at a time."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a friendly car salesman who speaks casually and helps customers pick vehicles."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


st.markdown("## 🚗 VehicleAdvisor Chat")

for key, question in questions:
    if key not in st.session_state.user_answers:
        for msg in st.session_state.chat_log:
            st.markdown(msg, unsafe_allow_html=True)

        user_input = st.text_input(question, key=key)
        if st.button("Submit", key=f"submit_{key}"):
            st.session_state.user_answers[key] = user_input
            reply = get_salesman_reply(key, user_input, st.session_state.user_answers)
            st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
            st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
            st.rerun()
        break
else:
    st.success("You’re all set! VehicleAdvisor has a few rides in mind for you.")
    recommendations = recommend_vehicles(st.session_state.user_answers)
    for _, row in recommendations.iterrows():
        st.markdown(f"**{row['Brand']} {row['Model']} ({row['Model Year']})**")
        st.markdown(f"MSRP Range: {row['MSRP Range']}")
