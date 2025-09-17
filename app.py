import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from wordcloud import WordCloud
from io import BytesIO
from pathlib import Path

st.set_page_config(page_title="Dashboard CAS–UDD", layout="wide")

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

# ============================
# 📥 Carga de datos
# ============================
@st.cache_data
def load_data(uploaded=None, sheet_name=0):
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name)
    elif Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name)
    else:
        st.error("No se encontró dataset. Sube un archivo XLSX.")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.stop()

# Normalización de columnas clave
if "Year" in df.columns:
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").fillna(0).astype(int)
else:
    st.error("No se encontró columna 'Year' en el dataset.")
    st.stop()

if "OpenAccess_flag" not in df.columns:
    df["OpenAccess_flag"] = False

if "JCR_Quartile" not in df.columns:
    df["JCR_Quartile"] = "Sin cuartil"

# ============================
# 🎛️ Filtros
# ============================
st.sidebar.header("Filtros")

year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Selecciona rango de años", year_min, year_max, (year_min, year_max))

oa_option = st.sidebar.radio("Open Access", ["Todos", "Open Access", "Closed Access"])

quartiles = st.sidebar.multiselect(
    "Cuartil JCR",
    options=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"],
    default=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
)

departments = []
if "Departamento" in df.columns:
    departments = st.sidebar.multiselect("Departamento", df["Departamento"].dropna().unique())

search_term = st.sidebar.text_input("Buscar en título")

# ============================
# 🔎 Aplicar filtros
# ============================
dff = df.copy()
dff = dff[(dff["Year"] >= year_range[0]) & (dff["Year"] <= year_range[1])]

if oa_option == "Open Access":
    dff = dff[dff["OpenAccess_flag"] == True]
elif oa_option == "Closed Access":
    dff = dff[dff["OpenAccess_flag"] == False]

dff = dff[dff["JCR_Quartile"].fillna("Sin cuartil").isin(quartiles)]

if departments:
    dff = dff[dff["Departamento"].isin(departments)]

if search_term:
    if "Title" in dff.columns:
        dff = dff[dff["Title"].str.contains(search_term, case=False, na=False)]

# ============================
# 📊 KPIs
# ============================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")

col1, col2 = st.columns(2)
col1.metric("Total publicaciones", len(dff))
oa_pct = 100 * dff["OpenAccess_flag"].mean() if not dff.empty else 0
col2.metric("% Open Access", f"{oa_pct:.1f}%")

# ============================
# 📑 Pestañas
# ============================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "☁️ Wordcloud"])

# --- Publicaciones ---
with tabs[0]:
    pub_year = dff.groupby("Year").size().reset_index(name="Publicaciones")
    fig = px.bar(pub_year, x="Year", y="Publicaciones", title="Publicaciones por año")
    st.plotly_chart(fig, use_container_width=True)

# --- Cuartiles ---
with tabs[1]:
    quart_count = dff["JCR_Quartile"].fillna("Sin cuartil").value_counts()
    fig_q = px.pie(
        values=quart_count.values,
        names=quart_count.index,
        hole=0.4,
        title="Distribución por cuartil",
        color=quart_count.index,
        color_discrete_map={
            "Q1": "green", "Q2": "yellow", "Q3": "orange", "Q4": "red", "Sin cuartil": "lightgrey"
        }
    )
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(quart_count.reset_index().rename(columns={"index":"Cuartil", "JCR_Quartile":"Publicaciones"}))

# --- Open Access ---
with tabs[2]:
    oa_year = dff.groupby("Year")["OpenAccess_flag"].mean().reset_index()
    oa_year["% Open Access"] = 100 * oa_year["OpenAccess_flag"]
    fig_oa = px.line(oa_year, x="Year", y="% Open Access", title="Evolución de % Open Access por año")
    st.plotly_chart(fig_oa, use_container_width=True)

# --- Wordcloud ---
with tabs[3]:
    if "Title" in dff.columns:
        text = " ".join(dff["Title"].dropna().tolist())
        if text:
            wc = WordCloud(width=1200, height=600, background_color="black", colormap="viridis").generate(text)
            st.image(wc.to_array(), caption="Wordcloud de títulos")
        else:
            st.info("No hay títulos para generar el Wordcloud.")
    else:
        st.warning("El dataset no contiene columna 'Title'")