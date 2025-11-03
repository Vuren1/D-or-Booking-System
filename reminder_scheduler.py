import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from twilio.rest import Client
import streamlit as st

# --- Twilio Configuratie ---
TWILIO_SID = st.secrets["TWILIO_SID"]
TWILIO_TOKEN = st.secrets["TWILIO_TOKEN"]
TWILIO_PHONE = st.secrets["TWILIO_PHONE"]

# --- Database pad ---
DB_NAME = "data/bookings.db"


def send_sms(to, body):
    """Verstuur sms via Twilio"""
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        message = client.messages.create(
            body=body,
            from_=TWILIO_PHONE,
            to=to
        )
        print(f"✅ SMS verstuurd naar {to}: {message.sid}")
        return True
    except Exception as e:
        print(f"❌ Fout bij SMS naar {to}: {e}")
        return False


def get_upcoming_bookings():
    """Haalt boekingen op uit de database"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM bookings", conn)
    conn.close()
    return df


def get_sms_settings(company_id):
    """Haalt sms-herinneringsinstellingen op"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT days_before, hours_before FROM sms_settings WHERE company_id=?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row or (1, 1)


def run_reminder_check():
    """Controleert afspraken en stuurt herinneringen"""
    print("🔍 Controleer afspraken voor herinneringen...")

    bookings = get_upcoming_bookings()
    if bookings.empty:
        print("Geen afspraken gevonden.")
        return

    now = datetime.now()

    for _, b in bookings.iterrows():
        try:
            appointment_time = datetime.strptime(f"{b['date']} {b['time']}", "%Y-%m-%d %H:%M")
        except Exception:
            # Als tijd niet exact in formaat staat (bijv. "09:00:00"), vang het op
            try:
                appointment_time = datetime.strptime(f"{b['date']} {b['time']}", "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"❌ Kon afspraak niet lezen: {e}")
                continue

        company_id = b["company_id"]
        name = b["name"]
        phone = b["phone"]

        # Herinneringsinstellingen ophalen
        days_before, hours_before = get_sms_settings(company_id)

        reminder_day_before = appointment_time - timedelta(days=days_before)
        reminder_same_day = appointment_time - timedelta(hours=hours_before)

        # Controleer of het nu tijd is om een herinnering te sturen
        if reminder_day_before.date() == now.date() and reminder_day_before.hour == now.hour:
            msg = f"📅 Hallo {name}, dit is een vriendelijke herinnering: je afspraak bij D'or Booking System is morgen om {appointment_time.strftime('%H:%M')}."
            send_sms(phone, msg)

        elif appointment_time.date() == now.date() and reminder_same_day.hour == now.hour:
            msg = f"⏰ Hallo {name}, je afspraak bij D'or Booking System begint over {hours_before} uur!"
            send_sms(phone, msg)


if __name__ == "__main__":
    run_reminder_check()
