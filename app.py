# app.py — D’or Booking System (Streamlit)
# =========================================
# Start lokaal met:  streamlit run app.py

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st
from datetime import date as _date, datetime, timedelta

from database import (
    # init & companies
    init_db,
    get_company_name_by_id,
    add_company,
    get_company_by_email,
    get_company,
    get_company_by_slug,
    get_company_slug,
    activate_company,
    is_company_paid,
    update_company_profile,
    set_company_logo,
    get_company_logo,
    # categories & services
    get_categories,
    add_category,
    get_services,
    add_service,
    update_service,
    delete_service,
    set_service_active,
    get_public_services,
    # availability
    add_availability,
    get_availability,
    # bookings & slots
    get_available_slots_for_duration,
    add_booking_with_items,
    get_bookings_overview,
    get_bookings,
    # reminders
    get_reminder_settings,
    upsert_reminder_settings,
)

# Logo voor de publieke loginpagina (rechts). Pas deze zelf aan.
APP_LOGO_URL = os.getenv("APP_LOGO_URL", "")

# Veilig fallback voor upsert_category
try:
    from database import upsert_category as _upsert_category  # type: ignore
except Exception:
    _upsert_category = None


def upsert_category(company_id: int, name: str, description: str = ""):
    """
    Gebruik database.upsert_category als die bestaat; anders simpele fallback.
    """
    if _upsert_category is not None:
        return _upsert_category(company_id, name, description)

    from database import (
        get_categories as _get_categories,
        add_category as _add_category,
    )

    cats = _get_categories(company_id)
    if not cats.empty and name in list(cats["name"]):
        return
    _add_category(company_id, name, description)


# =========================================
# Init
# =========================================
st.set_page_config(page_title="D’or Booking System", page_icon="💫", layout="wide")
init_db()


# =========================================
# Helpers
# =========================================
def _format_money(x: Any) -> str:
    try:
        return f"€{float(x):.2f}".replace(".", ",")
    except Exception:
        return "€0,00"


def _info(msg: str):
    st.info(msg)


def _success(msg: str):
    st.success(msg)


def _error(msg: str):
    st.error(msg)


# =========================================
# Login / registratie / sessie
# =========================================
def _select_or_create_company() -> int | None:
    """
    Regelt:
    - bestaande sessie
    - inloggen
    - nieuw bedrijf registreren
    - company uit mooie URL (?company=slug)
    """
    params = st.experimental_get_query_params()
    param_company = params.get("company", [None])[0]

    # 1) Bestaande sessie
    if "company_id" in st.session_state:
        cid = st.session_state["company_id"]
        with st.sidebar:
            st.markdown("### Account")
            name = get_company_name_by_id(cid) or "Onbekend bedrijf"
            st.markdown(f"**Ingelogd als:** {name} (#{cid})")
            if st.button("Uitloggen", key="logout_btn", use_container_width=True):
                st.session_state.clear()
                st.experimental_set_query_params()
                st.rerun()
        return cid

    # 2) Company uit URL (slug of numeriek id)
    if param_company:
        value = str(param_company)
        row = get_company_by_slug(value)
        if not row and value.isdigit():
            try:
                row = get_company(int(value))
            except Exception:
                row = None
        if row:
            cid = int(row[0])
            st.session_state["company_id"] = cid
            return cid

    # 3) Login / Registratie UI
    with st.sidebar:
        st.markdown("### Account")
        tabs = st.tabs(["Inloggen", "Nieuw bedrijf"])

        # --- Inloggen ---
        with tabs[0]:
            login_email = st.text_input("E-mail", key="login_email")
            login_password = st.text_input(
                "Wachtwoord", type="password", key="login_password"
            )
            if st.button("Inloggen", use_container_width=True, key="login_btn"):
                row = get_company_by_email(login_email.strip())
                if not row:
                    _error("Onbekende e-mail.")
                else:
                    if login_password and login_password == row[3]:
                        cid = int(row[0])
                        st.session_state["company_id"] = cid
                        slug = get_company_slug(cid) or str(cid)
                        st.experimental_set_query_params(company=slug)
                        _success("Ingelogd.")
                        st.rerun()
                    else:
                        _error("Ongeldig wachtwoord.")

        # --- Nieuw bedrijf ---
        with tabs[1]:
            reg_name = st.text_input("Bedrijfsnaam", key="reg_name")
            reg_email = st.text_input("E-mail", key="reg_email")
            reg_password = st.text_input(
                "Wachtwoord", type="password", key="reg_password"
            )
            if st.button(
                "Aanmaken",
                type="primary",
                use_container_width=True,
                key="create_company",
            ):
                if not reg_name or not reg_email or not reg_password:
                    _error("Vul Bedrijfsnaam, e-mail en wachtwoord in.")
                else:
                    cid = add_company(
                        reg_name.strip(), reg_email.strip(), reg_password
                    )
                    if cid > 0:
                        st.session_state["company_id"] = cid
                        slug = get_company_slug(cid) or str(cid)
                        st.experimental_set_query_params(company=slug)
                        _success("Bedrijf aangemaakt.")
                        st.rerun()
                    else:
                        _error(
                            "Kon bedrijf niet aanmaken. Mogelijk bestaat dit e-mailadres al."
                        )
    return None


