import stripe
import streamlit as st

stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

def create_checkout_session(company_id, email):
    session = stripe.checkout.Session.create(
        payment_method_types=['ideal', 'card'],
        line_items=[{
            'price': st.secrets.get("STRIPE_PRICE_ID", 'price_1...'),  # Vervang met je Stripe price ID
            'quantity': 1,
        }],
        mode='subscription',
        success_url=st.secrets.get("APP_URL", 'https://yourapp.streamlit.app') + f"/?company={company_id}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=st.secrets.get("APP_URL", 'https://yourapp.streamlit.app'),
        customer_email=email,
        metadata={'company_id': str(company_id)}
    )
    return session.url

def check_payment(session_id):
    session = stripe.checkout.Session.retrieve(session_id)
    return session.payment_status == 'paid'
