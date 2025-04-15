import streamlit as st
import pandas as pd
import openai
import re
import os

st.set_page_config(page_title="Vehicle Advisor", layout="centered")

# Load vehicle dataset
@st.cache_data
def load_data():
    df = pd.read_csv("vehicle_data.csv")
    df['MSRP Min'] = df['MSRP Range'].apply(
        lambda x: float(re.findall(r'\$([\d,]+)', str(x))[0].replace(',', ''))
        if re.findall(r'\$([\d,]+)', str(x)) else None
    )
    return df

df = load_data()

# Set OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

if "profile_complete" not in st.session_state:
    st.session_state.profile_complete = False

# Score weights for importance
score_weights = {
    "Budget": 2.0, "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6,
    "Credit Score": 0.6, "Garage Access": 0.5, "Eco-Conscious": 0.8,
    "Charging Access": 0.8, "Neighborhood Type": 0.9, "Towing Needs": 0.6,
    "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
    "Ownership Recommendation": 0.7, "Employment Status": 0.6,
    "Travel Frequency": 0.5, "Ownership Duration": 0.5
}

# Helper to get unanswered questions by score priority
def get_next_question():
    unanswered = sorted(
        [(k, v) for k, v in score_weights.items() if k not in st.session_state.user_answers],
        key=lambda x: -x[1]
    )
    if unanswered:
        field = unanswered[0][0]
        question_texts = {
            "Budget": "What's your max budget for this car?",
            "Use Category": "What will you mostly use the car for — commuting, hauling, family trips, etc.?",
            "Region": "Which region or state are you in?",
            "Neighborhood Type": "Do you live in a city, suburb, or rural area?",
            "Credit Score": "What’s your credit score range looking like?",
            "Eco-Conscious": "Are you interested in EVs or hybrids?",
            "Charging Access": "Do you have access to EV charging at home or nearby?",
            "Safety Priority": "Is top-tier safety a must-have for you?",
            "Tech Features": "Do you value modern tech like touchscreen, navigation, etc.?",
            "Car Size": "Do you prefer compact, midsize, or larger vehicles?",
            "Towing Needs": "Do you need to tow trailers, boats, etc.?",
            "Yearly Income": "What’s your approximate yearly income?",
            "Garage Access": "Do you have a garage or dedicated parking?",
            "Ownership Recommendation": "Would you rather lease or own?",
            "Employment Status": "What’s your current employment status?",
            "Travel Frequency": "Do you travel long distances frequently?",
            "Ownership Duration": "Are you planning to keep this car short-term or long-term?"
        }
        return field, question_texts.get(field, "Can you tell me more about your car needs?")
    return None, None

# Function to get top 3 car recommendations
def recommend_vehicles():
    df_filtered = df.copy()
    budget = st.session_state.user_answers.get("Budget")
    if budget:
        df_filtered = df_filtered[df_filtered["MSRP Min"] <= float(budget)]

    eco = st.session_state.user_answers.get("Eco-Conscious")
    if eco and eco.lower() in ["yes", "true", "y"]:
        df_filtered = df_filtered[df_filtered["Fuel Type"].str.contains("Hybrid|Electric", na=False)]

    neighborhood = st.session_state.user_answers.get("Neighborhood Type", "").lower()
    if "city" in neighborhood:
        df_filtered = df_filtered[df_filtered["Type"].str.contains("Sedan|Compact|Crossover", na=False)]
    elif "rural" in neighborhood:
        df_filtered = df_filtered[df_filtered["Type"].str.contains("SUV|Truck", na=False)]

    if df_filtered.empty:
        return []

    top3 = df_filtered.sort_values("MSRP Min").head(3)
    return top3

# Function to show recommendation and then question
def show_suggestion_then_question(suggestion, question):
    st.markdown(suggestion)
    st.markdown(question)

# Chat UI
st.markdown("### 🚗 Vehicle Advisor Chat")
user_input = st.text_input("You:", key="user_input")

if user_input:
    st.session_state.chat_history.append(("user", user_input))
    st.session_state.user_input = ""

    # Store known answers
    for field in score_weights:
        if field.lower() in user_input.lower() and field not in st.session_state.user_answers:
            st.session_state.user_answers[field] = user_input.split()[-1]  # crude grab

    # If user says to continue refining
    if "refine" in user_input.lower():
        field, next_q = get_next_question()
        if field and next_q:
            suggestion = "Got it. Let’s narrow this down a bit more."
            show_suggestion_then_question(suggestion, next_q)

    # If user says learn more about vehicles
    elif "learn more" in user_input.lower():
        top_cars = recommend_vehicles()
        if top_cars.empty:
            st.markdown("Couldn’t find more vehicles that match just yet. Let’s refine a bit.")
        else:
            for _, row in top_cars.iterrows():
                st.markdown(f"**{row['Make']} {row['Model']}** — {row['Type']} starting at {row['MSRP Range']}.\n\nFuel Type: {row['Fuel Type']} | Range: {row.get('Range', 'N/A')} | Horsepower: {row.get('Horsepower', 'N/A')}")

    # If enough answers gathered
    elif len(st.session_state.user_answers) >= 6 and not st.session_state.profile_complete:
        st.session_state.profile_complete = True
        st.markdown("✅ I’ve gathered enough information. Here are my top 3 car recommendations:")

        top3 = recommend_vehicles()
        if top3.empty:
            st.markdown("Hmm, no perfect matches yet. Want to continue refining?")
        else:
            for _, row in top3.iterrows():
                st.markdown(f"**{row['Make']} {row['Model']}** — {row['Type']} | {row['MSRP Range']}")
            st.markdown("Would you like to **learn more about these vehicles**, or should I **ask another question to refine your match**?")

    # Default flow
    else:
        field, next_q = get_next_question()
        if field and next_q:
            suggestion = "Let’s keep building your profile so I can get the perfect match for you."
            show_suggestion_then_question(suggestion, next_q)
        else:
            st.markdown("I think we’ve got your profile down! Want to see more cars or restart?")

# Show chat history
st.markdown("### 💬 Chat History")
for sender, msg in st.session_state.chat_history:
    role = "You" if sender == "user" else "Advisor"
    st.markdown(f"**{role}:** {msg}")
