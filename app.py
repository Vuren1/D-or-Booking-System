from payment import create_checkout_session, check_payment
import streamlit as st
from database import init_db, add_booking, get_employees, get_available_slots
from twilio_sms import send_sms
import pandas as pd

# Initialiseer database
init_db()

# Pagina-instellingen
st.set_page_config(page_title="D'or Booking System", layout="centered")
st.title(f"📅 {st.secrets.get('COMPANY_NAME', 'D'or Booking System')}")
st.caption("Boek je afspraak online – snel, eenvoudig en 24/7 beschikbaar")

# Simpele login voor bedrijven (als uitbreiding op de publieke pagina)
st.subheader("Bedrijf Login (voor configuratie)")
username = st.text_input("Username")
password = st.text_input("Password", type="password")
if st.button("Login"):
    if password == st.secrets.get('ADMIN_PASSWORD', 'vuren2025'):
        st.session_state.logged_in = True
        st.success("Ingelogd als bedrijf!")
        st.rerun()
    else:
        st.error("Onjuist wachtwoord")

# Als ingelogd → toon dashboard
if st.session_state.get("logged_in", False):
    company = get_company_by_email(username)  # Aanpassen als nodig
    company_id = company[0] if company else 1  # Voorbeeld ID

    st.subheader("Diensten Beheren")
    with st.form("add_service"):
        name = st.text_input("Naam van de dienst")
        price = st.number_input("Prijs (€)", min_value=0.0, step=0.5)
        duration = st.number_input("Duur (in minuten)", min_value=15, step=15)
        submitted = st.form_submit_button("Dienst toevoegen")
        if submitted and name:
            add_service(company_id, name, price, duration)
            st.success(f"Dienst '{name}' toegevoegd!")
            st.rerun()

    # Toon huidige diensten
    services = get_services(company_id)
    if not services.empty:
        st.write("**Huidige diensten:**")
        st.dataframe(services[["name", "price", "duration"]])
    else:
        st.info("Nog geen diensten toegevoegd.")

    st.subheader("Beschikbaarheid Instellen")
    with st.form("add_availability"):
        day = st.selectbox("Dag", [
            "Maandag", "Dinsdag", "Woensdag", "Donderdag",
            "Vrijdag", "Zaterdag", "Zondag"
        ])
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

    # Toon beschikbaarheid
    availability = get_availability(company_id)
    if not availability.empty:
        st.write("**Je beschikbaarheid:**")
        st.dataframe(availability[["day", "start_time", "end_time"]])
    else:
        st.info("Nog geen beschikbaarheid ingesteld.")

    # Uitloggen
    if st.button("Uitloggen"):
        st.session_state.logged_in = False
        st.rerun()

# Publieke boekingspagina voor klanten
else:
    # Formulier voor nieuwe boeking
    with st.form("booking_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Jouw naam*", placeholder="Jan Jansen")
        with col2:
            phone = st.text_input("Telefoonnummer*", placeholder="+31612345678")
        
        service = st.selectbox("Kies een dienst*", [
            "Consult (€30)", "Installatie (€100)", 
            "Onderhoud (€60)", "Training (€45)", 
            "Reparatie (€80)", "Schoonmaak (€50)"
        ])
        
        employee = st.selectbox("Medewerker*", get_employees())
        date = st.date_input("Datum*", min_value=pd.Timestamp.today())
        time = st.selectbox("Tijd*", get_available_slots(str(date)))

        submitted = st.form_submit_button("Boek nu!", type="primary")

        if submitted:
            if not name or not phone.startswith("+"):
                st.error("Vul naam en geldig telefoonnummer in (+316...)")
            else:
                booking_id = add_booking(name, phone, service, employee, str(date), time)
                msg = f"""
Beste {name},

Je afspraak is bevestigd! 

📅 {date} om {time}
🛠️ {service} met {employee}
🏢 {st.secrets.get('COMPANY_NAME', 'D'or Booking System')}

Tot snel!
                """.strip()
                success, sid = send_sms(phone, msg)
                if success:
                    st.success(f"Afspraak bevestigd! SMS verzonden (ID: {booking_id})")
                    st.balloons()
                else:
                    st.warning(f"Afspraak opgeslagen, maar SMS mislukt: {sid}")
                    st.info("Controleer of je telefoonnummer geverifieerd is in Twilio.")
