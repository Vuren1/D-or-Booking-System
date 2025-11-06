# app.py — D’or Booking System (Streamlit)
# =========================================
# Vereist: database.py zoals eerder opgeleverd, plus `pip install streamlit pandas`
# Start lokaal met:  streamlit run app.py

from __future__ import annotations

import os
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from datetime import date as _date, datetime, timedelta

# ---- Database laag
from database import (
    # init & companies
    init_db, get_company_name_by_id, add_company, get_company_by_email, get_company,
    activate_company, is_company_paid, update_company_profile,
    # categories & services
    get_categories, add_category, upsert_category, get_services, add_service, update_service, delete_service,
    set_service_active, get_public_services,
    # availability
    add_availability, get_availability,
    # bookings & slots
    get_available_slots_for_duration, add_booking_with_items,
    get_bookings_overview, get_bookings,
    # reminders
    get_reminder_settings, upsert_reminder_settings,
)

# =========================================
# Init
# =========================================
st.set_page_config(page_title="D’or Booking System", page_icon="💫", layout="wide")
init_db()  # migraties/PRAGMA/indexes

# =========================================
# Helpers
# =========================================
def _format_money(x: Any) -> str:
    try:
        return f"€{float(x):.2f}".replace(".", ",")
    except Exception:
        return "€0,00"

def _date_to_str(d: _date) -> str:
    return d.strftime("%Y-%m-%d")

def _success(msg: str):
    st.success(msg, icon="✅")

def _error(msg: str):
    st.error(msg, icon="❌")

def _info(msg: str):
    st.info(msg, icon="ℹ️")

# =========================================
# Auth / Company context (simpel & duidelijk)
# =========================================
def _select_or_create_company() -> int | None:
    params = st.experimental_get_query_params()
    param_company = params.get("company", [None])[0]

    with st.sidebar:
        st.markdown("### Account")
        if "company_id" in st.session_state:
            cid = st.session_state["company_id"]
            name = get_company_name_by_id(cid)
            st.markdown(f"**Ingelogd als:** {name} (#{cid})")
            if st.button("Uitloggen"):
                st.session_state.clear()
                st.experimental_set_query_params()
                st.rerun()
            return cid

        # 1) via URL parameter
        if param_company and str(param_company).isdigit():
            st.session_state["company_id"] = int(param_company)
            return st.session_state["company_id"]

        # 2) eenvoudig login/aanmaak
        tabs = st.tabs(["Inloggen", "Nieuw bedrijf"])
        with tabs[0]:
            email = st.text_input("E-mail")
            password = st.text_input("Wachtwoord", type="password")
            if st.button("Inloggen", use_container_width=True):
                row = get_company_by_email(email.strip())
                if not row:
                    _error("Onbekende e-mail.")
                else:
                    # row = (id, name, email, password, paid, created_at)
                    if password and password == row[3]:
                        st.session_state["company_id"] = int(row[0])
                        _success("Ingelogd.")
                        st.experimental_set_query_params(company=str(row[0]))
                        st.rerun()
                    else:
                        _error("Onjuist wachtwoord.")

        with tabs[1]:
            name = st.text_input("Bedrijfsnaam")
            email = st.text_input("E-mail (login)")
            password = st.text_input("Wachtwoord", type="password")
            if st.button("Aanmaken", type="primary", use_container_width=True, key="create_company"):
                if not name or not email or not password:
                    _error("Vul naam, e-mail en wachtwoord in.")
                else:
                    cid = add_company(name.strip(), email.strip(), password)
                    if cid > 0:
                        st.session_state["company_id"] = cid
                        _success("Bedrijf aangemaakt.")
                        st.experimental_set_query_params(company=str(cid))
                        st.rerun()
                    else:
                        _error("Kon bedrijf niet aanmaken.")
    return None

company_id = _select_or_create_company()
if not company_id:
    st.stop()

company_name = get_company_name_by_id(company_id)

# =========================================
# Sidebar: snelle navigatie
# =========================================
with st.sidebar:
    st.markdown("### Navigatie")
    if st.button("Bekijk publieke catalogus", use_container_width=True):
        params = st.experimental_get_query_params()
        params["view"] = ["public"]
        params["company"] = [str(company_id)]
        st.experimental_set_query_params(**params)
        st.rerun()

# =========================================
# URL mode: public vs admin
# =========================================
params = st.experimental_get_query_params()
view_mode = params.get("view", ["admin"])[0]  # 'admin' of 'public'

# =========================================
# Header
# =========================================
colA, colB = st.columns([1, 3], vertical_alignment="center")
with colA:
    st.image("https://static-00.iconduck.com/assets.00/sparkles-emoji-512x512-3jn4x2cw.png", width=64)
with colB:
    st.markdown(f"## Welkom, **{company_name}**")

