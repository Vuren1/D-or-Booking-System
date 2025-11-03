from payment import create_checkout_session, check_payment, get_company_id_from_session
import streamlit as st
import pandas as pd
from database import (
    init_db, add_company, get_company_by_email, get_company_by_id,
    is_company_paid, update_company_paid,
    add_service, get_services, add_availability, get_availability,
    add_booking, get_available_slots
)
from twilio_sms import send_sms
from payment import create_checkout_session, check_payment

# -----------------------------
# Init & UI
# -----------------------------
init_db()
st.set_page_config(page_title="D'or Booking System", layout="centered")
st.title("D'or Booking System")

# -----------------------------
# Query parameters
# -----------------------------
qp = st.experimental_get_query_params()
company_id_param = qp.get("company", [None])[0]
session_id = qp.get("session_id", [None])[0]
try:
    company_id_param = int(company_id_param) if company_id_param is not None else None
except Exception:
    company_id_param = None

# -----------------------------
# Auto-activate & auto-login na Stripe
if session_id and "logged_in" not in st.session_state:
    # Als ?company ontbreekt, haal hem uit Stripe metadata
    if not company_id_param:
        company_id_param = get_company_id_from_session(session_id)

    if company_id_param and check_payment(session_id):
        info = get_company_by_id(company_id_param)
        update_company_paid(company_id_param)
        st.session_state.logged_in = True
        st.session_state.company_id = company_id_param
        st.session_state.company_name = info[1] if info else f"Bedrijf #{company_id_param}"
        st.success("✅ Betaling gelukt! Dashboard geactiveerd.")
        st.experimental_rerun()

# ===================================================
# ROUTING: 1) Dashboard (ingelogd) → 2) Publiek (company=) → 3) Login/Registratie
# ===================================================

if "logged_in" in st.session_state:
    # ---------- DASHBOARD ----------
    company_id = st.session_state.company_id
    company_name = st.session_state.get("company_name", f"Bedrijf #{company_id}")

    # Als iemand toch met session_id terugkomt, nogmaals checken/afronden
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.success("✅ Betaling bevestigd.")
        st.rerun()

    if is_company_paid(company_id):
        st.header(f"Dashboard – {company_name}")

        # Diensten
        st.subheader("Diensten")
        with st.form("add_service"):
            name = st.text_input("Naam")
            price = st.number_input("Prijs (€)", min_value=0.0, step=1.0)
            duration = st.number_input("Duur (minuten)", min_value=15, step=5)
            submitted = st.form_submit_button("Toevoegen")
            if submitted and name:
                add_service(company_id, name, price, duration)
                st.success("Dienst toegevoegd.")
                st.rerun()

        services_df = get_services(company_id)
        if not services_df.empty:
            st.dataframe(services_df[["name", "price", "duration"]])
        else:
            st.info("Nog geen diensten toegevoegd.")

        # Beschikbaarheid
        st.subheader("Beschikbaarheid")
        with st.form("add_availability"):
            day = st.selectbox("Dag", ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"])
            col1, col2 = st.columns(2)
            with col1:
                start = st.time_input("Van", value=pd.Timestamp("09:00").time())
            with col2:
                end = st.time_input("Tot", value=pd.Timestamp("18:00").time())
            if st.form_submit_button("Opslaan"):
                add_availability(company_id, day, str(start), str(end))
                st.success("Beschikbaarheid opgeslagen.")
                st.rerun()

        avail_df = get_availability(company_id)
        if not avail_df.empty:
            st.dataframe(['{} {}–{}'.format(r['day'], r['start_time'], r['end_time']) for _, r in avail_df.iterrows()])
        else:
            st.info("Nog geen beschikbaarheid ingesteld.")

        st.divider()
        if st.button("Uitloggen"):
            st.session_state.clear()
            st.rerun()

    else:
        st.warning("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        checkout_url = create_checkout_session(company_id, st.session_state.get("company_name", ""))
        st.markdown(f"[Klik hier om te betalen (€25/maand)]({checkout_url})")

elif company_id_param:
    # ---------- PUBLIEKE KLANTEN-BOEKINGSPAGINA ----------
    info = get_company_by_id(company_id_param)
    company_title = info[1] if info else f"Bedrijf #{company_id_param}"

    st.markdown(
        f"<h2 style='text-align:center;color:#FFD700;'>Boek een afspraak bij {company_title}</h2>",
        unsafe_allow_html=True
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
            add_booking(company_id_param, name, phone, service_row["id"], str(date), time)
            msg = f"Beste {name}, je afspraak bij {company_title} is bevestigd op {date} om {time}."
            try:
                send_sms(phone, msg)
            except Exception as e:
                st.warning(f"Afspraak is bevestigd, maar SMS kon niet worden verzonden: {e}")
            st.success(f"🎉 Bedankt {name}! Je afspraak is bevestigd.")
            st.balloons()

else:
    # ---------- LANDING: REGISTRATIE / LOGIN ----------
    st.subheader("Nieuw bedrijf? Registreer hier")
    with st.form("register_form"):
        new_name = st.text_input("Bedrijfsnaam")
        new_email = st.text_input("E-mail")
        new_password = st.text_input("Wachtwoord", type="password")
        submitted = st.form_submit_button("Registreren")
        if submitted:
            if get_company_by_email(new_email):
                st.error("E-mail al in gebruik!")
            elif new_name and new_email and new_password:
                new_company_id = add_company(new_name, new_email, new_password)
                st.success("✅ Account aangemaakt! Betaal nu om te activeren.")
                checkout_url = create_checkout_session(new_company_id, new_email)
                st.markdown(f"[Klik hier om te betalen (€25/maand)]({checkout_url})")
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
            st.success("Succesvol ingelogd!")
            st.rerun()
        else:
            st.error("Onjuiste inloggegevens.")
