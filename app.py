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

init_db()
st.set_page_config(page_title="D'or Booking System", layout="centered")
st.title("D'or Booking System")

# Query params
qp = st.experimental_get_query_params()
company_id_param = qp.get("company", [None])[0]
session_id = qp.get("session_id", [None])[0]
if company_id_param:
    try:
        company_id_param = int(company_id_param)
    except Exception:
        company_id_param = None

# ✅ Auto-login NA Stripe-betaling (gebruikt session_id + company in URL)
if session_id and company_id_param and "logged_in" not in st.session_state:
    if check_payment(session_id):
        info = get_company_by_id(company_id_param)
        st.session_state.logged_in = True
        st.session_state.company_id = company_id_param
        st.session_state.company_name = info[1] if info else f"Bedrijf #{company_id_param}"
        update_company_paid(company_id_param)
        st.success("✅ Betaling gelukt! Dashboard geactiveerd.")
        st.experimental_rerun()

# ---------- ROUTING OP TOPLEVEL ----------
if "logged_in" in st.session_state:
    # ===== DASHBOARD =====
    company_id = st.session_state.company_id
    company_name = st.session_state.get("company_name", f"Bedrijf #{company_id}")

    # (optioneel) nogmaals checken als er toevallig toch een session_id is:
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.success("✅ Betaling bevestigd.")
        st.experimental_rerun()

    if is_company_paid(company_id):
        st.header(f"Dashboard - {company_name}")
        # ... (jouw bestaande dashboard secties: diensten, beschikbaarheid, uitloggen, etc.)
    else:
        st.warning("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        checkout_url = create_checkout_session(company_id, st.session_state.get("company_name",""))
        st.markdown(f"[Klik hier om te betalen (€25/maand)]({checkout_url})")

elif company_id_param:
    # ===== PUBLIEKE KLANTEN-BOEKINGSPAGINA =====
    info = get_company_by_id(company_id_param)
    company_title = info[1] if info else f"Bedrijf #{company_id_param}"
    st.markdown(f"<h1 style='text-align:center;color:#FFD700;'>Boek een afspraak bij {company_title}</h1>", unsafe_allow_html=True)

    services = get_services(company_id_param)
    if services.empty:
        st.info("Geen diensten beschikbaar voor dit bedrijf.")
        st.stop()

    st.markdown("### 💅 Kies een dienst")
    service_name = st.selectbox("Dienst*", services["name"].tolist())
    service_row = services[services["name"] == service_name].iloc[0]

    st.info(f"💰 **Prijs:** €{service_row['price']:.2f}  ⏱️ **Duur:** {service_row['duration']} min")

    st.markdown("### 📅 Kies datum en tijd")
    date = st.date_input("Datum*", min_value=pd.Timestamp.today())
    times = get_available_slots(company_id_param, str(date))
    if not times:
        st.warning("Geen beschikbare tijden op deze dag.")
        st.stop()
    time = st.selectbox("Tijd*", times)

    st.markdown("### 🧍‍♀️ Jouw gegevens")
    name = st.text_input("Naam*")
    phone = st.text_input("Telefoonnummer*", placeholder="+316...")

    if st.button("✅ Bevestig je afspraak"):
        if not name or not phone.startswith("+"):
            st.error("Vul alle velden correct in (telefoon moet met + beginnen).")
        else:
            add_booking(company_id_param, name, phone, service_row["id"], str(date), time)
            msg = f"Beste {name}, je afspraak bij {company_title} is bevestigd op {date} om {time}."
            send_sms(phone, msg)
            st.success(f"🎉 Bedankt {name}! Je afspraak is bevestigd. SMS is verzonden.")
            st.balloons()

else:
    # ===== REGISTRATIE / LOGIN LANDING =====
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
            st.experimental_rerun()
        else:
            st.error("Onjuiste inloggegevens.")

# --------------------------
# DASHBOARD (NA INLOGGEN)
# --------------------------
elif "logged_in" in st.session_state:
    company_id = st.session_state.company_id
    company_name = st.session_state.company_name

    # Betaling succesvol?
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.success("✅ Betaling gelukt! Dashboard geactiveerd.")
        st.rerun()

    # Als betaald -> dashboard
    if is_company_paid(company_id):
        st.header(f"Dashboard - {company_name}")

        # Diensten
        st.subheader("Diensten")
        with st.form("add_service"):
            name = st.text_input("Naam van dienst")
            price = st.number_input("Prijs (€)", min_value=0.0)
            duration = st.number_input("Duur (minuten)", min_value=15)
            if st.form_submit_button("Toevoegen") and name:
                add_service(company_id, name, price, duration)
                st.success("Dienst toegevoegd!")
                st.rerun()

        services = get_services(company_id)
        if not services.empty:
            st.dataframe(services[["name", "price", "duration"]])
        else:
            st.info("Nog geen diensten toegevoegd.")

        # Beschikbaarheid
        st.subheader("Beschikbaarheid")
        with st.form("add_avail"):
            day = st.selectbox("Dag", ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"])
            col1, col2 = st.columns(2)
            with col1:
                start = st.time_input("Van", value=pd.Timestamp("09:00").time())
            with col2:
                end = st.time_input("Tot", value=pd.Timestamp("18:00").time())

            if st.form_submit_button("Opslaan"):
                add_availability(company_id, day, str(start), str(end))
                st.success("Beschikbaarheid opgeslagen!")
                st.rerun()

        avail = get_availability(company_id)
        if not avail.empty:
            st.dataframe(avail[["day", "start_time", "end_time"]])
        else:
            st.info("Nog geen beschikbaarheid ingevoerd.")

        # ----------------------------------------------------
# SMS-herinnering instellingen
# ----------------------------------------------------
st.subheader("📱 SMS Herinneringen")
days_before, hours_before = get_sms_settings(company_id)

with st.form("sms_settings_form"):
    st.markdown("Stel hier in wanneer klanten een herinnering ontvangen voor hun afspraak.")
    col1, col2 = st.columns(2)
    with col1:
        new_days = st.number_input("Dagen vóór afspraak", min_value=0, max_value=7, value=days_before)
    with col2:
        new_hours = st.number_input("Uren vóór afspraak (op de dag zelf)", min_value=0, max_value=23, value=hours_before)
    if st.form_submit_button("Opslaan"):
        update_sms_settings(company_id, new_days, new_hours)
        st.success("SMS-herinneringsinstellingen opgeslagen!")

        # Uitloggen
        if st.button("Uitloggen"):
            st.session_state.clear()
            st.rerun()

    else:
        st.warning("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        checkout_url = create_checkout_session(company_id, st.session_state.get("company_name", ""))
        st.markdown(f"[Klik hier om te betalen (€25/maand)]({checkout_url})", unsafe_allow_html=True)

# --------------------------
# KLANT BOEKINGSPAGINA
# --------------------------
elif company_id_param:
    company_id = int(company_id_param)
    company_info = get_company_by_id(company_id)  # voeg deze helper toe in database.py
    company_name = company_info[1] if company_info else "Onbekend Bedrijf"

    st.markdown(
        f"<h1 style='text-align:center;color:#FFD700;'>Boek een afspraak bij {company_name}</h1>",
        unsafe_allow_html=True
    )

    with st.form("book_form"):
        name = st.text_input("Jouw naam*")
        phone = st.text_input("Telefoonnummer*", placeholder="+316...")
        service = st.selectbox("Dienst*", services["name"].tolist())
        date = st.date_input("Datum*", min_value=pd.Timestamp.today())
        time = st.selectbox("Tijd*", get_available_slots(company_id_param, str(date)))

        if st.form_submit_button("Boek nu!"):
            if not name or not phone.startswith("+"):
                st.error("Vul alle verplichte velden in (en gebruik +31...).")
            else:
                service_id = services[services["name"] == service]["id"].iloc[0]
                add_booking(company_id_param, name, phone, service_id, str(date), time)
                send_sms(phone, f"Beste {name}, je afspraak is bevestigd op {date} om {time}.")
                st.success("✅ Boeking gelukt! Bevestiging per SMS verstuurd.")
