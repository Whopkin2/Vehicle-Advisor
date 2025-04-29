import streamlit as st
import pandas as pd
import openai
import re

# Initialize OpenAI Client
client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🚗 Vehicle Advisor — Smart Filter with GPT Insights")

@st.cache_data
def load_data():
    return pd.read_csv("vehicle_data.csv")

df = load_data()

# Valid options exactly matching dataset
vehicle_types = ['Crossover', 'Hatchback', 'SUV', 'Sedan', 'Sports Car', 'Truck']
brands = ['Acura', 'Alfa Romeo', 'Audi', 'BMW', 'Cadillac', 'Chevrolet', 'Ferrari', 'Ford', 'GMC', 'Genesis',
          'Honda', 'Hyundai', 'Infiniti', 'Jaguar', 'Jeep', 'Kia', 'Lexus', 'Lucid', 'Mazda', 'Mercedes-Benz',
          'Mini', 'Nissan', 'Porsche', 'Ram', 'Rivian', 'Subaru', 'Tesla', 'Toyota', 'Volkswagen', 'Volvo']
fuel_types = ['Electric', 'Gas', 'Hybrid', 'Plug-in Hybrid']
regions = ['All Regions', 'Mid-West', 'North East', 'North West', 'South East', 'South West', 'West']
use_categories = ['Commuting', 'Family Vehicle', 'Leisure', 'Off-Roading', 'Sport/Performance', 'Utility']
credit_scores = ['Excellent (800+)', 'Fair (580-669)', 'Good (670-739)', 'Very Good (740-799)']
employment_statuses = ['Full-time', 'Part-time', 'Retired', 'Student']
garage_access_options = ['Yes', 'No']
ownership_recommendations = ['Buy', 'Lease', 'Rent']
income_brackets = ['<25k', '25k-50k', '50k-100k', '100k-150k', '150k+']

# Helper for input validation
def validated_text_input(label, options):
    st.markdown(f"**Options:** {', '.join(options)}")
    user_input = st.text_input(label)
    if user_input:
        user_input_clean = user_input.strip()
        valid_options_clean = [o.strip() for o in options]
        if user_input_clean not in valid_options_clean:
            st.error(f"❌ Invalid input. Please select one of the listed options exactly.")
            st.stop()
        return user_input_clean
    else:
        st.stop()

# User Inputs
vehicle_type = validated_text_input("🚗 Enter your desired vehicle type:", vehicle_types)
region = validated_text_input("🌎 Enter your region:", regions)
brand_input = st.text_input(f"🏷️ Enter preferred brand(s) (comma separated). Options: {', '.join(brands)}")
fuel_type = validated_text_input("🔋 Enter your fuel preference:", fuel_types)
employment_status = validated_text_input("💼 Enter your employment status:", employment_statuses)
credit_score = validated_text_input("📊 Enter your credit score range:", credit_scores)
garage_access = validated_text_input("🚗 Do you have garage access?", garage_access_options)
ownership = validated_text_input("🚘 Preferred ownership method:", ownership_recommendations)
income = validated_text_input("💵 Enter your yearly income bracket:", income_brackets)

if st.button("🔍 Show Matching Vehicles"):
    filtered = df[
        (df['Vehicle Type'] == vehicle_type) &
        (df['Fuel Type'].str.lower() == fuel_type.lower()) &
        (df['Employment Status'] == employment_status) &
        (df['Credit Score'] == credit_score) &
        (df['Garage Access'] == garage_access) &
        (df['Ownership Recommendation'] == ownership) &
        (df['Yearly Income'] == income)
    ]

    # Special handling for Region because multiple regions can exist in one cell
    filtered = filtered[filtered['Region'].str.contains(region, na=False)]

    # Handle multiple brands entered
    if brand_input:
        selected_brands = [b.strip() for b in brand_input.split(",") if b.strip()]
        filtered = filtered[filtered['Brand'].isin(selected_brands)]

    if not filtered.empty:
        st.success(f"✅ Found {len(filtered)} matching vehicle(s):")
        st.dataframe(filtered)

        st.markdown("---")
        st.header("🧠 GPT Explanations for Top Matches")

        for idx, row in filtered.head(3).iterrows():
            brand = row['Brand']
            model = row['Model']
            year = row['Model Year']
            fuel = row['Fuel Type']

            prompt = (
                f"Explain in 2-3 sentences why a {year} {brand} {model} "
                f"with a {fuel} engine would be a good fit for someone living in {region} "
                f"who prefers {vehicle_type}s and falls into the {income} income bracket."
            )

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=120
            )

            explanation = response.choices[0].message.content.strip()
            st.markdown(f"**{brand} {model} ({year})**: {explanation}")

    else:
        st.warning("❌ No matching vehicles found with your selected criteria.")
