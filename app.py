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
    # AI / AI Telefoniste
    get_company_ai_settings,
    set_company_ai_enabled,
    set_company_ai_phone_number,
    update_company_ai_line,
    update_company_ai_safeguards,
    get_ai_local_minutes_balance,
    add_ai_local_minutes,
    update_company_ai_instructions,
)

APP_LOGO_URL = os.getenv("APP_LOGO_URL", "")


st.set_page_config(
    page_title="D’or Booking System",
    page_icon="💫",
    layout="wide",
)

# AI Telefoniste configuratie
PREMIUM_AI_0900_RATE_EUR = 0.10   # tarief dat bellers betalen via 0900
LOCAL_AI_INCLUDED_MINUTES = 200   # inbegrepen minuten bij lokaal nummer add-on
LOCAL_AI_EXTRA_RATE_EUR = 0.15    # tarief voor extra minuten bij lokaal nummer

init_db()


# =============================
# Helpers
# =============================
def _parse_time_str(value: str) -> dtime:
    try:
        h, m = str(value).split(":")
        return dtime(int(h), int(m))
    except Exception:
        return dtime(9, 0)

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

    settings_df = get_reminder_settings(cid)
    if settings_df is None or settings_df.empty:
        settings = {}
    else:
        settings = settings_df.iloc[0].to_dict()

    # veilige defaults
    active = bool(settings.get("active", 0))
    rem1_days_before = int(settings.get("rem1_days_before", 1))
    rem1_time_str = settings.get("rem1_time", "09:00")
    rem1_sms = bool(settings.get("rem1_sms", 0))
    rem1_whatsapp = bool(settings.get("rem1_whatsapp", 1))
    rem1_email = bool(settings.get("rem1_email", 1))
    rem1_message_sms = settings.get("rem1_message_sms") or ""
    rem1_message_whatsapp = settings.get("rem1_message_whatsapp") or ""
    rem1_message_email = settings.get("rem1_message_email") or ""

    rem2_minutes_before = int(settings.get("rem2_minutes_before", 60))
    rem2_sms = bool(settings.get("rem2_sms", 0))
    rem2_whatsapp = bool(settings.get("rem2_whatsapp", 0))
    rem2_email = bool(settings.get("rem2_email", 1))
    rem2_message_sms = settings.get("rem2_message_sms") or ""
    rem2_message_whatsapp = settings.get("rem2_message_whatsapp") or ""
    rem2_message_email = settings.get("rem2_message_email") or ""

    # Globale schakelaar
    global_active = st.checkbox(
        "Herinneringen inschakelen",
        value=active,
        key="rem_global_active",
    )

    st.markdown("---")
    st.markdown("### Herinnering 1 – dagen vóór de afspraak")

    col1, col2 = st.columns(2)
    rem1_days_before_new = col1.number_input(
        "Aantal dagen vóór afspraak",
        min_value=0,
        max_value=365,
        value=rem1_days_before,
        key="rem1_days_before_input",
    )
    rem1_time_new = col2.time_input(
        "Verzendtijd",
        value=_parse_time_str(rem1_time_str),
        key="rem1_time_input",
    )

    ch1_col1, ch1_col2, ch1_col3 = st.columns(3)
    rem1_sms_new = ch1_col1.checkbox(
        "SMS",
        value=rem1_sms,
        key="rem1_sms_checkbox",
    )
    rem1_whatsapp_new = ch1_col2.checkbox(
        "WhatsApp",
        value=rem1_whatsapp,
        key="rem1_whatsapp_checkbox",
    )
    rem1_email_new = ch1_col3.checkbox(
        "E-mail",
        value=rem1_email,
        key="rem1_email_checkbox",
    )

    st.markdown("**Berichtteksten Herinnering 1**")
    m1_sms_new = st.text_area(
        "SMS tekst",
        value=rem1_message_sms,
        placeholder="Beste {klantnaam}, dit is een herinnering voor uw afspraak op {datum} om {tijd}.",
        height=70,
        key="rem1_message_sms_input",
    )
    m1_wa_new = st.text_area(
        "WhatsApp tekst",
        value=rem1_message_whatsapp,
        placeholder="Beste {klantnaam}, we zien u graag op {datum} om {tijd}.",
        height=70,
        key="rem1_message_whatsapp_input",
    )
    m1_email_new = st.text_area(
        "E-mail tekst",
        value=rem1_message_email,
        placeholder=(
            "Beste {klantnaam},\n\n"
            "Dit is een herinnering voor uw afspraak op {datum} om {tijd}.\n\n"
            "Met vriendelijke groeten,\n{bedrijfsnaam}"
        ),
        height=110,
        key="rem1_message_email_input",
    )

    st.markdown("---")
    st.markdown("### Herinnering 2 – minuten vóór de afspraak (zelfde dag)")

    col3, _ = st.columns(2)
    rem2_minutes_before_new = col3.number_input(
        "Aantal minuten vóór afspraak",
        min_value=0,
        max_value=1440,
        value=rem2_minutes_before,
        key="rem2_minutes_before_input",
    )

    ch2_col1, ch2_col2, ch2_col3 = st.columns(3)
    rem2_sms_new = ch2_col1.checkbox(
        "SMS",
        value=rem2_sms,
        key="rem2_sms_checkbox",
    )
    rem2_whatsapp_new = ch2_col2.checkbox(
        "WhatsApp",
        value=rem2_whatsapp,
        key="rem2_whatsapp_checkbox",
    )
    rem2_email_new = ch2_col3.checkbox(
        "E-mail",
        value=rem2_email,
        key="rem2_email_checkbox",
    )

    st.markdown("**Berichtteksten Herinnering 2**")
    m2_sms_new = st.text_area(
        "SMS tekst (zelfde dag)",
        value=rem2_message_sms,
        placeholder="Beste {klantnaam}, uw afspraak start om {tijd}. Tot zo!",
        height=70,
        key="rem2_message_sms_input",
    )
    m2_wa_new = st.text_area(
        "WhatsApp tekst (zelfde dag)",
        value=rem2_message_whatsapp,
        placeholder="Hi {klantnaam}, een korte reminder: uw afspraak begint om {tijd}.",
        height=70,
        key="rem2_message_whatsapp_input",
    )
    m2_email_new = st.text_area(
        "E-mail tekst (zelfde dag)",
        value=rem2_message_email,
        placeholder=(
            "Beste {klantnaam},\n\n"
            "Dit is een korte herinnering dat uw afspraak binnenkort start om {tijd}.\n\n"
            "Met vriendelijke groeten,\n{bedrijfsnaam}"
        ),
        height=110,
        key="rem2_message_email_input",
    )

    if st.button("Instellingen opslaan", type="primary", key="reminders_save_btn"):
        ok = upsert_reminder_settings(
            cid,
            global_active,
            int(rem1_days_before_new),
            rem1_time_new.strftime("%H:%M"),
            rem1_sms_new,
            rem1_whatsapp_new,
            rem1_email_new,
            m1_sms_new,
            m1_wa_new,
            m1_email_new,
            int(rem2_minutes_before_new),
            rem2_sms_new,
            rem2_whatsapp_new,
            rem2_email_new,
            m2_sms_new,
            m2_wa_new,
            m2_email_new,
        )
        if ok:
            _success("Herinneringsinstellingen opgeslagen.")
            st.rerun()
        else:
            _error("Kon instellingen niet opslaan.")

    st.info(
        "Deze instellingen bepalen timing, kanalen en teksten. "
        "WhatsApp/SMS worden alleen verzonden als er voldoende bundeltegoed is "
        "en je externe provider correct is gekoppeld."
    )