# =========================================
# Public catalogus (read-only) — geen selectievakjes/boeken
# =========================================
def render_public_catalog(cid: int):
    st.markdown("### Diensten & tarieven")
    df = get_public_services(cid)
    if df.empty:
        _info("Er zijn nog geen gepubliceerde diensten.")
        return

    for cat, grp in df.groupby(df["category"].fillna("Algemeen")):
        with st.expander(cat, expanded=True):
            for _, r in grp.iterrows():
                st.markdown(f"**{r['name']}** — {_format_money(r['price'])} • {int(r['duration'])} min")
                if r.get("description"):
                    st.caption(r["description"])
                st.divider()

if view_mode == "public":
    st.info("Publieke weergave (alleen lezen).", icon="🌐")
    if st.button("⤺ Terug naar beheer"):
        params["view"] = ["admin"]
        st.experimental_set_query_params(**params)
        st.rerun()
    render_public_catalog(company_id)
    st.stop()

# =========================================
# Tabs (beheer + klant preview)
# =========================================
tab_overview, tab_services, tab_availability, tab_reminders, tab_client, tab_appointments, tab_account = st.tabs(
    ["Overzicht", "Diensten", "Beschikbaarheid", "Herinneringen", "Klant-preview", "Afspraken", "Account"]
)

# -----------------------------------------
# Overzicht
# -----------------------------------------
with tab_overview:
    st.subheader("Overzicht")
    # Kennismaking + wat cijfers
    cur_services = get_services(company_id)
    cur_bookings = get_bookings_overview(company_id)

    m1, m2, m3 = st.columns(3)
    m1.metric("Diensten", len(cur_services))
    m2.metric("Afspraken", len(cur_bookings))
    total_rev = cur_bookings["total_price"].sum() if not cur_bookings.empty else 0
    m3.metric("Totale omzet", _format_money(total_rev))

    st.markdown("#### Laatste afspraken")
    if cur_bookings.empty:
        _info("Nog geen afspraken.")
    else:
        df = cur_bookings.copy()
        df["total_price"] = df["total_price"].map(_format_money)
        st.dataframe(df, use_container_width=True)

# -----------------------------------------
# Diensten (beheer)
# -----------------------------------------
with tab_services:
    st.subheader("Diensten (beheer)")

    cats_df = get_categories(company_id)
    cat_options = ["Algemeen"] + (cats_df["name"].tolist() if not cats_df.empty else [])

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    sv_name = c1.text_input("Naam", placeholder="Bijv. Pedicure Basic")
    sv_price = c2.number_input("Prijs (€)", min_value=0.0, step=0.50, value=0.0)
    sv_dur = c3.number_input("Duur (minuten)", min_value=5, step=5, value=30)
    pick_cat = c4.selectbox(
        "Categorie",
        options=["Algemeen", "Nieuwe categorie…"] + (cats_df["name"].tolist() if not cats_df.empty else []),
    )

    new_cat_name, new_cat_desc = None, ""
    if pick_cat == "Nieuwe categorie…":
        st.info("Nieuwe categorie", icon="🗂️")
        new_cat_name = st.text_input("Categorie naam", placeholder="Bijv. Deelbehandelingen")
        new_cat_desc = st.text_area("Categorie beschrijving (optioneel)", placeholder="Deze groep bevat…")

    sv_desc = st.text_area(
        "Beschrijving (opt.)",
        placeholder="Bijv. Voetbad, nagels knippen en vijlen, voetmassage (5min)"
    )

    if st.button("➕ Toevoegen", type="primary"):
        if not sv_name:
            _error("Vul een dienstnaam in.")
        else:
            final_cat = pick_cat
            if pick_cat == "Nieuwe categorie…" and new_cat_name:
                upsert_category(company_id, new_cat_name, new_cat_desc)
                final_cat = new_cat_name
            add_service(company_id, sv_name, sv_price, sv_dur, final_cat, sv_desc)
            _success("Dienst toegevoegd.")
            st.rerun()

    st.divider()
    st.markdown("#### Huidige diensten")

    cur = get_services(company_id)
    if cur.empty:
        _info("Nog geen diensten toegevoegd.")
    else:
        # Probeer is_active te tonen indien kolom aanwezig
        show_cols = [c for c in cur.columns if c in ["id","name","price","duration","category","is_active"]]
        pretty = cur[show_cols].copy()
        if "price" in pretty.columns:
            pretty["price"] = pretty["price"].map(_format_money)
        st.dataframe(pretty, use_container_width=True)

        with st.expander("✏️ Bewerken of verwijderen", expanded=False):
            ids = cur["id"].tolist()
            edit_id = st.selectbox(
                "Kies dienst",
                options=ids,
                format_func=lambda x: f"{x} – {cur[cur['id'] == x]['name'].iloc[0]}"
            )

            row = cur[cur["id"] == edit_id].iloc[0]
            ec1, ec2, ec3, ec4 = st.columns([2, 1, 1, 1])

            e_name = ec1.text_input("Naam", value=row["name"], key=f"name_{row['id']}")
            e_price = ec2.number_input("Prijs (€)", value=float(row["price"]), key=f"price_{row['id']}")
            e_dur = ec3.number_input(
                "Duur (minuten)",
                min_value=5, step=5, value=int(row["duration"]),
                key=f"dur_{row['id']}"
            )
            e_cat = ec4.selectbox(
                "Categorie",
                options=cat_options,
                index=(cat_options.index(row["category"]) if row["category"] in cat_options else 0)
            )
            e_desc = st.text_area("Beschrijving", value=row.get("description") or "", height=90)

            # Zichtbaarheids-toggle
            active_val = True
            if "is_active" in row.index and pd.notna(row["is_active"]):
                try:
                    active_val = bool(int(row["is_active"]))
                except Exception:
                    active_val = True
            e_active = st.checkbox("Zichtbaar voor klanten", value=active_val, key=f"act_{row['id']}")

            bc1, bc2, bc3 = st.columns([1, 1, 1])
            if bc1.button("Opslaan wijzigingen", type="primary", key=f"save_{row['id']}"):
                update_service(edit_id, e_name, e_price, e_dur, e_cat, e_desc)
                set_service_active(edit_id, e_active)
                _success("Dienst bijgewerkt.")
                st.rerun()
            if bc2.button("❌ Verwijderen", key=f"del_{row['id']}"):
                delete_service(edit_id)
                _success("Dienst verwijderd.")
                st.rerun()
            if bc3.button("👀 Bekijk als klant", key=f"pub_{row['id']}"):
                params["view"] = ["public"]
                params["company"] = [str(company_id)]
                st.experimental_set_query_params(**params)
                st.rerun()

