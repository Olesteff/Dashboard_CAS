# ============================================
# 📊 Dashboard CAS – Producción científica
# ============================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from typing import Dict
from pathlib import Path

# =========================
# 📂 Configuración
# =========================
st.set_page_config(page_title="Dashboard CAS", layout="wide")

DEFAULT_FILE = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

# =========================
# 📥 Cargar dataset
# =========================
st.sidebar.header("Datos base")

uploaded_file = st.sidebar.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name=0)
else:
    if Path(DEFAULT_FILE).exists():
        df = pd.read_excel(DEFAULT_FILE, sheet_name=0)
        st.sidebar.markdown(f"Por defecto: `{DEFAULT_FILE}` (se leerá la 1ª hoja)")
    else:
        st.error("No se encontró archivo base ni se subió uno.")
        st.stop()

# =========================
# 🔄 Actualizar dataset (merge)
# =========================
st.sidebar.subheader("Actualizar dataset (merge)")
merge_file = st.sidebar.file_uploader("Nuevos CSV/XLSX", type=["csv", "xlsx"])
apply_merge = st.sidebar.checkbox("Aplicar actualización")

if merge_file and apply_merge:
    new_df = pd.read_csv(merge_file) if merge_file.name.endswith(".csv") else pd.read_excel(merge_file)
    df = pd.concat([df, new_df], ignore_index=True).drop_duplicates()
    st.sidebar.success("✅ Dataset actualizado")

# =========================
# 🎛 Filtros
# =========================
st.sidebar.header("Filtros")

# Rango de años
if "Year" in df.columns:
    min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
    year_range = st.sidebar.slider("Año", min_year, max_year, (min_year, max_year))
else:
    year_range = (1980, 2030)

# Fuente
fuentes = [c for c in ["in_Scopus", "in_WoS", "in_PubMed"] if c in df.columns]
fuente_sel = st.sidebar.multiselect("Fuente", fuentes, default=fuentes)

# Open Access
if "Open Access" in df.columns:
    oa_opts = df["Open Access"].dropna().unique().tolist()
    oa_sel = st.sidebar.multiselect("Open Access", oa_opts, default=oa_opts)
else:
    oa_sel = []

# Cuartiles
if "JCR_Quartile" in df.columns:
    quartiles = df["JCR_Quartile"].dropna().unique().tolist()
    quartile_sel = st.sidebar.multiselect("Cuartil JCR", quartiles, default=quartiles)
else:
    quartile_sel = []

# Buscar título
title_kw = st.sidebar.text_input("Buscar en título")

# Departamento
if "Departamento" in df.columns:
    dept_opts = df["Departamento"].dropna().unique().tolist()
    dept_sel = st.sidebar.multiselect("Departamento", dept_opts)
else:
    dept_sel = []

# =========================
# 🔍 Aplicar filtros
# =========================
dff = df.copy()

if "Year" in dff.columns:
    dff = dff[dff["Year"].between(year_range[0], year_range[1])]

for col in fuente_sel:
    dff = dff[dff[col] == True]

if oa_sel and "Open Access" in dff.columns:
    dff = dff[dff["Open Access"].isin(oa_sel)]

if quartile_sel and "JCR_Quartile" in dff.columns:
    dff = dff[dff["JCR_Quartile"].isin(quartile_sel)]

if title_kw:
    dff = dff[dff["Article Title"].str.contains(title_kw, case=False, na=False)]

if dept_sel and "Departamento" in dff.columns:
    dff = dff[dff["Departamento"].isin(dept_sel)]

# =========================
# 📊 KPIs
# =========================
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"

    # OA
    if "Open Access" in dff.columns:
        kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%"
    else:
        kpis["% OA"] = "—"

    # Citas
    if "Times Cited" in dff.columns:
        kpis["Mediana citas"] = f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}"
    else:
        kpis["Mediana citas"] = "—"

    # Sponsors
    if "Has_Sponsor" in dff.columns:
        kpis["Con sponsor"] = f"{int(dff['Has_Sponsor'].sum()):,}"
    else:
        kpis["Con sponsor"] = "0"

    # Ensayos clínicos
    if "ClinicalTrial_flag" in dff.columns:
        kpis["Ensayos clínicos"] = f"{int(dff['ClinicalTrial_flag'].sum()):,}"
    else:
        kpis["Ensayos clínicos"] = "0"

    return kpis

st.markdown("## 📊 Resumen")

KP = _kpis_summary(dff)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Nº publicaciones", KP["Nº publicaciones"])
k2.metric("% OA", KP["% OA"])
k3.metric("Mediana citas", KP["Mediana citas"])
k4.metric("Con sponsor", KP["Con sponsor"])
k5.metric("Ensayos clínicos", KP["Ensayos clínicos"])

# =========================
# 🥧 Gráfico OA
# =========================
if "Open Access" in dff.columns and not dff.empty:
    fig_oa = px.pie(dff, names="Open Access", title="Proporción OA / No OA", hole=0.4)
    st.plotly_chart(fig_oa, use_container_width=True, key="oa_pie_resumen")

# =========================
# 🥧 Gráfico Cuartiles
# =========================
if "JCR_Quartile" in dff.columns and not dff.empty:
    fig_q = px.pie(
        dff,
        names="JCR_Quartile",
        title="Distribución por cuartiles JCR",
        hole=0.4,
        color="JCR_Quartile",
        color_discrete_map={
            "Q1": "green",
            "Q2": "yellow",
            "Q3": "orange",
            "Q4": "darkred",
            "Sin cuartil": "lightgrey",
        },
    )
    st.plotly_chart(fig_q, use_container_width=True, key="quartiles_pie_resumen")