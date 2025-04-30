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

# Questions
questions = [
    {"key": "new_or_used", "question": "Do you prefer a new or used car? (New or Used)"},
    {"key": "vehicle_type", "question": "What type of vehicle are you looking for? (Sedan, SUV, Truck, Crossover, Sports Car, Van, Coupe)"},
    {"key": "car_size", "question": "What size of vehicle do you want? (Compact, Midsize, Fullsize)"},
    {"key": "budget", "question": "What's your maximum budget for a vehicle (in USD)?"},
    {"key": "fuel_type", "question": "What fuel type do you prefer? (Gasoline, Electric, Hybrid, Plug-in Hybrid)"},
    {"key": "region", "question": "Which region are you located in? (North East, Mid-West, West, South)"},
    {"key": "use_category", "question": "What will be the vehicle's primary use? (Family Vehicle, Commuting, Utility, Off-Roading)"},
    {"key": "eco_conscious", "question": "Are you eco-conscious? (Yes or No)"},
    {"key": "charging_access", "question": "Do you have access to a charging station? (Yes or No)"},
    {"key": "neighborhood_type", "question": "What type of neighborhood are you in? (City, Suburbs, Rural)"},
    {"key": "tech_features", "question": "What level of tech features do you want? (Advanced, Basic, Moderate)"},
    {"key": "safety_priority", "question": "How important are safety features to you? (High, Medium, Low)"},
    {"key": "garage_access", "question": "Do you have a garage for your vehicle? (Yes or No)"},
    {"key": "employment_status", "question": "What is your employment status? (Employed, Student, Retired)"},
    {"key": "credit_score", "question": "What is your approximate credit range? (Excellent 800+, Very Good 799-750, Good 749-700, Fair <700)"},
    {"key": "travel_frequency", "question": "How often do you travel long distances? (Daily, Occasionally, Rarely)"},
    {"key": "ownership_duration", "question": "How long do you plan to own the vehicle? (Short Term, Medium Term, Long Term)"},
    {"key": "ownership_recommendation", "question": "Would you prefer to Buy, Lease, or Rent the vehicle?"},
    {"key": "yearly_income", "question": "What is your estimated yearly income? (e.g., 50k-100k, 100k-150k)"},
    {"key": "brand", "question": "Do you have a preferred vehicle brand? (e.g., Honda, Ford, Audi, Mercedes)"},
]

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "question_index" not in st.session_state:
    st.session_state.question_index = 0

st.title("\U0001F697 Vehicle Advisor Chatbot")

# Show previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Show first question if empty
if st.session_state.question_index == 0 and len(st.session_state.messages) == 0:
    first_q = questions[0]["question"]
    with st.chat_message("assistant"):
        st.markdown(first_q)
    st.session_state.messages.append({"role": "assistant", "content": first_q})

# Filter cars 
def filter_cars():
    filtered = df.copy()
    for key, value in st.session_state.answers.items():
        value = value.strip().lower()
        if value in ["no", "none", "any"]:
            continue
            
        elif key == "budget":
            try:
                max_budget = float(value.lower().replace('$', '').replace(',', '').replace('k', '000').strip())

                # Extract MSRP Range into Min and Max
                price_range = filtered["MSRP Range"].str.extract(r'\$?([\d,]+)\s*[-–]\s*\$?([\d,]+)')
                filtered["Min Price"] = price_range[0].str.replace(',', '').astype(float)
                filtered["Max Price"] = price_range[1].str.replace(',', '').astype(float)

                # Filter only cars fully within budget range
                filtered = filtered[
                    (filtered["Min Price"] <= max_budget) &
                    (filtered["Max Price"] <= max_budget)
                ]
            except Exception as e:
                st.warning(f"Budget parsing failed: {e}")

        elif key == "new_or_used":
            if "used" in value:
                filtered = filtered[filtered["New or Used"].str.lower().str.contains("used", na=False)]
            elif "new" in value:
                filtered = filtered[~filtered["New or Used"].str.lower().str.contains("used", na=False)]

        elif key == "fuel_type" and "Fuel Type" in filtered.columns:
            filtered = filtered[filtered["Fuel Type"].str.lower().str.contains(value, na=False)]

        elif key == "vehicle_type" and "Vehicle Type" in filtered.columns:
            filtered = filtered[filtered["Vehicle Type"].str.lower().str.contains(value, na=False)]

        elif key == "car_size" and "Car Size" in filtered.columns:
            filtered = filtered[filtered["Car Size"].str.lower().str.contains(value, na=False)]

        elif key == "region" and "Region" in filtered.columns:
            filtered = filtered[filtered["Region"].str.lower().str.contains(value, na=False)]

        elif key == "brand" and "Brand" in filtered.columns:
            filtered = filtered[filtered["Brand"].str.lower().str.contains(value, na=False)]

        elif key == "eco_conscious" and "Eco-Conscious" in filtered.columns:
            filtered = filtered[filtered["Eco-Conscious"].str.lower().str.contains(value, na=False)]

        elif key == "charging_access" and "Charging Access" in filtered.columns:
            filtered = filtered[filtered["Charging Access"].str.lower().str.contains(value, na=False)]

        elif key == "neighborhood_type" and "Neighborhood Type" in filtered.columns:
            filtered = filtered[filtered["Neighborhood Type"].str.lower().str.contains(value, na=False)]

        elif key == "tech_features" and "Tech Features" in filtered.columns:
            filtered = filtered[filtered["Tech Features"].str.lower().str.contains(value, na=False)]

        elif key == "safety_priority" and "Safety Priority" in filtered.columns:
            filtered = filtered[filtered["Safety Priority"].str.lower().str.contains(value, na=False)]

        elif key == "garage_access" and "Garage Access" in filtered.columns:
            filtered = filtered[filtered["Garage Access"].str.lower().str.contains(value, na=False)]

        elif key == "employment_status" and "Employment Status" in filtered.columns:
            filtered = filtered[filtered["Employment Status"].str.lower().str.contains(value, na=False)]

        elif key == "credit_score" and "Credit Score" in filtered.columns:
            filtered = filtered[filtered["Credit Score"].str.lower().str.contains(value, na=False)]

        elif key == "travel_frequency" and "Travel Frequency" in filtered.columns:
            filtered = filtered[filtered["Travel Frequency"].str.lower().str.contains(value, na=False)]

        elif key == "ownership_duration" and "Ownership Duration" in filtered.columns:
            filtered = filtered[filtered["Ownership Duration"].str.lower().str.contains(value, na=False)]

        elif key == "ownership_recommendation" and "Ownership Recommendation" in filtered.columns:
            filtered = filtered[filtered["Ownership Recommendation"].str.lower().str.contains(value, na=False)]

        elif key == "yearly_income" and "Yearly Income" in filtered.columns:
            filtered = filtered[filtered["Yearly Income"].str.lower().str.contains(value, na=False)]

        elif key == "use_category" and "Use Category" in filtered.columns:
            filtered = filtered[filtered["Use Category"].str.lower().str.contains(value, na=False)]

    return filtered

