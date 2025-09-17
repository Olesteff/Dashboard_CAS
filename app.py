# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import re
from wordcloud import WordCloud
from io import BytesIO

st.set_page_config(
    page_title="Dashboard Producción Científica CAS–UDD",
    layout="wide",
    page_icon="📊"
)

# ======================
# Utils
# ======================
QUARTILE_CANDS = [
    "JIF Quartile", "JCR Quartile", "JCI Quartile", "SJR Quartile",
    "Quartile", "Cuartil", "Quartil"
]

def _standardize_quartile(val):
    if pd.isna(val): 
        return "Sin cuartil"
    t = str(val).strip().upper()
    m = re.search(r"Q\s*([1-4])", t)
    if m:
        return f"Q{m.group(1)}"
    if t in {"1","2","3","4"}:
        return f"Q{t}"
    return "Sin cuartil"

def attach_quartiles(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in QUARTILE_CANDS if c in df.columns]
    if not cols:
        df["Quartile_std"] = "Sin cuartil"
        return df

    tmp = df[cols].copy()
    for c in tmp.columns:
        tmp[c] = tmp[c].map(_standardize_quartile)

    df["Quartile_std"] = tmp.replace("Sin cuartil", np.nan).bfill(axis=1).iloc[:, 0]
    df["Quartile_std"] = df["Quartile_std"].fillna("Sin cuartil")
    return df

def make_wordcloud(text_series, max_words=100):
    text = " ".join([str(t) for t in text_series.dropna()])
    if not text:
        return None
    wc = WordCloud(
        width=800, height=400,
        background_color="white",
        colormap="Dark2",
        max_words=max_words
    ).generate(text)
    return wc.to_image()

# ======================
# Load data
# ======================
DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

def load_data(uploaded=None):
    if uploaded is not None:
        df = pd.read_excel(uploaded, sheet_name=0)
    elif Path(DEFAULT_XLSX).exists():
        df = pd.read_excel(DEFAULT_XLSX, sheet_name=0)
    else:
        st.error("No se encontró dataset. Sube un archivo XLSX.")
        st.stop()
    return df

st.sidebar.header("📂 Datos base")
uploaded = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
df = load_data(uploaded)
df = attach_quartiles(df)

# ======================
# Filtros
# ======================
st.sidebar.header("Filtros")

# Año
if "Year_clean" in df.columns:
    min_year, max_year = int(df["Year_clean"].min()), int(df["Year_clean"].max())
else:
    min_year, max_year = 1975, 2025
sel_years = st.sidebar.slider(
    "Selecciona rango de años", min_year, max_year, (min_year, max_year)
)

# Open Access
oa_opts = ["Todos", "Open Access", "Closed Access"]
sel_oa = st.sidebar.radio("Open Access", oa_opts, index=0)

# Cuartiles
quartile_choices = ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
sel_quart = st.sidebar.multiselect("Cuartil JCR/SJR", quartile_choices, default=quartile_choices)

# Departamentos
if "Departamento" in df.columns:
    deps = sorted(df["Departamento"].dropna().unique())
    sel_dep = st.sidebar.multiselect("Departamento", deps, default=[])
else:
    sel_dep = []

# Buscar en título
search_text = st.sidebar.text_input("Buscar en título")

# ======================
# Aplicar filtros
# ======================
mask = (df["Year_clean"].between(sel_years[0], sel_years[1]))

if sel_oa != "Todos" and "OA_flag" in df.columns:
    mask &= df["OA_flag"].eq(sel_oa)

if sel_quart:
    mask &= df["Quartile_std"].isin(sel_quart)

if sel_dep:
    mask &= df["Departamento"].isin(sel_dep)

if search_text:
    mask &= df["Title"].str.contains(search_text, case=False, na=False)

dff = df.loc[mask].copy()

# ======================
# KPIs
# ======================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")
st.subheader("📌 Resumen general")

col1, col2 = st.columns(2)
col1.metric("Total publicaciones", len(dff))
if "OA_flag" in dff.columns:
    pct_oa = (dff["OA_flag"].eq("Open Access").mean() * 100).round(1)
    col2.metric("% Open Access", f"{pct_oa}%")

# ======================
# Tabs
# ======================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "☁ Wordcloud"])

with tabs[0]:
    st.subheader("Publicaciones por año")
    if "Year_clean" in dff.columns:
        pub_year = dff.groupby("Year_clean").size().reset_index(name="Publicaciones")
        fig = px.bar(pub_year, x="Year_clean", y="Publicaciones")
        st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.subheader("Distribución por cuartil")
    q_counts = dff["Quartile_std"].value_counts().reindex(quartile_choices, fill_value=0)
    fig_q = px.pie(
        values=q_counts.values,
        names=q_counts.index,
        hole=0.45,
        color=q_counts.index,
        color_discrete_map={
            "Q1": "#0a7d11",
            "Q2": "#fffb00",
            "Q3": "#ffa000",
            "Q4": "#8b0000",
            "Sin cuartil": "#cfcfcf"
        }
    )
    fig_q.update_traces(textinfo="percent+label", pull=[0.03]*len(q_counts))
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(q_counts.rename("Publicaciones").reset_index().rename(columns={"index":"Cuartil"}))

with tabs[2]:
    st.subheader("Evolución de Open Access")
    if "OA_flag" in dff.columns and "Year_clean" in dff.columns:
        oa_year = (
            dff.groupby(["Year_clean","OA_flag"]).size().reset_index(name="Publicaciones")
        )
        fig_oa = px.area(oa_year, x="Year_clean", y="Publicaciones", color="OA_flag")
        st.plotly_chart(fig_oa, use_container_width=True)

with tabs[3]:
    st.subheader("Nube de palabras (títulos)")
    if "Title" in dff.columns:
        img = make_wordcloud(dff["Title"])
        if img:
            st.image(img)
        else:
            st.info("No hay suficientes datos para generar wordcloud.")
            