import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from wordcloud import WordCloud
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

# ============================
# 🧹 Normalización de columnas
# ============================
if "Year" not in df.columns:
    st.error("El dataset necesita columna 'Year'")
    st.stop()

# --- Normalizar años ---
df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
df = df.dropna(subset=["Year"])
df["Year"] = df["Year"].astype(int)
df = df[(df["Year"] >= 1900) & (df["Year"] <= 2025)]

if df.empty:
    st.warning("No hay publicaciones en el rango de años válido (1900–2025).")
    st.stop()

# --- Normalizar otras columnas ---
df["OpenAccess_flag"] = df.get("OpenAccess_flag", False)
df["JCR_Quartile"] = df.get("JCR_Quartile", "Sin cuartil")
df["Departamento"] = df.get("Departamento", "Sin asignar")
df["Title"] = df.get("Title", "")

# ============================
# 🎛️ Filtros
# ============================
st.sidebar.header("Datos base")
uploaded = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
if uploaded:
    df = load_data(uploaded)

st.sidebar.header("Filtros")

year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Selecciona rango de años", year_min, year_max, (year_min, year_max))

oa_option = st.sidebar.radio("Open Access", ["Todos", "Open Access", "Closed Access"])

quartiles = st.sidebar.multiselect(
    "Cuartil JCR/SJR",
    options=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"],
    default=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
)

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
    dff = dff[dff["Title"].str.contains(search_term, case=False, na=False)]

# ============================
# 📊 KPIs
# ============================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total publicaciones", len(dff))
oa_pct = 100 * dff["OpenAccess_flag"].mean() if not dff.empty else 0
col2.metric("% Open Access", f"{oa_pct:.1f}%")

if "Clinical_trial" in dff.columns:
    col3.metric("Ensayos clínicos detectados", dff["Clinical_trial"].sum())
else:
    col3.metric("Ensayos clínicos detectados", 0)

if "Sponsor" in dff.columns:
    col4.metric("Publicaciones con sponsor", dff["Sponsor"].notna().sum())
else:
    col4.metric("Publicaciones con sponsor", 0)

# ============================
# 📑 Pestañas
# ============================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "⭐ Citas", "☁️ Wordcloud"])

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
        color_discrete_map={"Q1":"green","Q2":"yellow","Q3":"orange","Q4":"red","Sin cuartil":"lightgrey"}
    )
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(quart_count.reset_index().rename(columns={"index":"Cuartil", "JCR_Quartile":"Publicaciones"}))

# --- Open Access ---
with tabs[2]:
    oa_year = dff.groupby("Year")["OpenAccess_flag"].mean().reset_index()
    oa_year["% Open Access"] = 100 * oa_year["OpenAccess_flag"]
    fig_oa = px.line(oa_year, x="Year", y="% Open Access", title="Evolución de % Open Access por año")
    st.plotly_chart(fig_oa, use_container_width=True)

# --- Departamentos ---
with tabs[3]:
    depto = dff["Departamento"].value_counts().head(20).reset_index()
    depto.columns = ["Departamento","Publicaciones"]
    fig_d = px.bar(depto, x="Publicaciones", y="Departamento", orientation="h", title="Top 20 Departamentos")
    st.plotly_chart(fig_d, use_container_width=True)

# --- Revistas ---
with tabs[4]:
    if "Source title" in dff.columns:
        rev = dff["Source title"].value_counts().head(20).reset_index()
        rev.columns = ["Revista","Publicaciones"]
        fig_r = px.bar(rev, x="Publicaciones", y="Revista", orientation="h", title="Top 20 Revistas")
        st.plotly_chart(fig_r, use_container_width=True)
    else:
        st.info("No hay columna 'Source title' en el dataset")

# --- Citas ---
with tabs[5]:
    if "Cited by" in dff.columns:
        citas = dff.groupby("Year")["Cited by"].sum().reset_index()
        fig_c = px.line(citas, x="Year", y="Cited by", title="Citas por año")
        st.plotly_chart(fig_c, use_container_width=True)
    else:
        st.info("No hay columna 'Cited by' en el dataset")

# --- Wordcloud ---
with tabs[6]:
    text = " ".join(dff["Title"].dropna().astype(str).tolist())
    if text:
        wc = WordCloud(width=1200, height=600, background_color="black", colormap="viridis").generate(text)
        st.image(wc.to_array(), caption="Wordcloud de títulos")
    else:
        st.info("No hay títulos para generar el Wordcloud.")