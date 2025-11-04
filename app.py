# app.py
import streamlit as st
import pandas as pd
from datetime import datetime

from database import (
    init_db,
    # companies
    add_company, get_company_by_email, get_company_by_id,
    is_company_paid, update_company_paid,
    # categories
    upsert_category, get_categories, get_category_description,
    # services
    add_service, get_services, get_service_categories, get_services_by_ids,
    # availability & slots
    add_availability, get_availability,
    get_available_slots, get_available_slots_for_duration,
    # bookings
    add_booking_with_items, get_bookings_overview,
)

from payment import create_checkout_session, check_payment
from twilio_sms import send_sms


# -----------------------------
# INIT + PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="D'or Booking System", layout="wide")
init_db()

# Klein beetje styling (goudaccenten + titels)
st.markdown("""
<style>
.block-title {font-weight:700;font-size:22px;margin:8px 0 10px 0;color:#FFD166;}
.big-title {font-weight:800;font-size:38px;text-align:center;color:#FFD166;margin:8px 0 26px 0;}
.caption-muted {color:#b8b8b8;}
</style>
""", unsafe_allow_html=True)

# Query parameters voor Stripe en publieke klantpagina
query = st.experimental_get_query_params()
session_id = query.get("session_id", [None])[0]
company_id_param = query.get("company", [None])[0]

# -----------------------------
# 1️⃣ REGISTRATIE & LOGIN
# -----------------------------
if "logged_in" not in st.session_state and not company_id_param:
    st.title("D'or Booking System")

    col1, col2 = st.columns(2)

    # Registratie
    with col1:
        st.subheader("Nieuw bedrijf registreren")
        with st.form("register_form"):
            new_name = st.text_input("Bedrijfsnaam")
            new_email = st.text_input("E-mail")
            new_password = st.text_input("Wachtwoord", type="password")
            submit_reg = st.form_submit_button("Registreer")

            if submit_reg:
                if get_company_by_email(new_email):
                    st.error("E-mailadres is al geregistreerd.")
                elif new_name and new_email and new_password:
                    new_id = add_company(new_name, new_email, new_password)
                    st.success("✅ Account aangemaakt! Betaal nu om te activeren.")
                    try:
                        session_url = create_checkout_session(new_id, new_email, new_name)
                        st.markdown(f"[💳 Betaal abonnement (€25/maand)]({session_url})")
                    except Exception as e:
                        st.error(f"⚠️ Stripe-fout: {e}")
                else:
                    st.warning("Vul alle velden in.")

    # Login
    with col2:
        st.subheader("Bestaand bedrijf inloggen")
        email = st.text_input("E-mail (login)")
        password = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen"):
            user = get_company_by_email(email)
            if user and user[3] == password:
                st.session_state.logged_in = True
                st.session_state.company_id = user[0]
                st.session_state.company_name = user[1]
                st.rerun()
            else:
                st.error("Onjuiste gegevens.")

