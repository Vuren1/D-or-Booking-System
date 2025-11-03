import os
import streamlit as st
import pandas as pd

from database import (
    init_db,
    add_company, get_company_by_email, get_company_by_id,
    is_company_paid, update_company_paid,
    add_service, get_services,
    add_availability, get_availability,
    add_booking, get_available_slots,
    update_sms_settings
)
from twilio_sms import send_sms

# Probeer ook de helper te importeren; zo niet, hebben we een lokale fallback
try:
    from payment import create_checkout_session, check_payment, get_company_id_from_session
except Exception:
    from payment import create_checkout_session, check_payment

    def get_company_id_from_session(session_id: str):
        """Fallback: haal company_id uit Stripe metadata als helper niet bestaat."""
        try:
            import stripe
            sk = os.getenv("STRIPE_SECRET_KEY") or st.secrets["STRIPE_SECRET_KEY"]
            stripe.api_key = sk
            s = stripe.checkout.Session.retrieve(session_id)
            cid = (s.metadata or {}).get("company_id")
            return int(cid) if cid else None
        except Exception:
            return None


# ──────────────────────────────────────────────────────────────────────────────
# INIT & BASIS UI
# ──────────────────────────────────────────────────────────────────────────────
init_db()
st.set_page_config(page_title="D'or Booking System", layout="centered")
st.title("D'or Booking System")

# Zorg dat de logo-map bestaat (voor optionele upload)
os.makedirs("data/logos", exist_ok=True)

# Query params
qp = st.experimental_get_query_params()
company_id_param = qp.get("company", [None])[0]
session_id = qp.get("session_id", [None])[0]
try:
    company_id_param = int(company_id_param) if company_id_param is not None else None
except Exception:
    company_id_param = None


# ──────────────────────────────────────────────────────────────────────────────
# ───────────────── Auto-activate & auto-login na Stripe ─────────────────
if session_id and "logged_in" not in st.session_state:
    # 1) Probeer company uit de URL
    cid = company_id_param

    # 2) Anders: haal company_id uit Stripe metadata
    if not cid:
        try:
            from payment import get_company_id_from_session  # als je helper hebt
            cid = get_company_id_from_session(session_id)
        except Exception:
            cid = None

    # 3) Als we het nog niet weten: haal e-mail uit Stripe sessie en zoek in DB
    if not cid:
        try:
            import stripe, os
            sk = os.getenv("STRIPE_SECRET_KEY") or st.secrets["STRIPE_SECRET_KEY"]
            stripe.api_key = sk
            s = stripe.checkout.Session.retrieve(session_id, expand=["customer_details"])
            email = None
            # bron kan variëren:
            if getattr(s, "customer_details", None) and s.customer_details.email:
                email = s.customer_details.email
            elif getattr(s, "customer_email", None):
                email = s.customer_email
            if email:
                rec = get_company_by_email(email)
                if rec:
                    cid = rec[0]  # id
        except Exception:
            pass

    # 4) Als we een company_id hebben én de betaling is OK -> login + activate
    if cid and check_payment(session_id):
        info = get_company_by_id(cid)
        update_company_paid(cid)
        st.session_state.logged_in = True
        st.session_state.company_id = cid
        st.session_state.company_name = info[1] if info else f"Bedrijf #{cid}"
        # Zet de company ook zichtbaar in de URL (fijn voor refresh/links)
        st.experimental_set_query_params(company=cid)
        st.success("✅ Betaling bevestigd. Je account is nu geactiveerd en je bent ingelogd.")
        st.rerun()
    else:
        # Laat iets zien dat helpt debuggen i.p.v. stil blijven staan
        st.info("✅ Betaling bevestigd. Je wordt zo doorgestuurd…")
        st.caption("Tip: als dit scherm blijft staan, controleer of de success_url in payment.py de parameter &company=<id> bevat.")


