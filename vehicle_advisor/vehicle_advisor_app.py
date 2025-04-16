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

# Setup API
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Session state
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = pd.DataFrame()
if "locked_keys" not in st.session_state:
    st.session_state.locked_keys = set()
if "final_recs_shown" not in st.session_state:
    st.session_state.final_recs_shown = False

score_weights = {
    "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
    "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
    "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
    "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
    "Ownership Duration": 0.5, "Budget": 1.5, "Annual Mileage": 0.6, "Drive Type": 1.0
}

custom_repeat_prevention = set()

field_patterns = {
    "Budget": ["budget", "$", "k"],
    "Use Category": ["commute", "commuting", "daily driver", "everyday", "leisure"],
    "Region": ["located in", "from", "live"],
    "Safety Priority": ["safety"],
    "Tech Features": ["tech", "infotainment", "camera"],
    "Yearly Income": ["income", "salary", "make per year"],
    "Credit Score": ["credit score", "fico"],
    "Garage Access": ["garage", "parking"],
    "Eco-Conscious": ["eco", "environment", "green", "hybrid", "ev"],
    "Charging Access": ["charging", "charger", "plug in"],
    "Neighborhood Type": ["neighborhood", "urban", "suburban", "rural"],
    "Towing Needs": ["towing", "haul", "tow"],
    "Car Size": ["car size", "compact", "midsize", "full size"],
    "Ownership Recommendation": ["own", "lease", "rent", "buy"],
    "Employment Status": ["job", "employment", "work"],
    "Travel Frequency": ["travel", "trip", "fly", "frequent"],
    "Ownership Duration": ["how long", "keep", "own for"],
    "Annual Mileage": ["miles per year", "annual mileage", "drive per year"],
    "Drive Type": ["awd", "fwd", "rwd", "4wd", "rear wheel", "front wheel"]
}

def recommend_vehicles(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()
    try:
        budget_value = user_answers.get("Budget", "45000")
        user_budget = float(re.findall(r'\d+', budget_value.replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    def compute_score(row):
        return sum(
            weight for key, weight in score_weights.items()
            if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower()
        )

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

# --- UI HEADER ---
st.markdown("## 🚗 VehicleAdvisor Chat")

# Restart button
if st.button("🔄 Restart Profile"):
    for key in ["user_answers", "chat_log", "last_recommendations", "locked_keys", "final_recs_shown"]:
        if key in st.session_state:
            del st.session_state[key]
    st.experimental_rerun()

# Chat log display
if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(f"<div style='font-family:sans-serif;'>{msg}</div>", unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Your reply:")
        submitted = st.form_submit_button("Send")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
        user_input_lower = user_input.lower()

        for field in list(score_weights.keys()):
            if f"change my {field.lower()}" in user_input_lower or f"update my {field.lower()}" in user_input_lower:
                st.session_state.locked_keys.discard(field.lower())
                st.session_state.user_answers.pop(field, None)
                st.session_state.chat_log.append(
                    f"<b>VehicleAdvisor:</b> Got it — feel free to update your {field} preference now."
                )

        for field, keywords in field_patterns.items():
            if field.lower() in st.session_state.locked_keys or field.lower() in custom_repeat_prevention:
                continue
            if any(kw in user_input_lower for kw in keywords):
                if field in ["Safety Priority", "Tech Features", "Eco-Conscious"]:
                    match = re.search(r'(\d{1,2})', user_input_lower)
                    if match:
                        st.session_state.user_answers[field] = match.group(1)
                        st.session_state.locked_keys.add(field.lower())
                else:
                    match = re.search(r'(\d{2,3}[,\d{3}]*)', user_input.replace(",", "")) if field == "Budget" else None
                    value = f"${match.group(1)}" if match else user_input.title()
                    st.session_state.user_answers[field] = value
                    st.session_state.locked_keys.add(field.lower())

        for key in st.session_state.user_answers:
            st.session_state.locked_keys.add(key.lower())
            custom_repeat_prevention.add(key.lower())

        profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
        unlocked_questions = [k for k in score_weights if k.lower() not in st.session_state.locked_keys]

        gpt_prompt = f"""
You are a car advisor chatbot. You’re helping someone find the perfect vehicle by asking strategic questions based on the most important scoring factors.

- NEVER ask about anything already in the locked list: {list(st.session_state.locked_keys)}
- Only ask questions from this list: {unlocked_questions}

Here’s what they’ve shared:
{profile_summary}

User just said: {user_input}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a helpful car advisor that builds a user profile and recommends cars without repeating questions."},
                {"role": "user", "content": gpt_prompt}
            ]
        )

        reply = response.choices[0].message.content
        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")

        # ✅ Final recommendation logic block
        if len(st.session_state.locked_keys) >= 8 and not st.session_state.final_recs_shown:
            st.session_state.final_recs_shown = True
            final_recs = recomend_vehicles(st.session_state.user_answers, top_n=3)
            st.session_state.last_recommendations = final_recs
            st.session_state.chat_log.append("<b>VehicleAdvisor:</b> I’ve gathered enough information. Here are my top 3 car recommendations based on your preferences:")
            for idx, row in final_recs.iterrows():
                st.session_state.chat_log.append(
                    f"<b>{idx+1}. {row['Make']} {row['Model']} ({row['Model Year']})</b> – {row['MSRP Range']}"
                )
            st.session_state.chat_log.append("Would you like to restart and build a new profile, or see more cars that match your preferences?")
        st.rerun()

# Initial message
else:
    with st.form(key="initial_chat_form", clear_on_submit=True):
        user_input = st.text_input("Hey there! I’d love to help you find the perfect ride. What brings you in today?")
        submitted = st.form_submit_button("Start Chat")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
        st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Awesome! Let’s get started. Just to begin, what region are you located in?")
        st.rerun()

# ✅ Optional: Show table and download link if final recs shown
if st.session_state.final_recs_shown and not st.session_state.last_recommendations.empty:
    st.markdown("### 📊 Comparison of Recommended Vehicles")
    st.dataframe(st.session_state.last_recommendations[['Make', 'Model', 'Model Year', 'MSRP Range', 'score']])

    # Export
    full_export = st.session_state.last_recommendations.copy()
    for k, v in st.session_state.user_answers.items():
        full_export[k] = v
    csv = full_export.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Your Car Profile + Recommendations", csv, "car_recommendations.csv", "text/csv")
