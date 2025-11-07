from __future__ import annotations

import os
from datetime import time as dtime

import streamlit as st

from database import (
    init_db,
    # companies
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
    # services & categories
    get_categories,
    get_services,
    add_service,
    # availability & bookings
    add_availability,
    get_availability,
    get_bookings_overview,
    get_bookings,
    get_public_services,
    # reminders
    get_reminder_settings,
    upsert_reminder_settings,
)

APP_LOGO_URL = os.getenv("APP_LOGO_URL", "")

st.set_page_config(page_title="D’or Booking System", page_icon="💫", layout="wide")
init_db()


def _format_money(x) -> str:
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


# ---------------- Login / registratie ----------------
def _select_or_create_company():
    params = st.experimental_get_query_params()
    param_company = params.get("company", [None])[0]

    # Al ingelogd
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

    # Inloggen via ?company=
    if param_company:
        value = str(param_company)
        row = get_company_by_slug(value)
        if not row and value.isdigit():
            try:
                row = get_company(int(value))
            except Exception:
                row = None
        if row:
            cid = int(row["id"])
            st.session_state["company_id"] = cid
            return cid

    # UI: login / nieuw bedrijf
    with st.sidebar:
        st.markdown("### Account")
        tabs = st.tabs(["Inloggen", "Nieuw bedrijf"])

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
                    if login_password and login_password == row["password"]:
                        cid = int(row["id"])
                        st.session_state["company_id"] = cid
                        slug = get_company_slug(cid) or str(cid)
                        st.experimental_set_query_params(company=slug)
                        _success("Ingelogd.")
                        st.rerun()
                    else:
                        _error("Ongeldig wachtwoord.")

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


company_id = _select_or_create_company()
if not company_id:
    # Alleen login/register + logo
    _, col_right = st.columns([1, 2])
    with col_right:
        if APP_LOGO_URL:
            st.image(APP_LOGO_URL, use_column_width=False)
        else:
            st.markdown("## D’or Booking System")
            st.caption("Pas `APP_LOGO_URL` in app.py aan om hier je logo te tonen.")
    st.stop()

company_name = get_company_name_by_id(company_id)
company_logo = get_company_logo(company_id)
company_slug = get_company_slug(company_id)

# ---------------- Header ----------------
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
        "Publieke boekingslink voor klanten: "
        f"`?company={company_slug}&view=public`"
    )

# ---------------- Sidebar navigatie ----------------
with st.sidebar:
    st.markdown("### Navigatie")
    if st.button("Beheeromgeving", use_container_width=True):
        st.experimental_set_query_params(
            company=(company_slug or company_id),
            view="admin",
        )
        st.rerun()
    if st.button("Publieke catalogus bekijken", use_container_width=True):
        st.experimental_set_query_params(
            company=(company_slug or company_id),
            view="public",
        )
        st.rerun()

params = st.experimental_get_query_params()
view_mode = params.get("view", ["admin"])[0]


# ---------------- Views ----------------
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


def render_services(cid: int):
    st.markdown("## Diensten")
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
    if services.empty:
        _info("Nog geen diensten toegevoegd.")
    else:
        cols = [
            c
            for c in services.columns
            if c in ["id", "name", "price", "duration", "category", "is_active"]
        ]
        df = services[cols].copy()
        if "price" in df.columns:
            df["price"] = df["price"].map(_format_money)
        st.dataframe(df, use_container_width=True)


def render_availability(cid: int):
    st.markdown("## Beschikbaarheid")

    cols = st.columns(3)
    day = cols[0].selectbox(
        "Dag",
        [
            "Maandag",
            "Dinsdag",
            "Woensdag",
            "Donderdag",
            "Vrijdag",
            "Zaterdag",
            "Zondag",
        ],
    )
    start = cols[1].time_input("Starttijd")
    end = cols[2].time_input("Eindtijd")

    if st.button("Tijdvak toevoegen", type="primary"):
        add_availability(cid, day, start, end)
        _success("Tijdvak toegevoegd.")
        st.rerun()

    st.divider()
    df = get_availability(cid)
    if df.empty:
        _info("Nog geen beschikbaarheid ingesteld.")
    else:
        st.dataframe(df, use_container_width=True)


