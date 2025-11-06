# pages/01_Publieke_catalogus.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from database import init_db, get_public_services, get_company_name_by_id

# ---------- Setup ----------
st.set_page_config(page_title="D’or – Publieke catalogus", page_icon="🌐", layout="wide")
init_db()

def _fmt_eur(x) -> str:
    try:
        return f"€{float(x):.2f}".replace(".", ",")
    except Exception:
        return "€0,00"

# ---------- Company context ----------
params = st.experimental_get_query_params()
company_param = params.get("company", [None])[0]

st.title("Diensten & tarieven")

if company_param is None:
    st.info("Geef het **bedrijf-ID** in om de catalogus te tonen.")
    cid = st.number_input("Bedrijf ID", min_value=1, step=1, value=1)
    if st.button("Toon catalogus"):
        st.experimental_set_query_params(company=str(int(cid)))
        st.rerun()
    st.stop()

try:
    company_id = int(company_param)
except ValueError:
    st.error("Ongeldig bedrijf-ID in de URL-parameter ?company=...")
    st.stop()

company_name = get_company_name_by_id(company_id)
st.caption(f"Bedrijf: **{company_name}** (#{company_id})")

# ---------- Data ----------
df = get_public_services(company_id)

if df.empty:
    st.info("Er zijn nog geen gepubliceerde diensten.")
else:
    # nette grouping per categorie
    for cat, grp in df.groupby(df["category"].fillna("Algemeen")):
        with st.expander(str(cat), expanded=True):
            for _, r in grp.iterrows():
                st.markdown(
                    f"**{r['name']}** — {_fmt_eur(r['price'])} • {int(r['duration'])} min"
                )
                if r.get("description"):
                    st.caption(r["description"])
                st.divider()

# (optioneel) link terug naar hoofdapp als je dat prettig vindt:
try:
    st.page_link("app.py", label="⤺ Terug naar beheer", icon="↩️")
except Exception:
    pass
