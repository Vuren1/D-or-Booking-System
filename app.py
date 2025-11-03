import streamlit as st
import pandas as pd
from database import (
    init_db, add_company, get_company_by_email, is_company_paid, update_company_paid,
    add_service, get_services, add_availability, get_availability,
    add_booking, get_available_slots
)
from twilio_sms import send_sms
from payment import create_checkout_session, check_payment

# ----------------------------------------------------
# Initialiseer database
# ----------------------------------------------------
init_db()

st.set_page_config(page_title="D'or Booking System", layout="centered")
st.title("D'or Booking System")

# ----------------------------------------------------
# Query parameters (voor betaling of bedrijf)
# ----------------------------------------------------
query_params = st.experimental_get_query_params()
company_id_param = query_params.get("company", [None])[0]
session_id = query_params.get("session_id", [None])[0]

# ----------------------------------------------------
# REGISTRATIE & LOGIN
# ----------------------------------------------------
if "logged_in" not in st.session_state:
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

    # --------------------
    # LOGIN
    # --------------------
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

# ----------------------------------------------------
# DASHBOARD (alleen na betaling)
# ----------------------------------------------------
if "logged_in" in st.session_state:
    company_id = st.session_state.company_id
    company_name = st.session_state.company_name

    # ✅ Automatisch activeren + SMS na betaling
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.session_state.logged_in = True
        st.session_state.company_id = company_id

        # Verstuur bevestigings-SMS naar admin (optioneel e-mailadres of vast nummer)
        try:
            admin_phone = st.secrets.get("TWILIO_PHONE")
            msg = f"Beste {company_name}, je betaling voor D’or Booking System is succesvol ontvangen. Je account is nu geactiveerd."
            send_sms(admin_phone, msg)
            st.success("✅ Betaling gelukt! Dashboard geactiveerd en SMS-bevestiging verstuurd.")
        except Exception as e:
            st.warning(f"Betaling gelukt, maar SMS kon niet worden verzonden: {e}")

        st.rerun()

    # Controleer of het bedrijf actief (betaald) is
    if is_company_paid(company_id):
        st.header(f"Dashboard - {company_name}")

        # --------------------
        # Diensten beheren
        # --------------------
        st.subheader("Diensten")
        with st.form("add_service"):
            name = st.text_input("Naam")
            price = st.number_input("Prijs (€)", min_value=0.0)
            duration = st.number_input("Duur (min)", min_value=15)
            if st.form_submit_button("Toevoegen") and name:
                add_service(company_id, name, price, duration)
                st.success("Dienst toegevoegd!")
                st.rerun()

        services = get_services(company_id)
        if not services.empty:
            st.dataframe(services[["name", "price", "duration"]])
        else:
            st.info("Nog geen diensten toegevoegd.")

        # --------------------
        # Beschikbaarheid beheren
        # --------------------
        st.subheader("Beschikbaarheid")
        with st.form("add_availability"):
            day = st.selectbox(
                "Dag",
                ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
            )
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
            st.info("Nog geen beschikbaarheid toegevoegd.")

        # --------------------
        # Uitloggen
        # --------------------
        if st.button("Uitloggen"):
            st.session_state.clear()
            st.rerun()

    else:
        st.warning("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        checkout_url = create_checkout_session(company_id, st.session_state.get("company_name", ""))
        st.markdown(f"[Klik hier om te betalen (€25/maand)]({checkout_url})")

# ----------------------------------------------------
# KLANTENBOEKING (publieke pagina)
# ----------------------------------------------------
elif company_id_param:
    st.title(f"Boek een afspraak bij bedrijf #{company_id_param}")

    services = get_services(company_id_param)
    if services.empty:
        st.info("Geen diensten beschikbaar voor dit bedrijf.")
        st.stop()

    with st.form("book_form"):
        name = st.text_input("Jouw naam*")
        phone = st.text_input("Telefoonnummer*", placeholder="+316...")
        service = st.selectbox("Dienst*", services["name"].tolist())
        date = st.date_input("Datum*", min_value=pd.Timestamp.today())
        time = st.selectbox("Tijd*", get_available_slots(company_id_param, str(date)))

        if st.form_submit_button("Boek nu!"):
            if not name or not phone.startswith("+"):
                st.error("Vul alle verplichte velden correct in.")
            else:
                service_id = services[services["name"] == service]["id"].iloc[0]
                add_booking(company_id_param, name, phone, service_id, str(date), time)
                msg = f"Beste {name}, je afspraak is bevestigd op {date} om {time}."
                send_sms(phone, msg)
                st.success("✅ Boeking bevestigd! SMS verzonden.")
