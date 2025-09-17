# ============================================
# Dashboard CAS – versión completa corregida
# ============================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from typing import Dict
from wordcloud import WordCloud
import matplotlib.pyplot as plt

st.set_page_config(page_title="Dashboard CAS", layout="wide")

# =========================
# 📥 Carga de datos
# =========================
st.sidebar.header("Datos base")

uploaded_file = st.sidebar.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file, sheet_name=0)
else:
    df = pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS.xlsx", sheet_name=0)

# -------------------------
# Merge con nuevos datasets
# -------------------------
st.sidebar.subheader("Actualizar dataset (merge)")
new_files = st.sidebar.file_uploader("Nuevos CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=True)

if new_files:
    dfs_new = []
    for f in new_files:
        if f.name.endswith(".csv"):
            dfs_new.append(pd.read_csv(f))
        else:
            dfs_new.append(pd.read_excel(f))
    df_new = pd.concat(dfs_new, ignore_index=True)
    if st.sidebar.checkbox("Previsualizar unión"):
        st.write("Preview unión", df_new.head())
    if st.sidebar.button("Aplicar actualización"):
        df = pd.concat([df, df_new], ignore_index=True)
        st.success("Dataset actualizado")

# =========================
# 🎚️ Filtros
# =========================
st.sidebar.header("Filtros")

# Años
if "Year" in df.columns:
    min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
    year_range = st.sidebar.slider("Año", min_year, max_year, (min_year, max_year))
    df = df[(df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])]

# Fuente
if any(col in df.columns for col in ["in_Scopus", "in_WoS", "in_PubMed"]):
    fuentes = []
    for col in ["in_Scopus", "in_WoS", "in_PubMed"]:
        if col in df.columns:
            fuentes.append(col)
    selected_fuentes = st.sidebar.multiselect("Fuente", options=fuentes, default=fuentes)
    if selected_fuentes:
        mask = df[selected_fuentes].any(axis=1)
        df = df[mask]

# Open Access
if "Open Access" in df.columns:
    oa_vals = df["Open Access"].fillna("Desconocido").unique().tolist()
    selected_oa = st.sidebar.multiselect("Open Access", options=oa_vals, default=oa_vals)
    df = df[df["Open Access"].isin(selected_oa)]

# Buscar en título
if "Article Title" in df.columns:
    text_search = st.sidebar.text_input("Buscar en título")
    if text_search:
        df = df[df["Article Title"].str.contains(text_search, case=False, na=False)]

# Departamento
if "Departamento" in df.columns:
    deps = df["Departamento"].dropna().unique().tolist()
    selected_deps = st.sidebar.multiselect("Departamento", options=deps, default=deps)
    df = df[df["Departamento"].isin(selected_deps)]

# Cuartiles JCR
if "JCR_Quartile" in df.columns:
    quartiles = df["JCR_Quartile"].fillna("Sin cuartil").unique().tolist()
    selected_quartiles = st.sidebar.multiselect("Cuartiles JCR", options=quartiles, default=quartiles)
    df = df[df["JCR_Quartile"].fillna("Sin cuartil").isin(selected_quartiles)]

# =========================
# 📊 KPIs
# =========================
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

k1, k2, k3, k4, k5 = st.columns(5)
KP = _kpis_summary(df)
k1.metric("Nº publicaciones", KP["Nº publicaciones"])
k2.metric("% OA", KP["% OA"])
k3.metric("Mediana citas", KP["Mediana citas"])
k4.metric("Con sponsor", KP["Con sponsor"])
k5.metric("Ensayos clínicos", KP["Ensayos clínicos"])

# =========================
# 📈 Gráficos
# =========================

# OA
if "Open Access" in df.columns:
    oa_counts = df["Open Access"].fillna("Desconocido").value_counts()
    fig_oa = px.pie(
        names=oa_counts.index,
        values=oa_counts.values,
        hole=0.4,
        title="Proporción OA / No OA"
    )
    st.plotly_chart(fig_oa, use_container_width=True, key="oa_chart")

# Cuartiles JCR
if "JCR_Quartile" in df.columns:
    quartile_counts = df["JCR_Quartile"].fillna("Sin cuartil").value_counts()
    fig_q = px.pie(
        names=quartile_counts.index,
        values=quartile_counts.values,
        hole=0.4,
        color=quartile_counts.index,
        color_discrete_map={
            "Q1": "green",
            "Q2": "yellow",
            "Q3": "orange",
            "Q4": "darkred",
            "Sin cuartil": "lightgrey"
        },
        title="Distribución por cuartiles JCR"
    )
    st.plotly_chart(fig_q, use_container_width=True, key="quartiles_chart")

# Wordcloud de títulos
if "Article Title" in df.columns:
    text = " ".join(df["Article Title"].dropna().astype(str).tolist())
    if text.strip():
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        st.subheader("Nube de palabras en títulos")
        fig_wc, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig_wc, key="wordcloud_chart")