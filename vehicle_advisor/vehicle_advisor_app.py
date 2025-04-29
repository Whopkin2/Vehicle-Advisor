import streamlit as st
import pandas as pd
import openai
import requests
from io import StringIO

# Load vehicle data
@st.cache_data
def load_vehicle_data():
    url = "https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv"
    response = requests.get(url)
    if response.status_code == 200:
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)
        df['Brand'] = df['Brand'].str.lower()
        df['Model'] = df['Model'].str.lower()
        df['Min Price'] = df['MSRP Range'].str.extract(r'\$([\d,]+)')[0].str.replace(',', '').astype(float)
        return df
    else:
        st.error("Failed to load vehicle data.")
        return pd.DataFrame()

df = load_vehicle_data()

# Setup OpenAI
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Structured Questions
questions = [
    {"key": "budget", "question": "What's your maximum budget for a vehicle (in USD)?"},
    {"key": "fuel_type", "question": "What fuel type do you prefer? (Gasoline, Electric, Hybrid)"},
    {"key": "size", "question": "What size of vehicle are you looking for? (Compact, SUV, Full-size, etc.)"},
    {"key": "region", "question": "Which region are you located in? (Northeast, Midwest, West, South)"},
    {"key": "brand_preference", "question": "Do you have a preferred car brand? (e.g., Honda, Ford, Toyota)"},
    {"key": "tech_features", "question": "Any must-have technology features? (e.g., Bluetooth, Apple CarPlay)"},
    {"key": "safety_features", "question": "Any must-have safety features? (e.g., Blind Spot Detection, Adaptive Cruise Control)"},
    {"key": "annual_mileage", "question": "What is your expected annual mileage? (miles per year)"},
    {"key": "ownership_type", "question": "Will you own, lease, or rent the vehicle?"},
    {"key": "yearly_income", "question": "What is your estimated yearly income (in USD)?"}
]

# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "question_index" not in st.session_state:
    st.session_state.question_index = 0

# Title
st.title("🚗 Vehicle Advisor Chatbot")

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Filtering logic
def filter_cars():
    filtered = df.copy()

    # Strict: Budget
    if "budget" in st.session_state.answers:
        try:
            budget = float(st.session_state.answers["budget"])
            filtered = filtered[filtered["Min Price"] <= budget]
        except:
            pass

    # Strict: Fuel Type
    if "fuel_type" in st.session_state.answers and "Fuel" in filtered.columns:
        fuel_preference = st.session_state.answers["fuel_type"].strip().lower()

        if fuel_preference == "electric":
            filtered = filtered[filtered["Fuel"].str.lower() == "electric"]
        elif fuel_preference == "hybrid":
            filtered = filtered[filtered["Fuel"].str.lower() == "hybrid"]
        elif fuel_preference == "gasoline":
            filtered = filtered[filtered["Fuel"].str.lower() == "gasoline"]

    # Strict: Size
    if "size" in st.session_state.answers and "Size" in filtered.columns:
        size_preference = st.session_state.answers["size"].strip().lower()
        filtered = filtered[filtered["Size"].str.lower() == size_preference]

    # Strict: Region
    if "region" in st.session_state.answers and "Region" in filtered.columns:
        region_preference = st.session_state.answers["region"].strip().lower()
        filtered = filtered[filtered["Region"].str.lower() == region_preference]

    # Strict: Brand
    if "brand_preference" in st.session_state.answers and "Brand" in filtered.columns:
        brand_preference = st.session_state.answers["brand_preference"].strip().lower()
        filtered = filtered[filtered["Brand"].str.lower() == brand_preference]

    # Tech Feature Matching (optional, best effort)
    if "tech_features" in st.session_state.answers and "Tech Features" in filtered.columns:
        tech_pref = st.session_state.answers["tech_features"].strip().lower()
        if tech_pref != "none":
            filtered = filtered[filtered["Tech Features"].str.lower().str.contains(tech_pref, na=False)]

    # Safety Feature Matching (optional, best effort)
    if "safety_features" in st.session_state.answers and "Safety Features" in filtered.columns:
        safety_pref = st.session_state.answers["safety_features"].strip().lower()
        if safety_pref != "none":
            filtered = filtered[filtered["Safety Features"].str.lower().str.contains(safety_pref, na=False)]

    # Annual Mileage (prioritize high MPG/range if mileage > 15k)
    if "annual_mileage" in st.session_state.answers and "MPG/Range" in filtered.columns:
        try:
            mileage = float(st.session_state.answers["annual_mileage"])
            if mileage > 15000:
                filtered = filtered.sort_values(by="MPG/Range", ascending=False)
        except:
            pass

    return filtered
    
# Recommend cars
def recommend_cars(filtered_cars):
    top_cars = filtered_cars.head(2)
    if top_cars.empty:
        return st.markdown("_No matching vehicles yet based on current inputs._")
    
    car_list = "\n".join([
        f"- {row['Brand'].title()} {row['Model'].title()} (MSRP Range: {row['MSRP Range']})"
        for _, row in top_cars.iterrows()
    ])
    
    profile_context = "\n".join([
        f"{k.replace('_', ' ').title()}: {v}" for k, v in st.session_state.answers.items()
    ])

    prompt = (
        f"User profile:\n{profile_context}\n\n"
        f"Available cars:\n{car_list}\n\n"
        f"Pick the two best options matching user's preferences and explain briefly why."
        f" Mention the correct MSRP Range when you describe each car."
    )

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    return st.write_stream(stream)

# Ask first question if no messages
if st.session_state.question_index < len(questions) and len(st.session_state.messages) == 0:
    first_question = questions[st.session_state.question_index]["question"]
    with st.chat_message("assistant"):
        st.markdown(first_question)
    st.session_state.messages.append({"role": "assistant", "content": first_question})

# Chat input
if prompt := st.chat_input("Type your answer..."):
    # Save user input
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Save answer
    if st.session_state.question_index < len(questions):
        key = questions[st.session_state.question_index]["key"]
        st.session_state.answers[key] = prompt
        st.session_state.question_index += 1

    # Recommend cars after each answer
    filtered = filter_cars()
    with st.chat_message("assistant"):
        st.markdown("🚘 **Current Best Vehicle Matches:**")
        recommend_cars(filtered)

    # Ask next question if any
    if st.session_state.question_index < len(questions):
        next_q = questions[st.session_state.question_index]["question"]
        with st.chat_message("assistant"):
            st.markdown(next_q)
        st.session_state.messages.append({"role": "assistant", "content": next_q})
    else:
        with st.chat_message("assistant"):
            st.markdown("✅ You've completed all questions. Final recommendations above!")
