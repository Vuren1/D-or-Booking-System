import stripe
import streamlit as st

stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

def create_checkout_session(company_id, email):
    session = stripe.checkout.Session.create(
        payment_method_types=['ideal', 'card'],
        line_items=[{
            'price': 'price_...'  # Maak een price in Stripe voor je product
            'quantity': 1,
        }],
        mode='subscription',
        success_url=st.secrets["COMPANY_NAME"] + "/?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=st.secrets["COMPANY_NAME"] + "/",
        customer_email=email,
        metadata={'company_id': company_id}
    )
    return session.url

def check_payment(session_id):
    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status == 'paid':
        # Update database: bedrijf is betaald
        return True
    return False
