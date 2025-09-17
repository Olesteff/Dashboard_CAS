# app_dashboard.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# =========================
# Config
# =========================
st.set_page_config(
    page_title="📊 Dashboard de Producción Científica",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET_INDEX = 0

# =========================
# Funciones de apoyo
# =========================
def detect_department(affiliation: str) -> str:
    if not isinstance(affiliation, str):
        return "Sin asignar"
    aff = affiliation.lower()
    rules = [
        ("neurolog", "Neurología y Psiquiatría"),
        ("psiquiatr", "Neurología y Psiquiatría"),
        ("oncolog", "Oncología"),
        ("pediatr", "Pediatría"),
        ("ginecol", "Ginecología y Obstetricia"),
        ("obstetr", "Ginecología y Obstetricia"),
        ("medicina interna", "Medicina Interna"),
        ("internal medicine", "Medicina Interna"),
        ("trauma", "Traumatología y Ortopedia"),
        ("ortoped", "Traumatología y Ortopedia"),
        ("enfermer", "Enfermería"),
        ("imagen", "Imágenes"),
        ("radiolog", "Imágenes"),
        ("urgenc", "Urgencias"),
        ("cirug", "Cirugía"),
        ("anestesi", "Anestesiología"),
        ("cardiol", "Cardiología"),
    ]
    for kw, dep in rules:
        if kw in aff:
            return dep
    return "Clínica Alemana"

def detect_clinical_trial(row) -> bool:
    text = ""
    for col in ["Title", "Abstract", "Publication Type", "Keywords"]:
        if col in row and pd.notna(row[col]):
            text += " " + str(row[col])
    text = text.lower()
    ct_regex = r"(ensayo\s*cl[ií]nico|clinical\s*trial|randomi[sz]ed|phase\s*[i1v]+|double\s*blind|placebo\-controlled)"
    return bool(re.search(ct_regex, text))

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Año
    year_cols = ["_Year", "Year", "Publication Year", "PY"]
    for col in year_cols:
        if col in df.columns:
            df["Year"] = pd.to_numeric(df[col], errors="coerce")
            break
    if "Year" not in df.columns:
        df["Year"] = pd.NA

    # Open Access
    if "OpenAccess_flag" in df.columns:
        df["OpenAccess_flag"] = (
            df["OpenAccess_flag"].astype(str).str.lower().map({"true": True, "false": False})
        )
    else:
        df["OpenAccess_flag"] = False

    # JIF
    jif_cols = ["Journal Impact Factor", "Impact Factor", "JIF"]
    for col in jif_cols:
        if col in df.columns:
            df["Journal Impact Factor"] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            break
    if "Journal Impact Factor" not in df.columns:
        df["Journal Impact Factor"] = 0

    # Cuartiles
    quart_cols = ["JCR Quartile", "Quartile", "quartile_std"]
    for col in quart_cols:
        if col in df.columns:
            q = df[col].astype(str).str.upper().str.extract(r"(Q[1-4])", expand=False)
            df["Quartile"] = q.fillna("Sin cuartil")
            break
    if "Quartile" not in df.columns:
        df["Quartile"] = "Sin cuartil"

    # Departamentos
    aff_col = next((c for c in ["Authors with affiliations", "Affiliations", "Author Affiliations"] if c in df.columns), None)
    if aff_col:
        df["Departamento"] = df[aff_col].apply(detect_department)
    else:
        df["Departamento"] = "Sin asignar"

    # Ensayos clínicos
    df["ClinicalTrial_flag"] = df.apply(detect_clinical_trial, axis=1)

    return df

# =========================
# Carga
# =========================
@st.cache_data
def load_data(uploaded=None) -> pd.DataFrame:
    if uploaded is not None:
        df = pd.read_excel(uploaded, sheet_name=DEFAULT_SHEET_INDEX)
    elif Path(DEFAULT_XLSX).exists():
        df = pd.read_excel(DEFAULT_XLSX, sheet_name=DEFAULT_SHEET_INDEX)
    else:
        st.stop()
    return normalize_columns(df)

up = st.sidebar.file_uploader("📂 Sube un XLSX", type=["xlsx"])
df = load_data(up)

# =========================
# Filtros
# =========================
st.sidebar.header("🔎 Filtros")

year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Años", year_min, year_max, (year_min, year_max))

oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo OA", "No OA"])
quart_filter = st.sidebar.multiselect("Cuartiles", df["Quartile"].unique(), default=df["Quartile"].unique())
dept_filter = st.sidebar.multiselect("Departamentos", df["Departamento"].unique(), default=df["Departamento"].unique())
search_term = st.sidebar.text_input("Buscar en títulos")

dff = df[(df["Year"].between(year_range[0], year_range[1])) &
         (df["Quartile"].isin(quart_filter)) &
         (df["Departamento"].isin(dept_filter))]

if oa_filter == "Solo OA":
    dff = dff[dff["OpenAccess_flag"] == True]
elif oa_filter == "No OA":
    dff = dff[dff["OpenAccess_flag"] == False]

if search_term:
    dff = dff[dff["Title"].astype(str).str.contains(search_term, case=False, na=False)]

# =========================
# KPIs
# =========================
c1, c2, c3, c4 = st.columns(4)
c1.metric("📚 Publicaciones", len(dff))
c2.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
c3.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
c4.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

# =========================
# Tabs
# =========================
tabs = st.tabs(["📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📑 Revistas", "👥 Autores", "☁️ Wordcloud"])

with tabs[0]:
    st.subheader("📅 Publicaciones por año")
    pub_year = dff.groupby("Year").size().reset_index(name="Publicaciones")
    st.plotly_chart(px.bar(pub_year, x="Year", y="Publicaciones", title="Publicaciones por Año"), use_container_width=True)

    st.subheader("📈 Evolución JIF por año")
    jif_year = dff.groupby("Year")["Journal Impact Factor"].sum().reset_index()
    st.plotly_chart(px.line(jif_year, x="Year", y="Journal Impact Factor", markers=True, title="Suma JIF por Año"), use_container_width=True)

with tabs[1]:
    st.subheader("📊 Distribución por cuartiles")
    quart_count = dff["Quartile"].value_counts().reset_index()
    quart_count.columns = ["Quartile", "Publicaciones"]
    st.plotly_chart(px.pie(quart_count, names="Quartile", values="Publicaciones", hole=0.4), use_container_width=True)

with tabs[2]:
    st.subheader("🔓 Publicaciones Open Access")
    oa_count = dff["OpenAccess_flag"].value_counts().reset_index()
    oa_count.columns = ["OpenAccess", "Publicaciones"]
    st.plotly_chart(px.pie(oa_count, names="OpenAccess", values="Publicaciones", hole=0.4), use_container_width=True)

with tabs[3]:
    st.subheader("🏥 Publicaciones por Departamento")
    dept_count = dff["Departamento"].value_counts().reset_index()
    dept_count.columns = ["Departamento", "Publicaciones"]
    st.plotly_chart(px.bar(dept_count, x="Departamento", y="Publicaciones", title="Publicaciones por Departamento"), use_container_width=True)

with tabs[4]:
    st.subheader("📑 Revistas más frecuentes")
    jr_col = next((c for c in ["Journal", "Source Title", "Publication Name"] if c in dff.columns), None)
    if jr_col:
        journal_count = dff[jr_col].value_counts().head(20).reset_index()
        journal_count.columns = ["Revista", "Publicaciones"]
        st.dataframe(journal_count)

with tabs[5]:
    st.subheader("👥 Autores más frecuentes")
    authors_col = next((c for c in ["Author Full Names", "Authors", "Authors with affiliations"] if c in dff.columns), None)
    if authors_col:
        authors = dff[authors_col].dropna().str.split(";|,|\\|").explode().str.strip()
        top_authors = authors.value_counts().head(20).reset_index()
        top_authors.columns = ["Autor", "Publicaciones"]
        st.dataframe(top_authors)

with tabs[6]:
    st.subheader("☁️ Wordcloud de títulos")
    if "Title" in dff and not dff["Title"].dropna().empty:
        text = " ".join(dff["Title"].dropna().tolist())
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        fig, ax = plt.subplots()
        ax.imshow(wc, interpolation="bilinear"); ax.axis("off")
        st.pyplot(fig)