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

questions = [
    ("Region", "Which region(s) are you in?"),
    ("Use Category", "What will you primarily use the vehicle for?"),
    ("Yearly Income", "What is your yearly income?"),
    ("Credit Score", "What is your credit score?"),
    ("Garage Access", "Do you have garage access?"),
    ("Eco-Conscious", "Are you eco-conscious?"),
    ("Charging Access", "Do you have charging access?"),
    ("Neighborhood Type", "What type of neighborhood do you live in? (e.g., city, suburbs, rural)"),
    ("Towing Needs", "Do you have towing needs?"),
    ("Safety Priority", "How important is safety to you?"),
    ("Tech Features", "What level of tech features do you prefer?"),
    ("Car Size", "What car size do you prefer?"),
    ("Ownership Recommendation", "Are you looking to buy, lease, or rent?"),
    ("Employment Status", "What is your employment status?"),
    ("Travel Frequency", "How often do you travel with the car?"),
    ("Annual Mileage", "How many miles will you drive per year?"),
    ("Ownership Duration", "How long do you plan to own or use the vehicle?"),
    ("Budget", "What’s your budget or price range for the vehicle?")
]

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = False
if "profile_complete" not in st.session_state:
    st.session_state.profile_complete = False
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

def recommend_vehicle_conversational(user_answers, top_n=3):
    df = df_vehicle_advisor.copy()

    try:
        user_budget = float(re.findall(r'\d+', user_answers.get("Budget", "45000").replace("$", "").replace(",", "").strip())[0])
    except:
        user_budget = 45000

    df = df[df['MSRP Min'].fillna(999999) <= user_budget * 1.2]

    score_weights = {
        "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
        "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
        "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
        "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
        "Ownership Duration": 0.5, "Budget": 2.0, "Annual Mileage": 0.6
    }

    def compute_score(row):
        return sum(
            weight for key, weight in score_weights.items()
            if str(user_answers.get(key, "")).lower() in str(row.get(key, "")).lower()
        )

    df['score'] = df.apply(compute_score, axis=1)
    df = df.sort_values(by=['score', 'Model Year'], ascending=[False, False])
    return df.head(top_n).reset_index(drop=True)

def generate_summary_with_gpt(row, user_answers):
    profile = "\n".join([f"{k}: {v}" for k, v in user_answers.items()])
    prompt = (
        f"User profile:\n{profile}\n"
        f"Recommend the {row['Brand']} {row['Model']} ({row['Model Year']}) based on this profile."
        f" Explain why it's a good match. Include budget, size, fuel, tech, towing, mileage, and resale." 
        f" Include MSRP: {row['MSRP Range']}."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful vehicle advisor."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def feedback_response_after_input(key, value):
    profile = {**st.session_state.user_answers, key: value}
    weight = {
        "Region": 1.0, "Use Category": 1.0, "Yearly Income": 0.6, "Credit Score": 0.6,
        "Garage Access": 0.5, "Eco-Conscious": 0.8, "Charging Access": 0.8, "Neighborhood Type": 0.9,
        "Towing Needs": 0.6, "Safety Priority": 0.9, "Tech Features": 0.8, "Car Size": 0.7,
        "Ownership Recommendation": 0.7, "Employment Status": 0.6, "Travel Frequency": 0.5,
        "Ownership Duration": 0.5, "Budget": 2.0, "Annual Mileage": 0.6
    }.get(key, 0.5)

    prompt = (
        f"User just answered: {key} = {value}\n"
        f"Given the full profile so far: {profile}\n"
        f"Provide 2-3 example vehicles that might fit based on this new input."
        f" Also explain how influential this input is on scoring (weight = {weight})."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful vehicle advisor who provides real-time suggestions based on user profile and scoring weights."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def render_profile_summary():
    st.markdown("### 🧾 Your Profile Summary")
    st.table(pd.DataFrame.from_dict(st.session_state.user_answers, orient='index', columns=["Your Answer"]))

st.markdown("## 🚘 VehicleAdvisor Chatbot")

if not st.session_state.profile_complete:
    st.markdown("Welcome! Let's find your ideal vehicle. Answer a few quick questions:")
    for key, question in questions:
        if key not in st.session_state.user_answers:
            if key == "Tech Features":
                user_input = st.selectbox(question, ["Low", "Medium", "High"])
            elif key == "Car Size":
                user_input = st.selectbox(question, ["Small", "Midsize", "Full-Size", "SUV", "Truck"])
            elif key == "Use Category":
                user_input = st.selectbox(question, ["Commuting", "Leisure", "Work", "Family", "Off-road", "Towing"])
            elif key == "Neighborhood Type":
                user_input = st.selectbox(question, ["City", "Suburbs", "Rural"])
            else:
                user_input = st.text_input(question)

            if st.button("Submit Answer"):
                st.session_state.user_answers[key] = user_input
                feedback = feedback_response_after_input(key, user_input)
                st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {feedback}")
                st.rerun()
            break
    else:
        st.session_state.profile_complete = True
        st.rerun()

elif not st.session_state.chat_mode:
    st.success("✅ Profile complete! Generating recommendations...")
    render_profile_summary()
    recommendations = recommend_vehicle_conversational(st.session_state.user_answers)
    st.markdown("### 🚗 Top Vehicle Matches")
    for _, row in recommendations.iterrows():
        st.text(f"{row['Brand']} {row['Model']} ({row['Model Year']})")
        st.text(generate_summary_with_gpt(row, st.session_state.user_answers))
    st.markdown("---")
    st.markdown("Want to make changes or ask questions?")
    if st.button("💬 Enter Chat Mode"):
        st.session_state.chat_mode = True
        st.rerun()

else:
    st.markdown("### 💬 Chat with VehicleAdvisor")
    render_profile_summary()
    for message in st.session_state.chat_log:
        st.markdown(message, unsafe_allow_html=True)

    user_query = st.text_input("Ask a question, change preferences, or say what you want:")
    if st.button("Send") and user_query:
        st.session_state.chat_log.append(f"<b>You:</b> {user_query}")
        profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])

        gpt_prompt = (
            f"Current user profile:\n{profile_summary}\n"
            f"User message: {user_query}\n"
            f"Update the user profile if needed and recommend 3 new vehicles."
        )

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a smart vehicle assistant who updates profiles and reruns recommendations."},
                {"role": "user", "content": gpt_prompt}
            ]
        )

        reply = response.choices[0].message.content
        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
        st.rerun()
