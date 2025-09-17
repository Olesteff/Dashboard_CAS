import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from wordcloud import WordCloud
from io import BytesIO

# ============================
# CONFIGURACIÓN INICIAL
# ============================
st.set_page_config(
    page_title="Dashboard Producción Científica Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    layout="wide",
    initial_sidebar_state="expanded"
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

# ============================
# FUNCIONES AUXILIARES
# ============================

def load_data(uploaded=None):
    if uploaded:
        return pd.read_excel(uploaded, sheet_name=0)
    elif Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=0)
    else:
        st.error("No se encontró archivo de datos.")
        return pd.DataFrame()

def normalize_departments(df):
    cand_cols = [c for c in df.columns if "depart" in c.lower()]
    if cand_cols:
        df = df.rename(columns={cand_cols[0]: "Departamento"})
    else:
        df["Departamento"] = "Sin asignar"
    df["Departamento"] = (
        df["Departamento"]
        .fillna("Sin asignar")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    return df

def normalize_year(df):
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        df.loc[(df["Year"] < 1900) | (df["Year"] > 2100), "Year"] = np.nan
    return df

def normalize_quartiles(df):
    if "Quartile_std" not in df.columns:
        df["Quartile_std"] = "Sin cuartil"
    df["Quartile_std"] = df["Quartile_std"].fillna("Sin cuartil")
    valid = ["Q1", "Q2", "Q3", "Q4"]
    df.loc[~df["Quartile_std"].isin(valid), "Quartile_std"] = "Sin cuartil"
    return df

def normalize_oa(df):
    if "Open Access" not in df.columns:
        df["Open Access"] = "Desconocido"
    df["Open Access"] = df["Open Access"].fillna("Desconocido")
    return df

def wordcloud_from_column(df, col="Title"):
    text = " ".join(df[col].dropna().astype(str))
    if not text.strip():
        return None
    wc = WordCloud(width=800, height=400, background_color="black", colormap="Set2").generate(text)
    return wc.to_image()

# ============================
# CARGA DE DATOS
# ============================
st.sidebar.header("📂 Datos base")
uploaded_file = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
df = load_data(uploaded_file)

if df.empty:
    st.stop()

# Normalizaciones
df = normalize_year(df)
df = normalize_quartiles(df)
df = normalize_departments(df)
df = normalize_oa(df)

# ============================
# FILTROS
# ============================
st.sidebar.header("Filtros")
year_min, year_max = int(df["Year"].min(skipna=True) or 2000), int(df["Year"].max(skipna=True) or 2025)
years = st.sidebar.slider("Selecciona rango de años", year_min, year_max, (year_min, year_max))

oa_opts = ["Todos"] + sorted(df["Open Access"].unique())
oa_filter = st.sidebar.radio("Open Access", oa_opts, index=0)

quartile_opts = ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
quartile_filter = st.sidebar.multiselect("Cuartil JCR/SJR", quartile_opts, default=quartile_opts)

dept_opts = sorted(df["Departamento"].unique())
dept_filter = st.sidebar.multiselect("Departamento", dept_opts)

title_search = st.sidebar.text_input("Buscar en título")

# Aplicar filtros
dff = df.copy()
dff = dff[(dff["Year"].between(years[0], years[1]))]

if oa_filter != "Todos":
    dff = dff[dff["Open Access"] == oa_filter]

if quartile_filter:
    dff = dff[dff["Quartile_std"].isin(quartile_filter)]

if dept_filter:
    dff = dff[dff["Departamento"].isin(dept_filter)]

if title_search:
    dff = dff[dff["Title"].str.contains(title_search, case=False, na=False)]

# ============================
# KPIs
# ============================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total publicaciones", len(dff))
oa_pct = 100 * (dff["Open Access"].ne("Desconocido").mean() if len(dff) else 0)
col2.metric("% Open Access", f"{oa_pct:.1f}%")
col3.metric("Ensayos clínicos detectados", dff["Title"].str.contains("clinical trial", case=False, na=False).sum())
col4.metric("Publicaciones con sponsor", dff.get("Funding_info", pd.Series()).notna().sum())

# ============================
# PESTAÑAS
# ============================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👩‍🔬 Autores", "☁️ Wordcloud"])

with tabs[0]:
    st.subheader("Publicaciones por año")
    pubs_year = dff.groupby("Year").size().reset_index(name="Publicaciones")
    fig = px.bar(pubs_year, x="Year", y="Publicaciones")
    st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.subheader("Distribución por cuartil")
    quartiles = dff["Quartile_std"].value_counts().reindex(quartile_opts, fill_value=0)
    fig_q = px.pie(values=quartiles.values, names=quartiles.index, hole=0.4,
                   color=quartiles.index,
                   color_discrete_map={"Q1":"green","Q2":"yellow","Q3":"orange","Q4":"red","Sin cuartil":"lightgrey"})
    st.plotly_chart(fig_q, use_container_width=True)

with tabs[2]:
    st.subheader("Distribución Open Access")
    oa_counts = dff["Open Access"].value_counts()
    fig_oa = px.pie(values=oa_counts.values, names=oa_counts.index, hole=0.4)
    st.plotly_chart(fig_oa, use_container_width=True)

with tabs[3]:
    st.subheader("Distribución por departamento")
    dept_counts = dff["Departamento"].value_counts()
    fig_dept = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values)
    st.plotly_chart(fig_dept, use_container_width=True)

with tabs[4]:
    st.subheader("Revistas más frecuentes")
    if "Source title" in dff.columns:
        journals = dff["Source title"].value_counts().head(20)
        st.table(journals)

with tabs[5]:
    st.subheader("Autores más frecuentes")
    if "Authors" in dff.columns:
        authors = dff["Authors"].str.split(";").explode().str.strip().value_counts().head(20)
        st.table(authors)

with tabs[6]:
    st.subheader("Nube de palabras (Wordcloud)")
    wc_img = wordcloud_from_column(dff, col="Title")
    if wc_img:
        st.image(wc_img)
    else:
        st.warning("No hay datos suficientes para generar la nube de palabras.")