import streamlit as st
import pandas as pd
import time
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from fpdf import FPDF
import tempfile

st.title("🚗 Vehicle Advisor Chatbot")

# Load vehicle data from GitHub
@st.cache_data
def load_data():
    df = pd.read_csv("https://raw.githubusercontent.com/Whopkin2/Vehicle-Advisor/main/vehicle_advisor/vehicle_data.csv")
    if 'Brand' in df.columns:
        df['Brand'] = df['Brand'].str.lower()
    return df

df = load_data()

# Initialize chat history and shortlist
if "messages" not in st.session_state:
    st.session_state.messages = []
if "shortlist" not in st.session_state:
    st.session_state.shortlist = []

# Helper functions
def extract_budget(prompt):
    match = re.search(r'(?:under|below|less than|around)\s*\$?(\d+)', prompt)
    if match:
        return int(match.group(1))
    return None

def extract_year(prompt):
    match = re.search(r'(\d{4})', prompt)
    if match:
        return int(match.group(1))
    return None

def extract_mileage(prompt):
    match = re.search(r'(?:under|below|less than)\s*(\d{1,3}(?:,\d{3})*)\s*miles', prompt)
    if match:
        mileage = int(match.group(1).replace(",", ""))
        return mileage
    return None

# Generate smart response
def generate_vehicle_response(prompt):
    prompt = prompt.lower()

    budget = extract_budget(prompt)
    year = extract_year(prompt)
    mileage = extract_mileage(prompt)
    brand = None

    for known_brand in df['Brand'].unique():
        if known_brand in prompt:
            brand = known_brand
            break

    filtered = df.copy()

    if brand:
        filtered = filtered[filtered['Brand'].str.contains(brand, case=False, na=False)]
    if budget:
        filtered = filtered[filtered['MSRP Min'] <= budget]
    if year and 'Year' in filtered.columns:
        filtered = filtered[filtered['Year'] >= year]
    if mileage and 'Mileage' in filtered.columns:
        filtered = filtered[filtered['Mileage'] <= mileage]

    if filtered.empty:
        return "🚫 Sorry, I couldn't find any vehicles matching your description."

    top_cars = filtered.sample(min(3, len(filtered)))

    for _, vehicle in top_cars.iterrows():
        with st.expander(f"🔎 {vehicle['Brand'].title()} {vehicle['Model']}"):
            st.markdown(f"- **Starting Price:** ${vehicle['MSRP Min']:,}")
            if st.button(f"⭐ Save {vehicle['Brand'].title()} {vehicle['Model']} to Shortlist", key=f"save_{vehicle['Model']}"):
                st.session_state.shortlist.append(vehicle)
                st.success(f"Added {vehicle['Brand'].title()} {vehicle['Model']} to your shortlist!")

    return "Here are a few vehicles you might like!"

# Streamed response simulator
def stream_response(text):
    for word in text.split():
        yield word + " "
        time.sleep(0.02)

# Function to create PDF
def create_shortlist_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.cell(0, 10, "Your Shortlisted Vehicles", ln=True, align="C")
    pdf.ln(5)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)

    pdf.set_font("Helvetica", size=12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(60, 10, "Brand", border=1, fill=True)
    pdf.cell(80, 10, "Model", border=1, fill=True)
    pdf.cell(40, 10, "Price", border=1, ln=True, fill=True)

    for vehicle in st.session_state.shortlist:
        pdf.cell(60, 10, vehicle['Brand'].title(), border=1)
        pdf.cell(80, 10, str(vehicle['Model']), border=1)
        pdf.cell(40, 10, f"${int(vehicle['MSRP Min']):,}", border=1, ln=True)

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(temp_pdf.name)
    return temp_pdf.name

# Function to send PDF via email
def send_pdf_via_email(email_address):
    if not st.session_state.shortlist:
        st.error("Shortlist is empty!")
        return

    temp_pdf_path = create_shortlist_pdf()

    message = MIMEMultipart()
    message['From'] = "your-email@gmail.com"
    message['To'] = email_address
    message['Subject'] = "Your Vehicle Advisor Shortlist"
    body = "Please find attached your personalized shortlist of vehicles.\n\nThank you for using Vehicle Advisor!"
    message.attach(MIMEText(body, 'plain'))

    with open(temp_pdf_path, "rb") as f:
        attach = MIMEApplication(f.read(), _subtype="pdf")
        attach.add_header('Content-Disposition', 'attachment', filename="Shortlist.pdf")
        message.attach(attach)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login("your-email@gmail.com", "your-app-password")
    server.send_message(message)
    server.quit()
    st.success(f"📧 Email sent successfully to {email_address}!")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("Tell me what you're looking for in a vehicle 🚙"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        response_text = generate_vehicle_response(prompt)
        streamed_response = st.write_stream(stream_response(response_text))

    st.session_state.messages.append({"role": "assistant", "content": response_text})

# Allow user to request PDF report
if st.session_state.shortlist:
    st.markdown("---")
    st.header("📄 Your Shortlist")
    for vehicle in st.session_state.shortlist:
        st.write(f"- {vehicle['Brand'].title()} {vehicle['Model']} (${vehicle['MSRP Min']:,})")

    email_input = st.text_input("Enter your email address to receive the shortlist PDF:")
    if st.button("📧 Send PDF Report"):
        if email_input:
            send_pdf_via_email(email_input)
        else:
            st.error("Please enter a valid email address.")

    if st.button("⬇️ Download PDF Now"):
        temp_pdf_path = create_shortlist_pdf()
        with open(temp_pdf_path, "rb") as pdf_file:
            st.download_button(label="Download Your Shortlist PDF", data=pdf_file, file_name="Vehicle_Shortlist.pdf", mime="application/pdf")
