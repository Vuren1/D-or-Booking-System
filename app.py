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
    # categories & services
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
    # bundles & usage
    get_message_usage_summary,
    add_whatsapp_credits,
    add_sms_credits,
    add_email_limit,
    # stats
    get_customer_stats,
    get_status_overview,
)

APP_LOGO_URL = os.getenv("APP_LOGO_URL", "")

st.set_page_config(
    page_title="D’or Booking System",
    page_icon="💫",
    layout="wide",
)

init_db()


# =============================
# Helpers
# =============================
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


def _get_query_params():
    """Compat wrapper voor nieuwe & oude Streamlit API."""
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()


def _set_query_params(**kwargs):
    try:
        # nieuwe API: hele mapping toewijzen
        st.query_params = {k: str(v) for k, v in kwargs.items() if v is not None}
    except Exception:
        st.experimental_set_query_params(**{k: v for k, v in kwargs.items() if v is not None})


# =============================
# Login / registratie
# =============================
def _select_or_create_company():
    params = _get_query_params()
    raw_company = params.get("company")
    if isinstance(raw_company, list):
        raw_company = raw_company[0]
    param_company = raw_company

    # Als al ingelogd, toon account in sidebar
    if "company_id" in st.session_state:
        cid = st.session_state["company_id"]
        with st.sidebar:
            st.markdown("### Account")
            name = get_company_name_by_id(cid) or "Onbekend bedrijf"
            st.markdown(f"**Ingelogd als:** {name} (#{cid})")
            if st.button("Uitloggen", key="logout_btn_top", use_container_width=True):
                st.session_state.clear()
                _set_query_params()
                st.rerun()
        return cid

    # Inlog via URL (?company=slug of id)
    if param_company:
        row = get_company_by_slug(str(param_company))
        if not row and str(param_company).isdigit():
            try:
                row = get_company(int(param_company))
            except Exception:
                row = None
        if row:
            cid = int(row["id"])
            st.session_state["company_id"] = cid
            return cid

    # Nog niet ingelogd: login/registratie UI in sidebar
    with st.sidebar:
        st.markdown("### Account")
        login_tab, register_tab = st.tabs(["Inloggen", "Nieuw bedrijf"])

        # --- Inloggen ---
        with login_tab:
            login_email = st.text_input("E-mail", key="login_email")
            login_password = st.text_input(
                "Wachtwoord",
                type="password",
                key="login_password",
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
                        _set_query_params(company=slug)
                        _success("Ingelogd.")
                        st.rerun()
                    else:
                        _error("Ongeldig wachtwoord.")

        # --- Nieuw bedrijf ---
        with register_tab:
            reg_name = st.text_input("Bedrijfsnaam", key="reg_name")
            reg_email = st.text_input("E-mail", key="reg_email")
            reg_password = st.text_input(
                "Wachtwoord",
                type="password",
                key="reg_password",
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
                        reg_name.strip(),
                        reg_email.strip(),
                        reg_password,
                    )
                    if cid > 0:
                        st.session_state["company_id"] = cid
                        slug = get_company_slug(cid) or str(cid)
                        _set_query_params(company=slug)
                        _success("Bedrijf aangemaakt.")
                        st.rerun()
                    else:
                        _error(
                            "Kon bedrijf niet aanmaken. Mogelijk bestaat dit e-mailadres al."
                        )

    return None


company_id = _select_or_create_company()
if not company_id:
    # Alleen login/register zichtbaar; rechts plek voor logo / info
    _, col_right = st.columns([1, 2])
    with col_right:
        if APP_LOGO_URL:
            st.image(APP_LOGO_URL, use_column_width=False)
        else:
            st.markdown("## D’or Booking System")
            st.caption(
                "Jouw slimme afspraken & herinneringen platform. "
                "Login of registreer via de linkerkant."
            )
    st.stop()

company_name = get_company_name_by_id(company_id)
company_logo = get_company_logo(company_id)
company_slug = get_company_slug(company_id)
BASE_DOMAIN = os.getenv("BASE_DOMAIN", "dor-booking.com")

# =============================
# Header branding
# =============================
st.caption("Powered by D’or Booking System")

if company_logo:
    # Logo mooi centreren als het pad geldig is
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.image(company_logo, use_column_width=False)
else:
    # Fallback icoon als er nog geen logo is
    st.markdown(
        """
        <div style="text-align:center; margin-top:0.5rem; margin-bottom:1rem;">
            <span style="font-size:40px;">💫</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Titel + publieke link
st.markdown(f"### Beheeromgeving voor **{company_name}**")

if company_slug:
    st.caption(
        "Jouw publieke boekingslink: "
        f"`https://{company_slug}.{BASE_DOMAIN}`"
    )

# =============================
# Sidebar navigatie
# =============================
with st.sidebar:
    st.markdown("### Navigatie")
    if st.button("Beheeromgeving", use_container_width=True):
        _set_query_params(
            company=(company_slug or company_id),
            view="admin",
        )
        st.rerun()
    if st.button("Publieke catalogus", use_container_width=True):
        _set_query_params(
            company=(company_slug or company_id),
            view="public",
        )
        st.rerun()

params = _get_query_params()
view_mode = params.get("view", ["admin"])[0] if isinstance(params.get("view"), list) else params.get("view", "admin")
if not view_mode:
    view_mode = "admin"


# =============================
# Views
# =============================
def render_public_catalog(cid: int):
    st.markdown("### Diensten & tarieven")
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
            ["(geen)"] + (list(cats["name"]) if not cats.empty else []),
        )
        description = st.text_area("Beschrijving (optioneel)")
        publish = st.checkbox("Tonen in publieke catalogus", value=True)

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

    status_df = get_status_overview(cid)
    if not status_df.empty:
        st.markdown("### Status overzicht")
        st.dataframe(status_df, use_container_width=False)

    st.markdown("### Alle boekingen")
    df = get_bookings(cid)
    if df.empty:
        _info("Nog geen boekingen.")
    else:
        st.dataframe(df, use_container_width=True)

    # Extra: klantenanalyse
    cust = get_customer_stats(cid)
    with st.expander("Klanten & historie"):
        if cust.empty:
            _info("Nog geen klantenstatistieken beschikbaar.")
        else:
            st.dataframe(cust, use_container_width=True)


def render_reminders(cid: int):
    st.markdown("## Herinneringen & meldingen")

    settings = get_reminder_settings(cid).iloc[0]

    global_active = st.checkbox(
        "Herinneringen inschakelen",
        value=bool(settings["active"]),
        key="rem_global_active",
    )

    # -------- Herinnering 1: dagen ervoor --------
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

    def _parse_time_str(value: str) -> dtime:
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
        placeholder=(
            "Beste {klantnaam}, dit is een herinnering voor uw afspraak op {datum} om {tijd}."
        ),
        height=70,
        key="rem1_message_sms_input",
    )
    m1_wa = st.text_area(
        "WhatsApp tekst",
        value=str(settings["rem1_message_whatsapp"] or ""),
        placeholder=(
            "Beste {klantnaam}, we zien u graag op {datum} om {tijd}."
        ),
        height=70,
        key="rem1_message_whatsapp_input",
    )
    m1_email = st.text_area(
        "E-mail tekst",
        value=str(settings["rem1_message_email"] or ""),
        placeholder=(
            "Beste {klantnaam},\n\n"
            "Dit is een herinnering voor uw afspraak op {datum} om {tijd}.\n\n"
            "Met vriendelijke groeten,\n{bedrijfsnaam}"
        ),
        height=110,
        key="rem1_message_email_input",
    )

    # -------- Herinnering 2: minuten ervoor --------
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
        placeholder=(
            "Beste {klantnaam}, uw afspraak start om {tijd}. Tot zo!"
        ),
        height=70,
        key="rem2_message_sms_input",
    )
    m2_wa = st.text_area(
        "WhatsApp tekst (zelfde dag)",
        value=str(settings["rem2_message_whatsapp"] or ""),
        placeholder=(
            "Hi {klantnaam}, een korte reminder: uw afspraak begint om {tijd}."
        ),
        height=70,
        key="rem2_message_whatsapp_input",
    )
    m2_email = st.text_area(
        "E-mail tekst (zelfde dag)",
        value=str(settings["rem2_message_email"] or ""),
        placeholder=(
            "Beste {klantnaam},\n\n"
            "Dit is een korte herinnering dat uw afspraak binnenkort start om {tijd}.\n\n"
            "Met vriendelijke groeten,\n{bedrijfsnaam}"
        ),
        height=110,
        key="rem2_message_email_input",
    )

    # -------- Opslaan --------
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
        "Deze instellingen bepalen timing, kanalen en teksten. "
        "WhatsApp/SMS worden alleen verzonden als er voldoende bundeltegoed is "
        "en je externe provider correct is gekoppeld."
    )


def render_bundles_and_usage(cid: int):
    st.markdown("## Bundels & verbruik")

    usage = get_message_usage_summary(cid)
    wc = usage.get("whatsapp_credits", 0)
    sc = usage.get("sms_credits", 0)
    el = usage.get("email_limit", 1000)
    eu = usage.get("email_used", 0)

    st.caption(
        "Basis: D’or Basic bevat o.a. je boekingspagina, agenda en e-mailherinneringen "
        f"(bijvoorbeeld tot {el} e-mails/maand). WhatsApp en SMS werken via bundels."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("WhatsApp-tegoed", f"{wc} berichten")
    col2.metric("SMS-tegoed", f"{sc} berichten")
    col3.metric("E-mail gebruik", f"{eu} / {el}")

    if wc <= 0:
        st.warning(
            "Geen WhatsApp-tegoed: WhatsApp-herinneringen zijn uitgeschakeld totdat je een bundel toevoegt."
        )
    elif wc < 50:
        st.info("Je WhatsApp-tegoed is bijna op. Overweeg een nieuwe bundel.")

    if sc <= 0:
        st.caption("Geen actief SMS-tegoed (optioneel, premium kanaal).")
    elif sc < 50:
        st.info("Je SMS-tegoed is bijna op.")

        st.markdown("---")
    st.markdown("### Tarieven (voorbeeld, aanpasbaar)")

    st.markdown(
        """
        **WhatsApp-bundels**  \\
        - Bundel S (250 berichten): **€15**  \\
        - Bundel M (500 berichten): **€28**  \\
        - Bundel L (1.000 berichten): **€52**

        **SMS-bundels**  \\
        - Bundel S (100 berichten): **€15**  \\
        - Bundel M (250 berichten): **€35**  \\
        - Bundel L (500 berichten): **€65**

        **E-mail**  \\
        - Inclusief in D’or Basic, bijv. tot **1.000 e-mails / maand**.  \\
        - Extra 1.000 e-mails: **€5**

        _Prijzen zijn indicatief en kunnen door jou als beheerder worden aangepast.
        Je klanten betalen alleen voor daadwerkelijke bundels (geen verborgen kosten)._ 
        """
    )


    st.info(
        "Deze bundelknoppen simuleren het toevoegen van tegoed. "
        "In productie koppel je dit aan betalingen (Stripe/Mollie) "
        "of activeer je bundels handmatig per klant."
    )


def render_account(cid: int):
    st.markdown("## Account & abonnement")

    paid = is_company_paid(cid)
    st.markdown(
        f"Status abonnement: {'✅ Actief' if paid else '⏸️ Nog niet geactiveerd (D’or Basic)'}"
    )
    if not paid and st.button("Markeer als actief (admin)", key="activate_account_btn"):
        activate_company(cid)
        _success("Account gemarkeerd als actief.")
        st.rerun()

    st.markdown("### Profiel")
    cur = get_company(cid)

    col1, col2 = st.columns(2)
    new_name = col1.text_input("Bedrijfsnaam", value=cur["name"])
    new_email = col2.text_input("E-mail", value=cur["email"])
    new_pw = st.text_input("Nieuw wachtwoord (optioneel)", type="password")

    if st.button("Profiel opslaan", type="primary", key="save_profile_btn"):
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
        _set_query_params()
        st.rerun()


# =============================
# Routering
# =============================
if view_mode == "public":
    render_public_catalog(company_id)
else:
    tabs = st.tabs(
        [
            "Diensten",
            "Beschikbaarheid",
            "Boekingen",
            "Herinneringen",
            "Bundels & verbruik",
            "Account",
        ]
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
        render_bundles_and_usage(company_id)
    with tabs[5]:
        render_account(company_id)