# -----------------------------------------
# Beschikbaarheid (beheer)
# -----------------------------------------
with tab_availability:
    st.subheader("Beschikbaarheid")
    days = ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"]

    ac1, ac2, ac3 = st.columns(3)
    day = ac1.selectbox("Dag", options=days)
    start = ac2.time_input("Start", value=datetime.strptime("09:00","%H:%M").time())
    end = ac3.time_input("Einde", value=datetime.strptime("17:00","%H:%M").time())

    if st.button("➕ Toevoegen tijdvenster"):
        if end <= start:
            _error("Einde moet na start liggen.")
        else:
            add_availability(company_id, day, start.strftime("%H:%M"), end.strftime("%H:%M"))
            _success("Tijdvenster toegevoegd.")
            st.rerun()

    st.markdown("#### Huidige beschikbaarheid")
    avail = get_availability(company_id)
    if avail.empty:
        _info("Nog geen beschikbaarheid ingesteld.")
    else:
        st.dataframe(avail, use_container_width=True)

# -----------------------------------------
# Herinneringen (beheer)
# -----------------------------------------
with tab_reminders:
    st.subheader("Herinneringen")
    cfg = get_reminder_settings(company_id)

    rc1, rc2, rc3 = st.columns(3)
    enabled = rc1.checkbox("Herinneringen aan", value=bool(cfg["enabled"]))
    sms_enabled = rc2.checkbox("SMS", value=bool(cfg["sms_enabled"]))
    wa_enabled = rc3.checkbox("WhatsApp", value=bool(cfg["whatsapp_enabled"]))

    rc4, rc5, rc6 = st.columns(3)
    days_before = rc4.number_input("Dagen vooraf", min_value=0, max_value=14, value=int(cfg["days_before"]))
    send_time = rc5.text_input("Verzendtijd (HH:MM)", value=cfg["send_time"] or "09:00")
    tz = rc6.text_input("Tijdzone", value=cfg["tz"] or "Europe/Brussels")

    rc7, rc8 = st.columns(2)
    same_day_enabled = rc7.checkbox("Zelfde dag herinnering", value=bool(cfg["same_day_enabled"]))
    same_day_minutes_before = rc8.number_input("Minuten vooraf (zelfde dag)", min_value=0, max_value=600,
                                               value=int(cfg["same_day_minutes_before"]))

    st.markdown("**Templates (optioneel)**")
    t1 = st.text_area("SMS (dag ervoor)", value=cfg.get("template_day_before_sms") or "")
    t2 = st.text_area("SMS (zelfde dag)", value=cfg.get("template_same_day_sms") or "")
    t3 = st.text_area("WhatsApp (dag ervoor)", value=cfg.get("template_day_before_wa") or "")
    t4 = st.text_area("WhatsApp (zelfde dag)", value=cfg.get("template_same_day_wa") or "")

    if st.button("Opslaan", type="primary"):
        upsert_reminder_settings(
            company_id=company_id,
            enabled=int(enabled),
            sms_enabled=int(sms_enabled),
            whatsapp_enabled=int(wa_enabled),
            days_before=int(days_before),
            send_time=send_time,
            same_day_enabled=int(same_day_enabled),
            same_day_minutes_before=int(same_day_minutes_before),
            tz=tz,
            template_day_before_sms=t1 or None,
            template_same_day_sms=t2 or None,
            template_day_before_wa=t3 or None,
            template_same_day_wa=t4 or None,
        )
        _success("Herinneringen opgeslagen.")

