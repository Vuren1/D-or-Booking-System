import stripe
import streamlit as st

stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

def create_checkout_session(company_id, email):
    session = stripe.checkout.Session.create(
        payment_method_types=['ideal', 'card'],
        line_items=[{
            'price': st.secrets["STRIPE_PRICE_ID"],
            'quantity': 1,
        }],
        mode='subscription',
        success_url=st.secrets["APP_URL"] + f"/?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=st.secrets["APP_URL"],
        customer_email=email,
        metadata={'company_id': str(company_id)}
    )
    return session.url

def check_payment(session_id):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return session.payment_status == 'paid'
    except:
        return False
