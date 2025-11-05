import os
import stripe
import streamlit as st
import sqlite3


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
key = stripe.api_key or ""
print("Stripe key prefix loaded:", key[:7])  # toont alleen 'rk_test' of 'sk_test'


# ───────────────────────────────────────────────────────────────
# 3️⃣  Database-helper voor update van 'paid'-status
# ───────────────────────────────────────────────────────────────
from database import get_connection  # ← voeg deze import ook toe bovenaan je file

def update_company_paid(company_id: int) -> None:
    """Markeer een bedrijf als betaald (companies.paid = 1)."""
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE companies SET paid = 1 WHERE id = ?", (company_id,))
        conn.commit()
        st.info(f"✅ Bedrijf {company_id} gemarkeerd als betaald.")
    except Exception as e:
        st.warning(f"⚠️ Fout bij updaten van betaalstatus: {e}")
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass



# ───────────────────────────────────────────────────────────────
# 4️⃣  Maak Stripe Checkout-sessie aan
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
# 5️⃣  Controleer betaling (nu met database-update)
# ───────────────────────────────────────────────────────────────
def check_payment(session_id: str) -> bool:
    """
    Controleert of een sessie is betaald (voltooid).
    Als betaald → update automatisch companies.paid = 1
    """
    try:
        s = stripe.checkout.Session.retrieve(session_id)
        if s.payment_status == "paid":
            if hasattr(s, "metadata") and s.metadata.get("company_id"):
                company_id = int(s.metadata.get("company_id"))
                update_company_paid(company_id)
            return True
        return False
    except Exception as e:
        st.warning(f"⚠️ Kon betaling niet controleren: {e}")
        return False


# ───────────────────────────────────────────────────────────────
# 6️⃣  Haal company_id uit Stripe sessie
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
