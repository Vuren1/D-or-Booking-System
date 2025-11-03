import os
import stripe
import streamlit as st


# ───────────────────────────────────────────────────────────────
# 1️⃣  Hulpfunctie om secrets op te halen
# ───────────────────────────────────────────────────────────────
def get_secret(key: str) -> str:
    """Haalt veilige sleutel op uit Streamlit secrets of omgevingsvariabelen."""
    try:
        return st.secrets[key]
    except Exception:
        val = os.getenv(key)
        if not val:
            raise ValueError(f"Secret '{key}' ontbreekt in secrets.toml of ENV.")
        return val


# ───────────────────────────────────────────────────────────────
# 2️⃣  Stripe initialisatie
# ───────────────────────────────────────────────────────────────
stripe.api_key = get_secret("STRIPE_SECRET_KEY")


# ───────────────────────────────────────────────────────────────
# 3️⃣  Maak Stripe Checkout-sessie aan
# ───────────────────────────────────────────────────────────────
def create_checkout_session(company_id: int, company_email: str, company_name: str = "") -> str:
    """
    Maakt een Stripe Checkout sessie aan en geeft de URL terug.
    Na betaling wordt de gebruiker teruggestuurd met ?session_id=...&company=...
    """
    try:
        price_id = get_secret("STRIPE_PRICE_ID")
        app_url = get_secret("APP_URL")

        # Maak de Stripe Checkout sessie aan
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
        st.warning(f"⚠️ Fout bij aanmaken Stripe-sessie: {e}")
        return None


# ───────────────────────────────────────────────────────────────
# 4️⃣  Controleer betaling
# ───────────────────────────────────────────────────────────────
def check_payment(session_id: str) -> bool:
    """
    Controleert of een sessie is betaald (voltooid).
    """
    try:
        s = stripe.checkout.Session.retrieve(session_id)
        return s.payment_status == "paid"
    except Exception as e:
        st.warning(f"⚠️ Kon betaling niet controleren: {e}")
        return False


# ───────────────────────────────────────────────────────────────
# 5️⃣  Haal company_id uit Stripe sessie
# ───────────────────────────────────────────────────────────────
def get_company_id_from_session(session_id: str):
    """
    Haalt company_id op uit Stripe sessie metadata.
    Wordt gebruikt in app.py om automatisch in te loggen na betaling.
    """
    try:
        s = stripe.checkout.Session.retrieve(session_id)
        if hasattr(s, "metadata") and s.metadata:
            return int(s.metadata.get("company_id")) if s.metadata.get("company_id") else None
    except Exception as e:
        st.warning(f"⚠️ Kon company_id niet ophalen: {e}")
    return None
