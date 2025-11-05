import datetime as dt
import io
from datetime import datetime, date as _date
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import qrcode
from twilio.rest import Client

from database import (
    # init & companies
    init_db, add_company, get_company_by_email, is_company_paid, update_company_paid,
    # categories & services
    add_category, get_categories, update_category, delete_category,
    add_service, get_services, update_service, delete_service,
    # availability
    add_availability, get_availability,
    get_available_slots, get_available_slots_for_duration,
    # bookings
    add_booking_with_items, get_bookings_overview,
    # reminders
    get_reminder_settings, upsert_reminder_settings,
)

from payment import (
    create_checkout_session,
    check_payment,
    get_company_id_from_session,  # zorg dat deze in je payment.py staat (eerder gedeeld)
)

# -----------------------------
# Init & UI
# -----------------------------
init_db()
st.set_page_config(page_title="D'or Booking System", layout="wide")
st.markdown("<style> .st-emotion-cache-ffhzg2 h1 { color:#f5d97a !important; } </style>", unsafe_allow_html=True)

# -----------------------------
# Helpers
# -----------------------------
def _company_link(company_id: int) -> str:
    app_url = st.secrets.get("APP_URL", "")
    return f"{app_url}/?company={company_id}" if app_url else f"/?company={company_id}"

def _format_money(value: float) -> str:
    try:
        return f"€{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"€{value:.2f}"

def _schedule_sms_whatsapp_reminders(
    company_id: int, company_name: str,
    customer_name: str, to_phone: str,
    date_str: str, time_str: str
):
    """Plan dag-ervoor en (optioneel) zelfde-dag herinneringen via Twilio.
       Ondersteunt SMS en WhatsApp, ingesteld in Reminder Settings."""
    rs = get_reminder_settings(company_id)
    if not rs or not rs.get("enabled"):
        return

    # Twilio init
    try:
        sms_from = st.secrets["TWILIO_PHONE"]                         # bv. +31970...
        wa_from  = st.secrets.get("TWILIO_WHATSAPP_FROM", None)       # bv. 'whatsapp:+14155238886' (sandbox)
        client   = Client(st.secrets["TWILIO_SID"], st.secrets["TWILIO_TOKEN"])
    except Exception:
        return  # geen/ongeldige secrets: niet blokkeren

    tz = ZoneInfo(rs.get("tz", "Europe/Brussels"))
    appt_date = pd.to_datetime(date_str).date()
    appt_time = datetime.strptime(time_str, "%H:%M").time()
    appt_dt_local = datetime.combine(appt_date, appt_time).replace(tzinfo=tz)

    ctx = {
        "company": company_name or "uw salon",
        "name": customer_name,
        "date": appt_dt_local.strftime("%d-%m-%Y"),
        "time": appt_dt_local.strftime("%H:%M"),
    }

    # dag-ervoor tijd bepalen
    try:
        hh, mm = [int(x) for x in str(rs["send_time"]).split(":")[:2]]
    except Exception:
        hh, mm = 9, 0
    day_before_dt = (appt_dt_local - pd.Timedelta(days=int(rs["days_before"]))).replace(
        hour=hh, minute=mm, second=0, microsecond=0
    )

    # zelfde dag X minuten vooraf
    same_dt = None
    if rs.get("same_day_enabled"):
        same_dt = appt_dt_local - pd.Timedelta(minutes=int(rs["same_day_minutes_before"]))

    def _try_schedule(send_dt_local: datetime, template: str, channel: str):
        if not send_dt_local:
            return
        now_local = datetime.now(tz)
        if send_dt_local <= now_local:
            return
        body = template.format(**ctx)
        send_at_utc = send_dt_local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            if channel == "sms" and rs.get("sms_enabled") and sms_from:
                client.messages.create(
                    to=to_phone, from_=sms_from, body=body,
                    schedule_type="fixed", send_at=send_at_utc
                )
            elif channel == "wa" and rs.get("whatsapp_enabled") and wa_from:
                to_wa = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
                client.messages.create(
                    to=to_wa, from_=wa_from, body=body,
                    schedule_type="fixed", send_at=send_at_utc
                )
        except Exception:
            pass  # niet blokkeren

    # SMS
    _try_schedule(day_before_dt, rs["template_day_before_sms"], "sms")
    if same_dt is not None:
        _try_schedule(same_dt, rs["template_same_day_sms"], "sms")
    # WhatsApp
    _try_schedule(day_before_dt, rs["template_day_before_wa"], "wa")
    if same_dt is not None:
        _try_schedule(same_dt, rs["template_same_day_wa"], "wa")


