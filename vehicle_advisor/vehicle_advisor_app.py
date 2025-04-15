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

# OpenAI setup
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai.api_key)

# Session state setup
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = pd.DataFrame()
if "locked_keys" not in st.session_state:
    st.session_state.locked_keys = set()
if "vehicle_names_mentioned" not in st.session_state:
    st.session_state.vehicle_names_mentioned = []
if "awaiting_answer" not in st.session_state:
    st.session_state.awaiting_answer = False
if "considered_vehicles" not in st.session_state:
    st.session_state.considered_vehicles = []
if "blocked_brands" not in st.session_state:
    st.session_state.blocked_brands = set()
if "final_recommendation_given" not in st.session_state:
    st.session_state.final_recommendation_given = False
if "user_ended_convo" not in st.session_state:
    st.session_state.user_ended_convo = False
if "asked_keys" not in st.session_state:
    st.session_state.asked_keys = set()

score_weights = {
    "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
    "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
    "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
    "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
    "Ownership Duration": 0.5, "Budget": 2.0, "Annual Mileage": 0.6
}


def recommend_vehicles(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()
    try:
        user_budget = float(re.findall(r'\d+', user_answers.get("Budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000
    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    for brand in st.session_state.blocked_brands:
        df = df[~df['Brand'].str.lower().str.contains(brand.lower())]

    def compute_score(row):
        return sum(
            weight for key, weight in score_weights.items()
            if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower()
        )

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)


st.markdown("""
    <style>
    * { font-family: Arial, sans-serif; }
    </style>
""", unsafe_allow_html=True)

st.markdown("## 🚗 VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(msg, unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Your reply:")
        submitted = st.form_submit_button("Send")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")

        if user_input.lower() in ["restart", "start over"]:
            for key in st.session_state.keys():
                del st.session_state[key]
            st.experimental_rerun()

        budget_match = re.search(r"(?:budget\s*(?:is|to|around|about)?\s*\$?)(\d{2,6})", user_input.lower())
        if budget_match:
            new_budget = budget_match.group(1)
            st.session_state.user_answers["Budget"] = new_budget
            st.session_state.locked_keys.add("budget")
            st.session_state.final_recommendation_given = False
            st.session_state.chat_log.append(f"<i>Updated your budget to ${new_budget}.</i>")
            st.rerun()

        for model in st.session_state.considered_vehicles:
            if f"remove {model.lower()}" in user_input.lower():
                st.session_state.considered_vehicles.remove(model)
                st.session_state.chat_log.append(f"<i>Removed {model} from consideration.</i>")

        for brand in df_vehicle_advisor['Brand'].unique():
            if f"no more {brand.lower()}" in user_input.lower() or f"block {brand.lower()}" in user_input.lower():
                st.session_state.blocked_brands.add(brand)
                st.session_state.chat_log.append(f"<i>Blocked {brand} from future recommendations.</i>")

        if "more options" in user_input.lower():
            st.session_state.final_recommendation_given = False
            st.rerun()

        if "end conversation" in user_input.lower():
            st.session_state.user_ended_convo = True

        for key in score_weights:
            if key.lower() in user_input.lower():
                st.session_state.user_answers[key] = user_input
                st.session_state.locked_keys.add(key.lower())

        if not st.session_state.final_recommendation_given and len(st.session_state.locked_keys) >= 5:
            top_3 = recommend_vehicles(st.session_state.user_answers, top_n=3)
            car_names = top_3['Model'].tolist()
            profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
            explanation_prompt = f"Based on the following user profile:\n{profile_summary}\nExplain why these 3 cars are a perfect fit: {', '.join(car_names)}"
            explanation = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a car advisor."},
                    {"role": "user", "content": explanation_prompt}
                ]
            ).choices[0].message.content
            st.session_state.chat_log.append("<b>VehicleAdvisor:</b> I’ve gathered enough information to recommend the best matches for you. Here are my top 3 car suggestions:")
            for car in car_names:
                st.session_state.chat_log.append(f"<b>• {car}</b>")
            st.session_state.chat_log.append(f"<b>Why these cars?</b> {explanation}")
            st.session_state.chat_log.append("<b>Would you like more options, or are you happy with these? You can also type 'end conversation' to wrap up.</b>")
            st.session_state.final_recommendation_given = True
            st.rerun()

        if not st.session_state.user_ended_convo:
            unanswered = [k for k, _ in sorted(score_weights.items(), key=lambda item: -item[1]) if k.lower() not in st.session_state.locked_keys and k.lower() not in st.session_state.asked_keys]
            if unanswered:
    next_q = unanswered[0]
    natural_prompt = f"The user has not provided information about their {next_q}. Ask a casual, conversational follow-up to learn this detail. Be warm, friendly, and sound like you're building a connection."
    natural_response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful, casual, and conversational car advisor trying to get to know the user better to help them find the right car."},
            {"role": "user", "content": natural_prompt}
        ]
    ).choices[0].message.content
    st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {natural_response}")
    st.session_state.asked_keys.add(next_q.lower())
    st.rerun()

            else:
                profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
                gpt_prompt = f"You are a car advisor. Here’s the user's profile:\n{profile_summary}\nUser just said: \"{user_input}\". Reply naturally. Track mentioned cars in: {st.session_state.considered_vehicles}. Avoid blocked brands: {st.session_state.blocked_brands}."
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful car advisor."},
                        {"role": "user", "content": gpt_prompt}
                    ]
                )
                reply = response.choices[0].message.content
                st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
                for name in df_vehicle_advisor['Model'].unique():
                    if name.lower() in reply.lower() and name not in st.session_state.considered_vehicles:
                        st.session_state.considered_vehicles.append(name)
                st.session_state.last_recommendations = recommend_vehicles(st.session_state.user_answers)
                st.rerun()

else:
    with st.form(key="initial_chat_form", clear_on_submit=True):
        user_input = st.text_input("Hey there! I’d love to help you find the perfect ride. What brings you in today?")
        submitted = st.form_submit_button("Start Chat")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")
        st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Awesome! Let’s get started. Just to begin, what region are you located in?")
        st.session_state.asked_keys.add("region")
        st.rerun()
