# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from wordcloud import WordCloud
from io import BytesIO

# ================================
# Configuración general
# ================================
st.set_page_config(
    page_title="Dashboard Producción Científica CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================
# Utilidades
# ================================
def _first_existing_col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    for n in df.columns:
        if any(k.lower() in n.lower() for k in names):
            return n
    return None

def load_and_clean(path):
    df = pd.read_excel(path)

    # Normalizar nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]

    # Año
    ycol = _first_existing_col(df, "Year", "Publication Year")
    if ycol:
        df[ycol] = pd.to_numeric(df[ycol], errors="coerce")
        df = df[df[ycol].between(1900, 2100)]
    else:
        df["Year"] = np.nan
        ycol = "Year"

    # Open Access
    oacol = _first_existing_col(df, "Open Access", "OA Type")
    if oacol:
        df["OA_clean"] = df[oacol].fillna("Desconocido").astype(str)
        df["OA_bin"] = np.where(df["OA_clean"].str.contains("open access", case=False), "OA", "No OA")
    else:
        df["OA_clean"] = "Desconocido"
        df["OA_bin"] = "No OA"

    # Cuartiles
    qcol = _first_existing_col(df, "JCR_Quartile", "Quartile_std", "SJR Quartile")
    if qcol:
        df["Quartile_std"] = df[qcol].fillna("Sin cuartil").astype(str)
    else:
        df["Quartile_std"] = "Sin cuartil"

    # Ensayos clínicos
    pcol = _first_existing_col(df, "Publication Type", "Document Type")
    if pcol:
        df["ClinicalTrial_flag"] = df[pcol].str.contains("Clinical Trial", case=False, na=False).astype(int)
    else:
        df["ClinicalTrial_flag"] = 0

    # Sponsors
    scol = _first_existing_col(df, "Funding Sponsor", "Sponsors")
    if scol:
        df["Sponsor_flag"] = df[scol].notna().astype(int)
    else:
        df["Sponsor_flag"] = 0

    return df, ycol

# ================================
# Cargar dataset
# ================================
st.sidebar.header("📂 Datos base")
uploaded = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
DEFAULT_PATH = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

if uploaded:
    df, ycol = load_and_clean(uploaded)
elif Path(DEFAULT_PATH).exists():
    df, ycol = load_and_clean(DEFAULT_PATH)
else:
    st.error("Sube un archivo XLSX para comenzar.")
    st.stop()

# ================================
# Filtros
# ================================
st.sidebar.header("Filtros")

year_min, year_max = int(df[ycol].min()), int(df[ycol].max())
year_range = st.sidebar.slider("Selecciona rango de años", year_min, year_max, (year_min, year_max))
df = df[df[ycol].between(year_range[0], year_range[1])]

oa_filter = st.sidebar.radio("Open Access", ["Todos", "Open Access", "Closed Access"])
if oa_filter == "Open Access":
    df = df[df["OA_bin"] == "OA"]
elif oa_filter == "Closed Access":
    df = df[df["OA_bin"] == "No OA"]

quartiles = st.sidebar.multiselect(
    "Cuartil JCR/SJR",
    options=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"],
    default=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"],
)
df = df[df["Quartile_std"].isin(quartiles)]

dcol = _first_existing_col(df, "Departamento", "Department")
if dcol:
    deptos = st.sidebar.multiselect("Departamento", sorted(df[dcol].dropna().unique()), default=[])
    if deptos:
        df = df[df[dcol].isin(deptos)]

search_term = st.sidebar.text_input("Buscar en título")
tcol = _first_existing_col(df, "Title", "Article Title")
if search_term and tcol:
    df = df[df[tcol].str.contains(search_term, case=False, na=False)]

# ================================
# KPIs
# ================================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total publicaciones", len(df))
c2.metric("% Open Access", f"{100*df['OA_bin'].eq('OA').mean():.1f}%")
c3.metric("Ensayos clínicos detectados", df["ClinicalTrial_flag"].sum())
c4.metric("Publicaciones con sponsor detectado", df["Sponsor_flag"].sum())

# ================================
# Tabs
# ================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📈 Publicaciones",
    "📊 Cuartiles",
    "🔓 Open Access",
    "🏥 Departamentos",
    "📚 Revistas",
    "👨‍🔬 Autores",
    "☁️ Wordcloud"
])

# --- Publicaciones
with tab1:
    pub_year = df.groupby(ycol).size().reset_index(name="Publicaciones")
    fig = px.line(pub_year, x=ycol, y="Publicaciones", markers=True)
    st.plotly_chart(fig, use_container_width=True)

# --- Cuartiles
with tab2:
    q_counts = df["Quartile_std"].value_counts().reset_index()
    q_counts.columns = ["Cuartil", "Publicaciones"]
    fig_q = px.pie(q_counts, names="Cuartil", values="Publicaciones", hole=0.4,
                   color="Cuartil",
                   color_discrete_map={"Q1":"green","Q2":"yellow","Q3":"orange","Q4":"red","Sin cuartil":"lightgrey"})
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(q_counts)

# --- Open Access
with tab3:
    oa_counts = df["OA_clean"].value_counts().reset_index()
    oa_counts.columns = ["OA tipo", "Publicaciones"]
    fig_oa = px.pie(oa_counts, names="OA tipo", values="Publicaciones", hole=0.4)
    st.plotly_chart(fig_oa, use_container_width=True)
    st.dataframe(oa_counts)

# --- Departamentos
with tab4:
    if dcol:
        dep_counts = df[dcol].value_counts().reset_index()
        dep_counts.columns = ["Departamento", "Publicaciones"]
        fig_d = px.bar(dep_counts, x="Departamento", y="Publicaciones")
        st.plotly_chart(fig_d, use_container_width=True)
        st.dataframe(dep_counts)

# --- Revistas
with tab5:
    jcol = _first_existing_col(df, "Source title", "Journal")
    if jcol:
        top_journals = df[jcol].value_counts().head(20).reset_index()
        top_journals.columns = ["Revista", "Publicaciones"]
        fig_j = px.bar(top_journals, x="Revista", y="Publicaciones")
        st.plotly_chart(fig_j, use_container_width=True)
        st.dataframe(top_journals)

# --- Autores
with tab6:
    acol = _first_existing_col(df, "Authors", "Author Full Names")
    if acol:
        top_authors = df[acol].str.split(";").explode().str.strip().value_counts().head(20).reset_index()
        top_authors.columns = ["Autor", "Publicaciones"]
        fig_a = px.bar(top_authors, x="Autor", y="Publicaciones")
        st.plotly_chart(fig_a, use_container_width=True)
        st.dataframe(top_authors)

# --- Wordcloud
with tab7:
    if tcol:
        text = " ".join(df[tcol].dropna().astype(str))
        if text.strip():
            wc = WordCloud(width=1600, height=800, background_color="white").generate(text)
            st.image(wc.to_array(), use_column_width=True)
        else:
            st.info("No hay títulos disponibles para generar Wordcloud.")
            