def _reminder_settings_block(company_id: int, company_name: str):
    with st.expander("🔔 SMS-herinneringen & deel je link", expanded=False):
        app_url = st.secrets.get("APP_URL", "")
        public_link = f"{app_url}/?company={company_id}" if app_url else f"/?company={company_id}"
        st.text_input("Jouw boekingslink", value=public_link, disabled=True)

        qr_img = qrcode.make(public_link)
        buf = io.BytesIO(); qr_img.save(buf, format="PNG")
        st.image(buf.getvalue(), width=140, caption="Scan of download")
        st.download_button("⬇️ Download QR", data=buf.getvalue(),
                           file_name="booking_link_qr.png", mime="image/png")

        st.divider()
        st.subheader("Herinnering-instellingen", anchor=False)
        rs = get_reminder_settings(company_id)

        cols = st.columns(3)
        enabled = cols[0].toggle("Herinneringen aan", value=bool(rs["enabled"]))
        sms_enabled = cols[1].toggle("SMS", value=bool(rs["sms_enabled"]))
        wa_enabled  = cols[2].toggle("WhatsApp", value=bool(rs["whatsapp_enabled"]))

        col1, col2, col3 = st.columns([1,1,1])
        days_before = col1.number_input("Dagen vóór afspraak", 0, 30, int(rs["days_before"]))
        # tijd
        try:
            hh, mm = [int(x) for x in str(rs["send_time"]).split(":")[:2]]
        except Exception:
            hh, mm = 9, 0
        send_time = col2.time_input("Tijd (dag-ervoor)", value=datetime(2000,1,1,hh,mm).time())
        tz = col3.selectbox("Tijdzone", ["Europe/Brussels", "Europe/Amsterdam"],
                            index=0 if rs["tz"] == "Europe/Brussels" else 1)

        colA, colB = st.columns([1,2])
        same_day_enabled = colA.toggle("Ook op dezelfde dag", value=bool(rs["same_day_enabled"]))
        same_day_minutes_before = colB.number_input(
            "Minuten vóór afspraak (zelfde dag)",
            min_value=5, max_value=24*60, step=5,
            value=int(rs["same_day_minutes_before"]),
            disabled=not same_day_enabled
        )

        st.caption("Variabelen in tekst: {company}, {name}, {date}, {time}")
        st.markdown("**SMS-teksten**")
        sms_day_before = st.text_area("Dag-ervoor (SMS)", rs["template_day_before_sms"], height=70)
        sms_same_day   = st.text_area("Zelfde dag (SMS)", rs["template_same_day_sms"], height=70)

        st.markdown("**WhatsApp-teksten**")
        wa_day_before = st.text_area("Dag-ervoor (WhatsApp)", rs["template_day_before_wa"], height=70)
        wa_same_day   = st.text_area("Zelfde dag (WhatsApp)", rs["template_same_day_wa"], height=70)

        if st.button("Instellingen opslaan", type="primary"):
            save_reminder_settings(
                company_id=company_id,
                enabled=int(enabled),
                sms_enabled=int(sms_enabled),
                whatsapp_enabled=int(wa_enabled),
                days_before=int(days_before),
                send_time=send_time.strftime("%H:%M"),
                same_day_enabled=int(same_day_enabled),
                same_day_minutes_before=int(same_day_minutes_before),
                tz=tz,
                template_day_before_sms=sms_day_before.strip(),
                template_same_day_sms=sms_same_day.strip(),
                template_day_before_wa=wa_day_before.strip(),
                template_same_day_wa=wa_same_day.strip(),
            )
            st.success("Herinnering-instellingen opgeslagen.")