# =========================================
# Start app: check login
# =========================================
company_id = _select_or_create_company()
if not company_id:
    # Alleen login/registratie in de sidebar,
    # rechts tonen we een logo of placeholder.
    col_left, col_right = st.columns([1, 2])
    with col_right:
        if APP_LOGO_URL:
            st.image(APP_LOGO_URL, use_column_width=False)
        else:
            st.markdown("## D’or Booking System")
            st.caption(
                "Plaats hier je eigen logo door de variabele `APP_LOGO_URL` in `app.py` aan te passen."
            )
    st.stop()

company_name = get_company_name_by_id(company_id)
company_logo = get_company_logo(company_id)
company_slug = get_company_slug(company_id)

# =========================================
# Header
# =========================================
# Toon bedrijfslogo (indien ingesteld) mooi in het midden bovenaan
if company_logo:
    st.markdown(
        f'<div style="text-align:center; margin-top:0.5rem; margin-bottom:1rem;">'
        f'<img src="{company_logo}" alt="{company_name}" style="max-height:80px;"></div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div style="text-align:center; margin-top:0.5rem; margin-bottom:1rem;">'
        '<span style="font-size:40px;">💫</span>'
        "</div>",
        unsafe_allow_html=True,
    )

st.markdown(f"### Beheeromgeving voor **{company_name}**")
if company_slug:
    st.caption(
        "Jouw publieke boekingslink (deel met klanten): "
        f"`?company={company_slug}&view=public`"
    )

# =========================================
# Sidebar navigatie (alleen na login)
# =========================================
with st.sidebar:
    st.markdown("### Navigatie")
    if st.button("Beheeromgeving", use_container_width=True):
        st.experimental_set_query_params(company=(company_slug or company_id), view="admin")
        st.rerun()
    if st.button("Publieke catalogus bekijken", use_container_width=True):
        st.experimental_set_query_params(company=(company_slug or company_id), view="public")
        st.rerun()

# =========================================
# URL mode: admin of public
# =========================================
params = st.experimental_get_query_params()
view_mode = params.get("view", ["admin"])[0]  # 'admin' of 'public'

# =========================================
# Public catalogus (read-only)
# =========================================
def render_public_catalog(cid: int):
    st.markdown("### Diensten & tarieven (publiek)")
    df = get_public_services(cid)
    if df.empty:
        _info("Er zijn nog geen gepubliceerde diensten.")
        return

    if "category" in df.columns:
        for cat, grp in df.groupby("category"):
            label = str(cat) if str(cat).strip() else "Overige diensten"
            with st.expander(label, expanded=True):
                for _, r in grp.iterrows():
                    st.markdown(
                        f"**{r['name']}** — {_format_money(r['price'])} • {int(r['duration'])} min"
                    )
                    if r.get("description"):
                        st.caption(str(r["description"]))
                    st.divider()
    else:
        tmp = df.copy()
        if "price" in tmp.columns:
            tmp["price"] = tmp["price"].map(_format_money)
        st.table(tmp)