# ──────────────────────────────────────────────────────────────────────────────
# ROUTING: 1) Dashboard (ingelogd) → 2) Publieke boekingspagina (?company=) → 3) Landing (registratie/login)
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.get("logged_in"):
    # ============ DASHBOARD ============
    company_id = st.session_state["company_id"]
    company_name = st.session_state.get("company_name", f"Bedrijf #{company_id}")
    company_rec = get_company_by_id(company_id)  # (id, name, email, password, paid, created_at)
    company_email = company_rec[2] if company_rec else ""

    # Als iemand alsnog met session_id binnenkomt, dubbelcheck
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.success("✅ Betaling bevestigd.")
        st.rerun()

    # Actieve klant?
    if is_company_paid(company_id):
        st.header(f"Dashboard – {company_name}")

        # Optioneel bedrijfslogo tonen (uit data/logos/company_<id>.png)
        logo_path = f"data/logos/company_{company_id}.png"
        with st.expander("🏷️ Bedrijfsprofiel"):
            c1, c2 = st.columns([1, 2])
            with c1:
                if os.path.exists(logo_path):
                    st.image(logo_path, caption="Huidig logo", use_column_width=True)
                uploaded = st.file_uploader("Upload nieuw logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
                if uploaded is not None:
                    # Sla op als PNG
                    from PIL import Image
                    img = Image.open(uploaded).convert("RGBA")
                    img.save(logo_path)
                    st.success("Logo bijgewerkt.")
                    st.rerun()
            with c2:
                st.write(f"**Bedrijfsnaam:** {company_name}")
                st.write(f"**E-mail:** {company_email}")
                st.caption("Logo wordt lokaal opgeslagen in `data/logos/` (geen DB-kolom nodig).")

        st.divider()

        # ── Diensten
        st.subheader("Diensten")
        with st.form("add_service"):
            name = st.text_input("Naam")
            price = st.number_input("Prijs (€)", min_value=0.0, step=1.0)
            duration = st.number_input("Duur (minuten)", min_value=15, step=5)
            if st.form_submit_button("Toevoegen") and name:
                add_service(company_id, name, price, duration)
                st.success("Dienst toegevoegd.")
                st.rerun()

        services_df = get_services(company_id)
        if not services_df.empty:
            st.dataframe(services_df[["name", "price", "duration"]])
        else:
            st.info("Nog geen diensten toegevoegd.")

        # ── Beschikbaarheid
        st.subheader("Beschikbaarheid")
        with st.form("add_availability"):
            day = st.selectbox("Dag", ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"])
            c1, c2 = st.columns(2)
            with c1:
                start = st.time_input("Van", value=pd.Timestamp("09:00").time())
            with c2:
                end = st.time_input("Tot", value=pd.Timestamp("17:00").time())
            if st.form_submit_button("Opslaan"):
                add_availability(company_id, day, str(start), str(end))
                st.success("Beschikbaarheid opgeslagen.")
                st.rerun()

        avail_df = get_availability(company_id)
        if not avail_df.empty:
            st.dataframe(avail_df[["day", "start_time", "end_time"]])
        else:
            st.info("Nog geen beschikbaarheid ingesteld.")

        # ── 🟡 ONBOARDING: toon wizard als er nog géén dienst of beschikbaarheid is
        needs_onboarding = services_df.empty or avail_df.empty
        if needs_onboarding:
            st.markdown(
                """
                <div style="background:#0f1f14;border:1px solid #1e3a26;border-radius:16px;padding:24px;margin-top:10px">
                  <h3 style="color:#FFD166;margin:0 0 12px 0;">✨ Welkom bij D’or Booking System!</h3>
                  <p style="color:#cfe3d5">
                    Je account is actief. Zet nu je bedrijf klaar voor boekingen:
                    voeg een <b>dienst</b> toe en stel je <b>beschikbaarheid</b> in.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander("📱 Optioneel: SMS-herinneringen instellen"):
                d = st.number_input("Aantal dagen vooraf verzenden", 0, 7, 1, key="sms_days")
                h = st.number_input("Aantal uren vooraf (zelfde dag)", 0, 12, 2, key="sms_hours")
                if st.button("Instellingen opslaan", key="save_sms"):
                    update_sms_settings(company_id, d, h)
                    st.success("Herinneringsinstellingen opgeslagen.")

        st.divider()
        if st.button("Uitloggen"):
            st.session_state.clear()
            st.rerun()

    else:
        st.warning("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        pay_url = create_checkout_session(company_id, company_email, company_name)
        if pay_url:
            st.markdown(f"[Klik hier om te betalen (€25/maand)]({pay_url})")

elif company_id_param:
    # ============ PUBLIEKE KLANTEN-BOEKINGSPAGINA ============
    info = get_company_by_id(company_id_param)
    company_title = info[1] if info else f"Bedrijf #{company_id_param}"

    st.markdown(
        f"<h2 style='text-align:center;color:#FFD166;'>Boek een afspraak bij {company_title}</h2>",
        unsafe_allow_html=True,
    )

    services = get_services(company_id_param)
    if services.empty:
        st.info("Geen diensten beschikbaar voor dit bedrijf.")
        st.stop()

    st.subheader("Kies een dienst")
    service_name = st.selectbox("Dienst*", services["name"].tolist())
    service_row = services[services["name"] == service_name].iloc[0]
    st.info(f"💰 **Prijs:** €{service_row['price']:.2f}  ⏱️ **Duur:** {service_row['duration']} min")

    st.subheader("Kies datum & tijd")
    date = st.date_input("Datum*", min_value=pd.Timestamp.today())
    times = get_available_slots(company_id_param, str(date))
    if not times:
        st.warning("Geen beschikbare tijden op deze dag.")
        st.stop()
    time = st.selectbox("Tijd*", times)

    st.subheader("Jouw gegevens")
    name = st.text_input("Naam*")
    phone = st.text_input("Telefoonnummer*", placeholder="+316...")

    if st.button("✅ Bevestig je afspraak"):
        if not name or not phone.startswith("+"):
            st.error("Vul alle velden correct in (telefoonnummer moet met + beginnen).")
        else:
            add_booking(company_id_param, name, phone, int(service_row["id"]), str(date), time)
            sms = f"Beste {name}, je afspraak bij {company_title} is bevestigd op {date} om {time}."
            try:
                send_sms(phone, sms)
            except Exception as e:
                st.warning(f"Afspraak is bevestigd, maar SMS kon niet worden verzonden: {e}")
            st.success(f"🎉 Dank je, {name}! Je afspraak is bevestigd.")
            st.balloons()

else:
    # ============ LANDING: REGISTRATIE / LOGIN ============
    st.subheader("Nieuw bedrijf? Registreer hier")
    with st.form("register_form"):
        new_name = st.text_input("Bedrijfsnaam")
        new_email = st.text_input("E-mail")
        new_password = st.text_input("Wachtwoord", type="password")
        submitted = st.form_submit_button("Registreren")

        if submitted:
            if get_company_by_email(new_email):
                st.error("E-mailadres is al in gebruik.")
            elif new_name and new_email and new_password:
                new_company_id = add_company(new_name, new_email, new_password)
                st.success("✅ Account aangemaakt! Betaal nu om te activeren.")
                pay_url = create_checkout_session(new_company_id, new_email, new_name)
                if pay_url:
                    st.markdown(f"[Klik hier om te betalen (€25/maand)]({pay_url})")
            else:
                st.error("Vul alle velden in.")

    st.subheader("Bestaand bedrijf? Log in")
    login_email = st.text_input("E-mail", key="login_email")
    login_password = st.text_input("Wachtwoord", type="password", key="login_pw")
    if st.button("Inloggen"):
        company = get_company_by_email(login_email)
        if company and company[3] == login_password:
            st.session_state.logged_in = True
            st.session_state.company_id = company[0]
            st.session_state.company_name = company[1]
            st.success("Succesvol ingelogd.")
            st.rerun()
        else:
            st.error("Onjuiste inloggegevens.")