# ------------------------------------------------
# Query params & auto-activate
# ------------------------------------------------
qp = st.query_params
company_id_param = qp.get("company")     # geeft str of None
session_id_param = qp.get("session_id")  # geeft str of None

# Stripe terugkomst: activeer + log in
if session_id_param and "logged_in" not in st.session_state:
    paid_ok = check_payment(session_id_param)
    cid, meta = None, {}
    try:
        cid, meta = get_company_id_from_session(session_id_param)  # (company_id, metadata dict)
    except Exception:
        cid = None

    if paid_ok and cid:
        activate_company(cid)
        st.session_state.logged_in = True
        st.session_state.company_id = int(cid)
        st.session_state.company_name = meta.get("company_name", f"bedrijf #{cid}")
        st.success("Betaling bevestigd. Welkom!")

        # URL opschonen: laat alleen company-id staan
        st.query_params["company"] = str(cid)
        st.query_params.pop("session_id", None)

# ...
    activate_company(company_id)
    st.success("✅ Betaling ontvangen! Je account is nu actief.")

    # -----------------------------
    # DASHBOARD (alleen na betaling)
    # -----------------------------
    company_id = int(st.session_state.company_id)
    company_name = st.session_state.get("company_name", f"bedrijf #{company_id}")

    if not is_company_paid(company_id):
        st.warning("Je account is nog niet actief. Betaal om toegang te krijgen tot het dashboard.")
        try:
            link = create_checkout_session(company_id, st.session_state.get("login_email", ""), company_name)
            st.markdown(f"[Betaal abonnement (€25/maand)]({link})")
        except Exception:
            pass
        st.stop()

# ------------------------------------------------
# ✅ Login & registratie (boven tabs)
# ------------------------------------------------

