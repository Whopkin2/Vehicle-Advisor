import streamlit as st
import pandas as pd
import re

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
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "question_step" not in st.session_state:
    st.session_state.question_step = 0

luxury_brands = ['bmw', 'mercedes', 'audi', 'lexus', 'cadillac', 'infiniti', 'acura', 'volvo']

def extract_number(text):
    """Extract integer from text like '65k', '10,000', '10k miles'"""
    text = text.lower().replace(',', '').strip()
    if 'k' in text:
        number = re.findall(r'\d+', text)
        return int(number[0]) * 1000 if number else None
    number = re.findall(r'\d+', text)
    return int(number[0]) if number else None

def parse_yes_no(text):
    return text.strip().lower() in ['yes', 'y']

def clean_brand_input(text):
    """Handles input like 'Ford, Chevy, Volvo' into a clean list"""
    brands = [b.strip().lower() for b in re.split(',|&|and', text) if b.strip()]
    return brands

def flexible_filter(df, answers):
    filtered = df.copy()

    # Vehicle type
    if answers.get("type"):
        car_type = answers["type"].lower()
        if 'Body Type' in filtered.columns:
            filtered = filtered[filtered['Body Type'].str.contains(car_type, case=False, na=False)]
        elif 'Category' in filtered.columns:
            filtered = filtered[filtered['Category'].str.contains(car_type, case=False, na=False)]

    # Region based AWD boost
    if answers.get("region") in ["northeast", "midwest"]:
        if 'Drive Type' in filtered.columns:
            filtered = filtered[filtered['Drive Type'].str.contains('awd|4wd', case=False, na=False)]

    # Budget
    if answers.get("budget"):
        filtered = filtered[filtered['MSRP Min'] <= answers["budget"]]

    # Brand(s)
    if answers.get("brands"):
        brand_filter = filtered['Brand'].apply(lambda x: any(brand in x for brand in answers['brands']))
        filtered = filtered[brand_filter]

    # Minimum Year
    if answers.get("year") and 'Year' in filtered.columns:
        filtered = filtered[filtered['Year'] >= answers["year"]]

    # Max mileage
    if answers.get("mileage") and 'Mileage' in filtered.columns:
        filtered = filtered[filtered['Mileage'] <= answers["mileage"]]

    # Electric
    if answers.get("electric") == True:
        filtered = filtered[filtered['Fuel Type'].str.contains('electric', case=False, na=False)]

    # Luxury preference
    if answers.get("luxury") == True:
        filtered = filtered[filtered['Brand'].isin(luxury_brands)]

    return filtered

questions = [
    "🚗 What type of car are you looking for? (e.g., SUV, Sedan, Truck)",
    "🌎 Which region are you in? (e.g., Northeast, Midwest, South, West)",
    "💬 What's your maximum budget?",
    "🏷️ Any preferred brands you'd like? (e.g., Ford, Chevy, Volvo)",
    "📅 What's the minimum model year you're aiming for?",
    "🛣️ What's your maximum mileage per year?",
    "🔋 Do you prefer electric vehicles? (yes/no)",
    "🚙 Need AWD or 4WD? (yes/no)",
    "👨‍👩‍👧‍👦 Need a third-row seat? (yes/no)",
    "💎 Prefer a luxury brand? (yes/no)",
    "💵 What's your maximum monthly payment goal?"
]

# Show chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Ask initial question
if len(st.session_state.messages) == 0:
    with st.chat_message("assistant"):
        st.markdown(questions[0])
    st.session_state.messages.append({"role": "assistant", "content": questions[0]})

user_input = st.chat_input("Type your answer here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    idx = st.session_state.question_step

    # Save cleaned answer
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
        st.session_state.answers["mileage"] = extract_number(user_input)
    elif idx == 6:
        st.session_state.answers["electric"] = parse_yes_no(user_input)
    elif idx == 7:
        st.session_state.answers["awd"] = parse_yes_no(user_input)
    elif idx == 8:
        st.session_state.answers["third_row"] = parse_yes_no(user_input)
    elif idx == 9:
        st.session_state.answers["luxury"] = parse_yes_no(user_input)
    elif idx == 10:
        st.session_state.answers["monthly_payment"] = extract_number(user_input)

    # Flexible partial filtering
    filtered = flexible_filter(df, st.session_state.answers)

    # Always try to suggest something
    if not filtered.empty:
        top_cars = filtered.head(2)
        reply = "🔎 Based on your answers so far, here are two cars you might love:\n"
        for _, car in top_cars.iterrows():
            name = f"{car['Brand'].title()} {car['Model']}"
            price = f"${car['MSRP Min']:,}"
            reply += f"✨ **{name}**\n- 💲 **Price:** {price}\n\n"
        st.session_state.messages.append({"role": "assistant", "content": reply})
    else:
        st.session_state.messages.append({"role": "assistant", "content": "⚠️ No exact matches yet, but we'll keep adjusting!"})

    # Next question
    if idx + 1 < len(questions):
        next_q = questions[idx + 1]
        st.session_state.messages.append({"role": "assistant", "content": next_q})
        st.session_state.question_step += 1
    else:
        # Final recommendations
        st.session_state.messages.append({"role": "assistant", "content": "✅ Finalizing your top matches now!"})

# Final recommendations
if st.session_state.question_step >= len(questions):
    filtered = flexible_filter(df, st.session_state.answers)

    if not filtered.empty:
        st.markdown("🚗 **Top Matches Based on Your Full Profile:**")
        top_cars = filtered.head(3)
        for _, car in top_cars.iterrows():
            name = f"{car['Brand'].title()} {car['Model']}"
            price = f"${car['MSRP Min']:,}"
            st.markdown(f"✨ **{name}**\n- 💲 **Price:** {price}")
    else:
        st.markdown("❗ No perfect matches. Showing best available options:")
        fallback = df.sort_values(by='MSRP Min').head(3)
        for _, car in fallback.iterrows():
            name = f"{car['Brand'].title()} {car['Model']}"
            price = f"${car['MSRP Min']:,}"
            st.markdown(f"✨ **{name}**\n- 💲 **Price:** {price}")

# Restart
if st.button("🔄 Restart Profile"):
    st.session_state.clear()
    st.rerun()
