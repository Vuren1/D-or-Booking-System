import os
import streamlit as st
from twilio.rest import Client
import pandas as pd
from datetime import datetime, timedelta

# 🔐 Probeer eerst omgevingsvariabelen (voor GitHub Actions)
TWILIO_SID = os.getenv("TWILIO_SID", None)
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", None)
TWILIO_PHONE = os.getenv("TWILIO_PHONE", None)

# 🔄 Als we lokaal of in Streamlit draaien, gebruik st.secrets
if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_PHONE]):
    TWILIO_SID = st.secrets["TWILIO_SID"]
    TWILIO_TOKEN = st.secrets["TWILIO_TOKEN"]
    TWILIO_PHONE = st.secrets["TWILIO_PHONE"]

client = Client(TWILIO_SID, TWILIO_TOKEN)

print("🔍 Controleer afspraken voor herinneringen...")

# 👉 HIER TESTEN WE MET EEN VAST NUMMER (je mag dit tijdelijk gebruiken)
test_number = os.getenv("TEST_SMS_TO", None)

if test_number:
    try:
        message = client.messages.create(
            body="✅ Testbericht van D'or Booking System – herinnering werkt!",
            from_=TWILIO_PHONE,
            to=test_number
        )
        print(f"✅ SMS verzonden naar {test_number}, SID: {message.sid}")
    except Exception as e:
        print(f"❌ Fout bij verzenden testbericht: {e}")
else:
    print("ℹ️ Geen TEST_SMS_TO opgegeven, geen testbericht verzonden.")