if "company_id" not in st.session_state:
    # Titel bovenaan, gecentreerd
    st.markdown("<h1 style='text-align: center;'>💎 D'or Booking System</h1>", unsafe_allow_html=True)
    st.write("Welkom! Registreer als nieuw bedrijf of log in als bestaande klant.")

        # 📱 Mobile-friendly layout (werkt gegarandeerd)
    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
            /* Zet kolommen onder elkaar */
            [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
            }

            /* Geef extra ruimte tussen de twee secties */
            [data-testid="column"] {
                margin-bottom: 2rem !important;
            }

            /* Centreer de knoppen */
            button[kind="primary"] {
                width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


    # Twee kolommen: links registratie, rechts login
    col_reg, col_log = st.columns(2)

    # --- 🆕 Nieuwe registratie ---
    with col_reg:
        st.subheader("Nieuw bedrijf registreren")
        r_name = st.text_input("Bedrijfsnaam", placeholder="Bijv. Salon Bella", key="reg_name")
        r_email = st.text_input("E-mail", placeholder="bijv. info@bella.be", key="reg_email")
        r_pwd = st.text_input("Wachtwoord", type="password", placeholder="Minstens 6 tekens", key="reg_pwd")

        if st.button("📋 Registreer", key="register_button"):
            if not r_name or not r_email or not r_pwd:
                st.error("Vul alle velden in (bedrijfsnaam, e-mail en wachtwoord).")
            else:
                existing = get_company_by_email(r_email)
                if existing:
                    st.error("⚠️ Dit e-mailadres is al geregistreerd.")
                else:
                    new_id = add_company(r_name, r_email, r_pwd)
                    if new_id > 0:
                        st.session_state.company_id = new_id
                        st.session_state.company_name = r_name
                        st.success(f"✅ {r_name} is succesvol geregistreerd!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Er ging iets mis bij het registreren. Probeer opnieuw.")

    # --- 🔑 Bestaande klant login ---
    with col_log:
        st.subheader("Bestaand bedrijf inloggen")
        l_email = st.text_input("E-mail", placeholder="bijv. info@bella.be", key="login_email")
        l_pwd = st.text_input("Wachtwoord", type="password", key="login_pwd")

        if st.button("🔓 Inloggen", key="login_button"):
            company = get_company_by_email(l_email)
            if not company:
                st.error("❌ Geen account gevonden met dit e-mailadres.")
            elif company[3] != l_pwd:
                st.error("⚠️ Onjuist wachtwoord.")
            else:
                st.session_state.company_id = company[0]
                st.session_state.company_name = company[1]
                st.success(f"Welkom terug, {company[1]}!")
                st.rerun()

    st.stop()  # Stop hier zodat tabs niet zichtbaar zijn

# ------------------------------------------------
# ✅ Bedrijf is ingelogd → dashboard
# ------------------------------------------------
company_id = st.session_state.company_id
company_name = st.session_state.company_name

# 💼 Toon naam + uitlogknop naast elkaar
col_left, col_right = st.columns([3, 1])
with col_left:
    st.info(f"💼 Ingelogd als: **{company_name}**")
with col_right:
    if st.button("🚪 Uitloggen"):
        st.session_state.clear()
        st.success("Je bent uitgelogd.")
        st.rerun()

   # -------------------------------------------------
# Tabs
# -------------------------------------------------
tabs = st.tabs([
    "🏠 Overzicht",
    "💅 Diensten",
    "🕓 Beschikbaarheid",
    "🔔 Herinneringen",      # ← nieuw
    "👓 Klant-preview",
    "📁 Afspraken",
    "⚙️ Account"            # ← nieuw
])


# -------------------------------------------------
# 🏠 Overzicht
# -------------------------------------------------
with tabs[0]:
    st.subheader("Overzicht")
    # eventueel iets van je overzichtspagina hier
    st.info("Welkom bij het overzicht van je bedrijf.")


# -------------------------------------------------
# 💅 Diensten
# -------------------------------------------------
with tabs[1]:
    st.subheader("Diensten")

    cats_df = get_categories(company_id)
    cat_names = ["Algemeen"] + (cats_df["name"].tolist() if not cats_df.empty else [])

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    sv_name = col1.text_input("Naam", placeholder="Bijv. Pedicure Basic")
    sv_price = col2.number_input("Prijs (€)", min_value=0.0, step=0.50, value=0.0)
    sv_dur = col3.number_input("Duur (minuten)", min_value=5, step=5, value=30)
    pick_cat = col4.selectbox("Categorie", options=["Algemeen", "Nieuwe categorie…"] + (cats_df["name"].tolist() if not cats_df.empty else []))

    new_cat_name, new_cat_desc = None, ""
    if pick_cat == "Nieuwe categorie…":
        st.info("Nieuwe categorie")
        new_cat_name = st.text_input("Categorie naam", placeholder="Bijv. Deelbehandelingen")
        new_cat_desc = st.text_area("Categorie beschrijving (optioneel)", placeholder="Deze groep bevat…")

    sv_desc = st.text_area("Beschrijving (dienst, optioneel)", placeholder="Bijv. Voetbad, nagels knippen en vijlen, voetmassage (5min)")

    if st.button("➕ Toevoegen", type="primary", use_container_width=False):
        if not sv_name:
            st.error("Vul een dienstnaam in.")
        else:
            final_cat = pick_cat
            if pick_cat == "Nieuwe categorie…" and new_cat_name:
                upsert_category(company_id, new_cat_name, new_cat_desc)
                final_cat = new_cat_name
            add_service(company_id, sv_name, sv_price, sv_dur, final_cat, sv_desc)
            st.success("Dienst toegevoegd.")
            st.rerun()

    st.divider()
    st.markdown("#### Huidige diensten")
    cur = get_services(company_id)
    if cur.empty:
        st.info("Nog geen diensten toegevoegd.")
    else:
        st.dataframe(cur, use_container_width=True)

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
                min_value=5,
                step=5,
                value=int(row["duration"]),
                key=f"dur_{row['id']}"
            )
            e_cat = ec4.selectbox(
                "Categorie",
                options=cat_names,
                index=(cat_names.index(row["category"]) if row["category"] in cat_names else 0)
            )
            e_desc = st.text_area("Beschrijving", value=row["description"] or "", height=90)

            bc1, bc2 = st.columns([1, 1])
            if bc1.button("Opslaan wijzigingen", type="primary", key=f"save_{row['id']}"):
                update_service(edit_id, e_name, e_price, e_dur, e_cat, e_desc)
                st.success("Dienst bijgewerkt.")
                st.rerun()
            if bc2.button("❌ Verwijderen", type="secondary", key=f"del_{row['id']}"):
                delete_service(edit_id)
                st.success("Dienst verwijderd.")
                st.rerun()


    # --- Beschikbaarheid ---
    with tabs[2]:
        st.subheader("Beschikbaarheid")
        days = ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"]
        c1,c2,c3 = st.columns(3)
        d = c1.selectbox("Dag", days)
        t1 = c2.time_input("Start", value=datetime(2000,1,1,9,0).time())
        t2 = c3.time_input("Einde", value=datetime(2000,1,1,18,0).time())
        if st.button("Opslaan", type="primary"):
            add_availability(company_id, d, t1.strftime("%H:%M"), t2.strftime("%H:%M"))
            st.success("Beschikbaarheid toegevoegd.")
            st.rerun()

        av = get_availability(company_id)
        if av.empty:
            st.info("Nog geen beschikbaarheid.")
        else:
            st.dataframe(av, use_container_width=True)

    # --- 🔔 Herinneringen ---
