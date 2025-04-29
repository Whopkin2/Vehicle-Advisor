import streamlit as st
import pandas as pd
import openai

# Initialize OpenAI Client
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🚗 Vehicle Advisor — Real-Time Smart Filtering with GPT")

@st.cache_data
def load_data():
    return pd.read_csv("https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv")

df = load_data()

# Valid values (UPDATED: Remove "All Regions")
vehicle_types = ['Crossover', 'Hatchback', 'SUV', 'Sedan', 'Sports Car', 'Truck']
brands = ['Acura', 'Alfa Romeo', 'Audi', 'BMW', 'Cadillac', 'Chevrolet', 'Ferrari', 'Ford', 'GMC', 'Genesis',
          'Honda', 'Hyundai', 'Infiniti', 'Jaguar', 'Jeep', 'Kia', 'Lexus', 'Lucid', 'Mazda', 'Mercedes-Benz',
          'Mini', 'Nissan', 'Porsche', 'Ram', 'Rivian', 'Subaru', 'Tesla', 'Toyota', 'Volkswagen', 'Volvo']
fuel_types = ['Electric', 'Gas', 'Hybrid', 'Plug-in Hybrid']
regions = ['Mid-West', 'North East', 'North West', 'South East', 'South West', 'West']  # Removed "All Regions"
credit_scores = ['Excellent (800+)', 'Fair (580-669)', 'Good (670-739)', 'Very Good (740-799)']
employment_statuses = ['Full-time', 'Part-time', 'Retired', 'Student']
garage_access_options = ['Yes', 'No']
ownership_recommendations = ['Buy', 'Lease', 'Rent']
income_brackets = ['<25k', '25k-50k', '50k-100k', '100k-150k', '150k+']

# Question flow
questions = [
    ("Vehicle Type", vehicle_types),
    ("Region", regions),
    ("Preferred Brand", brands),
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
    "Preferred Brand": "Brand",
    "Fuel Type": "Fuel Type",
    "Employment Status": "Employment Status",
    "Credit Score": "Credit Score",
    "Garage Access": "Garage Access",
    "Ownership Recommendation": "Ownership Recommendation",
    "Yearly Income": "Yearly Income"
}

# Session State
if "step" not in st.session_state:
    st.session_state.step = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "filtered" not in st.session_state:
    st.session_state.filtered = df.copy()

# Functions
def validated_text_input(label, options):
    st.markdown(f"**Options:** {', '.join(options)}")
    value = st.text_input(label, key=f"input_{st.session_state.step}")
    if value:
        value_clean = value.strip()
        if value_clean not in options:
            st.error("❌ Invalid input. Please pick from the options exactly.")
            st.stop()
        return value_clean
    else:
        st.stop()

def ask_gpt_about(field, value):
    prompt = f"Explain briefly in 2-3 sentences why selecting '{value}' for {field} could be important when choosing a vehicle."
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=120
    )
    return response.choices[0].message.content.strip()

# Main Flow
if st.session_state.step < len(questions):
    field_name, options = questions[st.session_state.step]
    user_answer = validated_text_input(f"✍ Enter your {field_name}:", options)
    st.session_state.answers[field_name] = user_answer

    # GPT Explanation
    gpt_explanation = ask_gpt_about(field_name, user_answer)
    st.markdown(f"🧠 **GPT Insight:** {gpt_explanation}")

    # Filter vehicles so far
    data_field = field_mapping[field_name]

    if data_field == "Region":
        st.session_state.filtered = st.session_state.filtered[
            st.session_state.filtered['Region'].str.contains(user_answer, na=False)
        ]
    elif data_field == "Brand":
        st.session_state.filtered = st.session_state.filtered[
            st.session_state.filtered['Brand'] == user_answer
        ]
    else:
        st.session_state.filtered = st.session_state.filtered[
            st.session_state.filtered[data_field].str.strip().str.lower() == user_answer.strip().lower()
        ]

    # Show partial matches
    if not st.session_state.filtered.empty:
        st.markdown("---")
        st.subheader(f"🚘 Matching Vehicles After {field_name}:")
        st.dataframe(st.session_state.filtered[['Brand', 'Model', 'Vehicle Type', 'Fuel Type', 'MSRP Range']])
    else:
        st.warning("❌ No matches found so far. You may need to restart.")

    # 🚀 Immediately move to next question
    st.session_state.step += 1
    st.experimental_rerun()

# After all questions done
else:
    st.success("✅ All questions answered! Final matches below:")

    if not st.session_state.filtered.empty:
        st.dataframe(st.session_state.filtered[['Brand', 'Model', 'Vehicle Type', 'Fuel Type', 'MSRP Range']])
    else:
        st.warning("❌ No vehicles match your full profile.")

# Restart option
if st.button("🔄 Restart"):
    st.session_state.clear()
    st.rerun()
