import streamlit as st
import pandas as pd
import requests
from io import StringIO
import openai

# Load vehicle data from GitHub
@st.cache_data
def load_vehicle_data():
    url = "https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv"
    response = requests.get(url)
    if response.status_code == 200:
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)
        df['Brand'] = df['Brand'].str.lower()  # standardize brand names
        return df
    else:
        st.error("Failed to load vehicle data from GitHub.")
        return pd.DataFrame()

df = load_vehicle_data()

# Setup page
st.title("🚗 Vehicle Advisor Chatbot")

# OpenAI setup
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "blocked_brands" not in st.session_state:
    st.session_state.blocked_brands = set()
if "profile_complete" not in st.session_state:
    st.session_state.profile_complete = False

if "current_question_asked" not in st.session_state:
    st.session_state.current_question_asked = False

if not st.session_state.current_question_asked:
    first_question = get_next_question()
    if first_question:
        with st.chat_message("assistant"):
            st.markdown(first_question["question"])
        st.session_state.current_question_asked = True

# Question list
questions = [
    {"key": "car_type", "question": "What type of vehicle are you looking for? (e.g., SUV, Sedan, Truck)"},
    {"key": "budget", "question": "What's your approximate budget in USD?"},
    {"key": "condition", "question": "Are you looking for a new or used vehicle?"},
    {"key": "fuel_type", "question": "Do you prefer gasoline, hybrid, or electric vehicles?"},
    {"key": "features", "question": "Are there any must-have features? (e.g., AWD, Luxury, Fuel Economy)"},
    {"key": "region", "question": "Which region are you located in? (e.g., Northeast, South, West)"},
    {"key": "size", "question": "Are you looking for a compact or full-size vehicle?"},
]

# Helper functions
def get_next_question():
    for q in questions:
        if q["key"] not in st.session_state.answers:
            return q
    st.session_state.profile_complete = True
    return None

def filter_cars():
    filtered = df.copy()
    for key, value in st.session_state.answers.items():
        if key == "budget":
            try:
                budget = float(value)
                filtered = filtered[filtered["MSRP Min"] <= budget]
            except:
                pass
        elif key == "car_type":
            filtered = filtered[filtered["Type"].str.contains(value, case=False, na=False)]
        elif key == "fuel_type":
            filtered = filtered[filtered["Fuel"].str.contains(value, case=False, na=False)]
        elif key == "condition":
            if value.lower() == "new":
                filtered = filtered[filtered["Condition"].str.contains("New", case=False, na=False)]
            else:
                filtered = filtered[filtered["Condition"].str.contains("Used", case=False, na=False)]
        elif key == "region":
            filtered = filtered[filtered["Region"].str.contains(value, case=False, na=False)]
        elif key == "size":
            filtered = filtered[filtered["Size"].str.contains(value, case=False, na=False)]
    if st.session_state.blocked_brands:
        filtered = filtered[~filtered["Brand"].str.lower().isin(st.session_state.blocked_brands)]
    return filtered

def gpt_recommend_cars(cars, context=""):
    car_list = "\n".join([f"{row['Brand'].title()} {row['Model']}" for idx, row in cars.iterrows()])
    prompt = (
        f"Given the user's profile: {context}\n\n"
        f"Recommend and explain why these two cars would be a good fit:\n{car_list}\n"
        f"Keep it short, friendly, and specific to their needs."
    )
    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    return st.write_stream(stream)

def gpt_final_recommendation(cars, context=""):
    car_list = "\n".join([f"{row['Brand'].title()} {row['Model']}" for idx, row in cars.iterrows()])
    prompt = (
        f"Based on the user's full profile: {context}\n\n"
        f"Pick the top 3 vehicles from this list:\n{car_list}\n"
        f"Explain clearly in 2–3 sentences for each why it matches their profile."
    )
    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    return st.write_stream(stream)

def compare_cars(car1, car2):
    cars = df[df["Model"].str.contains(car1, case=False, na=False) | df["Model"].str.contains(car2, case=False, na=False)]
    if cars.empty:
        st.error("Couldn't find one or both cars.")
    else:
        st.dataframe(cars[["Brand", "Model", "Type", "MSRP Min", "Fuel", "Condition", "Size", "Region"]])

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Type here..."):
    # Check for commands
    if prompt.lower().startswith("remove"):
        brand_to_remove = prompt.split("remove",1)[1].strip().lower()
        st.session_state.blocked_brands.add(brand_to_remove)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            st.markdown(f"✅ Brand '{brand_to_remove.title()}' has been removed from future suggestions.")
    elif prompt.lower().startswith("compare"):
        try:
            parts = prompt.lower().split("compare",1)[1]
            car1, car2 = parts.split(" and ")
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                compare_cars(car1.strip(), car2.strip())
        except:
            with st.chat_message("assistant"):
                st.error("Please format your compare request as: 'compare [Car1] and [Car2]'")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        # If still building profile
        if not st.session_state.profile_complete:
            current_question = get_next_question()
            if current_question:
                st.session_state.answers[current_question["key"]] = prompt
                filtered = filter_cars()
                top_cars = filtered.head(2)
                if not top_cars.empty:
                    with st.chat_message("assistant"):
                        gpt_recommend_cars(top_cars, context=st.session_state.answers)
                next_question = get_next_question()
                if next_question:
                    with st.chat_message("assistant"):
                        st.markdown(next_question["question"])
            else:
                st.session_state.profile_complete = True
        # If profile complete
        if st.session_state.profile_complete:
            filtered = filter_cars()
            top_cars = filtered.head(10)
            if not top_cars.empty:
                with st.chat_message("assistant"):
                    st.markdown("Based on everything you've shared, here are the top 3 vehicle matches for you 🚗✨:")
                    gpt_final_recommendation(top_cars, context=st.session_state.answers)