def render_bundles_and_usage(company_id: int):
    st.markdown("## Bundels & verbruik")

    usage = get_message_usage_summary(company_id) or {}
    whatsapp_credits = int(usage.get("whatsapp_credits", 0))
    sms_credits = int(usage.get("sms_credits", 0))
    email_limit = int(usage.get("email_limit", 0))
    email_used = int(usage.get("email_used", 0))
    email_left = max(email_limit - email_used, 0)

    ai_minutes = get_ai_local_minutes_balance(company_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("WhatsApp-tegoed", f"{whatsapp_credits}")
    c2.metric("SMS-tegoed", f"{sms_credits}")
    c3.metric("E-mail", f"{email_used} / {email_limit}", f"{email_left} over")
    c4.metric("AI-belminuten", f"{ai_minutes} min")

    st.caption(
        "De bundels hieronder voegen in deze demo direct tegoed toe. "
        "In productie koppel je dit aan je betaalprovider."
    )

    st.markdown("### Berichtbundels")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Starter**")
        st.write("€15 · 500 WhatsApp · 500 SMS")
        if st.button("Toevoegen", key="bundle_msg_starter"):
            add_whatsapp_credits(company_id, 500)
            add_sms_credits(company_id, 500)
            _success("Starter bundel toegevoegd (demo).")
            st.rerun()

    with col2:
        st.markdown("**Groei**")
        st.write("€45 · 2.000 WhatsApp · 2.000 SMS")
        if st.button("Toevoegen", key="bundle_msg_growth"):
            add_whatsapp_credits(company_id, 2000)
            add_sms_credits(company_id, 2000)
            _success("Groei bundel toegevoegd (demo).")
            st.rerun()

    with col3:
        st.markdown("**E-mail**")
        st.write("€19 · +10.000 e-mails")
        if st.button("Toevoegen", key="bundle_email_10k"):
            add_email_limit(company_id, 10_000)
            _success("E-mail bundel toegevoegd (demo).")
            st.rerun()

    st.markdown("### AI-belminuten bundels")

    ai_col1, ai_col2, ai_col3 = st.columns(3)
    with ai_col1:
        st.markdown("**AI 250**")
        st.write("€25 · 250 AI-minuten")
        if st.button("AI 250", key="bundle_ai_250"):
            add_ai_local_minutes(company_id, 250)
            _success("250 AI-minuten toegevoegd (demo).")
            st.rerun()
    with ai_col2:
        st.markdown("**AI 500**")
        st.write("€45 · 500 AI-minuten")
        if st.button("AI 500", key="bundle_ai_500"):
            add_ai_local_minutes(company_id, 500)
            _success("500 AI-minuten toegevoegd (demo).")
            st.rerun()
    with ai_col3:
        st.markdown("**AI 1000**")
        st.write("€80 · 1.000 AI-minuten")
        if st.button("AI 1000", key="bundle_ai_1000"):
            add_ai_local_minutes(company_id, 1000)
            _success("1.000 AI-minuten toegevoegd (demo).")
            st.rerun()

    st.markdown("### Handmatige correctie (alleen admin/debug)")

    hc1, hc2, hc3, hc4 = st.columns(4)
    add_wa = hc1.number_input("Extra WhatsApp", min_value=0, step=50, key="bundles_manual_wa")
    add_sms_val = hc2.number_input("Extra SMS", min_value=0, step=50, key="bundles_manual_sms")
    add_email_val = hc3.number_input("Extra e-mail limiet", min_value=0, step=1000, key="bundles_manual_email")
    add_ai_val = hc4.number_input("Extra AI-minuten", min_value=0, step=50, key="bundles_manual_ai")

    if st.button("Opslaan correcties", key="bundles_save_manual"):
        changed = False
        if add_wa:
            add_whatsapp_credits(company_id, int(add_wa))
            changed = True
        if add_sms_val:
            add_sms_credits(company_id, int(add_sms_val))
            changed = True
        if add_email_val:
            add_email_limit(company_id, int(add_email_val))
            changed = True
        if add_ai_val:
            add_ai_local_minutes(company_id, int(add_ai_val))
            changed = True

        if changed:
            _success("Tegoeden handmatig bijgewerkt.")
            st.rerun()
        else:
            _info("Geen wijzigingen om op te slaan.")

def render_ai(company_id: int):
    st.markdown("## AI Telefoniste / Callbot")

    st.caption(
        "De AI-telefoniste neemt de telefoon op, beantwoordt vragen en plant afspraken "
        "op basis van jouw diensten en beschikbaarheid."
    )

    # Huidige instellingen ophalen
    settings = get_company_ai_settings(company_id) or {}
    ai_instructions = (settings.get("ai_instructions") or "").strip()

    enabled = bool(
        settings.get("enabled")
        or settings.get("ai_assistant_enabled", 0)
    )

    line_type = settings.get("ai_line_type") or "standard"  # 'standard' of 'premium'

    phone_number = (
        settings.get("phone_number")
        or settings.get("ai_phone_number")
        or ""
    )

    guard_max_minutes = int(settings.get("ai_guard_max_minutes", 8) or 8)
    guard_idle_seconds = int(settings.get("ai_guard_idle_seconds", 25) or 25)
    guard_hangup_after_booking = bool(
        int(settings.get("ai_guard_hangup_after_booking", 1) or 1)
    )
    tariff_announce = bool(
        int(settings.get("ai_tariff_announce", 1) or 1)
    )

    ai_minutes = get_ai_local_minutes_balance(company_id)
    premium_rate_cents = int(PREMIUM_AI_0900_RATE_EUR * 100)

    # 1. Globale schakelaar
    enabled_new = st.checkbox(
        "AI-telefoniste inschakelen",
        value=enabled,
        help="Als dit uit staat, neemt de AI nooit op, ongeacht de instellingen hieronder.",
        key="ai_enabled",
    )

    # 2. Kies optie: 0900 of lokaal nummer
    mode_labels = {
        "0900": "0900-nummer (beller betaalt, AI inbegrepen)",
        "local": "Lokaal nummer (AI uit je minutenbundel)",
    }
    default_mode = "0900" if line_type == "premium" else "local"

    selected_mode = st.radio(
        "Kies hoe jouw AI-telefoniste bereikbaar is",
        options=["0900", "local"],
        index=0 if default_mode == "0900" else 1,
        format_func=lambda v: mode_labels[v],
        horizontal=True,
        key="ai_mode_choice",
    )

    use_premium = (selected_mode == "0900")

    # Waarden die per optie worden gezet
    phone_to_save: str | None = None
    line_type_new: str = line_type
    extra_min: int = 0  # alleen gebruikt bij lokaal nummer

    # =============================
    # OPTIE 1: 0900-NUMMER
    # =============================
    if use_premium:
        st.markdown("### Optie 1: 0900-nummer")

        if enabled_new:
            st.success("Deze optie is actief zodra je hieronder je 0900-nummer instelt.")
        else:
            st.warning("Je hebt 0900 geselecteerd, maar de AI-telefoniste staat uit.")

        number_0900 = st.text_input(
            "Jouw 0900-nummer om te delen met klanten",
            value=phone_number if line_type == "premium" else "",
            placeholder="0900-....",
            help="Dit nummer deel je met klanten. Oproepen hierop gaan naar de AI-telefoniste.",
            key="ai_0900_number",
        )

        st.write(
            f"- Vast tarief voor de beller: **{_format_money(PREMIUM_AI_0900_RATE_EUR)} per minuut**."
        )
        st.write("- Tarief is standaard voor alle bedrijven en niet aanpasbaar.")
        st.write("- De kosten van de AI zijn hiermee gedekt; je hoeft geen AI-minutenbundels te kopen.")
        st.write("- Ideaal als je kosten wilt doorbelasten aan de beller.")

        phone_to_save = number_0900 or None
        line_type_new = "premium"

        else:
        # =============================
        # OPTIE 2: LOKAAL NUMMER
        # =============================
        st.markdown("### Optie 2: Lokaal nummer")

        if enabled_new:
            st.success("Deze optie is actief zodra je hieronder je AI-nummer instelt.")
        else:
            st.warning("Je hebt lokaal nummer geselecteerd, maar de AI-telefoniste staat uit.")

        local_number = st.text_input(
            "AI-nummer (bestemmingsnummer voor doorschakeling)",
            value=phone_number if line_type != "premium" else "",
            placeholder="+31..., +32...",
            help=(
                "Dit is het nummer waarop de AI-telefoniste je oproepen mag aannemen. "
                "Gebruik bij voorkeur een extra vast/VoIP-nummer. "
                "Stel bij je provider in dat je huidige zakelijke nummer naar dit AI-nummer "
                "wordt doorgeschakeld bij geen antwoord, buiten openingstijden of altijd."
            ),
            key="ai_local_number",
        )

        st.info(
            "Praktisch voorbeeld:\n"
            "- Behoud je huidige nummer (bv. 03..., 06...).\n"
            "- Vraag een extra nummer of VoIP-nummer aan waarop de AI mag opnemen.\n"
            "- Stel bij je provider in:\n"
            "    • Bij geen antwoord / bij bezet / buiten openingsuren: doorschakelen naar dit AI-nummer.\n"
            "- Oproepen die op dit AI-nummer binnenkomen, worden door de AI afgehandeld en verbruiken minuten uit je bundel."
        )

        st.metric("Beschikbare AI-belminuten", f"{ai_minutes} min")
        st.caption(
            "Oproepen naar dit AI-nummer verbruiken minuten uit je bundel. "
            "Is je bundel leeg, dan neemt de AI niet meer op tot je aanvult."
        )

        st.markdown("**AI-minuten bundels (demo)**")
        b1, b2, b3 = st.columns(3)
        with b1:
            st.write("€25 · 250 min")
            if st.button("Koop 250 min", key="ai_bundle_250"):
                add_ai_local_minutes(company_id, 250)
                _success("250 AI-minuten toegevoegd (demo).")
                st.rerun()
        with b2:
            st.write("€45 · 500 min")
            if st.button("Koop 500 min", key="ai_bundle_500"):
                add_ai_local_minutes(company_id, 500)
                _success("500 AI-minuten toegevoegd (demo).")
                st.rerun()
        with b3:
            st.write("€80 · 1.000 min")
            if st.button("Koop 1.000 min", key="ai_bundle_1000"):
                add_ai_local_minutes(company_id, 1000)
                _success("1.000 AI-minuten toegevoegd (demo).")
                st.rerun()

        extra_min = st.number_input(
            "Handmatig AI-minuten toevoegen (alleen admin/debug)",
            min_value=0,
            max_value=10000,
            step=50,
            key="ai_add_minutes",
        )

        phone_to_save = local_number or None
        line_type_new = "standard"

    # =============================
    # AI-INSTRUCTIES
    # =============================

    st.markdown(
        """
        <style>
        /* Altijd een duidelijke gouden rand rond het AI-instructieveld */
        div[data-testid="stTextArea"] textarea {
            border: 2px solid #d9a81e !important;
            border-radius: 4px !important;
            box-shadow: none !important;
            outline: none !important;
        }

        /* Geen extra effect bij focus; gewoon dezelfde rand houden */
        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stTextArea"] textarea:focus-visible {
            border: 2px solid #d9a81e !important;
            box-shadow: none !important;
            outline: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### AI-telefoniste instructies (optioneel)")
    st.caption(
        "Personaliseer je assistente op maat van je bedrijf. "
        "Je kan de voorbeeldtekst onderaan kopiëren, hier plakken en aanpassen met je eigen gegevens."
    )

    ai_instructions_new = st.text_area(
        "Instructies voor jouw AI-telefoniste",
        value=ai_instructions,
        placeholder=(
            "Schrijf hier hoe de AI zich moet gedragen voor jouw bedrijf. "
            "Gebruik de voorbeeldtekst onderaan als basis en pas die aan."
        ),
        height=160,
        key="ai_instructions_input",
    )

    # (voorbeeldtekst + ideeën blijven hierna staan)

    st.markdown(
        "**Voorbeeldtekst** (kopieer en pas aan):\n"
        "Je bent de telefoniste van **Kapsalon Luna** in **Antwerpen**. "
        "Je spreekt vriendelijk en duidelijk Nederlands en gebruikt **'u'**. "
        "Je helpt bij het maken, verplaatsen en annuleren van afspraken. "
        "Je vraagt altijd naar **naam**, **telefoonnummer** en **reden van het bezoek**. "
        "Je bevestigt elke afspraak kort en duidelijk en je geeft geen prijzen of info die je niet zeker weet."
    )

    st.markdown(
        "**Ideeën wat je hier nog meer kunt toevoegen:**\n"
        "- Taal & toon: formeel of informeel, 'u' of 'je'.\n"
        "- Hoe je je bedrijf noemt aan de telefoon (bedrijfsnaam, merknaam, locatie).\n"
        "- Welke diensten je aanbiedt en de standaard duur per dienst.\n"
        "- Wat te doen bij volgeboekt: alternatief tijdstip voorstellen, wachtlijst, terugbelverzoek.\n"
        "- Regels rond annuleren/no-shows (bijv. min. 24u op voorhand).\n"
        "- Of de assistente nooit prijzen mag verzinnen: liever zeggen dat iemand van het team dit bevestigt.\n"
        "- Of ze afspraken altijd moet herhalen ter bevestiging (datum, tijd, dienst, naam klant).\n"
        "- Of ze bepaalde woorden/zinnen juist wél of juist niet mag gebruiken."
    )

    # =============================
    # SAFEGUARDS
    # =============================
    st.markdown("### Veiligheidslimieten (Safeguards)")

    sg1, sg2 = st.columns(2)
    max_minutes_new = sg1.slider(
        "Max. gespreksduur (minuten)",
        min_value=1,
        max_value=30,
        value=guard_max_minutes,
        help="Na deze tijd verbreekt de AI automatisch het gesprek.",
        key="ai_guard_max_minutes",
    )
    idle_seconds_new = sg2.slider(
        "Max. stilte (seconden)",
        min_value=5,
        max_value=120,
        value=guard_idle_seconds,
        help="Bij langere stilte verbreekt de AI automatisch het gesprek.",
        key="ai_guard_idle_seconds",
    )

    cb1, cb2 = st.columns(2)
    hangup_new = cb1.checkbox(
        "Ophangen na succesvolle booking",
        value=guard_hangup_after_booking,
        key="ai_guard_hangup",
    )
    tariff_new = cb2.checkbox(
        "Tarief aankondigen bij start",
        value=tariff_announce,
        key="ai_tariff_announce",
    )

    st.caption(
        "Safeguards beschermen jou en je klanten tegen eindeloze gesprekken, fouten of misbruik."
    )

    # =============================
    # OPSLAAN
    # =============================
    if st.button("AI-instellingen opslaan", type="primary", key="ai_save_btn"):
        try:
            set_company_ai_enabled(company_id, enabled_new)
            set_company_ai_phone_number(company_id, phone_to_save)

            update_company_ai_line(
                company_id,
                line_type=line_type_new,
                premium_rate_cents=premium_rate_cents if line_type_new == "premium" else None,
            )

            update_company_ai_safeguards(
                company_id,
                max_minutes=int(max_minutes_new),
                idle_seconds=int(idle_seconds_new),
                hangup_after_booking=bool(hangup_new),
                tariff_announce=bool(tariff_new),
            )

            update_company_ai_instructions(
                company_id,
                (ai_instructions_new or "").strip() or None,
            )

            if line_type_new == "standard" and extra_min > 0:
                add_ai_local_minutes(company_id, int(extra_min))

            _success("AI-instellingen opgeslagen.")
            st.rerun()

        except Exception as e:
            _error(f"Opslaan mislukt: {e}")

    st.info(
        "Optie 1 (0900): beller betaalt een vast tarief per minuut, jij hoeft geen AI-minuten te beheren. "
        "Optie 2 (lokaal nummer): gesprekken verbruiken minuten uit je bundel; je behoudt controle via bundels en safeguards."
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
    # Publieke boekingspagina voor klanten
    render_public_catalog(company_id)
else:
    # Beheeromgeving tabs
    tabs = st.tabs(
        [
            "Diensten",
            "Beschikbaarheid",
            "Boekingen",
            "Herinneringen",
            "Bundels & verbruik",
            "AI",
            "Account",
        ]
    )

    (
        tab_diensten,
        tab_beschikbaarheid,
        tab_boekingen,
        tab_herinneringen,
        tab_bundels,
        tab_ai,
        tab_account,
    ) = tabs

    with tab_diensten:
        render_services(company_id)

    with tab_beschikbaarheid:
        render_availability(company_id)

    with tab_boekingen:
        render_bookings(company_id)

    with tab_herinneringen:
        render_reminders(company_id)

    with tab_bundels:
        render_bundles_and_usage(company_id)

    with tab_ai:
        render_ai(company_id)

    with tab_account:
        render_account(company_id)
