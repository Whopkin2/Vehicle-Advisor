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
        # Extract minimum MSRP
        df['Min Price'] = df['MSRP Range'].str.extract(r'\$([\d,]+)')[0].str.replace(',', '').astype(float)
        return df
    else:
        st.error("Failed to load vehicle data.")
        return pd.DataFrame()

df = load_vehicle_data()

# Setup OpenAI
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Questions to ask
questions = [
    {"key": "budget", "question": "What is your budget for the vehicle (in USD)?"},
    {"key": "car_type", "question": "What type of vehicle are you looking for? (SUV, Sedan, Truck?)"},
    {"key": "fuel_type", "question": "Preferred fuel type? (Gasoline, Electric, Hybrid?)"},
    {"key": "condition", "question": "New or used vehicle?"},
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

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Helper to filter cars based on answers
def filter_cars():
    filtered = df.copy()

    if "budget" in st.session_state.answers:
        try:
            budget = float(st.session_state.answers["budget"])
            filtered = filtered[filtered["Min Price"] <= budget]
        except:
            pass

    if "car_type" in st.session_state.answers:
        filtered = filtered[filtered["Size"].str.contains(st.session_state.answers["car_type"], case=False, na=False)]

    if "fuel_type" in st.session_state.answers:
        filtered = filtered[filtered["Fuel"].str.contains(st.session_state.answers["fuel_type"], case=False, na=False)]

    if "condition" in st.session_state.answers:
        filtered = filtered[filtered["Condition"].str.contains(st.session_state.answers["condition"], case=False, na=False)]

    return filtered

# Recommend cars using GPT
def recommend_cars(filtered_cars):
    top_cars = filtered_cars.sample(n=min(2, len(filtered_cars)))
    car_list = "\n".join([f"{row['Brand'].title()} {row['Model'].title()} (${row['Min Price']})" for _, row in top_cars.iterrows()])

    prompt = (
        f"Recommend the following cars to the user and explain why they fit their preferences:\n{car_list}\n"
        f"Make it friendly and concise."
    )

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    return st.write_stream(stream)

# Ask the next question automatically
if st.session_state.question_index < len(questions):
    current_q = questions[st.session_state.question_index]["question"]
    with st.chat_message("assistant"):
        st.markdown(current_q)

# Accept user input
if prompt := st.chat_input("Type your answer..."):
    # Save user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Save answer to correct field
    if st.session_state.question_index < len(questions):
        key = questions[st.session_state.question_index]["key"]
        st.session_state.answers[key] = prompt
        st.session_state.question_index += 1

    # If ready, recommend cars after answers collected
    if st.session_state.question_index >= len(questions):
        filtered = filter_cars()
        if not filtered.empty:
            with st.chat_message("assistant"):
                recommend_cars(filtered)
        else:
            with st.chat_message("assistant"):
                st.markdown("😔 Sorry, no matching vehicles found based on your preferences.")