def render_bookings(cid: int):
    st.markdown("## Boekingen")
    overview = get_bookings_overview(cid)
    if not overview.empty:
        st.markdown("### Overzicht per dag")
        st.dataframe(overview, use_container_width=True)

    st.markdown("### Alle boekingen")
    df = get_bookings(cid)
    if df.empty:
        _info("Nog geen boekingen.")
    else:
        st.dataframe(df, use_container_width=True)


def _parse_time_str(value: str) -> dtime:
    try:
        h, m = value.split(":")
        return dtime(int(h), int(m))
    except Exception:
        return dtime(9, 0)


def render_reminders(cid: int):
    st.markdown("## Herinneringen & meldingen")

    settings = get_reminder_settings(cid).iloc[0]

    # Globale schakelaar
    global_active = st.checkbox(
        "Herinneringen inschakelen",
        value=bool(settings["active"]),
        key="rem_global_active",
    )

    # =========================
    # Herinnering 1 - dagen vóór
    # =========================
    st.markdown("---")
    st.markdown("### Herinnering 1 – dagen vóór de afspraak")

    col1, col2 = st.columns(2)
    rem1_days_before = col1.number_input(
        "Aantal dagen vóór afspraak",
        min_value=0,
        max_value=365,
        value=int(settings["rem1_days_before"]),
        key="rem1_days_before_input",
    )
    # tijd-string -> time
    def _parse_time_str(value: str):
        try:
            h, m = value.split(":")
            return dtime(int(h), int(m))
        except Exception:
            return dtime(9, 0)

    rem1_time = col2.time_input(
        "Verzendtijd",
        value=_parse_time_str(str(settings["rem1_time"])),
        key="rem1_time_input",
    )

    ch1_col1, ch1_col2, ch1_col3 = st.columns(3)
    rem1_sms = ch1_col1.checkbox(
        "SMS",
        value=bool(settings["rem1_sms"]),
        key="rem1_sms_checkbox",
    )
    rem1_whatsapp = ch1_col2.checkbox(
        "WhatsApp",
        value=bool(settings["rem1_whatsapp"]),
        key="rem1_whatsapp_checkbox",
    )
    rem1_email = ch1_col3.checkbox(
        "E-mail",
        value=bool(settings["rem1_email"]),
        key="rem1_email_checkbox",
    )

    st.markdown("**Berichtteksten Herinnering 1**")
    m1_sms = st.text_area(
        "SMS tekst",
        value=str(settings["rem1_message_sms"] or ""),
        placeholder="Bijvoorbeeld: Beste {klantnaam}, dit is een herinnering voor uw afspraak op {datum} om {tijd}.",
        height=70,
        key="rem1_message_sms_input",
    )
    m1_wa = st.text_area(
        "WhatsApp tekst",
        value=str(settings["rem1_message_whatsapp"] or ""),
        placeholder="Bijvoorbeeld: Beste {klantnaam}, we zien u graag op {datum} om {tijd}.",
        height=70,
        key="rem1_message_whatsapp_input",
    )
    m1_email = st.text_area(
        "E-mail tekst",
        value=str(settings["rem1_message_email"] or ""),
        placeholder=(
            "Bijvoorbeeld: Beste {klantnaam},\n\n"
            "Dit is een herinnering voor uw afspraak op {datum} om {tijd}.\n\n"
            "Met vriendelijke groeten,\n{bedrijfsnaam}"
        ),
        height=110,
        key="rem1_message_email_input",
    )

    # =========================
    # Herinnering 2 - minuten vóór
    # =========================
    st.markdown("---")
    st.markdown("### Herinnering 2 – minuten vóór de afspraak (zelfde dag)")

    col3, _ = st.columns(2)
    rem2_minutes_before = col3.number_input(
        "Aantal minuten vóór afspraak",
        min_value=0,
        max_value=1440,
        value=int(settings["rem2_minutes_before"]),
        key="rem2_minutes_before_input",
    )

    ch2_col1, ch2_col2, ch2_col3 = st.columns(3)
    rem2_sms = ch2_col1.checkbox(
        "SMS",
        value=bool(settings["rem2_sms"]),
        key="rem2_sms_checkbox",
    )
    rem2_whatsapp = ch2_col2.checkbox(
        "WhatsApp",
        value=bool(settings["rem2_whatsapp"]),
        key="rem2_whatsapp_checkbox",
    )
    rem2_email = ch2_col3.checkbox(
        "E-mail",
        value=bool(settings["rem2_email"]),
        key="rem2_email_checkbox",
    )

    st.markdown("**Berichtteksten Herinnering 2**")
    m2_sms = st.text_area(
        "SMS tekst (zelfde dag)",
        value=str(settings["rem2_message_sms"] or ""),
        placeholder="Bijvoorbeeld: Beste {klantnaam}, uw afspraak start om {tijd}. Tot zo!",
        height=70,
        key="rem2_message_sms_input",
    )
    m2_wa = st.text_area(
        "WhatsApp tekst (zelfde dag)",
        value=str(settings["rem2_message_whatsapp"] or ""),
        placeholder="Bijvoorbeeld: Hi {klantnaam}, een korte reminder: uw afspraak begint om {tijd}.",
        height=70,
        key="rem2_message_whatsapp_input",
    )
    m2_email = st.text_area(
        "E-mail tekst (zelfde dag)",
        value=str(settings["rem2_message_email"] or ""),
        placeholder=(
            "Bijvoorbeeld: Beste {klantnaam},\n\n"
            "Dit is een korte herinnering dat uw afspraak binnenkort start om {tijd}.\n\n"
            "Met vriendelijke groeten,\n{bedrijfsnaam}"
        ),
        height=110,
        key="rem2_message_email_input",
    )

    # =========================
    # Opslaan
    # =========================
    if st.button("Instellingen opslaan", type="primary", key="reminders_save_btn"):
        ok = upsert_reminder_settings(
            cid,
            global_active,
            int(rem1_days_before),
            rem1_time.strftime("%H:%M"),
            rem1_sms,
            rem1_whatsapp,
            rem1_email,
            m1_sms,
            m1_wa,
            m1_email,
            int(rem2_minutes_before),
            rem2_sms,
            rem2_whatsapp,
            rem2_email,
            m2_sms,
            m2_wa,
            m2_email,
        )
        if ok:
            _success("Herinneringsinstellingen opgeslagen.")
        else:
            _error("Kon instellingen niet opslaan.")

    st.info(
        "Alle tijden, kanalen en teksten worden hier per bedrijf opgeslagen. "
        "De daadwerkelijke SMS/WhatsApp/E-mail verzending hangt af van de gekoppelde provider en bundels."
    )

    
