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
valid_brands = set(df_vehicle_advisor['Brand'].unique())

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

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
if "blocked_brands" not in st.session_state:
    st.session_state.blocked_brands = set()
if "preferred_brands" not in st.session_state:
    st.session_state.preferred_brands = set()
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

score_weights = {
    "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
    "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
    "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
    "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
    "Ownership Duration": 0.5, "Budget": 1.5, "Annual Mileage": 0.6, "Drive Type": 1.0
}

custom_repeat_prevention = set()

def recommend_vehicles(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()

    if st.session_state.blocked_brands:
        df = df[~df['Brand'].isin(st.session_state.blocked_brands)]
    if st.session_state.preferred_brands:
        df = df[df['Brand'].isin(st.session_state.preferred_brands)]

    budget_value = user_answers.get("Budget", "45000").replace("$", "").replace(",", "").lower().strip()
    try:
        if "k" in budget_value:
            user_budget = float(budget_value.replace("k", "")) * 1000
        else:
            user_budget = float(re.findall(r'\d+', budget_value)[0])
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

st.markdown("## 🚗 VehicleAdvisor Chat")

if st.button("🔄 Restart Profile"):
    for key in ["user_answers", "chat_log", "last_recommendations", "locked_keys", "final_recs_shown", "blocked_brands", "preferred_brands", "pending_question"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(f"<div style='font-family:sans-serif;'>{msg}</div>", unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Your reply:")
        submitted = st.form_submit_button("Send")

        if submitted and user_input:
            st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
            user_input_lower = user_input.lower()
            st.session_state.pending_question = None

            brand_matches = [b for b in valid_brands if b.lower() in user_input_lower]
            if "interested in" in user_input_lower or "like" in user_input_lower:
                for b in brand_matches:
                    st.session_state.preferred_brands.add(b)

            blocked = re.findall(r"(remove|block|exclude|not interested in)\s+([\w\s,&]+)", user_input_lower)
            unblocked = re.findall(r"(add|include|consider)\s+([\w\s,&]+)", user_input_lower)

            if blocked:
                for _, brands in blocked:
                    for brand in re.split(r"[,&]", brands):
                        b = brand.strip().title()
                        if b in valid_brands:
                            st.session_state.blocked_brands.add(b)
                            st.session_state.preferred_brands.discard(b)
                st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> Got it — I’ve removed these brands from future suggestions: {', '.join(st.session_state.blocked_brands)}.")

            if unblocked:
                for _, brands in unblocked:
                    for brand in re.split(r"[,&]", brands):
                        b = brand.strip().title()
                        if b in valid_brands:
                            st.session_state.blocked_brands.discard(b)
                            st.session_state.preferred_brands.add(b)
                st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> I’ve added these brands back into consideration: {', '.join(st.session_state.preferred_brands)}.")

            for field in score_weights:
                if f"change my {field.lower()}" in user_input_lower or f"update my {field.lower()}" in user_input_lower:
                    st.session_state.locked_keys.discard(field.lower())
                    st.session_state.user_answers.pop(field, None)
                    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> Got it — feel free to update your {field} preference now.")

            field_patterns = {
                "Budget": ["budget", "$", "k"],
                "Use Category": ["commute", "commuting", "daily driver", "everyday", "leisure", "commercial"],
                "Region": ["located in", "from", "live"],
                "Safety Priority": ["safety"],
                "Tech Features": ["tech", "infotainment", "dashboard"],
                "Yearly Income": ["income", "salary"],
                "Credit Score": ["credit score", "fico"],
                "Garage Access": ["garage", "parking"],
                "Eco-Conscious": ["eco", "green", "hybrid"],
                "Charging Access": ["charging", "plug"],
                "Neighborhood Type": ["neighborhood", "urban", "suburban", "rural"],
                "Towing Needs": ["towing", "haul"],
                "Car Size": ["compact", "midsize", "large", "car size"],
                "Ownership Recommendation": ["own", "lease", "rent"],
                "Employment Status": ["employment", "job", "work", "retired", "self-employed"],
                "Travel Frequency": ["travel", "trip", "fly"],
                "Ownership Duration": ["how long", "own for"],
                "Annual Mileage": ["miles per year", "annual mileage"],
                "Drive Type": ["awd", "fwd", "rwd", "rear wheel"]
            }

            for field, keywords in field_patterns.items():
                if field.lower() in st.session_state.locked_keys:
                    continue
                if any(kw in user_input_lower for kw in keywords):
                    match = re.search(r'(\d{1,5})', user_input_lower)
                    value = match.group(1) if match else user_input.title()
                    st.session_state.user_answers[field] = value
                    st.session_state.locked_keys.add(field.lower())

            for key in st.session_state.user_answers:
                st.session_state.locked_keys.add(key.lower())
                custom_repeat_prevention.add(key.lower())

            profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
            unlocked_questions = [k for k in score_weights if k.lower() not in st.session_state.locked_keys]

            gpt_prompt = f"""You are a car chatbot, that is tasked with helping a person or a car salesman find the best cars that fit the needs specified.
You will look into the vehicle data CSV and ask questions regarding the profile of the individual based on attributes of the cars to find out which car will best suit that individual.
These questions should be based on the score weights — some hold much higher weights than others because they are more important — but that doesn't mean you ignore the lower-weighted ones.

Once the user answers a question, HARD LOCK that information — NEVER ask for it again. For example, if they share their budget or employment status, that is FINAL. Do not re-ask it. Do not imply it wasn't given.

Only if the user clearly says something like "update my budget" or "change my credit score" should you allow the field to be modified.

Blocked brands (do not suggest unless user adds them back): {list(st.session_state.blocked_brands)}
Preferred brands (ONLY suggest from these if present): {list(st.session_state.preferred_brands)}

NEVER repeat or rephrase locked fields. If they’ve already answered Employment Status, DO NOT ask about it again.

After each question, mention 1–2 cars that could fit the individual's preferences so far, based on the latest answer and all prior locked values.

You should ask a total of 8–10 thoughtful, dynamic questions before recommending final vehicles.

Here’s what they’ve shared so far:
{profile_summary}

They just said: {user_input}

Locked preferences: {list(st.session_state.locked_keys)}
Remaining questions: {unlocked_questions}"""

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful vehicle advisor that never repeats questions once answered."},
                    {"role": "user", "content": gpt_prompt}
                ]
            )

            reply = response.choices[0].message.content
            st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
            st.session_state.pending_question = True
            st.rerun()

else:
    with st.form(key="initial_chat_form", clear_on_submit=True):
        user_input = st.text_input("Hey there! I’d love to help you find the perfect ride. What brings you in today?")
        submitted = st.form_submit_button("Start Chat")
        if submitted and user_input:
            st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
            st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Awesome! Let’s get started. What region are you located in?")
            st.rerun()

if len(st.session_state.locked_keys) >= 8 and not st.session_state.final_recs_shown and not st.session_state.pending_question:
    st.session_state.final_recs_shown = True
    final_recs = recommend_vehicles(st.session_state.user_answers, top_n=3)
    st.session_state.last_recommendations = final_recs
    st.session_state.chat_log.append("<b>VehicleAdvisor:</b> I’ve gathered enough information. Here are my top 3 car recommendations based on your preferences:")
    for idx, row in final_recs.iterrows():
        st.session_state.chat_log.append(
            f"<b>{idx+1}. {row['Brand']} {row['Model']} ({row['Model Year']})</b> – {row['MSRP Range']}"
        )
    st.session_state.chat_log.append("Would you like to restart and build a new profile, or see more cars that match your preferences?")
    st.rerun()

if st.session_state.final_recs_shown and not st.session_state.last_recommendations.empty:
    st.markdown("### 📊 Comparison of Recommended Vehicles")
    st.dataframe(st.session_state.last_recommendations[['Brand', 'Model', 'Model Year', 'MSRP Range', 'score']])
    full_export = st.session_state.last_recommendations.copy()
    for k, v in st.session_state.user_answers.items():
        full_export[k] = v
    csv = full_export.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Your Car Profile + Recommendations", csv, "car_recommendations.csv", "text/csv")
