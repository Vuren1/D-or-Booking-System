import stripe
import streamlit as st

# -----------------------------------------------
# Stripe-instellingen vanuit Streamlit secrets
# -----------------------------------------------
def get_secret(key: str, required: bool = True):
    """Veilig ophalen van secret variabelen."""
    value = st.secrets.get(key)
    if required and not value:
        st.error(f"❌ '{key}' ontbreekt in secrets.toml. Voeg dit toe in Streamlit → Settings → Secrets.")
        raise ValueError(f"Secret '{key}' ontbreekt")
    return value

stripe.api_key = get_secret("STRIPE_SECRET_KEY")

# -----------------------------------------------
# Maak een Stripe Checkout-sessie aan
# -----------------------------------------------
def success_url = f"{app_url}/?session_id={{CHECKOUT_SESSION_ID}}&company={company_id}"
    """Maakt een Stripe checkout sessie aan en geeft de URL terug."""
    try:
        price_id = get_secret("STRIPE_PRICE_ID")
        app_url = get_secret("APP_URL")

        # Maak de sessie aan in testmodus
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
        st.error(f"⚠️ Fout bij aanmaken van de Stripe sessie: {e}")
        return "#"

# -----------------------------------------------
# Controleer of een betaling is geslaagd
# -----------------------------------------------
def check_payment(session_id: str) -> bool:
    """Controleert of betaling of abonnement succesvol is."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        # Abonnementen hebben status 'complete' of 'paid'
        return session.status == "complete" or session.payment_status == "paid"
    except Exception as e:
        st.warning(f"Kon betaling niet controleren: {e}")
        return False
