# /app/app.py
# Dashboard Cienciométrico CAS-UDD

from __future__ import annotations
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =============================
# Configuración general
# =============================
st.set_page_config(
    page_title="Dashboard Cienciométrico",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "_Year"],
    "journal": ["Journal_norm", "Source title", "Publication Name"],
    "dept": ["Departamento", "Department"],
    "cited": ["Times Cited", "Cited by"],
    "oa_flags": ["OpenAccess_flag", "OA", "Open Access"],
    "quartile": ["JCR_Quartile", "Quartile", "Cuartil"],
    "sponsor": ["Has_Sponsor"],
    "trial": ["ClinicalTrial_flag"],
}

# =============================
# Utilidades
# =============================
def _first_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for c in names:
        if c in df.columns:
            return c
    return None

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name="Datos") -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.getvalue()

# =============================
# Carga
# =============================
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, dtype=str)
    st.error("No se encontró dataset base")
    return pd.DataFrame()

# =============================
# KPIs
# =============================
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"

    if "DOI_norm" in dff.columns and len(dff):
        kpis["% con DOI"] = f"{(dff['DOI_norm'].notna().mean() * 100):.1f}%"
    else:
        kpis["% con DOI"] = "—"

    oa_col = _first_col(dff, CAND["oa_flags"])
    if oa_col and len(dff):
        kpis["% OA"] = f"{(dff[oa_col].eq('OA').mean() * 100):.1f}%"
    else:
        kpis["% OA"] = "—"

    ccol = _first_col(dff, CAND["cited"])
    if ccol:
        kpis["Mediana citas"] = f"{pd.to_numeric(dff[ccol], errors='coerce').median():.0f}"
    else:
        kpis["Mediana citas"] = "—"

    scol = _first_col(dff, CAND["sponsor"])
    if scol:
        kpis["Con sponsor"] = f"{int(dff[scol].sum()):,}"
    else:
        kpis["Con sponsor"] = "0"

    tcol = _first_col(dff, CAND["trial"])
    if tcol:
        kpis["Ensayos clínicos"] = f"{int(dff[tcol].sum()):,}"
    else:
        kpis["Ensayos clínicos"] = "0"

    return kpis

# =============================
# Gráficos
# =============================
def _fig_year_counts(dff):
    ycol = _first_col(dff, CAND["year"])
    if not ycol:
        return None
    g = dff[ycol].dropna().astype(int).value_counts().sort_index()
    return px.bar(x=g.index, y=g.values, labels={"x": "Año", "y": "Nº publicaciones"},
                  title="Publicaciones por año")

def _fig_oa_pie(dff):
    oa_col = _first_col(dff, CAND["oa_flags"])
    if not oa_col:
        return None
    counts = dff[oa_col].fillna("Desconocido").value_counts()
    fig = px.pie(names=counts.index, values=counts.values, title="Proporción OA / No OA")
    fig.update_traces(textinfo="percent+label")
    return fig

def _fig_quartiles(dff):
    qcol = _first_col(dff, CAND["quartile"])
    if not qcol:
        return None
    q_counts = dff[qcol].fillna("Sin cuartil").value_counts()
    fig = px.pie(names=q_counts.index, values=q_counts.values,
                 title="Distribución por cuartiles JCR")
    fig.update_traces(textinfo="percent+label")
    return fig

# =============================
# Sidebar
# =============================
with st.sidebar:
    st.subheader("Datos base")
    up = st.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])
    st.caption(f"Por defecto: `{DEFAULT_XLSX}` (se leerá la 1ª hoja)")
    st.markdown("---")

# Cargar dataset
df = load_dataframe(up)
if df.empty:
    st.stop()

mask = pd.Series(True, index=df.index)

with st.sidebar:
    # Años
    ycol = _first_col(df, CAND["year"])
    if ycol and df[ycol].notna().any():
        ys = pd.to_numeric(df[ycol], errors="coerce").dropna().astype(int)
        y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Año", y_min, y_max, (y_min, y_max))
        mask &= df[ycol].astype(float).between(y1, y2)

    # Fuente
    src_opts = [c for c in ["in_Scopus", "in_WoS", "in_PubMed"] if c in df.columns]
    sel_src = st.multiselect("Fuente", options=src_opts, default=src_opts)
    if sel_src:
        mask &= df[sel_src].fillna(False).any(axis=1)

    # OA
    oa_col = _first_col(df, CAND["oa_flags"])
    if oa_col:
        vals = df[oa_col].fillna("Desconocido").unique().tolist()
        sel_oa = st.multiselect("Open Access", vals, default=vals)
        mask &= df[oa_col].isin(sel_oa)

    # Cuartiles
    qcol = _first_col(df, CAND["quartile"])
    if qcol:
        q_vals = df[qcol].fillna("Sin cuartil").unique().tolist()
        sel_q = st.multiselect("Cuartil JCR", q_vals, default=q_vals)
        mask &= df[qcol].fillna("Sin cuartil").isin(sel_q)

    # Departamento
    dcol = _first_col(df, CAND["dept"])
    if dcol:
        dep_vals = df[dcol].dropna().unique().tolist()
        sel_dep = st.multiselect("Departamento", dep_vals, default=[])
        if sel_dep:
            mask &= df[dcol].isin(sel_dep)

    query = st.text_input("Buscar en título", "")
    tcol = _first_col(df, CAND["title"])
    if query and tcol:
        mask &= df[tcol].fillna("").str.contains(query, case=False, na=False)

dff = df[mask].copy()

# =============================
# Tabs
# =============================
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📊 Cuartiles"])

with tabs[0]:
    st.subheader("KPIs")
    k1, k2, k3, k4, k5 = st.columns(5)
    KP = _kpis_summary(dff)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"])
    k2.metric("% OA", KP["% OA"])
    k3.metric("Mediana citas", KP["Mediana citas"])
    k4.metric("Con sponsor", KP["Con sponsor"])
    k5.metric("Ensayos clínicos", KP["Ensayos clínicos"])

    fig_y = _fig_year_counts(dff)
    if fig_y:
        st.plotly_chart(fig_y, use_container_width=True, key="fig_year")

    fig_oa = _fig_oa_pie(dff)
    if fig_oa:
        st.plotly_chart(fig_oa, use_container_width=True, key="fig_oa")

with tabs[1]:
    st.subheader("Datos filtrados")
    st.dataframe(dff.head(500), use_container_width=True)
    st.download_button("⬇️ CSV", dff.to_csv(index=False).encode("utf-8"),
                       "resultados_filtrados.csv", "text/csv")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    st.download_button("⬇️ XLSX", xlsx_bytes, "resultados_filtrados.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tabs[2]:
    st.subheader("📊 Distribución por cuartiles JCR")
    fig_q = _fig_quartiles(dff)
    if fig_q:
        st.plotly_chart(fig_q, use_container_width=True, key="fig_quartiles")
    else:
        st.info("No se encontró columna de cuartiles.")