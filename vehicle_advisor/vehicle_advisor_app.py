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
    {"field": "Region", "question": "What region are you located in? (e.g., North East, South West, Mid-West)"},
    {"field": "Use Category", "question": "What will you mainly use this vehicle for? (e.g., Commuting, Family, Off-Roading, Utility)"},
    {"field": "Budget", "question": "What’s your vehicle budget? (e.g., $30k, $45,000, under $50k)"},
    {"field": "Credit Score", "question": "What is your approximate credit score? (e.g., Poor, Fair, Good, Very Good, Excellent, 650)"},
    {"field": "Yearly Income", "question": "What’s your annual income range? (e.g., $50k, $90,000, over $120k)"},
    {"field": "Car Size", "question": "What size of vehicle do you prefer? (e.g., Compact, Midsize, Fullsize, SUV, Truck, Crossover)"},
    {"field": "Eco-Conscious", "question": "Are you looking for an eco-friendly vehicle? (Yes/No)"},
    {"field": "Garage Access", "question": "Do you have access to a garage or secure parking? (Yes/No)"},
    {"field": "Charging Access", "question": "Do you have access to EV charging? (Yes/No)"},
    {"field": "Towing Needs", "question": "Do you need the vehicle to handle towing? (Yes/No)"},
    {"field": "Neighborhood Type", "question": "Is your area more rural, urban, or suburban? (e.g., Urban, Suburban, Rural)"},
    {"field": "Drive Type", "question": "Do you prefer AWD, FWD, or RWD? (All Wheel, Front Wheel, Rear Wheel)"},
    {"field": "Safety Priority", "question": "Is safety a top priority for you? (Yes/No)"},
    {"field": "Tech Features", "question": "Do you want advanced tech features? (Yes/No)"},
    {"field": "Travel Frequency", "question": "Do you travel long distances often? (Yes/No)"},
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

       # Define expected keywords for each field
expected_fields_keywords = {
    "Region": ["north", "south", "east", "west", "midwest", "northeast", "southeast", "pacific", "central"],
    "Use Category": ["commuting", "family", "off-road", "offroading", "utility", "city", "work", "daily", "leisure"],
    "Budget": ["$", "k", "000", "usd", "dollars"],
    "Credit Score": ["poor", "fair", "good", "very good", "excellent", "score", "credit", "600", "700", "800"],
    "Yearly Income": ["$", "k", "000", "income", "salary"],
    "Car Size": ["compact", "midsize", "fullsize", "suv", "sedan", "truck", "crossover"],
    "Eco-Conscious": ["yes", "no"],
    "Garage Access": ["yes", "no"],
    "Charging Access": ["yes", "no"],
    "Towing Needs": ["yes", "no"],
    "Neighborhood Type": ["urban", "suburban", "rural", "city", "town"],
    "Drive Type": ["awd", "fwd", "rwd", "all wheel", "front wheel", "rear wheel"],
    "Safety Priority": ["yes", "no"],
    "Tech Features": ["yes", "no"],
    "Travel Frequency": ["yes", "no", "often", "rarely", "frequent"]
}

if submitted and user_input:
    keywords = expected_fields_keywords.get(field, [])
    if keywords and not any(k in user_input.lower() for k in keywords):
        st.session_state.chat_log.append(
            f"<b>VehicleAdvisor:</b> Hmm... I didn’t quite catch your answer about your {field.lower()}. Could you rephrase it?"
        )
        st.rerun()

    st.session_state.user_answers[field] = user_input
    st.session_state.locked_keys.add(field.lower())
    st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> Thanks! I've noted your {field.lower()}.")

    if "not interested in" in user_input.lower():
        for brand in valid_brands:
            if brand.lower() in user_input.lower():
                st.session_state.blocked_brands.add(brand)

    recs = recommend_vehicles(st.session_state.user_answers, top_n=2)
    st.session_state.last_recommendations = recs

    for idx, row in recs.iterrows():
        if field == "Region":
            explanation = f"This model is known for strong performance across various climates — great for areas like {user_input} with diverse weather."
        elif field == "Use Category":
            if any(b.lower() in user_input.lower() and "not interested" in user_input.lower() for b in valid_brands):
                explanation = f"This model may appear despite your preferences — let me know if you'd like to exclude certain brands."
            else:
                category = row.get("Use Category", "").lower()
                if "off-road" in category:
                    explanation = "Rugged build, high clearance, and traction systems make it excellent for off-road and utility driving."
                elif "commuting" in category:
                    explanation = "Great for daily use — it’s efficient, maneuverable, and reliable for frequent drives."
                elif "family" in category:
                    explanation = "Spacious, safe, and loaded with comfort features — ideal for family needs."
                else:
                    explanation = f"This model fits your intended use case of '{user_input}'."
        elif field == "Eco-Conscious" and user_input.lower() == "yes":
            explanation = f"This model is eco-friendly — with either hybrid or electric powertrains to reduce emissions and save on fuel."
        elif field == "Car Size":
            explanation = f"As a {row['Car Size']} vehicle, it aligns well with your space, visibility, and handling expectations."
        elif field == "Towing Needs":
            explanation = f"This model supports towing — making it suitable for trailers, boats, or equipment hauling."
        elif field == "Drive Type":
            explanation = f"It features {row['Drive Type']} — giving you great control and traction for your driving preference."
        elif field == "Neighborhood Type":
            explanation = f"This model suits {user_input.lower()} settings — whether navigating urban streets or open rural roads."
        elif field == "Tech Features":
            explanation = f"Packed with advanced driver assistance and smart features for a modern driving experience."
        else:
            explanation = f"Based on your input for {field.lower()}, this vehicle matches well."

        st.session_state.chat_log.append(
            f"<b>Suggested:</b> {row['Brand']} {row['Model']} ({row['Model Year']}) – {row['MSRP Range']}<br><i>Why this fits:</i> {explanation}"
        )

    st.session_state.current_question_index += 1
    st.rerun()
 
