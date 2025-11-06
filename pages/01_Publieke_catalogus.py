from __future__ import annotations

import streamlit as st

from database import (
    init_db,
    get_public_services,
    get_company_name_by_id,
    get_company_by_slug,
    get_company,
)

st.set_page_config(
    page_title="D’or – Publieke catalogus",
    page_icon="🌐",
    layout="wide",
)

init_db()


def _fmt_eur(x) -> str:
    try:
        return f"€{float(x):.2f}".replace(".", ",")
    except Exception:
        return "€0,00"


params = st.experimental_get_query_params()
param_company = params.get("company", [None])[0]

company_id = None
company_name = None

if param_company:
    value = str(param_company)
    row = get_company_by_slug(value)
    if not row and value.isdigit():
        try:
            row = get_company(int(value))
        except Exception:
            row = None
    if row:
        company_id = int(row[0])
        company_name = row[1]

st.title("Diensten & tarieven")

if not company_id:
    st.info(
        "Dit is de **publieke catalogus** die je met klanten kunt delen.\n\n"
        "- Gebruik in je link `?company=JOUW-BEDRIJFSNAAM&view=public`.\n"
        "- Of vul hieronder tijdelijk je Bedrijf-ID in om te testen."
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        c_id = st.number_input("Bedrijf-ID", min_value=1, step=1, value=1)
    with col2:
        if st.button("Toon catalogus", type="primary"):
            st.experimental_set_query_params(company=str(int(c_id)))
            st.rerun()
else:
    st.subheader(f"Bedrijf: {company_name} (#{company_id})")
    df = get_public_services(company_id)
    if df.empty:
        st.info("Er zijn nog geen gepubliceerde diensten.")
    else:
        if "category" in df.columns:
            for cat, grp in df.groupby("category"):
                label = str(cat) if str(cat).strip() else "Overige diensten"
                with st.expander(label, expanded=True):
                    for _, r in grp.iterrows():
                        st.markdown(
                            f"**{r['name']}** — {_fmt_eur(r['price'])} • {int(r['duration'])} min"
                        )
                        if r.get("description"):
                            st.caption(str(r["description"]))
                        st.divider()
        else:
            st.table(df)

try:
    st.page_link("app.py", label="⤺ Terug naar beheer", icon="↩️")
except Exception:
    pass
