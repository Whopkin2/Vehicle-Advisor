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

if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {}
if "recommendation_made" not in st.session_state:
    st.session_state.recommendation_made = False
if "intro_shown" not in st.session_state:
    st.session_state.intro_shown = False


def recommend_vehicle_dynamic(profile):
    df = df_vehicle_advisor.copy()
    try:
        user_budget = float(re.findall(r'\d+', profile.get("budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    weight_map = {
        "Credit Score": 2.0,
        "Yearly Income": 2.0,
        "MSRP Range": 2.0,
        "Region": 1.5,
        "Use Category": 1.5,
        "Vehicle Type": 1.5,
        "Fuel Type": 1.5,
        "Car Size": 1.5,
        "Garage Access": 1.5,
        "Eco-Conscious": 1.5,
        "Charging Access": 1.2,
        "Neighborhood Type": 1.2,
        "Towing Needs": 1.2,
        "Travel Frequency": 1.2,
        "Ownership Recommendation": 1.2,
        "Ownership Duration": 1.2,
        "Tech Features": 1.0,
        "Safety Priority": 1.0,
        "Employment Status": 1.0
    }

    def compute_weighted_score(row):
        score = 0.0
        row_text = str(row.to_dict()).lower()
        for key, value in profile.items():
            for col in df.columns:
                if str(value).lower() in str(row[col]).lower():
                    score += weight_map.get(col, 0.5)
        return score

    df['score'] = df.apply(compute_weighted_score, axis=1)
    df = df.sort_values(by='score', ascending=False)
    return df.head(3).reset_index(drop=True)


def gpt_vehicle_response(user_message):
    profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_profile.items()])
    prompt = (
        f"You are a helpful, friendly AI vehicle advisor helping a user pick the perfect car.\n"
        f"Here is what you've learned so far:\n{profile_summary}\n"
        f"User just said: {user_message}\n"
        f"If the user provides new profile info, don't re-ask it again.\n"
        f"Keep building the profile naturally, infer missing details, ask smart follow-ups.\n"
        f"When you have enough (budget, region, purpose, size/fuel preferences), return top 3 cars and why they fit.\n"
        f"Then offer comparison or to revise profile."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a smart, friendly vehicle advisor chatbot."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content


def reset_chat():
    st.session_state.chat_log = []
    st.session_state.user_profile = {}
    st.session_state.recommendation_made = False
    st.session_state.intro_shown = False
    st.experimental_rerun()

st.markdown("## 🚘 VehicleAdvisor Chatbot")

st.markdown("### 💬 Chat with VehicleAdvisor")

if not st.session_state.intro_shown:
    intro = "<b>VehicleAdvisor:</b> Hi! I'm here to help you find the perfect car. Let's get started. What region are you located in?"
    st.session_state.chat_log.append(intro)
    st.session_state.intro_shown = True

for message in st.session_state.chat_log:
    st.markdown(message, unsafe_allow_html=True)

with st.form(key="chat_form", clear_on_submit=True):
    user_query = st.text_input("You:")
    submitted = st.form_submit_button("Send")

if submitted and user_query:
    st.session_state.chat_log.append(f"<b>You:</b> {user_query}")

    if user_query.strip().lower() == "reset":
        reset_chat()

    keyword_map = {
        "region": ["region", "location", "state"],
        "budget": ["budget", "price", "cost"],
        "credit": ["credit score"],
        "salary": ["income", "salary"],
        "garage": ["garage"],
        "mileage": ["miles", "driving"],
        "eco": ["eco", "environment"],
        "hybrid": ["hybrid", "electric"],
        "features": ["feature", "gps", "leather", "safety"],
        "commute": ["commute", "use"],
        "suv": ["suv"],
        "sedan": ["sedan"]
    }
    for key, synonyms in keyword_map.items():
        if any(term in user_query.lower() for term in synonyms):
            st.session_state.user_profile[key] = user_query

    reply = gpt_vehicle_response(user_query)
    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")

    if not st.session_state.recommendation_made and len(st.session_state.user_profile) >= 4:
        top_vehicles = recommend_vehicle_dynamic(st.session_state.user_profile)
        st.session_state.chat_log.append("<br><b>✅ I've gathered enough to recommend your top 3 vehicles:</b>")
        for _, row in top_vehicles.iterrows():
            st.session_state.chat_log.append(f"- <b>{row['Brand']} {row['Model']} ({row['Model Year']})</b>: {row['MSRP Range']}")
        st.session_state.chat_log.append("<br>Would you like to compare these cars in a table or by features? Or would you like to change any preferences or start over?")
        st.session_state.recommendation_made = True

    st.rerun()