with tabs[3]:
    st.subheader("Herinneringsberichten")

    # 1) Ophalen huidige instellingen (maakt automatisch default record als het nog niet bestaat)
    s = get_reminder_settings(company_id)

    # 2) UI
    colA, colB = st.columns(2)
    enabled = colA.toggle("Herinneringen inschakelen", value=bool(s.get("enabled", 0)))
    sms_enabled = colA.toggle("SMS gebruiken", value=bool(s.get("sms_enabled", 1)))
    wa_enabled = colA.toggle("WhatsApp gebruiken", value=bool(s.get("whatsapp_enabled", 0)))

    days_before = colB.number_input(
        "Dagen op voorhand",
        min_value=0,
        max_value=7,
        value=int(s.get("days_before", 1))
    )

    # '09:00' → tijdobject
    send_time_str = (s.get("send_time") or "09:00")
    try:
        default_time = dt.datetime.strptime(send_time_str, "%H:%M").time()
    except Exception:
        default_time = dt.time(9, 0)
    send_time = colB.time_input("Verzendtijd", value=default_time)

    same_day = colA.toggle("Extra herinnering op de dag zelf", value=bool(s.get("same_day_enabled", 0)))
    same_day_min = colB.number_input(
        "Minuten vóór afspraak (zelfde dag)",
        min_value=5,
        step=5,
        value=int(s.get("same_day_minutes", 30))
    )

    tz_choices = ["Europe/Brussels", "Europe/Amsterdam", "UTC"]
    tz_value = s.get("tz") or "Europe/Brussels"
    tz = colB.selectbox(
        "Tijdzone",
        tz_choices,
        index=tz_choices.index(tz_value) if tz_value in tz_choices else 0
    )

    st.markdown("#### 📄 Sjablonen")
    c1, c2 = st.columns(2)

    # --- SMS sjablonen ---
    tpl_sms_day_before = c1.text_area(
        "SMS – dag ervoor",
        value=s.get("template_day_before_sms") or
        "Herinnering: je afspraak is morgen om {TIME} bij {COMPANY}. Tot dan!"
    )

    tpl_sms_same_day = c1.text_area(
        "SMS – zelfde dag",
        value=s.get("template_same_day_sms") or
        "Herinnering: je afspraak is vandaag om {TIME} bij {COMPANY}."
    )

    # --- WhatsApp sjablonen ---
    tpl_wa_day_before = c2.text_area(
        "WhatsApp – dag ervoor",
        value=s.get("template_day_before_wa") or
        "👋 Hallo! Herinnering: je afspraak is morgen om {TIME} bij {COMPANY}."
    )

    tpl_wa_same_day = c2.text_area(
        "WhatsApp – zelfde dag",
        value=s.get("template_same_day_wa") or
        "👋 Hallo! Herinnering: je afspraak is vandaag om {TIME} bij {COMPANY}."
    )

    st.caption("Beschikbare placeholders: {TIME}, {DATE}, {COMPANY}, {NAME} (indien van toepassing).")

    if st.button("💾 Instellingen opslaan", type="primary"):
        upsert_reminder_settings(
            company_id=company_id,
            enabled=int(enabled),
            sms_enabled=int(sms_enabled),
            whatsapp_enabled=int(wa_enabled),
            days_before=int(days_before),
            send_time=send_time.strftime("%H:%M"),
            same_day_enabled=int(same_day),
            same_day_minutes_before=int(same_day_min),
            tz=tz,
            template_day_before_sms=tpl_sms_day_before,
            template_same_day_sms=tpl_sms_same_day,
            template_day_before_wa=tpl_wa_day_before,
            template_same_day_wa=tpl_wa_same_day,
        )
        st.success("✅ Herinneringsinstellingen opgeslagen.")
        st.rerun()

    # --- Klant-preview ---
    with tabs[3]:
        st.subheader("Zo ziet je klant het")
        serv = get_services(company_id)
        cats = serv["category"].dropna().unique().tolist()
        cats_sorted = sorted(cats, key=lambda x: (x != "Algemeen", x.lower()))
        selected_ids = set()
        for cat in cats_sorted:
            desc = get_category_description(company_id, cat) if cat != "Algemeen" else ""
            with st.expander(cat, expanded=(cat=="Algemeen")):
                if desc:
                    st.caption(desc)
                for _, s in serv[serv["category"]==cat].iterrows():
                    colL, colR = st.columns([6,1])
                    label = f"{s['name']} — {_format_money(float(s['price']))} • {int(s['duration'])} min"
                    if s.get("description"):
                        st.caption(s["description"])
                    checked = colR.checkbox("", key=f"preview_{int(s['id'])}")
                    colL.write(label)
                    if checked:
                        selected_ids.add(int(s["id"]))
        if not selected_ids:
            st.info("Selecteer één of meerdere diensten om te testen.")

    # --- Afspraken ---
    with tabs[4]:
        st.subheader("Afspraken-overzicht")
        bok = get_bookings_overview(company_id)
        if bok.empty:
            st.info("Nog geen afspraken.")
        else:
            # nette sortering / tonen
            bok["total_price"] = bok["total_price"].fillna(0.0).map(_format_money)
            st.dataframe(bok, use_container_width=True)

    st.divider()
    if st.button("Uitloggen"):
        st.session_state.clear()
        st.experimental_set_query_params()
        st.rerun()

