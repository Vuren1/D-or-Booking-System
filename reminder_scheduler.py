import os
from twilio.rest import Client
from datetime import datetime

print("🚀 Start reminder_scheduler.py")

# ✅ Eerst proberen omgevingsvariabelen (GitHub Actions)
TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE")
TEST_SMS_TO = os.environ.get("TEST_SMS_TO")

# 🧩 Controleer of we iets hebben
if TWILIO_SID and TWILIO_TOKEN and TWILIO_PHONE:
    print("✅ Twilio-gegevens gevonden via omgevingsvariabelen (GitHub Secrets).")
else:
    print("⚠️ Geen omgevingsvariabelen gevonden — probeer Streamlit secrets.")
    import streamlit as st
    TWILIO_SID = st.secrets["TWILIO_SID"]
    TWILIO_TOKEN = st.secrets["TWILIO_TOKEN"]
    TWILIO_PHONE = st.secrets["TWILIO_PHONE"]
    TEST_SMS_TO = st.secrets.get("TEST_SMS_TO", None)

client = Client(TWILIO_SID, TWILIO_TOKEN)
print(f"⏰ {datetime.now()}: SMS scheduler gestart")

# 🧪 Testbericht sturen
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