# -----------------------------------------
# Klant-preview (boeken)
# -----------------------------------------
with tab_client:
    st.subheader("Klant-preview (boeken)")
    # Lijst van publieke services (zichtbaar=1)
    pub = get_public_services(company_id)
    if pub.empty:
        _info("Er zijn nog geen gepubliceerde diensten. Zet in Diensten ‘Zichtbaar voor klanten’ aan.")
    else:
        selected_items: List[Dict[str, Any]] = []
        total_price = 0.0
        total_minutes = 0

        st.markdown("#### Kies je dienst(en)")
        for cat, grp in pub.groupby(pub["category"].fillna("Algemeen")):
            with st.expander(cat, expanded=True):
                for _, r in grp.iterrows():
                    chk = st.checkbox(
                        f"{r['name']} — {_format_money(r['price'])} • {int(r['duration'])} min",
                        key=f"svc_{r['id']}"
                    )
                    if chk:
                        selected_items.append({
                            "service_id": int(r["id"]),
                            "name": r["name"],
                            "price": float(r["price"]),
                            "duration": int(r["duration"]),
                        })
                        total_price += float(r["price"])
                        total_minutes += int(r["duration"])

        if not selected_items:
            _info("Selecteer één of meerdere diensten om tijdsloten te zien.")
        else:
            st.markdown(f"**Geselecteerd:** {_format_money(total_price)} • {total_minutes} min")

            d = st.date_input("Datum", value=_date.today())
            sel_date = _date_to_str(d)

            slots = get_available_slots_for_duration(company_id, sel_date, total_minutes)
            if not slots:
                _info("Geen beschikbare tijdsloten voor deze datum.")
            else:
                slot = st.selectbox("Beschikbare tijdsloten", options=slots)
                cc1, cc2 = st.columns([2, 1])
                cust_name = cc1.text_input("Naam")
                cust_phone = cc2.text_input("Telefoon")

                if st.button("Bevestig afspraak", type="primary"):
                    if not cust_name or not cust_phone:
                        _error("Vul naam en telefoon in.")
                    else:
                        try:
                            # Plaats boeking (met snapshot van items)
                            booking_id = add_booking_with_items(
                                company_id, cust_name, cust_phone, sel_date, slot, selected_items
                            )
                            _success(f"Afspraak bevestigd (#{booking_id}) op {sel_date} om {slot}.")
                            st.balloons()
                        except Exception as e:
                            _error(f"Kon afspraak niet plaatsen: {e}")

# -----------------------------------------
# Afspraken-overzicht
# -----------------------------------------
with tab_appointments:
    st.subheader("Afspraken-overzicht")
    bok = get_bookings_overview(company_id)
    if bok.empty:
        _info("Nog geen afspraken.")
    else:
        df = bok.copy()
        df["total_price"] = df["total_price"].map(_format_money)
        st.dataframe(df, use_container_width=True)

# -----------------------------------------
# Account
# -----------------------------------------
with tab_account:
    st.subheader("Account")
    paid = is_company_paid(company_id)
    st.write("Status:", "✅ Actief" if paid else "⏸️ Nog niet geactiveerd")
    if not paid and st.button("Activeer"):
        activate_company(company_id)
        _success("Account geactiveerd.")
        st.rerun()

    st.markdown("#### Profiel bijwerken")
    cur = get_company(company_id)
    # cur = (id, name, email, password, paid, created_at)
    pc1, pc2 = st.columns(2)
    new_name = pc1.text_input("Bedrijfsnaam", value=cur[1] if cur else "")
    new_email = pc2.text_input("E-mail", value=cur[2] if cur else "")
    new_pw = st.text_input("Nieuw wachtwoord (optioneel)", type="password")

    if st.button("Opslaan profiel", type="primary"):
        ok = update_company_profile(company_id, new_name, new_email, new_pw or None)
        if ok:
            _success("Profiel opgeslagen.")
            st.rerun()
        else:
            _error("Kon profiel niet opslaan.")

    st.divider()
    if st.button("Uitloggen"):
        st.session_state.clear()
        st.experimental_set_query_params()
        st.rerun()
