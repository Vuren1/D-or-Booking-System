# payment.py
import os
import stripe
import streamlit as st

def _get_secret(key: str) -> str:
    """Lees secret uit ENV (GitHub/locaal) of uit st.secrets (Streamlit)."""
    val = os.getenv(key)
    if val:
        return val
    if key in st.secrets:
        return st.secrets[key]
    raise ValueError(f"Secret '{key}' ontbreekt")

# Stripe initialiseren
stripe.api_key = _get_secret("STRIPE_SECRET_KEY")

def create_checkout_session(company_id: int, company_email: str, company_name: str = "") -> str | None:
    """Maak een Stripe Checkout sessie aan en retourneer de URL."""
    try:
        price_id = _get_secret("STRIPE_PRICE_ID")
        app_url  = _get_secret("APP_URL")

        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card", "ideal"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{app_url}/?session_id={{CHECKOUT_SESSION_ID}}&company={company_id}",
            cancel_url=f"{app_url}",
            customer_email=company_email,
            metadata={
                "company_id": str(company_id),
                "company_email": company_email,
                "company_name": company_name,
            },
        )
        return session.url
    except Exception as e:
        # In Streamlit kun je dit tonen; lokaal/logs mag je printen
        try:
            st.error(f"Fout bij aanmaken van de Stripe sessie: {e}")
        except Exception:
            print("Fout bij aanmaken van Stripe sessie:", e)
        return None

def check_payment(session_id: str) -> bool:
    """Check of de checkout/subscription betaald/actief is."""
    try:
        sess = stripe.checkout.Session.retrieve(
            session_id, expand=["subscription", "payment_intent"]
        )
        # direct betaald?
        if getattr(sess, "payment_status", None) == "paid":
            return True
        # of subscription actief / trialing
        sub = getattr(sess, "subscription", None)
        if sub and getattr(sub, "status", "") in ("active", "trialing"):
            return True
        return False
    except Exception:
        return False