def render_account(cid: int):
    st.markdown("## Account & abonnement")

    paid = is_company_paid(cid)
    st.markdown(
        f"Status abonnement: {'✅ Actief' if paid else '⏸️ Nog niet geactiveerd'}"
    )
    if not paid and st.button("Activeer abonnement"):
        activate_company(cid)
        _success("Account geactiveerd.")
        st.rerun()

    st.markdown("### Profiel")
    cur = get_company(cid)

    col1, col2 = st.columns(2)
    new_name = col1.text_input("Bedrijfsnaam", value=cur["name"])
    new_email = col2.text_input("E-mail", value=cur["email"])
    new_pw = st.text_input("Nieuw wachtwoord (optioneel)", type="password")

    if st.button("Profiel opslaan", type="primary"):
        ok = update_company_profile(cid, new_name, new_email, new_pw or None)
        if ok:
            _success("Profiel opgeslagen.")
            st.rerun()
        else:
            _error("Kon profiel niet opslaan.")

    st.markdown("### Bedrijfslogo")
    uploaded_logo = st.file_uploader(
        "Upload logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_uploader"
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
    elif company_logo:
        st.image(company_logo, caption="Huidig logo", width=160)

    st.divider()
    if st.button("Uitloggen", key="logout_btn_bottom"):
        st.session_state.clear()
        st.experimental_set_query_params()
        st.rerun()


# ---------------- Routering ----------------
if view_mode == "public":
    render_public_catalog(company_id)
else:
    tabs = st.tabs(
        ["Diensten", "Beschikbaarheid", "Boekingen", "Herinneringen", "Account"]
    )
    with tabs[0]:
        render_services(company_id)
    with tabs[1]:
        render_availability(company_id)
    with tabs[2]:
        render_bookings(company_id)
    with tabs[3]:
        render_reminders(company_id)
    with tabs[4]:
        render_account(company_id)
