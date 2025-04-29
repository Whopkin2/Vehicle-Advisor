import streamlit as st
import pandas as pd
import openai

# Initialize OpenAI Client
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🚗 Vehicle Advisor — Smart Step-by-Step with GPT")

@st.cache_data
def load_data():
    return pd.read_csv("https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv")

df = load_data()

# Valid values
vehicle_types = ['Crossover', 'Hatchback', 'SUV', 'Sedan', 'Sports Car', 'Truck']
brands = ['Acura', 'Alfa Romeo', 'Audi', 'BMW', 'Cadillac', 'Chevrolet', 'Ferrari', 'Ford', 'GMC', 'Genesis',
          'Honda', 'Hyundai', 'Infiniti', 'Jaguar', 'Jeep', 'Kia', 'Lexus', 'Lucid', 'Mazda', 'Mercedes-Benz',
          'Mini', 'Nissan', 'Porsche', 'Ram', 'Rivian', 'Subaru', 'Tesla', 'Toyota', 'Volkswagen', 'Volvo']
fuel_types = ['Electric', 'Gas', 'Hybrid', 'Plug-in Hybrid']
regions = ['All Regions', 'Mid-West', 'North East', 'North West', 'South East', 'South West', 'West']
credit_scores = ['Excellent (800+)', 'Fair (580-669)', 'Good (670-739)', 'Very Good (740-799)']
employment_statuses = ['Full-time', 'Part-time', 'Retired', 'Student']
garage_access_options = ['Yes', 'No']
ownership_recommendations = ['Buy', 'Lease', 'Rent']
income_brackets = ['<25k', '25k-50k', '50k-100k', '100k-150k', '150k+']

# Helper functions
def validated_text_input(label, options):
    st.markdown(f"**Options:** {', '.join(options)}")
    value = st.text_input(label)
    if value:
        value_clean = value.strip()
        if value_clean not in options:
            st.error("❌ Invalid input. Please pick from options exactly.")
            st.stop()
        return value_clean
    else:
        st.stop()

def ask_gpt_about(field, value):
    prompt = f"Explain briefly in 2 sentences why selecting '{value}' for {field} could be important when choosing a vehicle."
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=100
    )
    return response.choices[0].message.content.strip()

# Session state setup
if "step" not in st.session_state:
    st.session_state.step = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}

# Step-by-step questioning
questions = [
    ("Vehicle Type", vehicle_types),
    ("Region", regions),
    ("Preferred Brands", brands),
    ("Fuel Type", fuel_types),
    ("Employment Status", employment_statuses),
    ("Credit Score", credit_scores),
    ("Garage Access", garage_access_options),
    ("Ownership Recommendation", ownership_recommendations),
    ("Yearly Income", income_brackets)
]

field_mapping = {
    "Vehicle Type": "Vehicle Type",
    "Region": "Region",
    "Preferred Brands": "Brand",
    "Fuel Type": "Fuel Type",
    "Employment Status": "Employment Status",
    "Credit Score": "Credit Score",
    "Garage Access": "Garage Access",
    "Ownership Recommendation": "Ownership Recommendation",
    "Yearly Income": "Yearly Income"
}

# Go through questions one-by-one
if st.session_state.step < len(questions):
    field_name, options = questions[st.session_state.step]
    user_answer = validated_text_input(f"✍ Enter your {field_name}:", options)
    st.session_state.answers[field_name] = user_answer

    # GPT explanation
    gpt_explanation = ask_gpt_about(field_name, user_answer)
    st.markdown(f"🧠 **GPT Insight:** {gpt_explanation}")

    # Move to next
    st.session_state.step += 1
    st.stop()

# After all answers are collected
else:
    st.success("✅ All answers collected. Finding your best matches...")

    # Filtering based on collected answers
    filtered = df.copy()

    if "Vehicle Type" in st.session_state.answers:
        filtered = filtered[filtered['Vehicle Type'] == st.session_state.answers["Vehicle Type"]]

    if "Region" in st.session_state.answers:
        filtered = filtered[filtered['Region'].str.contains(st.session_state.answers["Region"], na=False)]

    if "Preferred Brands" in st.session_state.answers:
        selected_brand = st.session_state.answers["Preferred Brands"]
        filtered = filtered[filtered['Brand'] == selected_brand]

    if "Fuel Type" in st.session_state.answers:
        filtered = filtered[filtered['Fuel Type'].str.lower() == st.session_state.answers["Fuel Type"].lower()]

    if "Employment Status" in st.session_state.answers:
        filtered = filtered[filtered['Employment Status'] == st.session_state.answers["Employment Status"]]

    if "Credit Score" in st.session_state.answers:
        filtered = filtered[filtered['Credit Score'] == st.session_state.answers["Credit Score"]]

    if "Garage Access" in st.session_state.answers:
        filtered = filtered[filtered['Garage Access'] == st.session_state.answers["Garage Access"]]

    if "Ownership Recommendation" in st.session_state.answers:
        filtered = filtered[filtered['Ownership Recommendation'] == st.session_state.answers["Ownership Recommendation"]]

    if "Yearly Income" in st.session_state.answers:
        filtered = filtered[filtered['Yearly Income'] == st.session_state.answers["Yearly Income"]]

    # Show results
    if not filtered.empty:
        st.dataframe(filtered)
    else:
        st.warning("❌ No matching vehicles found based on your criteria.")

# Restart option
if st.button("🔄 Restart"):
    st.session_state.step = 0
    st.session_state.answers = {}
    st.rerun()
