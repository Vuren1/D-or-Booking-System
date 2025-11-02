import streamlit as st
import pandas as pd
from database import (
    init_db, add_company, get_company_by_email, is_company_paid, update_company_paid,
    add_service, get_services, add_availability, get_availability,
    add_booking, get_available_slots
)
from twilio_sms import send_sms
from payment import create_checkout_session, check_payment  # Maak payment.py als het ontbreekt

# Initialiseer database
init_db()

# Pagina-instellingen
st.set_page_config(page_title="D'or Booking System", layout="centered")
st.title("D'or Booking System")

# Haal query params voor company_id of session_id
query_params = st.experimental_get_query_params()
company_id = query_params.get("company", [None])[0]
session_id = query_params.get("session_id", [None])[0]

# --- REGISTRATIE VOOR NIEUWE BEDRIJVEN ---
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
                st.success("Account aangemaakt! Betaal nu om te activeren.")
                # Stripe betaling link (testmode)
                session_url = create_checkout_session(new_company_id, new_email)
                st.markdown(f"[Betaal abonnement (€10/maand)]({session_url})")
                st.rerun()
            else:
                st.error("Vul alle velden in.")

    # --- LOGIN ---
    st.subheader("Bestaand bedrijf? Log in")
    username = st.text_input("E-mail (gebruikersnaam)")
    password = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        company = get_company_by_email(username)
        if company and company[3] == password:  # company[3] = password
            st.session_state.logged_in = True
            st.session_state.company_id = company[0]
            st.session_state.company_name = company[1]
            st.success(f"Welkom, {company[1]}!")
            st.rerun()
        else:
            st.error("Onjuiste e-mail of wachtwoord")

# --- DASHBOARD (ALLEEN ALS INGELOGD EN BETAALD) ---
if "logged_in" in st.session_state:
    company_id = st.session_state.company_id
    company_name = st.session_state.company_name

    # Check betaling (gebruik session_id uit URL of database)
    if session_id:
        if check_payment(session_id):
            update_company_paid(company_id)
            st.success("Betaling gelukt! Dashboard geactiveerd.")
            st.rerun()
        else:
            st.warning("Betaling in behandeling – probeer later.")

    if is_company_paid(company_id):
        st.header(f"Dashboard - {company_name}")

        # Diensten beheren
        st.subheader("Diensten Beheren")
        with st.form("add_service_form"):
            name = st.text_input("Naam van de dienst")
            price = st.number_input("Prijs (€)", min_value=0.0, step=0.5)
            duration = st.number_input("Duur (in minuten)", min_value=15, step=15)
            submitted = st.form_submit_button("Dienst toevoegen")
            if submitted and name:
                add_service(company_id, name, price, duration)
                st.success(f"Dienst '{name}' toegevoegd!")
                st.rerun()

        services = get_services(company_id)
        if not services.empty:
            st.write("**Huidige diensten:**")
            st.dataframe(services[["name", "price", "duration"]])
        else:
            st.info("Nog geen diensten toegevoegd.")

        # Beschikbaarheid
        st.subheader("Beschikbaarheid Instellen")
        with st.form("add_availability_form"):
            day = st.selectbox("Dag", ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"])
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.time_input("Starttijd", value=pd.Timestamp("09:00").time())
            with col2:
                end_time = st.time_input("Eindtijd", value=pd.Timestamp("18:00").time())
            submitted = st.form_submit_button("Beschikbaarheid opslaan")
            if submitted:
                add_availability(company_id, day, str(start_time), str(end_time))
                st.success(f"Beschikbaarheid voor {day} toegevoegd!")
                st.rerun()

        availability = get_availability(company_id)
        if not availability.empty:
            st.write("**Je beschikbaarheid:**")
            st.dataframe(availability[["day", "start_time", "end_time"]])
        else:
            st.info("Nog geen beschikbaarheid ingesteld.")

        # Uitloggen
        if st.button("Uitloggen"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    else:
        st.error("Betaal je abonnement om toegang te krijgen tot het dashboard.")
        # Herinnering aan betaling
        st.markdown("[Betaal hier](https://dashboard.stripe.com/test/payments)")

# --- PUBLIEKE BOEKINGSPAGINA (VOOR KLANTEN) ---
else:
    if not company_id:
        st.error("Geen bedrijf gespecificeerd. Gebruik ?company=ID in de URL.")
        st.stop()

    st.title(f"Boek bij bedrijf ID {company_id}")

    services = get_services(company_id)
    if services.empty:
        st.info("Dit bedrijf heeft nog geen diensten ingesteld.")
        st.stop()

    with st.form("booking_form"):
        customer_name = st.text_input("Jouw naam*")
        customer_phone = st.text_input("Telefoonnummer*", placeholder="+316...")
        service_name = st.selectbox("Kies een dienst*", services["name"].tolist())
        date = st.date_input("Datum*", min_value=pd.Timestamp.today())
        time = st.selectbox("Beschikbare tijd*", get_available_slots(company_id, str(date)))
        submitted = st.form_submit_button("Boek nu!")

        if submitted:
            if not customer_name or not customer_phone.startswith("+"):
                st.error("Vul naam en geldig telefoonnummer in.")
            else:
                service_id = services[services["name"] == service_name]["id"].iloc[0]
                booking_id = add_booking(company_id, customer_name, customer_phone, service_id, str(date), time)
                msg = f"Beste {customer_name}, je afspraak is bevestigd voor {date} om {time}. Bedankt!"
                success, sid = send_sms(customer_phone, msg)
                if success:
                    st.success("Boeking geslaagd! SMS verzonden.")
                else:
                    st.warning("Boeking opgeslagen, maar SMS mislukt.")