def recommend_final_cars(filtered):
    top = filtered.head(3)
    if top.empty:
        return st.markdown("_No matching vehicles found for full profile._")

    profile = "\n".join([
        f"{k.replace('_',' ').title()}: {v}" for k,v in st.session_state.answers.items()
    ])

    explanations = []
    for _, row in top.iterrows():
        brand = row['Brand'].title()
        model = row['Model'].title()
        msrp = row['MSRP Range']
        prompt = (
            f"User Profile:\n{profile}\n\n"
            f"Explain in 2-3 sentences why a {brand} {model} would be a good fit for a user with this profile. "
            f"Highlight any features that make it especially suitable, such as luxury, AWD, fuel economy, or reliability. "
            f"Include the MSRP range: {msrp}."
        )
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = response.choices[0].message.content
        explanations.append(f"**{brand} {model}**  \n{explanation}  \n**MSRP Range:** {msrp}")

    st.markdown(
        f"<div style='font-family: Arial; font-size: 16px; line-height: 1.6;'>{'<br><br>'.join(explanations)}</div>",
        unsafe_allow_html=True
    )

# User input
if prompt := st.chat_input("Type your answer..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.question_index < len(questions):
        q_key = questions[st.session_state.question_index]["key"]
        st.session_state.answers[q_key] = prompt
        st.session_state.question_index += 1

    filtered = filter_cars()
    
    if st.session_state.question_index >= len(questions):
        recommend_final_cars(filtered)
        
    else:
        with st.chat_message("assistant"):
            top = filtered.head(2)  # ✅ Define 'top' first
            st.markdown("<div style='font-family: Arial; font-size: 16px; line-height: 1.6;'>🚘 <strong>Current Best Vehicle Matches:</strong></div>", unsafe_allow_html=True)
            explanations_html = "<ul style='font-family: Arial; font-size: 16px;'>"
    for _, row in top.iterrows():
        brand = row['Brand'].title()
        model = row['Model'].title()
        msrp = row['MSRP Range']

        profile_so_far = "\n".join([
            f"{k.replace('_',' ').title()}: {v}" for k, v in st.session_state.answers.items()
        ])

        prompt = (
            f"User Profile so far:\n{profile_so_far}\n\n"
            f"Explain in 2-3 sentences why the {brand} {model} is a good choice for this user. "
            f"Highlight anything notable like fuel economy, comfort, utility, safety, or luxury. "
            f"Include MSRP range: {msrp}."
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            explanation = response.choices[0].message.content.strip()
        except Exception as e:
            explanation = f"*(Failed to generate explanation: {e})*"

        explanations_html += f"<li><strong>{brand} {model}</strong> (MSRP Range: {msrp})<br>{explanation}</li>"

    explanations_html += "</ul>"

    st.markdown(explanations_html, unsafe_allow_html=True)   

        if st.session_state.question_index < len(questions):
            next_q = questions[st.session_state.question_index]["question"]
            with st.chat_message("assistant"):
                st.markdown(next_q)
            st.session_state.messages.append({"role": "assistant", "content": next_q})

