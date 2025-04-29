import streamlit as st
import pandas as pd
import time
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from fpdf import FPDF
import tempfile

st.title("🚗 Vehicle Advisor Chatbot")

@st.cache_data
def load_data():
    df = pd.read_csv("https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv")
    if 'Brand' in df.columns:
        df['Brand'] = df['Brand'].str.lower()
    return df

df = load_data()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "shortlist" not in st.session_state:
    st.session_state.shortlist = []
if "question_step" not in st.session_state:
    st.session_state.question_step = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "current_question" not in st.session_state:
    st.session_state.current_question = "🚗 What type of car are you looking for? (e.g., SUV, Sedan, Truck)"

luxury_brands = ['bmw', 'mercedes', 'audi', 'lexus', 'cadillac', 'infiniti', 'acura', 'volvo']

def extract_int(text):
    numbers = re.findall(r'\d+', text.replace(',', ''))
    return int(numbers[0]) if numbers else None

def yes_no_to_bool(text):
    return text.strip().lower() in ["yes", "y"]

def prioritize_by_budget(filtered):
    if filtered.empty:
        return filtered
    if not all(col in filtered.columns for col in ['MSRP Min', 'Year', 'Mileage']):
        return filtered

    budget = st.session_state.answers.get("budget", 0)
    preferred_brands = []

    if budget <= 25000:
        preferred_brands = ['toyota', 'honda', 'nissan', 'hyundai', 'ford', 'kia', 'mazda']
    elif 25001 <= budget <= 50000:
        preferred_brands = ['acura', 'lexus', 'subaru', 'volkswagen', 'ford', 'chevrolet', 'chevy']
    elif budget > 50000:
        preferred_brands = ['bmw', 'mercedes', 'audi', 'lexus', 'cadillac', 'tesla']

    if preferred_brands:
        filtered['preferred'] = filtered['Brand'].apply(lambda x: 0 if x.lower() in preferred_brands else 1)
        sort_columns = ['preferred', 'MSRP Min', 'Year', 'Mileage']
        ascending_order = [True, True, False, True]
    else:
        sort_columns = ['MSRP Min', 'Year', 'Mileage']
        ascending_order = [True, False, True]

    filtered = filtered.sort_values(by=sort_columns, ascending=ascending_order)

    if 'preferred' in filtered.columns:
        filtered = filtered.drop(columns=['preferred'])

    return filtered

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# First question
if len(st.session_state.messages) == 0:
    with st.chat_message("assistant"):
        st.markdown(st.session_state.current_question)
    st.session_state.messages.append({"role": "assistant", "content": st.session_state.current_question})

