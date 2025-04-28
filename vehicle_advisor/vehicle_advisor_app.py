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

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "shortlist" not in st.session_state:
    st.session_state.shortlist = []
if "question_step" not in st.session_state:
    st.session_state.question_step = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "current_question" not in st.session_state:
    st.session_state.current_question = "🚗 What type of car are you looking for? (e.g., SUV, Sedan, Truck)"

# Helper functions
def extract_int(text):
    numbers = re.findall(r'\d+', text)
    return int(numbers[0]) if numbers else None

def yes_no_to_bool(text):
    return text.strip().lower() in ["yes", "y"]

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

# If no messages yet, start conversation
if len(st.session_state.messages) == 0:
    with st.chat_message("assistant"):
        st.markdown(st.session_state.current_question)
    st.session_state.messages.append({"role": "assistant", "content": st.session_state.current_question})

# Conversation flow
user_input = st.chat_input("Type your answer here...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    idx = st.session_state.question_step

    # Save answers
    if idx == 0:
        st.session_state.answers["type"] = user_input
    elif idx == 1:
        st.session_state.answers["budget"] = extract_int(user_input)
    elif idx == 2:
        st.session_state.answers["brand"] = user_input.lower()
    elif idx == 3:
        st.session_state.answers["year"] = extract_int(user_input)
    elif idx == 4:
        st.session_state.answers["mileage"] = extract_int(user_input)
    elif idx == 5:
        st.session_state.answers["electric"] = yes_no_to_bool(user_input)
    elif idx == 6:
        st.session_state.answers["awd"] = yes_no_to_bool(user_input)
    elif idx == 7:
        st.session_state.answers["third_row"] = yes_no_to_bool(user_input)
    elif idx == 8:
        st.session_state.answers["luxury"] = yes_no_to_bool(user_input)
    elif idx == 9:
        st.session_state.answers["monthly_payment"] = extract_int(user_input)

    # Recommend cars dynamically
    luxury_brands = ['bmw', 'mercedes', 'audi', 'lexus', 'cadillac', 'infiniti', 'acura', 'volvo']
    filtered = df.copy()

    if st.session_state.answers.get("type"):
        filtered = filtered[filtered['Model'].str.contains(st.session_state.answers["type"], case=False, na=False)]
    if st.session_state.answers.get("brand"):
        filtered = filtered[filtered['Brand'].str.contains(st.session_state.answers["brand"], case=False, na=False)]
    if st.session_state.answers.get("budget"):
        filtered = filtered[filtered['MSRP Min'] <= st.session_state.answers["budget"]]
    if st.session_state.answers.get("year") and 'Year' in filtered.columns:
        filtered = filtered[filtered['Year'] >= st.session_state.answers["year"]]
    if st.session_state.answers.get("mileage") and 'Mileage' in filtered.columns:
        filtered = filtered[filtered['Mileage'] <= st.session_state.answers["mileage"]]
    if st.session_state.answers.get("electric") == True:
        filtered = filtered[filtered['Fuel Type'].str.contains('electric', case=False, na=False)]
    if st.session_state.answers.get("luxury") == True:
        filtered = filtered[filtered['Brand'].isin(luxury_brands)]

    if not filtered.empty:
        filtered = filtered.sort_values(by=["MSRP Min", "Year", "Mileage"], ascending=[True, False, True])
        top_cars = filtered.head(2)
        response = "🔎 Based on your answers so far, here are two cars you might love:
"
        for _, car in top_cars.iterrows():
            price = f"${car['MSRP Min']:,}"
            name = f"{car['Brand'].title()} {car['Model']}"
            if 'Fuel Type' in car and 'electric' in str(car['Fuel Type']).lower():
                reason = "⚡ Eco-friendly electric drive and modern features."
            elif car['Brand'].lower() in ['bmw', 'mercedes', 'audi', 'lexus', 'cadillac', 'infiniti', 'acura', 'volvo']:
                reason = "💎 Premium luxury and brand prestige."
            elif 'Mileage' in car and car['Mileage'] is not None and car['Mileage'] < 30000:
                reason = "🛡️ Very low mileage — almost like new!"
            else:
                reason = "✅ A perfect match for affordability and reliability."
            response += f"**✨ {name}**
- 💲 **Price:** {price}
- {reason}

"
        st.session_state.messages.append({"role": "assistant", "content": response})

    # Prepare next question
    if idx == 0:
        bot_reply = "💬 Great choice! Now, what's your maximum budget?"
    elif idx == 1:
        bot_reply = "🏷️ Any preferred brand you'd like?"
    elif idx == 2:
        bot_reply = "📅 What's the minimum model year you're aiming for?"
    elif idx == 3:
        bot_reply = "🛣️ What's your maximum mileage?"
    elif idx == 4:
        bot_reply = "🔋 Do you prefer electric vehicles? (yes/no)"
    elif idx == 5:
        bot_reply = "🚙 Need AWD or 4WD? (yes/no)"
    elif idx == 6:
        bot_reply = "👨‍👩‍👧‍👦 Need a third-row seat? (yes/no)"
    elif idx == 7:
        bot_reply = "💎 Prefer a luxury brand? (yes/no)"
    elif idx == 8:
        bot_reply = "💵 What's your maximum monthly payment goal?"
    else:
        bot_reply = "✅ Thanks! Let me find the best vehicles for you now..."

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    st.session_state.question_step += 1

if st.session_state.question_step > 9:
    with st.chat_message("assistant"):
        summary_parts = []
        if st.session_state.answers.get("type"):
            summary_parts.append(f"looking for a {st.session_state.answers['type'].lower()}")
        if st.session_state.answers.get("budget"):
            summary_parts.append(f"under ${st.session_state.answers['budget']:,}")
        if st.session_state.answers.get("year"):
            summary_parts.append(f"model year {st.session_state.answers['year']} or newer")
        if st.session_state.answers.get("mileage"):
            summary_parts.append(f"less than {st.session_state.answers['mileage']:,} miles")
        if st.session_state.answers.get("electric"):
            if st.session_state.answers['electric']:
                summary_parts.append("preferably electric")
        if st.session_state.answers.get("luxury"):
            if st.session_state.answers['luxury']:
                summary_parts.append("from a luxury brand")

        summary_text = ", ".join(summary_parts)
        st.markdown(f"🚗 Based on your preferences ({summary_text}), here are your top matches:")

        final_response = generate_vehicle_recommendations(st.session_state.answers)
        st.write_stream(stream_response(final_response))

# Shortlist and PDF download
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

if st.button("🔄 Restart Profile"):
    st.session_state.clear()
    st.rerun()
