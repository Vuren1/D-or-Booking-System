import os
import streamlit as st
import pandas as pd

from database import (
    init_db,
    add_company, get_company_by_email, get_company_by_id,
    is_company_paid, update_company_paid,
    add_service, get_services,
    add_availability, get_availability,
    add_booking, get_available_slots,
)
from twilio_sms import send_sms

# Probeer hulpfuncties uit payment te importeren
try:
    from payment import create_checkout_session, check_payment, get_company_id_from_session
except Exception:
    from payment import create_checkout_session, check_payment
    def get_company_id_from_session(session_id: str):
        # Fallback rechtstreeks via Stripe
        try:
            import stripe
            sk = os.getenv("STRIPE_SECRET_KEY") or st.secrets["STRIPE_SECRET_KEY"]
            stripe.api_key = sk
            s = stripe.checkout.Session.retrieve(session_id)
            cid = (s.metadata or {}).get("company_id")
            return int(cid) if cid else None
        except Exception:
            return None


# ─────────────────────────────────────────
# Init
# ─────────────────────────────────────────
init_db()
st.set_page_config(page_title="D'or Booking System", layout="centered")
st.title("D'or Booking System")

# Zorg dat logo-map bestaat (optioneel)
os.makedirs("data/logos", exist_ok=True)

