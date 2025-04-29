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

# 8 Structured Questions
questions = [
    {"key": "budget", "question": "What's your maximum budget for a vehicle (in USD)?"},
    {"key": "fuel", "question": "What fuel type do you prefer? (Gasoline, Electric, Hybrid)"},
    {"key": "condition", "question": "Do you prefer a new or used vehicle?"},
    {"key": "size", "question": "What size of vehicle are you looking for? (Compact, SUV, Full-size, etc.)"},
    {"key": "region", "question": "Which region are you located in? (e.g., Northeast, South, Midwest, West)"},
    {"key": "features", "question": "Any must-have features? (e.g., AWD, Luxury, Fuel Economy)"},
    {"key": "brand_preference", "question": "Is brand loyalty important to you? (e.g., prefer Honda, Toyota, Ford)"},
    {"key": "recent_models", "question": "Do you prefer recently released models only? (Yes/No)"}
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

# Helper: filter cars based on profile
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

    if "condition" in st.session_state.answers:
        filtered = filtered[filtered["Condition"].str.contains(st.session_state.answers["condition"], case=False, na=False)]

    if "size" in st.session_state.answers:
        filtered = filtered[filtered["Size"].str.contains(st.session_state.answers["size"], case=False, na=False)]

    if "region" in st.session_state.answers:
        filtered = filtered[filtered["Region"].str.contains(st.session_state.answers["region"], case=False, na=False)]

    if "features" in st.session_state.answers:
        feature = st.session_state.answers["features"]
        filtered = filtered[filtered.apply(lambda row: feature.lower() in str(row).lower(), axis=1)]

    if "brand_preference" in st.session_state.answers:
        brand = st.session_state.answers["brand_preference"]
        filtered = filtered[filtered["Brand"].str.contains(brand.lower(), case=False, na=False)]

    if "recent_models" in st.session_state.answers:
        pref = st.session_state.answers["recent_models"]
        if pref.lower() == "yes":
            filtered = filtered[filtered["Condition"].str.contains("New", case=False, na=False)]

    return filtered

# Recommend cars with GPT
def recommend_cars(filtered_cars):
    top_cars = filtered_cars.sample(n=min(2, len(filtered_cars)))
    car_list = "\n".join([f"- {row['Brand'].title()} {row['Model'].title()} (${row['Min Price']})" for _, row in top_cars.iterrows()])

    prompt = (
        f"Based on the user's preferences, recommend and explain why these vehicles fit:\n{car_list}\n"
        f"Be friendly, concise, and insightful."
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
    with st.chat_message("assistant"):
        st.markdown(current_q)

# Accept user input
if prompt := st.chat_input("Type your answer..."):
    # Save user input
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Save answer under correct field
    if st.session_state.question_index < len(questions):
        key = questions[st.session_state.question_index]["key"]
        st.session_state.answers[key] = prompt
        st.session_state.question_index += 1

    # Immediately ask next question if available
    if st.session_state.question_index < len(questions):
        next_q = questions[st.session_state.question_index]["question"]
        with st.chat_message("assistant"):
            st.markdown(next_q)

    # If all questions are done, recommend cars
    elif st.session_state.question_index >= len(questions):
        filtered = filter_cars()
        if not filtered.empty:
            with st.chat_message("assistant"):
                st.markdown("✅ Based on your preferences, here are two vehicle recommendations for you:")
                recommend_cars(filtered)
        else:
            with st.chat_message("assistant"):
                st.markdown("😔 Sorry, no matching vehicles found based on your preferences.")
