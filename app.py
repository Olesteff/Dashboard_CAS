import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import numpy as np
from collections import Counter
from wordcloud import WordCloud
from io import BytesIO

# =============================
# Configuración inicial
# =============================
st.set_page_config(
    page_title="Dashboard de Producción Científica – CAS–UDD",
    layout="wide",
)

st.title("📊 Dashboard de Producción Científica – Clínica Alemana – Universidad del Desarrollo")

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = "Consolidado_enriq"

# =============================
# Funciones de utilidad
# =============================
@st.cache_data(show_spinner=False)
def load_data(uploaded=None, sheet_name=DEFAULT_SHEET):
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name)
    st.error("No se encontró el archivo de datos")
    return pd.DataFrame()

def normalize_quartile(df):
    if "JCR_Quartile" in df.columns:
        df["Quartile_std"] = df["JCR_Quartile"].fillna("Sin cuartil").astype(str).str.upper()
    elif "SJR_Quartile" in df.columns:
        df["Quartile_std"] = df["SJR_Quartile"].fillna("Sin cuartil").astype(str).str.upper()
    else:
        df["Quartile_std"] = "Sin cuartil"
    return df

def wordcloud_png(freq: dict, width: int = 1600, height: int = 800):
    try:
        wc = WordCloud(width=width, height=height, background_color="white", colormap="tab10")
        img = wc.generate_from_frequencies(freq).to_image()
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None

# =============================
# Carga de datos
# =============================
df = load_data()
if df.empty:
    st.stop()

# Normalizar columnas
if "Year" in df.columns:
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").fillna(0).astype(int)
else:
    df["Year"] = 0

df = normalize_quartile(df)

if "Open Access" not in df.columns:
    df["Open Access"] = False

if "Departamento" not in df.columns:
    df["Departamento"] = "Sin departamento"

# =============================
# Barra lateral de filtros
# =============================
st.sidebar.header("📂 Datos base")
uploaded_file = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
if uploaded_file:
    df = load_data(uploaded_file)

st.sidebar.header("Filtros")

# Rango de años
year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider(
    "Selecciona rango de años",
    min_value=year_min,
    max_value=year_max,
    value=(year_min, year_max)
)

# Open Access
oa_filter = st.sidebar.radio(
    "Open Access",
    options=["Todos", "Open Access", "Closed Access"],
    index=0
)

# Cuartiles
quartiles = st.sidebar.multiselect(
    "Cuartil JCR/SJR",
    options=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"],
    default=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
)

# Departamentos
departments = st.sidebar.multiselect(
    "Departamento",
    options=sorted(df["Departamento"].dropna().unique()),
    default=[]
)

# Buscar por título
title_search = st.sidebar.text_input("Buscar en título")

# =============================
# Aplicar filtros
# =============================
fdf = df.copy()
fdf = fdf[(fdf["Year"] >= year_range[0]) & (fdf["Year"] <= year_range[1])]
if oa_filter == "Open Access":
    fdf = fdf[fdf["Open Access"] == True]
elif oa_filter == "Closed Access":
    fdf = fdf[fdf["Open Access"] == False]

fdf = fdf[fdf["Quartile_std"].isin(quartiles)]
if departments:
    fdf = fdf[fdf["Departamento"].isin(departments)]
if title_search:
    fdf = fdf[fdf["Title"].str.contains(title_search, case=False, na=False)]

# =============================
# KPIs
# =============================
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total publicaciones", len(fdf))
with col2:
    pct_oa = (fdf["Open Access"].sum() / len(fdf) * 100) if len(fdf) > 0 else 0
    st.metric("% Open Access", f"{pct_oa:.1f}%")
with col3:
    clinical_trials = fdf["Clinical Trial"].sum() if "Clinical Trial" in fdf.columns else 0
    st.metric("Ensayos clínicos detectados", int(clinical_trials))
with col4:
    sponsors = fdf["Funding sponsor"].notna().sum() if "Funding sponsor" in fdf.columns else 0
    st.metric("Publicaciones con sponsor", int(sponsors))

# =============================
# Tabs
# =============================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👥 Autores", "☁️ Wordcloud"])

# --- Publicaciones ---
with tabs[0]:
    st.subheader("Publicaciones por año")
    pub_year = fdf.groupby("Year").size().reset_index(name="Publicaciones")
    fig_pub = px.line(pub_year, x="Year", y="Publicaciones", markers=True)
    st.plotly_chart(fig_pub, use_container_width=True)

# --- Cuartiles ---
with tabs[1]:
    st.subheader("Distribución por cuartil")
    q_counts = fdf["Quartile_std"].value_counts()
    fig_q = px.pie(
        names=q_counts.index,
        values=q_counts.values,
        hole=0.4,
        color=q_counts.index,
        color_discrete_map={
            "Q1": "green",
            "Q2": "yellow",
            "Q3": "orange",
            "Q4": "red",
            "Sin cuartil": "lightgrey"
        }
    )
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(q_counts.rename_axis("Cuartil").reset_index(name="Publicaciones"))

# --- Open Access ---
with tabs[2]:
    st.subheader("Distribución Open Access")
    oa_counts = fdf["Open Access"].value_counts(dropna=False)
    fig_oa = px.pie(
        names=oa_counts.index.map({True: "Open Access", False: "Closed Access", np.nan: "Desconocido"}),
        values=oa_counts.values,
        hole=0.4,
        color=oa_counts.index.map({True: "Open Access", False: "Closed Access", np.nan: "Desconocido"}),
        color_discrete_map={"Open Access": "green", "Closed Access": "red", "Desconocido": "lightgrey"}
    )
    st.plotly_chart(fig_oa, use_container_width=True)
    st.dataframe(oa_counts.rename_axis("Open Access").reset_index(name="Publicaciones"))

# --- Departamentos ---
with tabs[3]:
    st.subheader("Distribución por departamento")
    dept_counts = fdf["Departamento"].value_counts()
    fig_dept = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values, text=dept_counts.values)
    fig_dept.update_layout(xaxis_title="Departamento", yaxis_title="Publicaciones")
    st.plotly_chart(fig_dept, use_container_width=True)
    st.dataframe(dept_counts.rename_axis("Departamento").reset_index(name="Publicaciones"))

# --- Revistas ---
with tabs[4]:
    st.subheader("Revistas más frecuentes")
    if "Source title" in fdf.columns:
        journal_counts = fdf["Source title"].value_counts().head(20)
        st.bar_chart(journal_counts)

# --- Autores ---
with tabs[5]:
    st.subheader("Autores más frecuentes")
    if "Authors" in fdf.columns:
        author_counts = fdf["Authors"].str.split(";").explode().str.strip().value_counts().head(20)
        st.bar_chart(author_counts)

# --- Wordcloud ---
with tabs[6]:
    st.subheader("Wordcloud de títulos")
    if "Title" in fdf.columns:
        words = Counter(" ".join(fdf["Title"].dropna().astype(str)).lower().split())
        img_data = wordcloud_png(words)
        if img_data:
            st.image(img_data)