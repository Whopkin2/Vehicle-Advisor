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
        df.columns = df.columns.str.strip()
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

# Structured Questions (brand moved toward end)
questions = [
    {"key": "vehicle_type", "question": "What type of vehicle are you looking for? (Sedan, SUV, Truck, Coupe, etc.)"},
    {"key": "car_size", "question": "What size of vehicle do you want? (Compact, Midsize, Full-size, etc.)"},
    {"key": "budget", "question": "What's your maximum budget for a vehicle (in USD)?"},
    {"key": "fuel_type", "question": "What fuel type do you prefer? (Gasoline, Electric, Hybrid)"},
    {"key": "region", "question": "Which region are you located in? (Northeast, Midwest, West, South)"},
    {"key": "use_category", "question": "What will be the vehicle's primary use? (Personal, Commercial, etc.)"},
    {"key": "eco_conscious", "question": "Are you eco-conscious? (Yes or No)"},
    {"key": "charging_access", "question": "Do you have access to a charging station? (Yes or No)"},
    {"key": "neighborhood_type", "question": "What type of neighborhood are you in? (Urban, Suburban, Rural)"},
    {"key": "towing_needs", "question": "Do you have towing needs? (Yes or No)"},
    {"key": "tech_features", "question": "Any must-have tech features? (e.g., Bluetooth, Apple CarPlay)"},
    {"key": "safety_priority", "question": "Any must-have safety features? (e.g., Blind Spot Detection, Adaptive Cruise)"},
    {"key": "garage_access", "question": "Do you have a garage for your vehicle? (Yes or No)"},
    {"key": "employment_status", "question": "What is your employment status? (Employed, Student, Retired)"},
    {"key": "credit_score", "question": "What is your approximate credit score? (e.g., 700+)"},
    {"key": "travel_frequency", "question": "How often do you travel long distances? (Often, Occasionally, Rarely)"},
    {"key": "ownership_duration", "question": "How long do you plan to own the vehicle? (Short term, Long term)"},
    {"key": "ownership_recommendation", "question": "Would you prefer to own, lease, or rent the vehicle?"},
    {"key": "yearly_income", "question": "What is your estimated yearly income (in USD)?"},
    {"key": "brand", "question": "Do you have a preferred vehicle brand? (e.g., Honda, Ford, Toyota)"}
]

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "question_index" not in st.session_state:
    st.session_state.question_index = 0

st.title("🚗 Vehicle Advisor Chatbot")

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Strict filter with skip if "no", "none", "any"
def filter_cars():
    filtered = df.copy()

    for key, value in st.session_state.answers.items():
        value = value.strip().lower()

        if value in ["no", "none", "any"]:
            continue

        if key == "budget":
            try:
                budget = float(value.replace('$', '').replace(',', ''))
                filtered = filtered[filtered["Min Price"] <= budget]
            except:
                pass

        elif key == "fuel_type" and "Fuel Type" in filtered.columns:
            filtered = filtered[filtered["Fuel Type"].str.lower() == value]

        elif key == "vehicle_type" and "Vehicle Type" in filtered.columns:
            filtered = filtered[filtered["Vehicle Type"].str.lower() == value]

        elif key == "car_size" and "Car Size" in filtered.columns:
            filtered = filtered[filtered["Car Size"].str.lower() == value]

        elif key == "region" and "Region" in filtered.columns:
            filtered = filtered[filtered["Region"].str.lower() == value]

        elif key == "brand" and "Brand" in filtered.columns:
            filtered = filtered[filtered["Brand"].str.lower() == value]

        elif key == "eco_conscious" and "Eco-Conscious" in filtered.columns:
            filtered = filtered[filtered["Eco-Conscious"].str.lower() == value]

        elif key == "charging_access" and "Charging Access" in filtered.columns:
            filtered = filtered[filtered["Charging Access"].str.lower() == value]

        elif key == "neighborhood_type" and "Neighborhood Type" in filtered.columns:
            filtered = filtered[filtered["Neighborhood Type"].str.lower() == value]

        elif key == "towing_needs" and "Towing Needs" in filtered.columns:
            filtered = filtered[filtered["Towing Needs"].str.lower() == value]

        elif key == "tech_features" and "Tech Features" in filtered.columns:
            filtered = filtered[filtered["Tech Features"].str.lower().str.contains(value, na=False)]

        elif key == "safety_priority" and "Safety Priority" in filtered.columns:
            filtered = filtered[filtered["Safety Priority"].str.lower().str.contains(value, na=False)]

        elif key == "garage_access" and "Garage Access" in filtered.columns:
            filtered = filtered[filtered["Garage Access"].str.lower() == value]

        elif key == "employment_status" and "Employment Status" in filtered.columns:
            filtered = filtered[filtered["Employment Status"].str.lower() == value]

        elif key == "credit_score" and "Credit Score" in filtered.columns:
            try:
                credit_score = int(value.replace('+','').strip())
                filtered = filtered[pd.to_numeric(filtered["Credit Score"], errors='coerce') >= credit_score]
            except:
                pass

        elif key == "travel_frequency" and "Travel Frequency" in filtered.columns:
            filtered = filtered[filtered["Travel Frequency"].str.lower() == value]

        elif key == "ownership_duration" and "Ownership Duration" in filtered.columns:
            filtered = filtered[filtered["Ownership Duration"].str.lower() == value]

        elif key == "ownership_recommendation" and "Ownership Recommendation" in filtered.columns:
            filtered = filtered[filtered["Ownership Recommendation"].str.lower() == value]

        elif key == "yearly_income" and "Yearly Income" in filtered.columns:
            try:
                income = int(value.replace('$', '').replace(',', ''))
                filtered = filtered[pd.to_numeric(filtered["Yearly Income"], errors='coerce') <= income * 2]
            except:
                pass

        elif key == "use_category" and "Use Category" in filtered.columns:
            filtered = filtered[filtered["Use Category"].str.lower() == value]

        elif key == "mpg_range" and "MPG/Range" in filtered.columns:
            try:
                mpg = int(value.split()[0])
                filtered = filtered[pd.to_numeric(filtered["MPG/Range"], errors='coerce') >= mpg]
            except:
                pass

    return filtered

# Recommend using GPT after every answer
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
        f"User profile so far:\n{profile_context}\n\n"
        f"Available cars:\n{car_list}\n\n"
        f"Recommend the two best vehicles that fit the current profile. Mention MSRP Range correctly."
    )

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    return st.write_stream(stream)

# First question
if st.session_state.question_index < len(questions) and len(st.session_state.messages) == 0:
    first_question = questions[st.session_state.question_index]["question"]
    with st.chat_message("assistant"):
        st.markdown(first_question)
    st.session_state.messages.append({"role": "assistant", "content": first_question})

# Chat input flow
if prompt := st.chat_input("Type your answer..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.question_index < len(questions):
        key = questions[st.session_state.question_index]["key"]
        st.session_state.answers[key] = prompt
        st.session_state.question_index += 1

    # Always filter cars and recommend after every answer
    filtered = filter_cars()
    with st.chat_message("assistant"):
        st.markdown("🚘 **Current Best Vehicle Matches:**")
        recommend_cars(filtered)

    # Then ask next question
    if st.session_state.question_index < len(questions):
        next_q = questions[st.session_state.question_index]["question"]
        with st.chat_message("assistant"):
            st.markdown(next_q)
        st.session_state.messages.append({"role": "assistant", "content": next_q})
    else:
        with st.chat_message("assistant"):
            st.markdown("✅ You've completed all questions. Final recommendations are above!")
