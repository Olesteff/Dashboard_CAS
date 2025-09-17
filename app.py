# /app/app.py
# Dashboard Cienciométrico con filtros, KPIs y gráficas

from __future__ import annotations
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# -----------------------------
# Configuración general
# -----------------------------
st.set_page_config(
    page_title="Dashboard Cienciométrico",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "_Year", "Year_clean"],
    "doi": ["DOI", "Doi"],
    "journal": ["Journal_norm", "Source title", "Publication Name"],
    "dept": ["Departamento", "Dept_CAS_list", "Dept_FMUDD_list", "Department"],
    "authors": ["Author Full Names", "Authors"],
    "cited": ["Cited by", "Times Cited"],
    "quartile": ["JCR_Quartile", "Quartile", "Cuartil"],
}

# -----------------------------
# Utilidades
# -----------------------------
def _first_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for c in names:
        if c in df.columns:
            return c
    return None

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    try:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=sheet_name)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

# -----------------------------
# Gráficos
# -----------------------------
def _fig_year_counts(dff: pd.DataFrame):
    ycol = _first_col(dff, CAND["year"])
    if ycol is None:
        return None
    g = dff[ycol].dropna().astype(int).value_counts().sort_index()
    return px.bar(x=g.index, y=g.values, labels={"x": "Año", "y": "Nº publicaciones"}, title="Conteo por año")

def _fig_oa_pie(dff: pd.DataFrame):
    if "Open Access" not in dff.columns:
        return None
    oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
    fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="Proporción OA / No OA")
    fig.update_traces(textinfo="percent+label")
    return fig

def _fig_quartiles(dff: pd.DataFrame):
    qcol = _first_col(dff, CAND["quartile"])
    if qcol is None:
        return None
    q_counts = dff[qcol].fillna("Sin cuartil").value_counts()
    fig = px.pie(
        names=q_counts.index,
        values=q_counts.values,
        hole=0.4,
        title="Distribución por cuartiles JCR"
    )
    fig.update_traces(textinfo="percent+label")
    return fig

# -----------------------------
# KPIs
# -----------------------------
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"

    if "DOI_norm" in dff.columns and len(dff):
        kpis["% con DOI"] = f"{(dff['DOI_norm'].notna().mean() * 100):.1f}%"
    else:
        kpis["% con DOI"] = "—"

    if "Open Access" in dff.columns and len(dff):
        kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%"
    else:
        kpis["% OA"] = "—"

    if "Times Cited" in dff.columns and len(dff):
        kpis["Mediana citas"] = f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}"
    else:
        kpis["Mediana citas"] = "—"

    if "Has_Sponsor" in dff.columns:
        kpis["Con sponsor"] = f"{int(dff['Has_Sponsor'].sum()):,}"
    else:
        kpis["Con sponsor"] = "0"

    if "ClinicalTrial_flag" in dff.columns:
        kpis["Ensayos clínicos"] = f"{int(dff['ClinicalTrial_flag'].sum()):,}"
    else:
        kpis["Ensayos clínicos"] = "0"

    return kpis

# -----------------------------
# Carga de datos
# -----------------------------
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, dtype=str)
    st.stop()

try:
    df = load_dataframe(st.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"]))
except Exception as e:
    st.error(str(e))
    st.stop()

df.columns = df.columns.astype(str).str.strip()

# -----------------------------
# Filtros
# -----------------------------
mask = pd.Series(True, index=df.index)

ycol = _first_col(df, CAND["year"])
if ycol:
    ys = df[ycol].dropna().astype(int)
    y_min, y_max = int(ys.min()), int(ys.max())
    y1, y2 = st.sidebar.slider("Año", y_min, y_max, (y_min, y_max))
    mask &= df[ycol].astype(float).between(y1, y2)

src_opts = [c for c in ["in_Scopus", "in_WoS", "in_PubMed"] if c in df.columns]
sel_src = st.sidebar.multiselect("Fuente", options=src_opts, default=src_opts)
if sel_src:
    mask &= df[sel_src].fillna(False).any(axis=1)

if "Open Access" in df.columns:
    oa_vals = ["OA", "No OA", "Desconocido"]
    sel_oa = st.sidebar.multiselect("Open Access", oa_vals, default=oa_vals)
    mask &= df["Open Access"].isin(sel_oa)

if "Departamento" in df.columns:
    dep_pool = df["Departamento"].dropna().unique().tolist()
    sel_dep = st.sidebar.multiselect("Departamento", sorted(dep_pool), default=[])
    if sel_dep:
        mask &= df["Departamento"].isin(sel_dep)

dff = df[mask].copy()

# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📊 Cuartiles"])

# --- RESUMEN ---
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
        st.plotly_chart(fig_y, use_container_width=True, key="fig_year_resumen")

    fig_oa = _fig_oa_pie(dff)
    if fig_oa:
        st.plotly_chart(fig_oa, use_container_width=True, key="fig_oa_resumen")

# --- DATOS ---
with tabs[1]:
    st.subheader("Datos filtrados")
    st.dataframe(dff.head(500), use_container_width=True)
    st.download_button("⬇️ CSV", dff.to_csv(index=False).encode("utf-8"),
                       "resultados_filtrados.csv", "text/csv")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ XLSX", xlsx_bytes, "resultados_filtrados.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- CUARTILES ---
with tabs[2]:
    st.subheader("📊 Distribución por cuartiles JCR")
    fig_q = _fig_quartiles(dff)
    if fig_q:
        st.plotly_chart(fig_q, use_container_width=True, key="fig_quartiles_tab")
    else:
        st.info("No se encontró columna de cuartiles en el dataset.")