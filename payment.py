import stripe
import streamlit as st

# ----------------------------------------------------------
# STRIPE CONFIGURATIE
# ----------------------------------------------------------
# Zet je test secret key in Streamlit secrets.toml als:
# STRIPE_SECRET_KEY = "sk_test_..."
# STRIPE_PRICE_ID = "price_..."
# APP_URL = "https://d-or-booking-system-gwbucvc56tnfubjkhgzsqn.streamlit.app"
# ----------------------------------------------------------

stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

def create_checkout_session(company_id: int, email: str) -> str:
    """Maak een Stripe Checkout sessie aan en geef de URL terug."""
    price_id = st.secrets.get("STRIPE_PRICE_ID")
    app_url = st.secrets.get("APP_URL")

    if not price_id or not app_url:
        raise ValueError("❌ STRIPE_PRICE_ID of APP_URL ontbreekt in secrets.toml")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card", "ideal"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{app_url}/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{app_url}/?cancelled=true",
            customer_email=email,
            metadata={"company_id": str(company_id)},
        )
        return session.url

    except Exception as e:
        st.error(f"Fout bij aanmaken van betaalpagina: {e}")
        return "#"

def check_payment(session_id: str) -> bool:
    """Controleer of betaling of abonnement succesvol is."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        # Voor abonnementen is 'complete' status voldoende
        return session.status == "complete" or session.payment_status == "paid"
    except Exception as e:
        st.warning(f"Kon betaling niet controleren: {e}")
        return False
        