# --- ⚙️ Account ---
with tabs[6]:
    st.subheader("Accountinstellingen")

    row = get_company(company_id)  # (id, name, email, password, paid, created_at)
    if not row:
        st.error("Account niet gevonden.")
    else:
        cur_name, cur_email = row[1], row[2]

        a1, a2 = st.columns(2)
        new_name  = a1.text_input("Bedrijfsnaam", value=cur_name or "")
        new_email = a2.text_input("E-mail", value=cur_email or "")

        st.markdown("**Wachtwoord wijzigen (optioneel)**")
        pw1, pw2 = st.columns(2)
        new_pwd = pw1.text_input("Nieuw wachtwoord", type="password", placeholder="Leeg laten = niet wijzigen")
        new_pwd2 = pw2.text_input("Herhaal nieuw wachtwoord", type="password", placeholder="")

        if st.button("💾 Opslaan", type="primary"):
            if new_pwd and new_pwd != new_pwd2:
                st.error("Nieuw wachtwoord komt niet overeen.")
            else:
                ok = update_company_profile(
                    company_id,
                    name=new_name.strip(),
                    email=new_email.strip(),
                    password=(new_pwd.strip() if new_pwd else None),
                )
                if ok:
                    st.success("Gegevens bijgewerkt.")
                    # update naamsbadge
                    st.session_state.company_name = new_name.strip() or st.session_state.company_name
                    st.rerun()
                else:
                    st.error("Wijzigen mislukt. Bestaat dit e-mailadres al?")

