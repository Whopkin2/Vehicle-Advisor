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

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "awaiting_vehicle_detail" not in st.session_state:
    st.session_state.awaiting_vehicle_detail = False
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = []
if "refine_requested" not in st.session_state:
    st.session_state.refine_requested = False

# --- Extract user intent from input ---
def extract_profile_info(user_input):
    text = user_input.lower()
    if "commute" in text:
        st.session_state.user_answers["Use Category"] = "Daily Commute"
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
    if "jersey" in text:
        st.session_state.user_answers["Region"] = "New Jersey"

    if "refine" in text or "more info" in text or "continue" in text:
        st.session_state.refine_requested = True

# --- Recommend cars based on filtered profile ---
def recommend_vehicles(user_answers, top_n=2):
    df = df_vehicle_advisor.copy()
    try:
        user_budget = float(re.findall(r'\d+', user_answers.get("Budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    score_weights = {
        "Region": 1.0, "Use Category": 1.0, "Fuel Preference": 1.0, "Brand Preference": 1.0, "Condition": 1.0,
        "Budget": 2.0
    }

    def compute_score(row):
        return sum(
            weight for key, weight in score_weights.items()
            if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower()
        )

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

# --- UI ---
st.markdown("## VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(msg, unsafe_allow_html=True)

with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Your reply:")
    submitted = st.form_submit_button("Send")

if submitted and user_input:
    st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
    extract_profile_info(user_input)

    if st.session_state.awaiting_vehicle_detail and "learn" in user_input.lower():
        details = ""
        for car in st.session_state.last_recommendations:
            details += f"**{car['Brand']} {car['Model']} ({car['Model Year']})**\n"
            details += f"- MSRP Range: {car.get('MSRP Range', 'N/A')}\n"
            details += f"- Size: {car.get('Car Size', 'N/A')}\n"
            details += f"- Safety: {car.get('Safety Priority', 'N/A')}\n"
            details += f"- Tech Features: {car.get('Tech Features', 'N/A')}\n\n"
        details += "Would you like to continue refining your preferences?"
        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b><br>{details}")
        st.session_state.awaiting_vehicle_detail = False
        st.rerun()

    if st.session_state.refine_requested:
        st.session_state.refine_requested = False
        st.session_state.awaiting_vehicle_detail = False
        gpt_prompt = (
            f"You are a professional vehicle advisor. Continue asking follow-up questions to gather missing preferences.\n"
            f"Avoid asking what has already been answered.\n\n"
            f"Current Profile:\n" + "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()]) + "\n\n"
            f"User just said: {user_input}\n"
            f"Ask one specific follow-up question to refine their needs further."
        )
    else:
        profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
        answered_keys = list(st.session_state.user_answers.keys())
        answered_list = ", ".join(answered_keys) if answered_keys else "None yet"

        gpt_prompt = (
            f"You are a professional vehicle advisor. Do not ask questions already answered: {answered_list}.\n"
            f"User profile:\n{profile_summary}\n\n"
            f"User input: {user_input}\n\n"
            f"Update profile if needed. Recommend 1-2 vehicles with a sentence each.\n"
            f"Then ask: 'Would you like to learn more about these vehicles or continue refining your preferences?'"
        )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a formal and helpful vehicle advisor."},
            {"role": "user", "content": gpt_prompt}
        ]
    )
    reply = response.choices[0].message.content
    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")

    vehicle_names = re.findall(r"\d\.\s*(.*?):", reply)
    matched_vehicles = []
    for name in vehicle_names:
        match = df_vehicle_advisor[df_vehicle_advisor['Model'].str.contains(name, case=False, na=False)]
        if not match.empty:
            matched_vehicles.append(match.iloc[0].to_dict())

    st.session_state.last_recommendations = matched_vehicles
    st.session_state.awaiting_vehicle_detail = True
    st.rerun()

if not st.session_state.chat_log:
    st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Welcome. Please tell me your location or intended vehicle usage.")
    st.rerun()

# --- Sidebar Profile ---
with st.sidebar:
    st.markdown("### Your Vehicle Preferences")
    if st.session_state.user_answers:
        for key, val in st.session_state.user_answers.items():
            st.markdown(f"**{key}**: {val}")
    else:
        st.markdown("_No preferences collected yet._")
