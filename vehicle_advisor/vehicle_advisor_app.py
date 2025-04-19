import streamlit as st
import pandas as pd
import openai
import re
import os

st.set_page_config(page_title="Vehicle Advisor", layout="centered")

@st.cache_data
def load_data():
    df = pd.read_csv("vehicle_advisor/vehicle_data.csv")
    df['MSRP Min'] = df['MSRP Range'].apply(
        lambda msrp_range: float(re.findall(r'\$([\d,]+)', str(msrp_range))[0].replace(',', ''))
        if re.findall(r'\$([\d,]+)', str(msrp_range)) else None
    )
    return df

df_vehicle_advisor = load_data()
valid_brands = set(df_vehicle_advisor['Brand'].unique())

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "locked_keys" not in st.session_state:
    st.session_state.locked_keys = set()
if "final_recs_shown" not in st.session_state:
    st.session_state.final_recs_shown = False
if "blocked_brands" not in st.session_state:
    st.session_state.blocked_brands = set()
if "preferred_brands" not in st.session_state:
    st.session_state.preferred_brands = set()
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = -1
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = pd.DataFrame()

score_weights = {
    "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
    "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
    "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
    "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
    "Ownership Duration": 0.5, "Budget": 1.5, "Annual Mileage": 0.6, "Drive Type": 1.0
}

fixed_questions = [
    {"field": "Region", "question": "What region are you located in?"},
    {"field": "Use Category", "question": "What will you mainly use this vehicle for?"},
    {"field": "Budget", "question": "What’s your vehicle budget?"},
    {"field": "Credit Score", "question": "What is your approximate credit score?"},
    {"field": "Yearly Income", "question": "What’s your annual income range?"},
    {"field": "Car Size", "question": "What size of vehicle do you prefer?"},
    {"field": "Eco-Conscious", "question": "Are you looking for an eco-friendly vehicle?"},
    {"field": "Garage Access", "question": "Do you have access to a garage or secure parking?"},
    {"field": "Charging Access", "question": "Do you have access to EV charging?"},
    {"field": "Towing Needs", "question": "Do you need the vehicle to handle towing?"},
    {"field": "Neighborhood Type", "question": "Is your area more rural, urban, or suburban?"},
    {"field": "Drive Type", "question": "Do you prefer AWD, FWD, or RWD?"},
    {"field": "Safety Priority", "question": "Is safety a top priority for you?"},
    {"field": "Tech Features", "question": "Do you want advanced tech features?"},
    {"field": "Travel Frequency", "question": "Do you travel long distances often?"}
]

def recommend_vehicles(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()
    if st.session_state.blocked_brands:
        df = df[~df['Brand'].isin(st.session_state.blocked_brands)]
    if st.session_state.preferred_brands:
        df = df[df['Brand'].isin(st.session_state.preferred_brands)]

    budget_value = user_answers.get("Budget", "45000").replace("$", "").replace(",", "").lower().strip()
    try:
        user_budget = float(budget_value.replace("k", "")) * 1000 if "k" in budget_value else float(re.findall(r'\d+', budget_value)[0])
    except:
        user_budget = 45000
    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    def compute_score(row):
        return sum(weight for key, weight in score_weights.items() if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower())

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

st.title("Vehicle Advisor")

if st.button("🔄 Restart Profile"):
    for key in ["user_answers", "chat_log", "locked_keys", "final_recs_shown", "blocked_brands", "preferred_brands", "current_question_index", "last_recommendations"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

if not st.session_state.chat_log and st.session_state.current_question_index == -1:
    st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Hey there! I’m here to help you find the perfect vehicle. Let’s get started with a few quick questions.")
    st.session_state.current_question_index = 0
    st.rerun()

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(f"<div style='font-family:sans-serif;'>{msg}</div>", unsafe_allow_html=True)

current_index = st.session_state.current_question_index

if current_index < len(fixed_questions):
    field = fixed_questions[current_index]['field']
    question = fixed_questions[current_index]['question']

    with st.form(key="qa_form", clear_on_submit=True):
        user_input = st.text_input(question)
        submitted = st.form_submit_button("Send")

       if submitted and user_input:
            st.session_state.user_answers[field] = user_input
            st.session_state.locked_keys.add(field.lower())
            st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
            st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> Thanks! I've noted your {field.lower()}.")

            # 🔒 Auto-block brands based on negative mentions
                if "not interested in" in user_input.lower():
                    for brand in valid_brands:
                        if brand.lower() in user_input.lower():
                            st.session_state.blocked_brands.add(brand)

    # ✅ Generate recommendations AFTER blocking
    recs = recommend_vehicles(st.session_state.user_answers, top_n=2)