# Stijl (goud/donker)
st.markdown("""
<style>
:root { --gold:#FFD166; }
.block-title { color:var(--gold); font-weight:700; font-size:1.2rem; margin:8px 0 4px; }
.box { border:1px solid #1e3a26; border-radius:16px; padding:16px; background:#0f1f14; }
.label { color:#cfe3d5; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

# Query params
qp = st.experimental_get_query_params()
company_id_param = qp.get("company", [None])[0]
session_id = qp.get("session_id", [None])[0]
try:
    company_id_param = int(company_id_param) if company_id_param is not None else None
except Exception:
    company_id_param = None


# ───────────────── Auto-activate & auto-login na Stripe ─────────────────
if session_id and "logged_in" not in st.session_state:
    # 1) Probeer company uit de URL
    cid = company_id_param

    # 2) Anders: haal company_id uit Stripe metadata
    if not cid:
        try:
            cid = get_company_id_from_session(session_id)
        except Exception:
            cid = None

    # 3) Als we het nog niet weten: haal e-mail uit Stripe sessie en zoek in DB
    if not cid:
        try:
            import stripe
            sk = os.getenv("STRIPE_SECRET_KEY") or st.secrets["STRIPE_SECRET_KEY"]
            stripe.api_key = sk
            s = stripe.checkout.Session.retrieve(session_id, expand=["customer_details"])
            email = None
            if getattr(s, "customer_details", None) and s.customer_details.email:
                email = s.customer_details.email
            elif getattr(s, "customer_email", None):
                email = s.customer_email
            if email:
                rec = get_company_by_email(email)
                if rec:
                    cid = rec[0]
        except Exception:
            pass

    # 4) Log in & activeer
    if cid and check_payment(session_id):
        info = get_company_by_id(cid)
        update_company_paid(cid)
        st.session_state.logged_in = True
        st.session_state.company_id = cid
        st.session_state.company_name = info[1] if info else f"Bedrijf #{cid}"
        # Zet company ook in de URL (handig bij refresh/delen)
        st.experimental_set_query_params(company=cid)
        st.success("✅ Betaling bevestigd. Je account is nu geactiveerd en je bent ingelogd.")
        st.rerun()
    else:
        st.info("✅ Betaling bevestigd. Je wordt zo doorgestuurd…")
        st.caption("Blijft dit scherm staan? Controleer of de success_url &company=<id> bevat in payment.py.")


# ───────────────── ROUTING ─────────────────
if st.session_state.get("logged_in"):
    # ============ DASHBOARD ============
    company_id = st.session_state["company_id"]
    company_name = st.session_state.get("company_name", f"Bedrijf #{company_id}")
    company_rec = get_company_by_id(company_id)
    company_email = company_rec[2] if company_rec else ""

    # Hercontrole als er toch nog een session_id hing
    if session_id and check_payment(session_id):
        update_company_paid(company_id)
        st.success("✅ Betaling bevestigd.")
        st.rerun()

    if is_company_paid(company_id):
        st.header(f"Dashboard – {company_name}")

        # Optioneel: bedrijfslogo
        logo_path = f"data/logos/company_{company_id}.png"
        with st.expander("🏷️ Bedrijfsprofiel"):
            c1, c2 = st.columns([1, 2])
            with c1:
                if os.path.exists(logo_path):
                    st.image(logo_path, caption="Huidig logo", use_column_width=True)
                uploaded = st.file_uploader("Upload nieuw logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
                if uploaded is not None:
                    from PIL import Image
                    img = Image.open(uploaded).convert("RGBA")
                    img.save(logo_path)
                    st.success("Logo bijgewerkt.")
                    st.rerun()
            with c2:
                st.write(f"**Bedrijfsnaam:** {company_name}")
                st.write(f"**E-mail:** {company_email}")

        st.divider()

        # ====== TABS ======
        tab_dash, tab_services, tab_avail, tab_preview = st.tabs(
            ["🏠 Overzicht", "💅 Diensten", "🕒 Beschikbaarheid", "👀 Klant-preview"]
        )

        # ---------------------- OVERZICHT ----------------------
        with tab_dash:
            st.markdown("<div class='block-title'>Welkom!</div>", unsafe_allow_html=True)
            st.write("Vul je diensten en beschikbaarheid in. Gebruik de tabs hierboven.")
            st.markdown(
                f"""
                **Publieke boekingslink voor klanten**  
                👉 `?company={company_id}` aan je app-URL toevoegen  
                Voorbeeld:  
                `{st.secrets.get("APP_URL", "https://<jouw-app>.streamlit.app")}?company={company_id}`
                """.strip()
            )

        # ---------------------- DIENSTEN -----------------------
        with tab_services:
    st.markdown("<div class='block-title'>Diensten</div>", unsafe_allow_html=True)

    # bestaande categorieën (vrijetekst), bedrijf kan nieuwe typen
    existing_cats = ["Algemeen"] + [c for c in get_service_categories(company_id) if c and c != "Algemeen"]
    col1, col2, col3, col4 = st.columns([2,1,1,1])
    with st.form("add_service_form"):
        with col1:
            name = st.text_input("Naam", placeholder="Bijv. Voetmassage")
        with col2:
            price = st.number_input("Prijs (€)", min_value=0.0, step=0.05, value=0.0)
        with col3:
            duration = st.number_input("Duur (minuten)", min_value=5, step=5, value=30)
        with col4:
            category = st.selectbox("Categorie", options=existing_cats + ["+ Nieuwe categorie..."])
        new_cat = None
        if category == "+ Nieuwe categorie...":
            new_cat = st.text_input("Nieuwe categorie", placeholder="Bijv. Nagels")
        if st.form_submit_button("➕ Toevoegen"):
            final_cat = (new_cat or category or "Algemeen").strip()
            if name:
                add_service(company_id, name, price, duration, final_cat)
                st.success("Dienst toegevoegd.")
                st.rerun()
            else:
                st.warning("Vul een naam in.")

    services_df = get_services(company_id)
    if services_df.empty:
        st.info("Nog geen diensten.")
    else:
        st.dataframe(services_df[["id","name","price","duration","category"]], use_container_width=True)
        if st.button("💾 Alles opslaan (Diensten)"):
            st.success("Diensten zijn up-to-date.")

        # ------------------ BESCHIKBAARHEID -------------------
        with tab_avail:
            st.markdown("<div class='block-title'>Beschikbaarheid</div>", unsafe_allow_html=True)
            days = ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"]
            with st.form("add_avail_form"):
                dcol, scol, ecol = st.columns([2,1,1])
                with dcol:
                    day = st.selectbox("Dag", days)
                with scol:
                    start = st.time_input("Van", pd.Timestamp("09:00").time())
                with ecol:
                    end = st.time_input("Tot", pd.Timestamp("17:00").time())
                if st.form_submit_button("➕ Opslaan"):
                    add_availability(company_id, day, str(start), str(end))
                    st.success("Beschikbaarheid toegevoegd.")
                    st.rerun()

            avail_df = get_availability(company_id)
            if avail_df.empty:
                st.info("Nog geen beschikbaarheid.")
            else:
                st.dataframe(avail_df[["id","day","start_time","end_time"]], use_container_width=True)
                if st.button("💾 Alles opslaan (Beschikbaarheid)"):
                    st.success("Beschikbaarheid is up-to-date.")

        # ------------------- KLANT-PREVIEW --------------------
        with tab_preview:
    st.markdown("<div class='block-title'>Zo ziet je klant het</div>", unsafe_allow_html=True)

    services = get_services(company_id)
    if services.empty:
        st.info("Voeg eerst een dienst toe in tab 'Diensten'.")
    else:
        # Groepeer per categorie en toon checkboxes
        selected_ids = []
        for cat in services["category"].dropna().unique():
            st.markdown(f"**{cat}**")
            sub = services[services["category"] == cat]
            for _, row in sub.iterrows():
                checked = st.checkbox(f"{row['name']} — €{row['price']:.2f} • {int(row['duration'])} min",
                                      key=f"pv_{row['id']}")
                if checked:
                    selected_ids.append(int(row["id"]))

        if not selected_ids:
            st.info("Selecteer één of meerdere diensten hierboven.")
            st.stop()

        # Totals
        sel_df = services[services["id"].isin(selected_ids)]
        total_price = float(sel_df["price"].sum())
        total_duration = int(sel_df["duration"].sum())
        st.write(f"**Totaal:** €{total_price:.2f} — {total_duration} min")

        date = st.date_input("Datum", min_value=pd.Timestamp.today())
        slots = get_available_slots_for_duration(company_id, str(date), total_duration)
        if not slots:
            st.warning("Geen tijdslots beschikbaar voor deze totaalduur op deze dag.")
            st.stop()
        time = st.selectbox("Tijd", slots)

        cname = st.text_input("Jouw naam", placeholder="Voornaam Achternaam")
        cphone = st.text_input("Telefoon (met +)", placeholder="+316...")

        if st.button("📩 Boek (test, meerdere diensten)"):
            if not cname or not cphone.startswith("+"):
                st.error("Vul naam in en een geldig telefoonnummer met +.")
            else:
                booking_id = add_booking_with_items(company_id, cname, cphone, selected_ids, str(date), time)
                try:
                    names = ", ".join(sel_df["name"].tolist())
                    send_sms(cphone, f"Beste {cname}, je afspraak bij {company_name} is bevestigd op {date} om {time} — {names}.")
                except Exception:
                    pass
                st.success(f"Boeking #{booking_id} opgeslagen (test).")

    # ============ PUBLIEKE KLANTEN-BOEKINGSPAGINA ============
    info = get_company_by_id(company_id_param)
    company_title = info[1] if info else f"Bedrijf #{company_id_param}"

    st.markdown(
        f"<h2 style='text-align:center;color:#FFD166;'>Boek een afspraak bij {company_title}</h2>",
        unsafe_allow_html=True,
    )

    services = get_services(company_id_param)
    if services.empty:
        st.info("Geen diensten beschikbaar voor dit bedrijf.")
        st.stop()

    st.subheader("Kies een dienst")
    service_name = st.selectbox("Dienst*", services["name"].tolist())
    service_row = services[services["name"] == service_name].iloc[0]
    st.info(f"💰 **Prijs:** €{service_row['price']:.2f}  ⏱️ **Duur:** {service_row['duration']} min")

    st.subheader("Kies datum & tijd")
    date = st.date_input("Datum*", min_value=pd.Timestamp.today())
    times = get_available_slots(company_id_param, str(date))
    if not times:
        st.warning("Geen beschikbare tijden op deze dag.")
        st.stop()
    time = st.selectbox("Tijd*", times)

    st.subheader("Jouw gegevens")
    name = st.text_input("Naam*")
    phone = st.text_input("Telefoonnummer*", placeholder="+316...")

    if st.button("✅ Bevestig je afspraak"):
        if not name or not phone.startswith("+"):
            st.error("Vul alle velden correct in (telefoonnummer moet met + beginnen).")
        else:
            add_booking(company_id_param, name, phone, int(service_row["id"]), str(date), time)
            sms = f"Beste {name}, je afspraak bij {company_title} is bevestigd op {date} om {time}."
            try:
                send_sms(phone, sms)
            except Exception as e:
                st.warning(f"Afspraak is bevestigd, maar SMS kon niet worden verzonden: {e}")
            st.success(f"🎉 Dank je, {name}! Je afspraak is bevestigd.")
            st.balloons()

else:
    # ============ LANDING: REGISTRATIE / LOGIN ============
    st.subheader("Nieuw bedrijf? Registreer hier")
    with st.form("register_form"):
        new_name = st.text_input("Bedrijfsnaam")
        new_email = st.text_input("E-mail")
        new_password = st.text_input("Wachtwoord", type="password")
        submitted = st.form_submit_button("Registreren")

        if submitted:
            if get_company_by_email(new_email):
                st.error("E-mailadres is al in gebruik.")
            elif new_name and new_email and new_password:
                new_company_id = add_company(new_name, new_email, new_password)
                st.success("✅ Account aangemaakt! Betaal nu om te activeren.")
                pay_url = create_checkout_session(new_company_id, new_email, new_name)
                if pay_url:
                    st.markdown(f"[Klik hier om te betalen (€25/maand)]({pay_url})")
            else:
                st.error("Vul alle velden in.")

    st.subheader("Bestaand bedrijf? Log in")
    login_email = st.text_input("E-mail", key="login_email")
    login_password = st.text_input("Wachtwoord", type="password", key="login_pw")
    if st.button("Inloggen"):
        company = get_company_by_email(login_email)
        if company and company[3] == login_password:
            st.session_state.logged_in = True
            st.session_state.company_id = company[0]
            st.session_state.company_name = company[1]
            st.success("Succesvol ingelogd.")
            st.rerun()
        else:
            st.error("Onjuiste inloggegevens.")
