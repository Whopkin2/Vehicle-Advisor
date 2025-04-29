import streamlit as st
import pandas as pd
import openai
import re
import numpy as np

st.title("🚗 Vehicle Advisor Chatbot")

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

@st.cache_data
def load_data():
    df = pd.read_csv("https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv")
    if 'Brand' in df.columns:
        df['Brand'] = df['Brand'].str.lower()

    def parse_price_range(text):
        if isinstance(text, str):
            parts = re.findall(r'\$?\s?([\d,]+)', text)
            if len(parts) == 1:
                price = float(parts[0].replace(',', ''))
                return price, price
            elif len(parts) >= 2:
                min_price = float(parts[0].replace(',', ''))
                max_price = float(parts[1].replace(',', ''))
                return min_price, max_price
        return np.nan, np.nan

    df[['MSRP Min', 'MSRP Max']] = df['MSRP Range'].apply(lambda x: pd.Series(parse_price_range(x)))
    return df

df = load_data()

# Initialize Session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "question_step" not in st.session_state:
    st.session_state.question_step = 0

luxury_brands = ['bmw', 'mercedes', 'audi', 'lexus', 'cadillac', 'infiniti', 'acura', 'volvo']

# Utility Functions
def extract_number(text):
    text = text.lower().replace(',', '').strip()
    if 'k' in text:
        number = re.findall(r'\d+', text)
        return int(number[0]) * 1000 if number else None
    number = re.findall(r'\d+', text)
    return int(number[0]) if number else None

def parse_yes_no(text):
    return text.strip().lower() in ['yes', 'y']

def clean_brand_input(text):
    brands = [b.strip().lower() for b in re.split(',|&|and', text) if b.strip()]
    return brands

def flexible_filter(df, answers):
    filtered = df.copy()

    # 1. Enforce exact match for Category (e.g., Truck, SUV, Sedan)
    if answers.get("type") and 'Category' in filtered.columns:
        selected_type = answers["type"].strip().lower()
        filtered = filtered[filtered['Category'].str.strip().str.lower() == selected_type]

    # 2. AWD/4WD required by region (northeast, midwest)
    if answers.get("region") and answers["region"].strip().lower() in ["northeast", "midwest"]:
        if 'Drive Type' in filtered.columns:
            filtered = filtered[filtered['Drive Type'].str.contains(r'\b(awd|4wd)\b', case=False, na=False)]

    # 3. Budget cap on MSRP Min
    if answers.get("budget") and 'MSRP Min' in filtered.columns:
        filtered = filtered[filtered['MSRP Min'] <= answers["budget"]]

    # 4. Filter by preferred brands
    if answers.get("brands") and 'Brand' in filtered.columns:
        user_brands = [b.strip().lower() for b in answers["brands"]]
        filtered = filtered[filtered['Brand'].str.lower().isin(user_brands)]

    # 5. Minimum acceptable model year
    if answers.get("year") and 'Year' in filtered.columns:
        filtered = filtered[filtered['Year'] >= answers["year"]]

    # 6. Vehicle mileage threshold (how used the vehicle is)
    if answers.get("max_mileage") and 'Mileage' in filtered.columns:
        filtered = filtered[filtered['Mileage'] <= answers["max_mileage"]]

    # 7. Electric vehicle only if explicitly requested
    if answers.get("electric") == True and 'Fuel Type' in filtered.columns:
        filtered = filtered[filtered['Fuel Type'].str.contains('electric', case=False, na=False)]

    # 8. AWD/4WD if user specifically said yes
    if answers.get("awd") == True and 'Drive Type' in filtered.columns:
        filtered = filtered[filtered['Drive Type'].str.contains(r'\b(awd|4wd)\b', case=False, na=False)]

    # 9. Luxury brand enforcement
    if answers.get("luxury") == True and 'Brand' in filtered.columns:
        filtered = filtered[filtered['Brand'].str.lower().isin([b.lower() for b in luxury_brands])]

    # 10. Monthly payment → estimate max price
    if answers.get("monthly_payment") and 'MSRP Min' in filtered.columns:
        estimated_max_price = answers["monthly_payment"] * 60  # Approx 5-year loan, no interest
        filtered = filtered[filtered['MSRP Min'] <= estimated_max_price]

    return filtered

