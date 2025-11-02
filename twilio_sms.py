from twilio.rest import Client
import streamlit as st

def send_sms(to, body):
    try:
        client = Client(st.secrets["TWILIO_SID"], st.secrets["TWILIO_TOKEN"])
        message = client.messages.create(
            body=body,
            from_=st.secrets["TWILIO_PHONE"],
            to=to
        )
        return True, message.sid
    except Exception as e:
        return False, str(e)
