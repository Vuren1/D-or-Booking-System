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

# Optioneel (als je ze hebt toegevoegd in database.py)
try:
    from database import update_service, delete_service
except Exception:
    update_service = None
    delete_service = None

from payment import create_checkout_session, check_payment
from twilio_sms import send_sms


# -----------------------------
# INIT + PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="D'or Booking System", layout="wide")
init_db()

# Styling
st.markdown("""
<style>
.big-title {font-weight:800;font-size:38px;text-align:center;color:#FFD166;margin:8px 0 26px 0;}
.block-title {font-weight:700;font-size:22px;margin:8px 0 10px 0;color:#FFD166;}
.caption-muted {color:#b8b8b8;}
.expander > div > div {padding-top:4px;padding-bottom:8px;}
.service-row {padding:6px 8px;border-radius:8px;background:rgba(255,255,255,0.03);margin:4px 0;}
.service-label {font-size:16px;font-weight:600;}
.service-desc {color:#b8b8b8;margin-left:6px;}
</style>
""", unsafe_allow_html=True)

# Query parameters
query = st.experimental_get_query_params()
session_id = query.get("session_id", [None])[0]
company_id_param = query.get("company", [None])[0]


# -----------------------------
# 1) REGISTRATIE & LOGIN
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
# 2) DASHBOARD
# -----------------------------
elif "logged_in" in st.session_state and not company_id_param:
    company_id = st.session_state.company_id
    company_name = st.session_state.company_name

    # Terug van Stripe?
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.success("✅ Betaling gelukt! Dashboard geactiveerd.")
        st.rerun()

    if not is_company_paid(company_id):
        st.error("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        try:
            email = get_company_by_id(company_id)[2]
            checkout_url = create_checkout_session(company_id, email, company_name)
            st.markdown(f"[💳 Betaal hier (€25/maand)]({checkout_url})")
        except Exception as e:
            st.warning(f"Stripe error: {e}")
        st.stop()

    st.markdown(f"<div class='big-title'>Welkom, {company_name}</div>", unsafe_allow_html=True)

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
            Je klanten zien deze indeling ingeklapt per categorie. Checkboxen staan rechts van elke dienst.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -------------------
    # 💅 DIENSTEN (add + edit + delete)
    with tab_services:
        st.markdown("<div class='block-title'>Diensten</div>", unsafe_allow_html=True)

        cats_df = get_categories(company_id)
        cat_desc_map = {row["name"]: row.get("description", "") for _, row in cats_df.iterrows()}
        existing_cats = ["Algemeen"] + [c for c in sorted(cat_desc_map.keys()) if c != "Algemeen"]

        # 1) Toevoegen
        with st.form("add_service_form"):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                name = st.text_input("Naam", placeholder="Bijv. Pedicure Basic")
            with c2:
                price = st.number_input("Prijs (€)", min_value=0.0, step=0.05, value=0.0)
            with c3:
                duration = st.number_input("Duur (minuten)", min_value=5, step=5, value=30)
            with c4:
                category = st.selectbox("Categorie", options=existing_cats + ["+ Nieuwe categorie..."])

            service_desc = st.text_area(
                "Beschrijving (dienst, optioneel)",
                placeholder="Bijv. Voetbad, nagels knippen en vijlen, voetmassage (5min)",
                height=90,
            )

            # Nieuwe of bestaande categorie
            if category == "+ Nieuwe categorie...":
                new_cat = st.text_input("Nieuwe categorie-naam", placeholder="Bijv. Pedicure Pakket")
                cat_desc = st.text_area(
                    "Beschrijving categorie (optioneel)",
                    placeholder="Bijv. Samengestelde pedicure pakketten...",
                    height=80,
                )
                final_cat = (new_cat or "Algemeen").strip()
            else:
                final_cat = category
                cat_desc = st.text_area(
                    "Categorie-beschrijving (bewerken, optioneel)",
                    value=cat_desc_map.get(category, ""),
                    height=80,
                )

            if st.form_submit_button("➕ Toevoegen"):
                if not name.strip():
                    st.warning("Vul een naam in.")
                else:
                    upsert_category(company_id, final_cat, cat_desc or "")
                    add_service(company_id, name.strip(), price, int(duration), final_cat, service_desc.strip())
                    st.success("Dienst toegevoegd.")
                    st.rerun()

        services_df = get_services(company_id)

        # 2) Bewerken / Verwijderen
        st.markdown("### Bewerken of verwijderen")
        if services_df.empty:
            st.info("Nog geen diensten.")
        else:
            id_to_label = {int(r["id"]): f'{r["name"]}  (cat: {r["category"]})' for _, r in services_df.iterrows()}
            sel_id = st.selectbox("Kies dienst", options=list(id_to_label.keys()), format_func=lambda i: id_to_label[i])

            row = services_df[services_df["id"] == sel_id].iloc[0]
            with st.form("edit_service_form"):
                ec1, ec2, ec3, ec4 = st.columns([2, 1, 1, 1])
                with ec1:
                    e_name = st.text_input("Naam", value=row["name"])
                with ec2:
                    e_price = st.number_input("Prijs (€)", min_value=0.0, step=0.05, value=float(row["price"]))
                with ec3:
                    e_duration = st.number_input("Duur (minuten)", min_value=5, step=5, value=int(row["duration"]))
                with ec4:
                    e_category = st.selectbox("Categorie", options=existing_cats + ["+ Nieuwe categorie..."], index=existing_cats.index(row["category"]) if row["category"] in existing_cats else len(existing_cats))

                e_desc = st.text_area("Beschrijving (dienst)", value=row.get("description", "") or "", height=90)

                # Categorie-beschrijving
                if e_category == "+ Nieuwe categorie...":
                    e_new_cat = st.text_input("Nieuwe categorie-naam", placeholder="Nieuwe categorie")
                    e_cat_desc = st.text_area("Categorie-beschrijving", value="", height=80)
                    e_final_cat = e_new_cat.strip() or "Algemeen"
                else:
                    e_final_cat = e_category
                    e_cat_desc = st.text_area("Categorie-beschrijving", value=cat_desc_map.get(e_category, ""), height=80)

                update_btn, delete_btn = st.columns([1,1])
                do_update = update_btn.form_submit_button("💾 Opslaan")
                do_delete = delete_btn.form_submit_button("🗑 Verwijderen")

            if do_update:
                if update_service is None:
                    st.error("update_service ontbreekt in database.py")
                else:
                    upsert_category(company_id, e_final_cat, e_cat_desc or "")
                    update_service(sel_id, e_name.strip(), float(e_price), int(e_duration), e_final_cat, e_desc.strip())
                    st.success("Dienst bijgewerkt.")
                    st.rerun()

            if do_delete:
                if delete_service is None:
                    st.error("delete_service ontbreekt in database.py")
                else:
                    delete_service(sel_id)
                    st.success("Dienst verwijderd.")
                    st.rerun()

            st.markdown("### Alle diensten")
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
    # 👀 KLANT-PREVIEW (ingeklapte categorieën + checkbox rechts)
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
                with st.expander(cat, expanded=False):
                    cdesc = cat_desc_map.get(cat, "")
                    if cdesc:
                        st.caption(cdesc)

                    sub = services[services["category"] == cat]
                    for _, row in sub.iterrows():
                        c1, c2 = st.columns([0.92, 0.08])
                        with c1:
                            st.markdown(f"<div class='service-row'><div class='service-label'>{row['name']} — €{row['price']:.2f} • {int(row['duration'])} min</div>", unsafe_allow_html=True)
                            if row.get("description"):
                                st.markdown(f"<div class='service-desc'>{row['description']}</div></div>", unsafe_allow_html=True)
                            else:
                                st.markdown("</div>", unsafe_allow_html=True)
                        with c2:
                            checked = st.checkbox("", key=f"pv_{row['id']}")
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
# 3) PUBLIEKE KLANTENPAGINA (/?company=...)
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

    # Ingekapt per categorie + checkbox rechts
    for cat in services["category"].dropna().unique():
        with st.expander(cat, expanded=False):
            cdesc = cat_desc_map.get(cat, "")
            if cdesc:
                st.caption(cdesc)

            sub = services[services["category"] == cat]
            for _, row in sub.iterrows():
                c1, c2 = st.columns([0.92, 0.08])
                with c1:
                    st.markdown(f"<div class='service-row'><div class='service-label'>{row['name']} — €{row['price']:.2f} • {int(row['duration'])} min</div>", unsafe_allow_html=True)
                    if row.get("description"):
                        st.markdown(f"<div class='service-desc'>{row['description']}</div></div>", unsafe_allow_html=True)
                    else:
                        st.markdown("</div>", unsafe_allow_html=True)
                with c2:
                    checked = st.checkbox("", key=f"pub_{row['id']}")
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
