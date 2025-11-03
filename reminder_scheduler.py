import os
from twilio.rest import Client
from datetime import datetime

# ✅ Eerst proberen via omgevingsvariabelen (GitHub Actions)
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
TEST_SMS_TO = os.getenv("TEST_SMS_TO")

# 🧩 Alleen als dat niet lukt, proberen via Streamlit (lokaal)
if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE]):
    import streamlit as st
    TWILIO_SID = st.secrets["TWILIO_SID"]
    TWILIO_TOKEN = st.secrets["TWILIO_TOKEN"]
    TWILIO_PHONE = st.secrets["TWILIO_PHONE"]
    TEST_SMS_TO = st.secrets.get("TEST_SMS_TO", None)

client = Client(TWILIO_SID, TWILIO_TOKEN)

print(f"⏰ {datetime.now()}: reminder_scheduler gestart.")

# Testbericht (optioneel)
if TEST_SMS_TO:
    try:
        message = client.messages.create(
            body="✅ Testbericht van D’or Booking System – de SMS-herinnering werkt!",
            from_=TWILIO_PHONE,
            to=TEST_SMS_TO
        )
        print(f"✅ SMS verzonden naar {TEST_SMS_TO}, SID: {message.sid}")
    except Exception as e:
        print(f"❌ Fout bij verzenden SMS: {e}")
else:
    print("ℹ️ Geen TEST_SMS_TO ingesteld; geen testbericht verzonden.")
