from twilio.rest import Client
import streamlit as st

def send_sms(to, body):
    """Verstuur een SMS via Twilio."""
    try:
        sid = st.secrets.get("TWILIO_SID")
        token = st.secrets.get("TWILIO_TOKEN")
        from_number = st.secrets.get("TWILIO_PHONE")

        if not sid or not token or not from_number:
            raise ValueError("Twilio secrets ontbreken in secrets.toml")

        client = Client(sid, token)
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to
        )
        return True, message.sid

    except Exception as e:
        return False, str(e)
