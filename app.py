# app_dashboard.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, List

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
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Devuelve la primera columna existente en el DF de una lista de candidatos."""
    for c in candidates:
        if c in df.columns:
            return c
    return None

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

# =========================
# Normalización de columnas
# =========================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Año
    year_col = _first_col(df, ["_Year", "Year", "Publication Year", "PY"])
    if year_col:
        df["Year"] = pd.to_numeric(df[year_col], errors="coerce")
    else:
        df["Year"] = pd.NA

    # Open Access
    oa_col = _first_col(df, ["OpenAccess_flag", "Open Access", "OA"])
    if oa_col:
        df["OpenAccess_flag"] = df[oa_col].astype(str).str.lower().isin(
            {"1","true","t","yes","y","si","sí"}
        )
    else:
        df["OpenAccess_flag"] = False

    # JIF
    jif_col = _first_col(df, [
        "Journal Impact Factor", "Impact Factor", "JIF", "JIF_2023", "JCR_IF"
    ])
    if jif_col:
        df["Journal Impact Factor"] = pd.to_numeric(df[jif_col], errors="coerce").fillna(0)
    else:
        df["Journal Impact Factor"] = 0

    # Cuartiles
    def normalize_quartile(df: pd.DataFrame) -> pd.Series:
        q_col = _first_col(df, [
            "JCR Quartile", "JCR_Quartile", "Quartile", "quartile_std",
            "SJR Quartile", "SJR_Quartile","Quartile_JCR","JIF Quartile"
        ])
        if not q_col:
            return pd.Series("Sin cuartil", index=df.index)

        raw = df[q_col].astype(str).str.upper().str.strip()

        mapping = {
            "1": "Q1", "Q-1": "Q1", "QUARTIL 1": "Q1",
            "2": "Q2", "Q-2": "Q2", "QUARTIL 2": "Q2",
            "3": "Q3", "Q-3": "Q3", "QUARTIL 3": "Q3",
            "4": "Q4", "Q-4": "Q4", "QUARTIL 4": "Q4",
        }
        norm = raw.replace(mapping)
        norm = norm.str.extract(r"(Q[1-4])", expand=False).fillna(norm)
        norm = norm.where(norm.isin(["Q1","Q2","Q3","Q4"]), "Sin cuartil")
        return norm

    df["Quartile"] = normalize_quartile(df)

    # Departamentos
    aff_col = _first_col(df, ["Authors with affiliations", "Affiliations", "Author Affiliations"])
    if aff_col:
        df["Departamento"] = df[aff_col].apply(detect_department)
    else:
        df["Departamento"] = "Sin asignar"

    # Ensayos clínicos
    df["ClinicalTrial_flag"] = df.apply(detect_clinical_trial, axis=1)

    # Revistas
    jr_col = _first_col(df, ["Journal_norm", "Journal", "Source Title", "Publication Name", "Source title"])
    if jr_col:
        df["Journal_norm"] = df[jr_col].astype(str).fillna("—")
    else:
        df["Journal_norm"] = "—"

    # Autores
    a_col = _first_col(df, ["Author Full Names", "Author full names", "Authors"])
    if a_col:
        df["Authors_norm"] = df[a_col].astype(str).fillna("")
    else:
        df["Authors_norm"] = ""

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
    journal_count = dff["Journal_norm"].value_counts().head(20).reset_index()
    journal_count.columns = ["Revista", "Publicaciones"]
    st.dataframe(journal_count)

with tabs[5]:
    st.subheader("👥 Autores más frecuentes")
    authors = dff["Authors_norm"].dropna().str.split(";|,|\\|").explode().str.strip()
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