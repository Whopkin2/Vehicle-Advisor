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
if "last_recommendations" not in st.session_state:
    st.session_state.last_recommendations = pd.DataFrame()
if "locked_keys" not in st.session_state:
    st.session_state.locked_keys = set()

st.markdown("## 🚗 VehicleAdvisor Chat")

if st.session_state.chat_log:
    for msg in st.session_state.chat_log:
        st.markdown(msg, unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Your reply:")
        submitted = st.form_submit_button("Send")

    if submitted and user_input:
        st.session_state.chat_log.append(f"<b>You:</b> {user_input}")

        if "learn more about those vehicles" in user_input.lower():
            if not st.session_state.last_recommendations.empty:
                reply = "<br><br>".join(
                    [
                        f"<b>{row['Brand']} {row['Model']} ({row['Model Year']})</b><br>MSRP Range: {row['MSRP Range']}<br>{row.get('Description', 'No additional description available.')}"
                        for _, row in st.session_state.last_recommendations.iterrows()
                    ]
                )
            else:
                reply = "I haven't recommended any vehicles yet. Tell me what you're looking for first!"

        elif "continue refining" in user_input.lower():
            profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
            gpt_prompt = (
                f"You're a vehicle advisor. Here's what the user has shared so far:\n{profile_summary}\n\n"
                f"User just said: {user_input}\n"
                f"Ask the next best profiling question to refine their vehicle needs. Do NOT repeat anything the user already answered unless they ask to change it. Locked preferences: {list(st.session_state.locked_keys)}."
            )
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful vehicle advisor building a user profile through natural conversation."},
                    {"role": "user", "content": gpt_prompt}
                ]
            )
            reply = response.choices[0].message.content

        else:
            profile_summary = "\n".join([f"{k}: {v}" for k, v in st.session_state.user_answers.items()])
            gpt_prompt = (
                f"You're a vehicle advisor. Your goal is to chat casually and build the user's profile.\n\n"
                f"So far, they've shared:\n{profile_summary}\n\n"
                f"User just said: {user_input}\n\n"
                f"Update their profile if you learn something new and LOCK that information so you never ask for it again unless the user says they want to change it. Do NOT ask again about: {list(st.session_state.locked_keys)}."
                f"Suggest a car if you're ready, or ask one question to learn more about UNLOCKED topics only."
            )
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a friendly car salesman helping users choose a vehicle based on their profile."},
                    {"role": "user", "content": gpt_prompt}
                ]
            )
            reply = response.choices[0].message.content

            # Update locked keys by parsing profile-related additions from GPT response (stub for now)
            for key in st.session_state.user_answers:
                st.session_state.locked_keys.add(key.lower())

            st.session_state.last_recommendations = recommend_vehicles(st.session_state.user_answers)

        st.session_state.chat_log.append(f"<b>VehicleAdvisor:</b> {reply}")
        st.rerun()
else:
    st.session_state.chat_log.append("<b>VehicleAdvisor:</b> Hey there! I’d love to help you find the perfect ride. Just tell me what you're looking for or where you're from, and we'll go from there!")
    st.rerun()
