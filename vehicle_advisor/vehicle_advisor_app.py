import streamlit as st
import pandas as pd
import openai
import requests
from io import StringIO

# 🚗 Load vehicle dataset from GitHub
@st.cache_data
def load_vehicle_data():
    url = "https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv"
    response = requests.get(url)
    if response.status_code == 200:
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)
        df['Brand'] = df['Brand'].str.lower()
        df['Model'] = df['Model'].str.lower()
        return df
    else:
        st.error("Failed to load vehicle data.")
        return pd.DataFrame()

df = load_vehicle_data()

# 📚 Setup OpenAI (assuming your key is in secrets)
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# 🛠 Streamlit page
st.title("🚗 Simple Vehicle Advisor")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Function to recommend cars
def recommend_cars(preference):
    filtered = df.copy()

    # Simple filters based on keywords
    if "suv" in preference.lower():
        filtered = filtered[filtered["Size"].str.contains("SUV", case=False, na=False)]
    if "sedan" in preference.lower():
        filtered = filtered[filtered["Size"].str.contains("Sedan", case=False, na=False)]
    if "truck" in preference.lower():
        filtered = filtered[filtered["Size"].str.contains("Truck", case=False, na=False)]
    if "electric" in preference.lower():
        filtered = filtered[filtered["Fuel"].str.contains("Electric", case=False, na=False)]
    if "hybrid" in preference.lower():
        filtered = filtered[filtered["Fuel"].str.contains("Hybrid", case=False, na=False)]
    if "new" in preference.lower():
        filtered = filtered[filtered["Condition"].str.contains("New", case=False, na=False)]
    if "used" in preference.lower():
        filtered = filtered[filtered["Condition"].str.contains("Used", case=False, na=False)]

    if filtered.empty:
        return "Sorry, I couldn't find any vehicles matching your preference."

    top_cars = filtered.sample(n=min(2, len(filtered)))  # Pick 2 random cars matching
    car_list = "\n".join(f"- {row['Brand'].title()} {row['Model'].title()} (${row['MSRP Min']})" for _, row in top_cars.iterrows())

    prompt = (
        f"Based on the user's preference '{preference}', recommend and explain why these vehicles are good choices:\n"
        f"{car_list}\n"
        f"Make it friendly, specific to their needs, and 1–2 sentences per car."
    )

    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    return stream

# Accept user input
if prompt := st.chat_input("Tell me what you're looking for in a car..."):
    # Save user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate car recommendations
    with st.chat_message("assistant"):
        response = st.write_stream(recommend_cars(prompt))

    # Save assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})