# -----------------------------
# 2️⃣ DASHBOARD (voor bedrijven)
# -----------------------------
elif "logged_in" in st.session_state and not company_id_param:
    company_id = st.session_state.company_id
    company_name = st.session_state.company_name

    # Als je net terugkomt van Stripe: check betaling → activeer
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.success("✅ Betaling gelukt! Dashboard geactiveerd.")
        st.rerun()

    # Betaald?
    if not is_company_paid(company_id):
        st.error("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        try:
            # fallback: haal e-mail op uit DB
            email = get_company_by_id(company_id)[2]
            checkout_url = create_checkout_session(company_id, email, company_name)
            st.markdown(f"[💳 Betaal hier (€25/maand)]({checkout_url})")
        except Exception as e:
            st.warning(f"Stripe error: {e}")
        st.stop()

    # Titel
    st.markdown(f"<div class='big-title'>Welkom, {company_name}</div>", unsafe_allow_html=True)

    # Tabs (met afspraken-overzicht)
    tab_dash, tab_services, tab_avail, tab_preview, tab_bookings = st.tabs(
        ["🏠 Overzicht", "💅 Diensten", "🕒 Beschikbaarheid", "👀 Klant-preview", "📋 Afspraken"]
    )

    # -------------------
    # 🏠 OVERZICHT
    with tab_dash:
        st.markdown(
            """
            <div style='background-color:#333;padding:20px;border-radius:10px;color:white;'>
            <b>Welkom in je D'or dashboard!</b><br>
            Voeg hieronder je diensten (met beschrijving), categorieën (met beschrijving) en beschikbaarheid toe. 
            Alles wat je instelt wordt zichtbaar op je publieke boekingspagina.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -------------------
    # 💅 DIENSTEN (met beschrijving + categorie-beschrijving)
    with tab_services:
        st.markdown("<div class='block-title'>Diensten</div>", unsafe_allow_html=True)

        cats_df = get_categories(company_id)
        cat_desc_map = {row["name"]: row.get("description", "") for _, row in cats_df.iterrows()}
        existing_cats = ["Algemeen"] + [c for c in sorted(cat_desc_map.keys()) if c != "Algemeen"]

        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with st.form("add_service_form"):
            with col1:
                name = st.text_input("Naam", placeholder="Bijv. Pedicure Basic")
            with col2:
                price = st.number_input("Prijs (€)", min_value=0.0, step=0.05, value=0.0)
            with col3:
                duration = st.number_input("Duur (minuten)", min_value=5, step=5, value=30)
            with col4:
                category = st.selectbox("Categorie", options=existing_cats + ["+ Nieuwe categorie..."])

            service_desc = st.text_area(
                "Beschrijving (dienst, optioneel)",
                placeholder="Bijv. Voetbad, nagels knippen en vijlen, voetmassage (5min)",
                height=90,
            )

            # Nieuwe categorie of bestaande (met bewerkbare beschrijving)
            new_cat = None
            if category == "+ Nieuwe categorie...":
                new_cat = st.text_input("Nieuwe categorie-naam", placeholder="Bijv. Pedicure Pakket")
                cat_desc = st.text_area(
                    "Beschrijving categorie (optioneel)",
                    placeholder="Bijv. Samengestelde pedicure pakketten...",
                    height=80,
                )
            else:
                cat_desc = st.text_area(
                    "Categorie-beschrijving (bewerken, optioneel)",
                    value=cat_desc_map.get(category, ""),
                    height=80,
                )

            if st.form_submit_button("➕ Toevoegen"):
                final_cat = (new_cat or category or "Algemeen").strip()
                # maak/updates categorie
                upsert_category(company_id, final_cat, cat_desc or "")
                if name:
                    add_service(company_id, name, price, duration, final_cat, service_desc)
                    st.success("Dienst toegevoegd.")
                    st.rerun()
                else:
                    st.warning("Vul een naam in.")

        services_df = get_services(company_id)
        if services_df.empty:
            st.info("Nog geen diensten.")
        else:
            st.dataframe(
                services_df[["id", "name", "price", "duration", "category", "description"]],
                use_container_width=True
            )

    # -------------------
    # 🕒 BESCHIKBAARHEID
    with tab_avail:
        st.markdown("<div class='block-title'>Beschikbaarheid</div>", unsafe_allow_html=True)
        with st.form("avail_form"):
            day = st.selectbox("Dag", ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"])
            c1, c2 = st.columns(2)
            with c1:
                start = st.time_input("Starttijd", pd.Timestamp("09:00").time())
            with c2:
                end = st.time_input("Eindtijd", pd.Timestamp("18:00").time())
            if st.form_submit_button("Opslaan"):
                add_availability(company_id, day, str(start), str(end))
                st.success("Beschikbaarheid toegevoegd!")
                st.rerun()

        avail_df = get_availability(company_id)
        if avail_df.empty:
            st.info("Nog geen beschikbaarheid ingesteld.")
        else:
            st.dataframe(avail_df, use_container_width=True)

    # -------------------
    # 👀 KLANT-PREVIEW (met categorie/dienst-beschrijvingen)
    with tab_preview:
        st.markdown("<div class='block-title'>Zo ziet je klant het</div>", unsafe_allow_html=True)
        services = get_services(company_id)
        cats_df = get_categories(company_id)
        cat_desc_map = {row["name"]: row.get("description", "") for _, row in cats_df.iterrows()}

        if services.empty:
            st.info("Voeg eerst diensten toe in de tab 'Diensten'.")
        else:
            selected_ids = []
            for cat in services["category"].dropna().unique():
                st.markdown(f"### {cat}")
                cdesc = cat_desc_map.get(cat, "")
                if cdesc:
                    st.caption(cdesc)

                sub = services[services["category"] == cat]
                for _, row in sub.iterrows():
                    label = f"{row['name']} — €{row['price']:.2f} • {int(row['duration'])} min"
                    checked = st.checkbox(label, key=f"pv_{row['id']}")
                    if row.get("description"):
                        st.markdown(
                            f"<div class='caption-muted' style='margin-left:28px'>{row['description']}</div>",
                            unsafe_allow_html=True,
                        )
                    if checked:
                        selected_ids.append(int(row["id"]))

            if not selected_ids:
                st.info("Selecteer één of meerdere diensten om te testen.")
                st.stop()

            sel_df = services[services["id"].isin(selected_ids)]
            total_price = float(sel_df["price"].sum())
            total_duration = int(sel_df["duration"].sum())
            st.write(f"**Totaal:** €{total_price:.2f} — {total_duration} min")

            date = st.date_input("Datum", min_value=pd.Timestamp.today())
            slots = get_available_slots_for_duration(company_id, str(date), total_duration)
            if not slots:
                st.warning("Geen tijdslots beschikbaar.")
                st.stop()
            time = st.selectbox("Tijd", slots)

            cname = st.text_input("Naam (test)")
            cphone = st.text_input("Telefoon (test)", "+316...")

            if st.button("📩 Testboeking opslaan"):
                if not cname or not cphone.startswith("+"):
                    st.error("Vul naam en telefoon in.")
                else:
                    bid = add_booking_with_items(company_id, cname, cphone, selected_ids, str(date), time)
                    st.success(f"Testboeking #{bid} aangemaakt.")
                    st.balloons()

    # -------------------
    # 📋 AFSPRAKEN-OVERZICHT
    with tab_bookings:
        st.markdown("<div class='block-title'>Afspraken-overzicht</div>", unsafe_allow_html=True)
        df = get_bookings_overview(company_id)
        if df.empty:
            st.info("Nog geen afspraken.")
        else:
            st.dataframe(
                df.rename(columns={
                    "customer_name": "klant",
                    "total_price": "totaal (€)",
                    "total_duration": "duur (min)"
                }),
                use_container_width=True
            )

    # Uitloggen
    if st.button("🚪 Uitloggen"):
        st.session_state.clear()
        st.rerun()

# -----------------------------
# 3️⃣ PUBLIEKE KLANTENPAGINA (/?company=...)
# -----------------------------
elif company_id_param:
    try:
        company_id_param = int(company_id_param)
    except Exception:
        company_id_param = None

    if not company_id_param:
        st.error("Ongeldige bedrijfspagina.")
        st.stop()

    company = get_company_by_id(company_id_param)
    company_name = company[1] if company else f"Bedrijf #{company_id_param}"

    st.markdown(f"<div class='big-title'>Boek bij {company_name}</div>", unsafe_allow_html=True)

    services = get_services(company_id_param)
    cats_df = get_categories(company_id_param)
    cat_desc_map = {row["name"]: row.get("description", "") for _, row in cats_df.iterrows()}

    if services.empty:
        st.info("Dit bedrijf heeft nog geen diensten toegevoegd.")
        st.stop()

    st.subheader("Kies je diensten")
    selected_ids = []
    for cat in services["category"].dropna().unique():
        st.markdown(f"### {cat}")
        cdesc = cat_desc_map.get(cat, "")
        if cdesc:
            st.caption(cdesc)

        sub = services[services["category"] == cat]
        for _, row in sub.iterrows():
            label = f"{row['name']} — €{row['price']:.2f} • {int(row['duration'])} min"
            checked = st.checkbox(label, key=f"pub_{row['id']}")
            if row.get("description"):
                st.markdown(
                    f"<div class='caption-muted' style='margin-left:28px'>{row['description']}</div>",
                    unsafe_allow_html=True,
                )
            if checked:
                selected_ids.append(int(row["id"]))

    if not selected_ids:
        st.info("Selecteer één of meerdere diensten hierboven.")
        st.stop()

    sel_df = services[services["id"].isin(selected_ids)]
    total_price = float(sel_df["price"].sum())
    total_duration = int(sel_df["duration"].sum())
    st.write(f"**Totaal:** €{total_price:.2f} — {total_duration} min")

    date = st.date_input("Datum", min_value=pd.Timestamp.today())
    times = get_available_slots_for_duration(company_id_param, str(date), total_duration)
    if not times:
        st.warning("Geen beschikbare tijdslots.")
        st.stop()
    time = st.selectbox("Tijd", times)

    name = st.text_input("Naam*")
    phone = st.text_input("Telefoonnummer*", placeholder="+316...")

    if st.button("✅ Bevestig afspraak"):
        if not name or not phone.startswith("+"):
            st.error("Vul naam en telefoonnummer correct in (met +).")
        else:
            booking_id = add_booking_with_items(company_id_param, name, phone, selected_ids, str(date), time)
            names = ", ".join(sel_df["name"].tolist())
            try:
                send_sms(phone, f"Beste {name}, je afspraak bij {company_name} is bevestigd op {date} om {time} — {names}.")
            except Exception as e:
                st.warning(f"Afspraak is bevestigd, maar SMS kon niet worden verzonden: {e}")
            st.success(f"🎉 Afspraak bevestigd! (#{booking_id})")
            st.balloons()
