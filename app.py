import streamlit as st
from database import init_db
init_db()

st.title("D'or Booking System - Bedrijf Login")

# Simpele login (later authenticator)
username = st.text_input("Bedrijf Username")
password = st.text_input("Password", type="password")
if st.button("Login"):
    # Check in database (uitbreiden)
    st.success("Ingelogd! Stel je diensten in.")
    # Dashboard
    with st.form("add_service"):
        service_name = st.text_input("Dienst Naam")
        price = st.number_input("Prijs (€)")
        duration = st.number_input("Duur (min)")
        st.form_submit_button("Toevoegen")

# Publieke boekingspagina (voor klanten) later toevoegen