# =========================================================
# KLANT-BOEKINGSPAGINA (als niet ingelogd en ?company=...)
# =========================================================
if "logged_in" not in st.session_state and company_id_param:
    try:
        company_id = int(company_id_param)
    except Exception:
        st.stop()

    st.markdown("## Kies je diensten")
    services = get_services(company_id)
    if services.empty:
        st.info("Dit bedrijf heeft nog geen diensten gepubliceerd.")
        st.stop()

    # Categorieën ingeklapt (Algemeen open)
    cats = services["category"].dropna().unique().tolist()
    cats_sorted = sorted(cats, key=lambda x: (x != "Algemeen", x.lower()))
    selected_ids = []
    total_price = 0.0
    total_dur = 0

    for cat in cats_sorted:
        desc = get_category_description(company_id, cat) if cat != "Algemeen" else ""
        with st.expander(cat, expanded=(cat=="Algemeen")):
            if desc:
                st.caption(desc)
            for _, s in services[services["category"]==cat].iterrows():
                colL, colR = st.columns([6,1])
                label = f"{s['name']} — {_format_money(float(s['price']))} • {int(s['duration'])} min"
                colL.write(label)
                if s.get("description"):
                    st.caption(s["description"])
                chk = colR.checkbox("", key=f"book_{int(s['id'])}")
                if chk:
                    selected_ids.append(int(s["id"]))
                    total_price += float(s["price"])
                    total_dur += int(s["duration"])

    if not selected_ids:
        st.warning("Selecteer minimaal één dienst om verder te gaan.")
        st.stop()

    st.success(f"Geselecteerd: {_format_money(total_price)} • {total_dur} min")

    # Datum + tijden op basis van totale duur
    sel_date = st.date_input("Datum", value=_date.today())
    slots = get_available_slots_for_duration(company_id, str(sel_date), total_dur)
    if not slots:
        st.info("Geen tijdvakken beschikbaar op deze dag voor de gekozen duur.")
        st.stop()
    sel_time = st.selectbox("Starttijd", options=slots)

    # Klantgegevens
    colN, colP = st.columns([2,2])
    cust_name = colN.text_input("Jouw naam*")
    cust_phone = colP.text_input("Telefoon*", placeholder="+32... of voor WhatsApp ook gewoon +32...")

    if st.button("Boek nu!", type="primary", use_container_width=False):
        if not (cust_name and cust_phone.startswith("+")):
            st.error("Vul je naam in en een geldig telefoonnummer (beginnend met +).")
        else:
            bid = add_booking_with_items(company_id, cust_name, cust_phone, selected_ids, str(sel_date), sel_time)
            # Herinneringen plannen
            try:
                _schedule_sms_whatsapp_reminders(
                    company_id=company_id,
                    company_name=st.session_state.get("company_name", ""),
                    customer_name=cust_name,
                    to_phone=cust_phone,
                    date_str=str(sel_date),
                    time_str=sel_time,
                )
            except Exception:
                pass
            st.success("Boeking gelukt! Je ontvangt (indien ingesteld) automatisch herinneringen.")
            st.balloons()