user_input = st.chat_input("Type your answer here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    idx = st.session_state.question_step

    # Save answer
    if idx == 0:
        st.session_state.answers["type"] = user_input
    elif idx == 1:
        st.session_state.answers["region"] = user_input.lower()
    elif idx == 2:
        st.session_state.answers["budget"] = extract_int(user_input)
    elif idx == 3:
        st.session_state.answers["brand"] = user_input.lower()
    elif idx == 4:
        st.session_state.answers["year"] = extract_int(user_input)
    elif idx == 5:
        st.session_state.answers["mileage"] = extract_int(user_input)
    elif idx == 6:
        st.session_state.answers["electric"] = yes_no_to_bool(user_input)
    elif idx == 7:
        st.session_state.answers["awd"] = yes_no_to_bool(user_input)
    elif idx == 8:
        st.session_state.answers["third_row"] = yes_no_to_bool(user_input)
    elif idx == 9:
        st.session_state.answers["luxury"] = yes_no_to_bool(user_input)
    elif idx == 10:
        st.session_state.answers["monthly_payment"] = extract_int(user_input)

    # Filtering immediately
    filtered = df.copy()

    if st.session_state.answers.get("type"):
        filtered = filtered[filtered['Model'].str.contains(st.session_state.answers["type"], case=False, na=False)]
    if st.session_state.answers.get("brand"):
        filtered = filtered[filtered['Brand'].str.contains(st.session_state.answers["brand"], case=False, na=False)]
    if st.session_state.answers.get("budget"):
        filtered = filtered[filtered['MSRP Min'] <= st.session_state.answers["budget"]]
    if st.session_state.answers.get("year") and 'Year' in filtered.columns:
        filtered = filtered[filtered['Year'] >= st.session_state.answers["year"]]
    if st.session_state.answers.get("mileage") and 'Mileage' in filtered.columns:
        filtered = filtered[filtered['Mileage'] <= st.session_state.answers["mileage"]]
    if st.session_state.answers.get("electric") == True:
        filtered = filtered[filtered['Fuel Type'].str.contains('electric', case=False, na=False)]
    if st.session_state.answers.get("luxury") == True:
        filtered = filtered[filtered['Brand'].isin(luxury_brands)]

    # Regional AWD boosting
    region = st.session_state.answers.get("region", "")
    if region in ["northeast", "midwest"]:
        filtered = filtered[filtered['Drive Type'].str.contains('awd|4wd', case=False, na=False)]

    filtered = prioritize_by_budget(filtered)

    # Show 2 car suggestions
    if not filtered.empty:
        top_cars = filtered.head(2)
        response = "🔎 Based on your answers so far, here are two cars you might love:\n"
        for _, car in top_cars.iterrows():
            price = f"${car['MSRP Min']:,}"
            name = f"{car['Brand'].title()} {car['Model']}"
            reason = "✅ Strong match for your preferences."
            if 'Fuel Type' in car and 'electric' in str(car['Fuel Type']).lower():
                reason = "⚡ Eco-friendly electric drive."
            elif 'awd' in str(car.get('Drive Type', '')).lower() or '4wd' in str(car.get('Drive Type', '')).lower():
                reason = "🚙 Great for your region's weather."
            elif 'Mileage' in car and car['Mileage'] < 30000:
                reason = "🛡️ Very low mileage — almost like new!"
            response += f"**✨ {name}**\n- 💲 **Price:** {price}\n- {reason}\n\n"
        st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        st.session_state.messages.append({"role": "assistant", "content": "⚠️ No close matches yet, but let's continue building your profile!"})

    # Next question
    questions = [
        "🌎 Which region are you in? (e.g., Northeast, Midwest, South, West)",
        "💬 What's your maximum budget?",
        "🏷️ Any preferred brand you'd like?",
        "📅 What's the minimum model year you're aiming for?",
        "🛣️ What's your maximum mileage?",
        "🔋 Do you prefer electric vehicles? (yes/no)",
        "🚙 Need AWD or 4WD? (yes/no)",
        "👨‍👩‍👧‍👦 Need a third-row seat? (yes/no)",
        "💎 Prefer a luxury brand? (yes/no)",
        "💵 What's your maximum monthly payment goal?"
    ]

    if idx < len(questions):
        bot_reply = questions[idx]
    else:
        bot_reply = "✅ Thanks! Let’s finalize your perfect match..."

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    st.session_state.question_step += 1

# When finished
if st.session_state.question_step > 10:
    with st.chat_message("assistant"):
        st.markdown("🚗 Based on your full profile, here are your top matches:")
        final_filtered = df.copy()

        if st.session_state.answers.get("type"):
            final_filtered = final_filtered[final_filtered['Model'].str.contains(st.session_state.answers["type"], case=False, na=False)]
        if st.session_state.answers.get("brand"):
            final_filtered = final_filtered[final_filtered['Brand'].str.contains(st.session_state.answers["brand"], case=False, na=False)]
        if st.session_state.answers.get("budget"):
            final_filtered = final_filtered[final_filtered['MSRP Min'] <= st.session_state.answers["budget"]]
        if st.session_state.answers.get("year") and 'Year' in final_filtered.columns:
            final_filtered = final_filtered[final_filtered['Year'] >= st.session_state.answers["year"]]
        if st.session_state.answers.get("mileage") and 'Mileage' in final_filtered.columns:
            final_filtered = final_filtered[final_filtered['Mileage'] <= st.session_state.answers["mileage"]]
        if st.session_state.answers.get("electric") == True:
            final_filtered = final_filtered[final_filtered['Fuel Type'].str.contains('electric', case=False, na=False)]
        if st.session_state.answers.get("luxury") == True:
            final_filtered = final_filtered[final_filtered['Brand'].isin(luxury_brands)]
        if st.session_state.answers.get("region", "") in ["northeast", "midwest"]:
            final_filtered = final_filtered[final_filtered['Drive Type'].str.contains('awd|4wd', case=False, na=False)]

        final_filtered = prioritize_by_budget(final_filtered)

        if not final_filtered.empty:
            top_final = final_filtered.head(3)
            for _, car in top_final.iterrows():
                price = f"${car['MSRP Min']:,}"
                name = f"{car['Brand'].title()} {car['Model']}"
                st.markdown(f"**✨ {name}**\n- 💲 **Price:** {price}")
        else:
            st.markdown("❗ No final matches found based on all preferences.")

# Restart button
if st.button("🔄 Restart Profile"):
    st.session_state.clear()
    st.rerun()
