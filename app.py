import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
from io import BytesIO
from pathlib import Path

# =========================
# CONFIGURACIÓN GENERAL
# =========================
st.set_page_config(
    page_title="Dashboard de Producción Científica",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo")

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

# =========================
# CARGA DE DATOS
# =========================
@st.cache_data
def load_data(path=DEFAULT_XLSX, sheet_name=0):
    if not Path(path).exists():
        st.error(f"No se encontró el archivo {path}")
        return pd.DataFrame()
    df = pd.read_excel(path, sheet_name=sheet_name)
    # Normalizaciones mínimas
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce").fillna(0).astype(int)
    if "JIF" in df.columns:
        df["JIF"] = pd.to_numeric(df["JIF"], errors="coerce").fillna(0)
    return df

uploaded_file = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
else:
    df = load_data()

if df.empty:
    st.stop()

# =========================
# FILTROS
# =========================
st.sidebar.header("Filtros")

# Rango de años
if "Year" in df.columns:
    min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
    year_range = st.sidebar.slider("Selecciona rango de años", min_year, max_year, (min_year, max_year))
    df = df[(df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])]

# Open Access con True/False
if "OpenAccess_flag" in df.columns:
    oa_choice = st.sidebar.radio("Open Access", ["Todos", "Solo Open Access", "Solo Closed Access"])
    if oa_choice == "Solo Open Access":
        df = df[df["OpenAccess_flag"] == True]
    elif oa_choice == "Solo Closed Access":
        df = df[df["OpenAccess_flag"] == False]

# Cuartiles
if "Quartile_std" in df.columns:
    cuartiles = st.sidebar.multiselect("Cuartil JCR/SJR", df["Quartile_std"].dropna().unique(),
                                       default=list(df["Quartile_std"].dropna().unique()))
    df = df[df["Quartile_std"].isin(cuartiles)]

# Departamentos
if "Departamento" in df.columns:
    deptos = st.sidebar.multiselect("Departamento", df["Departamento"].dropna().unique())
    if deptos:
        df = df[df["Departamento"].isin(deptos)]

# Buscar en título
if "Title" in df.columns:
    search = st.sidebar.text_input("Buscar en título")
    if search:
        df = df[df["Title"].str.contains(search, case=False, na=False)]

# =========================
# KPIs
# =========================
total_pubs = len(df)
pct_oa = df["OpenAccess_flag"].mean() * 100 if "OpenAccess_flag" in df.columns and total_pubs > 0 else 0
total_jif = df["JIF"].sum() if "JIF" in df.columns else 0
clinical_trials = df["Tipo de publicación"].str.contains("ensayo clínico", case=False, na=False).sum() if "Tipo de publicación" in df.columns else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("📑 Total publicaciones", total_pubs)
col2.metric("🔓 % Open Access", f"{pct_oa:.1f}%")
col3.metric("⭐ Suma total JIF", f"{total_jif:.1f}")
col4.metric("🧪 Ensayos clínicos detectados", clinical_trials)

# =========================
# PESTAÑAS
# =========================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👩‍🔬 Autores", "☁️ Wordcloud"])

# -------------------------
# Publicaciones
with tabs[0]:
    st.subheader("Publicaciones por año")
    if "Year" in df.columns:
        pubs_year = df.groupby("Year").size().reset_index(name="Publicaciones")
        fig = px.bar(pubs_year, x="Year", y="Publicaciones", title="Publicaciones por año")
        st.plotly_chart(fig, use_container_width=True)

# -------------------------
# Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil")
    if "Quartile_std" in df.columns:
        cuartil_counts = df["Quartile_std"].fillna("Sin cuartil").value_counts().reset_index()
        cuartil_counts.columns = ["Quartil", "Publicaciones"]
        fig = px.pie(cuartil_counts, names="Quartil", values="Publicaciones", hole=0.4,
                     color="Quartil",
                     color_discrete_map={"Q1": "green", "Q2": "yellow", "Q3": "orange", "Q4": "red", "Sin cuartil": "lightgrey"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(cuartil_counts)

# -------------------------
# Open Access
with tabs[2]:
    st.subheader("Distribución Open Access")
    if "OpenAccess_flag" in df.columns:
        oa_counts = df["OpenAccess_flag"].map({True: "Open Access", False: "Closed Access"}).value_counts().reset_index()
        oa_counts.columns = ["Open Access", "Publicaciones"]
        fig = px.pie(oa_counts, names="Open Access", values="Publicaciones", hole=0.4,
                     color="Open Access", color_discrete_map={"Open Access": "green", "Closed Access": "red"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(oa_counts)

# -------------------------
# Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    if "Departamento" in df.columns:
        dept_counts = df["Departamento"].value_counts().reset_index()
        dept_counts.columns = ["Departamento", "Publicaciones"]
        fig = px.bar(dept_counts, x="Departamento", y="Publicaciones", title="Publicaciones por departamento")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dept_counts)

# -------------------------
# Revistas
with tabs[4]:
    st.subheader("Revistas más frecuentes")
    if "Source title" in df.columns:
        rev_counts = df["Source title"].value_counts().head(20).reset_index()
        rev_counts.columns = ["Revista", "Publicaciones"]
        fig = px.bar(rev_counts, x="Revista", y="Publicaciones", title="Top 20 revistas")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(rev_counts)

# -------------------------
# Autores
with tabs[5]:
    st.subheader("Autores más frecuentes")
    if "Authors" in df.columns:
        auth_counts = df["Authors"].str.split(",").explode().str.strip().value_counts().head(20).reset_index()
        auth_counts.columns = ["Autor", "Publicaciones"]
        fig = px.bar(auth_counts, x="Autor", y="Publicaciones", title="Top 20 autores")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(auth_counts)

# -------------------------
# Wordcloud
with tabs[6]:
    st.subheader("Nube de palabras (títulos)")
    if "Title" in df.columns:
        text = " ".join(df["Title"].dropna().astype(str).tolist())
        if text:
            wc = WordCloud(width=800, height=400, background_color="white").generate(text)
            buf = BytesIO()
            wc.to_image().save(buf, format="PNG")
            st.image(buf)
        else:
            st.info("No hay títulos para generar wordcloud")