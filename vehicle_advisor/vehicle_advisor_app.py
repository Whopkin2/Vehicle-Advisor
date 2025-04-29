import streamlit as st
import pandas as pd
import openai
import requests
from io import StringIO

# 🚗 Load vehicle data from GitHub
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

# 10 Structured Questions (split tech and safety)
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

# Streamlit setup
st.title("🚗 Vehicle Advisor Chatbot")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "question_index" not in st.session_state:
    st.session_state.question_index = 0

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Bulletproof filter_cars()
def filter_cars():
    filtered = df.copy()

    if "budget" in st.session_state.answers:
        try:
            budget = float(st.session_state.answers["budget"])
            filtered = filtered[filtered["Min Price"] <= budget]
        except:
            pass

    if "fuel_type" in st.session_state.answers and "Fuel" in filtered.columns:
        filtered = filtered[filtered["Fuel"].str.contains(st.session_state.answers["fuel_type"], case=False, na=False)]

    if "size" in st.session_state.answers and "Size" in filtered.columns:
        filtered = filtered[filtered["Size"].str.contains(st.session_state.answers["size"], case=False, na=False)]

    if "region" in st.session_state.answers and "Region" in filtered.columns:
        filtered = filtered[filtered["Region"].str.contains(st.session_state.answers["region"], case=False, na=False)]

    if "brand_preference" in st.session_state.answers and "Brand" in filtered.columns:
        filtered = filtered[filtered["Brand"].str.contains(st.session_state.answers["brand_preference"], case=False, na=False)]

    if "annual_mileage" in st.session_state.answers and "MPG/Range" in filtered.columns:
        try:
            mileage = float(st.session_state.answers["annual_mileage"])
            if mileage > 15000:
                filtered = filtered.sort_values(by="MPG/Range", ascending=False)
        except:
            pass

    return filtered

# Recommend cars after each answer
def recommend_cars(filtered_cars):
    top_cars = filtered_cars.head(2)
    if top_cars.empty:
        return st.markdown("_No matching vehicles yet based on current inputs._")
    
    car_list = "\n".join([f"- {row['Brand'].title()} {row['Model'].title()} (${row['Min Price']:.0f})" for _, row in top_cars.iterrows()])
    profile_context = "\n".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in st.session_state.answers.items()])

    prompt = (
        f"User profile:\n{profile_context}\n\n"
        f"Available cars:\n{car_list}\n\n"
        f"Pick the two best options matching user's preferences and explain briefly why."
    )

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    return st.write_stream(stream)

# Ask first question if needed
if st.session_state.question_index < len(questions) and not st.session_state.messages:
    current_q = questions[st.session_state.question_index]["question"]
    st.session_state.messages.append({"role": "assistant", "content": current_q})
    st.experimental_rerun()

# Accept user input
if prompt := st.chat_input("Type your answer..."):
    # Save user message
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

    # Ask next question
    if st.session_state.question_index < len(questions):
        next_q = questions[st.session_state.question_index]["question"]
        st.session_state.messages.append({"role": "assistant", "content": next_q})
        st.experimental_rerun()
    else:
        with st.chat_message("assistant"):
            st.markdown("✅ You've answered all questions! Here’s your final recommendation summary above.")
