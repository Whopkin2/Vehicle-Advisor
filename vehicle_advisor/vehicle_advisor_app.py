import streamlit as st
import pandas as pd
import openai
import re
import os

st.set_page_config(page_title="Vehicle Advisor", layout="centered")

@st.cache_data
def load_data():
    df = pd.read_csv("vehicle_data.csv")
    df['MSRP Min'] = df['MSRP Range'].apply(
        lambda msrp_range: float(re.findall(r'\$([\d,]+)', str(msrp_range))[0].replace(',', ''))
        if re.findall(r'\$([\d,]+)', str(msrp_range)) else None
    )
    return df

df_vehicle_advisor = load_data()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# --- SESSION STATE INIT ---
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "awaiting_vehicle_detail" not in st.session_state:
    st.session_state.awaiting_vehicle_detail = False
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = []

# --- BASIC KEYWORD EXTRACTION TO AUTO-UPDATE PROFILE ---
def extract_profile_info(user_input):
    text = user_input.lower()
    if "commute" in text:
        st.session_state.user_answers["Use Category"] = "Commute"
    if "fuel" in text:
        st.session_state.user_answers["Fuel Preference"] = "Fuel Efficiency" if "efficiency" in text else "Performance"
    if any(brand in text for brand in ["ford", "honda", "toyota", "chevy", "bmw", "hyundai", "tesla"]):
        st.session_state.user_answers["Brand Preference"] = user_input
    if "$" in text or "k" in text:
        st.session_state.user_answers["Budget"] = user_input
    if "new" in text:
        st.session_state.user_answers["Condition"] = "New"
    elif "used" in text:
        st.session_state.user_answers["Condition"] = "Used"

# --- VEHICLE RECOMMENDATION FUNCTION ---
def recommend_vehicles(user_answers, top_n=2):
    df = df_vehicle_advisor.copy()
    try:
        user_budget = float(re.findall(r'\d+', user_answers.get("Budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    score_weights = {
        "Region": 1.0, "Use Category": 1.0, "Fuel Preference": 1.0, "Brand Preference": 1.0, "Condition": 1.0,
        "Budget": 2.0, "Garage Access": 0.5, "Eco-Conscious": 0.8, "Neighborhood Type": 0.9,
        "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
        "Employment Status": 0.6, "Travel Frequency": 0.5, "Ownership Duration": 0.5, "Annual Mileage": 0.6
    }

    def compute_score(row):
        return sum(
            weight for key, weight in score_weights.items()
            if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower()
        )

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

# --- CHAT UI ---
st.markdown("## 🚗 VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(msg, unsafe_allow_html=True)

# --- INPUT FORM ---
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Your reply:")
    submitted = st.form_submit_button("Send")

# --- ON SUBMIT ---
if submitted and user_input:
    st.session_state.chat_log.append(f"<b>You:</b> {user_input}")

    # Auto-profile update
    extract_profile_info(user_input)

    # If user asked to learn more
    if st.session_state.awaiting_vehicle_detail and "learn" in user_input.lower():
        details = ""
        for car in st.session_state.last_recommendations:
            details += f"**{car['Brand']} {car['Model']} ({car['Model Year']})**\n"
            details += f"- MSRP Range: {car['MSRP Range']}\n"
            details += f"- Size: {car.get('Car Size', 'N/A')}\n"
            details += f"- Safety: {car.get('Safety Priority', 'N/A')}\n"
            details += f"- Tech Features: {car.get('Tech Features', 'N/A')}\n\n"
        details += "Would you like to continue refining your preferences?"
        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b><br>{details}")
        st.session_state.awaiting_vehicle_detail = False
        st.rerun()

    # Otherwise, build GPT prompt and continue
    profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
    answered_keys = [k for k, v in st.session_state.user_answers.items() if v]
    answered_list = ", ".join(answered_keys) if answered_keys else "None yet"

    gpt_prompt = (
        f"You are a professional vehicle advisor helping a customer select the ideal car.\n"
        f"Your tone is formal, concise, and helpful.\n\n"
        f"The user has already answered questions about: {answered_list}.\n"
        f"Do not ask about these again.\n\n"
        f"User profile summary so far:\n{profile_summary}\n\n"
        f"The user just said: {user_input}\n\n"
        f"Update the profile as needed. Recommend 1–2 suitable vehicles based on what is known. "
        f"Then conclude with: 'Would you like to learn more about these vehicles or continue refining your preferences?'"
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a formal, professional vehicle advisor."},
            {"role": "user", "content": gpt_prompt}
        ]
    )

    reply = response.choices[0].message.content
    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")

    # Recommend based on current profile
    recs = recommend_vehicles(st.session_state.user_answers)
    st.session_state.last_recommendations = recs.to_dict(orient="records")
    st.session_state.awaiting_vehicle_detail = True
    st.rerun()

# --- Initial Greeting ---
if not st.session_state.chat_log:
    st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Welcome. I’m here to assist in selecting the optimal vehicle for your needs. Please begin by telling me your location or intended vehicle usage.")
    st.rerun()
