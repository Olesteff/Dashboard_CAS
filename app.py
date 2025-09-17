# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from wordcloud import WordCloud
from io import BytesIO

# ============================
# CONFIGURACIÓN GENERAL
# ============================
st.set_page_config(
    page_title="Dashboard CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = 0

# ============================
# CARGA DE DATOS
# ============================
@st.cache_data
def load_dataframe(uploaded=None, sheet_name=DEFAULT_SHEET):
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name)
    elif Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name)
    else:
        st.error("No se encontró dataset base.")
        return pd.DataFrame()

df = load_dataframe()

# Normalización de columnas clave
if "Year" in df.columns:
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

if "JCR_Quartile" not in df.columns:
    df["JCR_Quartile"] = "Sin cuartil"

if "Open Access" in df.columns:
    df["Open Access"] = df["Open Access"].fillna("Desconocido")
else:
    df["Open Access"] = "Desconocido"

if "Departamento" not in df.columns:
    df["Departamento"] = "Otro"

# ============================
# SIDEBAR – FILTROS
# ============================
st.sidebar.header("Datos base")
uploaded = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
if uploaded:
    df = load_dataframe(uploaded)

st.sidebar.header("Filtros")

min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider(
    "Selecciona rango de años", 
    min_year, max_year, (min_year, max_year)
)

oa_filter = st.sidebar.radio(
    "Open Access", ["Todos", "Open Access", "Closed Access"]
)

quartile_opts = df["JCR_Quartile"].dropna().unique().tolist()
quartile_filter = st.sidebar.multiselect(
    "Cuartil JCR/SJR",
    options=quartile_opts,
    default=quartile_opts
)

dept_opts = df["Departamento"].dropna().unique().tolist()
dept_filter = st.sidebar.multiselect(
    "Departamento",
    options=dept_opts,
    default=dept_opts
)

title_filter = st.sidebar.text_input("Buscar en título")

# ============================
# APLICAR FILTROS
# ============================
dff = df.copy()
dff = dff[(dff["Year"] >= year_range[0]) & (dff["Year"] <= year_range[1])]
if oa_filter != "Todos" and "Open Access" in dff.columns:
    dff = dff[dff["Open Access"] == oa_filter]
if quartile_filter:
    dff = dff[dff["JCR_Quartile"].isin(quartile_filter)]
if dept_filter:
    dff = dff[dff["Departamento"].isin(dept_filter)]
if title_filter:
    dff = dff[dff["Title"].str.contains(title_filter, case=False, na=False)]

# ============================
# KPIs
# ============================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")
st.subheader("📌 Resumen general")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total publicaciones", len(dff))
col2.metric("% Open Access", f"{(dff['Open Access'].eq('Open Access').mean() * 100):.1f}%")
col3.metric("Ensayos clínicos detectados", dff.get("Clinical Trial", pd.Series()).sum() if "Clinical Trial" in dff.columns else 0)
col4.metric("Publicaciones con sponsor", dff["Funding sponsor"].notna().sum() if "Funding sponsor" in dff.columns else 0)

# ============================
# TABS
# ============================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👩‍🔬 Autores", "☁️ Wordcloud"])

# --- Publicaciones por año
with tabs[0]:
    pubs_year = dff.groupby("Year").size().reset_index(name="Publicaciones")
    fig_year = px.bar(pubs_year, x="Year", y="Publicaciones", title="Publicaciones por año")
    st.plotly_chart(fig_year, use_container_width=True)

# --- Cuartiles
with tabs[1]:
    quart_count = dff["JCR_Quartile"].fillna("Sin cuartil").value_counts()
    fig_q = px.pie(
        values=quart_count.values,
        names=quart_count.index,
        hole=0.4,
        title="Distribución por cuartil",
        color=quart_count.index,
        color_discrete_map={
            "Q1":"green","Q2":"yellow","Q3":"orange","Q4":"red","Sin cuartil":"lightgrey"
        }
    )
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(quart_count.reset_index().rename(
        columns={"index":"Cuartil","JCR_Quartile":"Publicaciones"}
    ))

# --- Open Access
with tabs[2]:
    oa_count = dff["Open Access"].value_counts()
    fig_oa = px.pie(values=oa_count.values, names=oa_count.index, hole=0.4, title="Distribución Open Access")
    st.plotly_chart(fig_oa, use_container_width=True)
    st.dataframe(oa_count.reset_index().rename(columns={"index":"OA","Open Access":"Publicaciones"}))

# --- Departamentos
with tabs[3]:
    dept_count = dff["Departamento"].value_counts()
    fig_dept = px.bar(dept_count, x=dept_count.index, y=dept_count.values, title="Publicaciones por departamento")
    st.plotly_chart(fig_dept, use_container_width=True)
    st.dataframe(dept_count.reset_index().rename(columns={"index":"Departamento","Departamento":"Publicaciones"}))

# --- Revistas
with tabs[4]:
    if "Source title" in dff.columns:
        rev_count = dff["Source title"].value_counts().head(20)
        st.bar_chart(rev_count)

# --- Autores
with tabs[5]:
    if "Authors" in dff.columns:
        auth_count = dff["Authors"].str.split(",").explode().str.strip().value_counts().head(20)
        st.bar_chart(auth_count)

# --- Wordcloud
with tabs[6]:
    if "Title" in dff.columns:
        text = " ".join(dff["Title"].dropna().astype(str))
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        st.image(wc.to_array(), caption="Nube de palabras en títulos")
        