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
valid_brands = set(df_vehicle_advisor['Brand'].unique())  # FIX: changed Make → Brand

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Initialize session state
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
    if st.session_state.blocked_brands:
        df = df[~df['Brand'].isin(st.session_state.blocked_brands)]

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
    for key in ["user_answers", "chat_log", "last_recommendations", "locked_keys", "final_recs_shown", "blocked_brands", "pending_question"]:
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
            st.session_state.pending_question = None  # Clear any old pending marker

            # Brand blocking/unblocking
            blocked = re.findall(r"(remove|block|exclude|not interested in)\s+([\w\s,&]+)", user_input_lower)
            unblocked = re.findall(r"(add|include|consider)\s+([\w\s,&]+)", user_input_lower)

            if blocked:
                for _, brands in blocked:
                    for brand in re.split(r"[,&]", brands):
                        b = brand.strip().title()
                        if b in valid_brands:
                            st.session_state.blocked_brands.add(b)
                st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> Got it — I’ve removed these brands from future suggestions: {', '.join(st.session_state.blocked_brands)}.")

            if unblocked:
                for _, brands in unblocked:
                    for brand in re.split(r"[,&]", brands):
                        b = brand.strip().title()
                        if b in valid_brands:
                            st.session_state.blocked_brands.discard(b)
                st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> Got it — I’ll consider those brands again from now on.")

            # Field updates
            for field in list(score_weights.keys()):
                if f"change my {field.lower()}" in user_input_lower or f"update my {field.lower()}" in user_input_lower:
                    st.session_state.locked_keys.discard(field.lower())
                    st.session_state.user_answers.pop(field, None)
                    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> Got it — feel free to update your {field} preference now.")

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
                        match = re.search(r'(\d{2,3}[,\d{3}]*)', user_input.replace(",", "")) if field in ["Budget", "Credit Score"] else None
                        value = f"${match.group(1)}" if match and field == "Budget" else match.group(1) if match else user_input.title()
                        st.session_state.user_answers[field] = value
                        st.session_state.locked_keys.add(field.lower())

            for k in st.session_state.user_answers:
                st.session_state.locked_keys.add(k.lower())
                custom_repeat_prevention.add(k.lower())

            profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
            unlocked_questions = [k for k in score_weights if k.lower() not in st.session_state.locked_keys]

            learn_more_prompt = """
If the user says 'Tell me more about [car]', give a detailed description from the dataset.
If the user hasn't said that, after recommending cars, you may occasionally say: "Would you like to learn more about any of these cars?"
If they say yes, respond with rich info about those cars. Then continue the profiling questions.
"""

            gpt_prompt = f"""You are a car chatbot, that is tasked with helping a person or a car salesman find the best cars that fit the needs specified.
You will look into the vehicle data CSV and ask questions regarding the profile of the individual based on attributes of the cars to find out which car will best suit that individual.
These questions should be based on the score weights — some hold much higher weights than others because they are more important — but that doesn't mean you ignore the lower-weighted ones.

Once the user answers a question, HARD LOCK that information — NEVER ask for it again. For example, if they share their budget, that is FINAL. Do not re-ask it. Do not imply it wasn't given.

Only if the user clearly says something like "update my budget" or "change my credit score" should you allow the field to be modified.

Blocked brands (do not suggest unless user adds them back): {list(st.session_state.blocked_brands)}

After each question, mention 1–2 cars that could fit the individual's preferences so far, based on the latest answer and all prior locked values.
You should ask a total of 8 to 10 thoughtful, dynamic questions before recommending the final vehicles that match best.

You can use charts to visually compare options and highlight matches. Your goal is to be as human and fluid as possible — make the interaction feel natural.
Wait for the user to respond before continuing. You must complete 8–10 total questions unless the user asks to skip ahead.
IMPORTANT: Do not repeat any questions, even if they are rephrased. For example, if the user already answered their "use category" or "budget," you must not ask it again in any form, including clarifying variations (e.g., "daily driver," "personal vs commercial," etc.). Once a preference is locked, it is FINAL unless the user explicitly asks to change it.

{learn_more_prompt}

Here’s what they’ve shared so far:
{profile_summary}

They just said: {user_input}

Locked preferences: {list(st.session_state.locked_keys)}
Remaining preference options to ask about: {unlocked_questions}

Start by responding conversationally. Acknowledge their latest message, then update their profile (only if relevant), recommend 1–2 cars, and ask the next best question. NEVER ask about anything that is already locked unless the user asked to change it.
Wait for the user to respond before continuing. You must complete 8–10 total questions unless the user asks to skip ahead."""

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You're a helpful car advisor that builds a user profile and recommends cars without repeating questions."},
                    {"role": "user", "content": gpt_prompt}
                ]
            )

            reply = response.choices[0].message.content
            st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
            st.session_state.pending_question = True  # A question was asked, wait before final rec
            st.rerun()

else:
    with st.form(key="initial_chat_form", clear_on_submit=True):
        user_input = st.text_input("Hey there! I’d love to help you find the perfect ride. What brings you in today?")
        submitted = st.form_submit_button("Start Chat")
        if submitted and user_input:
            st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
            st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Awesome! Let’s get started. Just to begin, what region are you located in?")
            st.rerun()

# Final rec trigger only if 8+ are locked and no question is pending
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
