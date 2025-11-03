import stripe
import os
from streamlit.runtime.secrets import get_secret

stripe.api_key = get_secret("STRIPE_SECRET_KEY")

# -----------------------------
# Maak een Stripe Checkout-sessie aan
# -----------------------------
def create_checkout_session(company_id, company_name):
    """Maakt een Stripe checkout sessie aan en geeft de URL terug."""
    try:
        price_id = get_secret("STRIPE_PRICE_ID")
        app_url = get_secret("APP_URL")

        # ✅ BELANGRIJK: success_url binnen de functie definiëren
        success_url = f"{app_url}/?session_id={{CHECKOUT_SESSION_ID}}&company={company_id}"

        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card", "ideal"],
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"company_id": company_id, "company_name": company_name},
            success_url=success_url,
            cancel_url=f"{app_url}?cancelled=true",
        )
        return session.url
    except Exception as e:
        print("Fout bij aanmaken van Stripe sessie:", e)
        return None
