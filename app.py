# ============================================
# Dashboard CAS – Producción científica
# ============================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from wordcloud import WordCloud
from pathlib import Path
from io import BytesIO

# ============================================
# CONFIGURACIÓN GENERAL
# ============================================
st.set_page_config(
    page_title="Dashboard CAS",
    layout="wide",
    page_icon="📊"
)

# ============================================
# VARIABLES Y ARCHIVOS
# ============================================
DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

# ============================================
# FUNCIONES AUXILIARES
# ============================================

def load_dataframe(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        st.error(f"❌ No se encontró el archivo {path}")
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name=0)

def kpis_summary(df: pd.DataFrame) -> dict:
    kpis = {}
    if df.empty: return kpis
    kpis["Total publicaciones"] = len(df)
    if "OpenAccess_flag" in df:
        kpis["% Open Access"] = f"{100 * df['OpenAccess_flag'].mean():.1f}%"
    if "Journal Impact Factor" in df:
        kpis["Promedio JIF"] = round(df["Journal Impact Factor"].dropna().mean(), 2)
    return kpis

def quartile_distribution(df: pd.DataFrame):
    if "JCR_Quartile" not in df: return None
    counts = df["JCR_Quartile"].fillna("Sin cuartil").value_counts()
    fig = px.pie(
        names=counts.index,
        values=counts.values,
        hole=0.4,
        color=counts.index,
        color_discrete_map={
            "Q1": "green", "Q2": "yellow",
            "Q3": "orange", "Q4": "darkred",
            "Sin cuartil": "lightgrey"
        }
    )
    fig.update_traces(textinfo="label+percent")
    fig.update_layout(title="📊 Distribución por cuartiles JCR", showlegend=True)
    return fig

def publications_per_year(df: pd.DataFrame):
    if "Year_clean" not in df: return None
    counts = df["Year_clean"].value_counts().sort_index()
    fig = px.bar(x=counts.index, y=counts.values,
                 labels={"x": "Año", "y": "N° Publicaciones"})
    fig.update_layout(title="📈 Publicaciones por año")
    return fig

def oa_evolution(df: pd.DataFrame):
    if "Year_clean" not in df or "OpenAccess_flag" not in df: return None
    grouped = df.groupby("Year_clean")["OpenAccess_flag"].mean().mul(100)
    fig = px.line(x=grouped.index, y=grouped.values,
                  labels={"x": "Año", "y": "% Open Access"})
    fig.update_layout(title="🔓 Evolución de % OA por año")
    return fig

def wordcloud_png(df: pd.DataFrame, col="Title"):
    if col not in df: return None
    text = " ".join(df[col].dropna().astype(str))
    wc = WordCloud(width=1600, height=800, background_color="black").generate(text)
    buf = BytesIO()
    wc.to_image().save(buf, format="PNG")
    return buf

# ============================================
# CARGA DE DATOS
# ============================================
st.sidebar.header("📂 Datos base")
uploaded = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])

if uploaded:
    df = pd.read_excel(uploaded, sheet_name=0)
else:
    df = load_dataframe(DEFAULT_XLSX)

if df.empty:
    st.stop()

# Normalización
if "Year" in df:
    df["Year_clean"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")

if "OpenAccess_flag" not in df:
    if any(c.startswith("OA_") for c in df.columns):
        df["OpenAccess_flag"] = df.filter(like="OA_").max(axis=1).fillna(0).astype(int)
    else:
        df["OpenAccess_flag"] = 0

# ============================================
# FILTROS
# ============================================
st.sidebar.header("Filtros")

# Años
years = df["Year_clean"].dropna().unique()
if len(years) > 0:
    min_year, max_year = int(years.min()), int(years.max())
    year_range = st.sidebar.slider("Selecciona rango de años", min_year, max_year, (min_year, max_year))
    df = df[(df["Year_clean"] >= year_range[0]) & (df["Year_clean"] <= year_range[1])]

# Open Access
oa_filter = st.sidebar.radio("Open Access", ["Todos", "Open Access", "Closed Access"])
if oa_filter == "Open Access":
    df = df[df["OpenAccess_flag"] == 1]
elif oa_filter == "Closed Access":
    df = df[df["OpenAccess_flag"] == 0]

# Fuente
if "Fuente" in df:
    fuentes = df["Fuente"].dropna().unique().tolist()
    fuentes_sel = st.sidebar.multiselect("Fuente", fuentes, default=fuentes)
    df = df[df["Fuente"].isin(fuentes_sel)]

# Cuartil JCR
if "JCR_Quartile" in df:
    cuartiles = df["JCR_Quartile"].fillna("Sin cuartil").unique().tolist()
    cuartiles_sel = st.sidebar.multiselect("Cuartil JCR", cuartiles, default=cuartiles)
    df = df[df["JCR_Quartile"].fillna("Sin cuartil").isin(cuartiles_sel)]

# Departamentos
if "Departamento" in df:
    dptos = df["Departamento"].dropna().unique().tolist()
    dptos_sel = st.sidebar.multiselect("Departamento", dptos, default=dptos)
    df = df[df["Departamento"].isin(dptos_sel)]

# Búsqueda en título
if "Title" in df:
    keyword = st.sidebar.text_input("Buscar en título")
    if keyword:
        df = df[df["Title"].str.contains(keyword, case=False, na=False)]

# ============================================
# RESUMEN KPI
# ============================================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")

kpis = kpis_summary(df)
st.subheader("📌 Resumen general")
cols = st.columns(len(kpis))
for i, (k, v) in enumerate(kpis.items()):
    cols[i].metric(label=k, value=v)

# ============================================
# GRÁFICOS
# ============================================
tab1, tab2, tab3, tab4 = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "☁ Wordcloud"])

with tab1:
    fig = publications_per_year(df)
    if fig: st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig = quartile_distribution(df)
    if fig: st.plotly_chart(fig, use_container_width=True)

with tab3:
    fig = oa_evolution(df)
    if fig: st.plotly_chart(fig, use_container_width=True)

with tab4:
    buf = wordcloud_png(df, col="Title")
    if buf: st.image(buf, use_column_width=True)