def generate_reasoning_gpt(car, answers):
    brand = car['Brand'].title()
    model = car['Model']
    car_type = answers.get("type", "vehicle")
    region = answers.get("region", "your region")
    budget = f"${answers.get('budget'):,}" if answers.get('budget') else "your budget"

    prompt = (
        f"Explain in 2-3 sentences why a {brand} {model} would be a good fit for a user looking for a {car_type}, "
        f"living in the {region}, with a budget around {budget}. "
        f"Highlight any features that make it especially suitable, such as luxury, AWD, fuel economy, or reliability."
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=120
    )

    return response.choices[0].message.content.strip()

# Updated Questions
questions = [
    "🚗 What type of car are you looking for? (e.g., SUV, Sedan, Truck)",
    "🌎 Which region are you in? (e.g., Northeast, Midwest, South, West)",
    "💬 What's your maximum budget?",
    "🏷️ Any preferred brands you'd like? (e.g., Ford, Chevy, Volvo)",
    "📅 What's the minimum model year you're aiming for?",
    "🛣️ What's your maximum allowable mileage on the vehicle?",
    "🛫 About how many miles do you drive annually?",
    "🔋 Do you prefer electric vehicles? (yes/no)",
    "🚙 Need AWD or 4WD? (yes/no)",
    "💎 Prefer a luxury brand? (yes/no)",
    "💵 What's your approximate monthly car payment budget?"
]

# Display Conversation
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if len(st.session_state.messages) == 0:
    with st.chat_message("assistant"):
        st.markdown(questions[0])
    st.session_state.messages.append({"role": "assistant", "content": questions[0]})

user_input = st.chat_input("Type your answer here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    idx = st.session_state.question_step

    if idx == 0:
        st.session_state.answers["type"] = user_input
    elif idx == 1:
        st.session_state.answers["region"] = user_input.lower()
    elif idx == 2:
        st.session_state.answers["budget"] = extract_number(user_input)
    elif idx == 3:
        st.session_state.answers["brands"] = clean_brand_input(user_input)
    elif idx == 4:
        st.session_state.answers["year"] = extract_number(user_input)
    elif idx == 5:
        st.session_state.answers["max_mileage"] = extract_number(user_input)
    elif idx == 6:
        st.session_state.answers["annual_mileage"] = extract_number(user_input)
    elif idx == 7:
        st.session_state.answers["electric"] = parse_yes_no(user_input)
    elif idx == 8:
        st.session_state.answers["awd"] = parse_yes_no(user_input)
    elif idx == 9:
        st.session_state.answers["luxury"] = parse_yes_no(user_input)
    elif idx == 10:
        st.session_state.answers["monthly_payment"] = extract_number(user_input)

    # Apply filtering
    filtered = flexible_filter(df, st.session_state.answers)

    if not filtered.empty:
        top_cars = filtered.head(2)
        reply = "🔎 Based on your answers so far, here are two cars you might love:\n\n"
        for _, car in top_cars.iterrows():
            name = f"{car['Brand'].title()} {car['Model']}"
            if pd.notnull(car['MSRP Min']):
                min_price = f"${int(car['MSRP Min']):,}"
            else:
                min_price = "N/A"
            if pd.notnull(car.get('MSRP Max')):
                max_price = f"${int(car['MSRP Max']):,}"
            else:
                max_price = None
            price_range = min_price if not max_price else f"{min_price} – {max_price}"
            explanation = generate_reasoning_gpt(car, st.session_state.answers)
            reply += f"✨ **{name}**\n- 💲 **Price Range:** {price_range}\n- 🧠 {explanation}\n\n"
        st.session_state.messages.append({"role": "assistant", "content": reply})
    else:
        st.session_state.messages.append({"role": "assistant", "content": "⚠️ No exact matches yet, but we'll keep adjusting!"})

    # Move to next question
    if idx + 1 < len(questions):
        st.session_state.question_step += 1
        st.session_state.messages.append({"role": "assistant", "content": questions[st.session_state.question_step]})
    else:
        st.session_state.messages.append({"role": "assistant", "content": "✅ Finalizing your top matches now!"})

# Restart Button
if st.button("🔄 Restart Profile"):
    st.session_state.clear()
    st.rerun()