# =========================================
# Admin views
# =========================================
def render_services_admin(cid: int):
    st.markdown("## Diensten beheren")
    cats = get_categories(cid)
    services = get_services(cid)

    with st.expander("Nieuwe dienst toevoegen", expanded=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Naam dienst")
        price = col2.number_input("Prijs", min_value=0.0, step=1.0)
        duration = col1.number_input("Duur (minuten)", min_value=0, step=5)
        category = col2.selectbox(
            "Categorie",
            ["(geen)"] + list(cats["name"]) if not cats.empty else ["(geen)"],
        )
        description = st.text_area("Beschrijving (optioneel)")
        publish = st.checkbox("Publiceren in publieke catalogus", value=True)

        if st.button("Opslaan dienst", type="primary"):
            if not name:
                _error("Naam is verplicht.")
            else:
                cat_val = None if category == "(geen)" else category
                add_service(
                    cid,
                    name,
                    price,
                    duration,
                    cat_val,
                    description,
                    is_active=publish,
                )
                _success("Dienst toegevoegd.")
                st.rerun()

    st.divider()
    st.markdown("#### Huidige diensten")

    cur = services
    if cur.empty:
        _info("Nog geen diensten toegevoegd.")
    else:
        show_cols = [
            c
            for c in cur.columns
            if c in ["id", "name", "price", "duration", "category", "is_active"]
        ]
        pretty = cur[show_cols].copy()
        if "price" in pretty.columns:
            pretty["price"] = pretty["price"].map(_format_money)
        st.dataframe(pretty, use_container_width=True)


def render_availability(cid: int):
    st.markdown("## Beschikbaarheid")
    st.caption("Stel je vaste openingstijden in.")

    days = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
    col1, col2, col3 = st.columns(3)
    day = col1.selectbox("Dag", days)
    start = col2.time_input("Starttijd")
    end = col3.time_input("Eindtijd")

    if st.button("Toevoegen tijdvak", type="primary"):
        add_availability(cid, day, start, end)
        _success("Tijdvak toegevoegd.")
        st.rerun()

    st.divider()
    cur = get_availability(cid)
    if cur.empty:
        _info("Nog geen beschikbaarheid ingesteld.")
    else:
        st.dataframe(cur, use_container_width=True)


def render_bookings(cid: int):
    st.markdown("## Boekingen")
    overview = get_bookings_overview(cid)
    st.dataframe(overview, use_container_width=True)

    st.markdown("#### Alle boekingen (detail)")
    bookings = get_bookings(cid)
    st.dataframe(bookings, use_container_width=True)


def render_account(cid: int):
    st.markdown("## Account & abonnement")

    paid = is_company_paid(cid)
    st.markdown(
        f"Status abonnement: {'✅ Actief' if paid else '⏸️ Nog niet geactiveerd'}"
    )
    if not paid and st.button("Activeer"):
        activate_company(cid)
        _success("Account geactiveerd.")
        st.rerun()

    st.markdown("#### Profiel bijwerken")
    cur = get_company(cid)
    # cur = (id, name, email, password, paid, created_at, slug, logo_path, ...)
    pc1, pc2 = st.columns(2)
    new_name = pc1.text_input("Bedrijfsnaam", value=cur[1] if cur else "")
    new_email = pc2.text_input("E-mail", value=cur[2] if cur else "")
    new_pw = st.text_input("Nieuw wachtwoord (optioneel)", type="password")

    if st.button("Opslaan profiel", type="primary"):
        ok = update_company_profile(cid, new_name, new_email, new_pw or None)
        if ok:
            _success("Profiel opgeslagen.")
            st.rerun()
        else:
            _error("Kon profiel niet opslaan.")

    st.markdown("#### Bedrijfslogo")
    uploaded_logo = st.file_uploader(
        "Upload je bedrijfslogo (PNG/JPG)",
        type=["png", "jpg", "jpeg"],
        key="logo_uploader",
    )
    if uploaded_logo is not None:
        os.makedirs("data/logos", exist_ok=True)
        ext = os.path.splitext(uploaded_logo.name)[1].lower() or ".png"
        logo_path = f"data/logos/company_{cid}{ext}"
        with open(logo_path, "wb") as f:
            f.write(uploaded_logo.getbuffer())
        if set_company_logo(cid, logo_path):
            _success("Logo opgeslagen.")
            st.rerun()
        else:
            _error("Kon logo niet opslaan.")
    elif get_company_logo(cid):
        st.image(
            get_company_logo(cid),
            caption="Huidig logo",
            width=160,
        )

    st.divider()
    if st.button("Uitloggen"):
        st.session_state.clear()
        st.experimental_set_query_params()
        st.rerun()


# =========================================
# Routering tussen admin/public
# =========================================
if view_mode == "public":
    render_public_catalog(company_id)
else:
    tabs = st.tabs(["Diensten", "Beschikbaarheid", "Boekingen", "Account"])
    with tabs[0]:
        render_services_admin(company_id)
    with tabs[1]:
        render_availability(company_id)
    with tabs[2]:
        render_bookings(company_id)
    with tabs[3]:
        render_account(company_id)
