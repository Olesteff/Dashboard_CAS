import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# =============================
# CONFIGURACIÓN INICIAL
# =============================
st.set_page_config(
    page_title="Dashboard Producción Científica CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = "Consolidado_enriq"

# =============================
# CARGA DE DATOS
# =============================
@st.cache_data
def load_data(path=DEFAULT_XLSX, sheet_name=DEFAULT_SHEET):
    df = pd.read_excel(path, sheet_name=sheet_name)

    # Normalizar año
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        df = df[df["Year"].between(1900, 2100)]   # 🔥 solo años válidos
        df["Year"] = df["Year"].astype(int)
    else:
        df["Year"] = 0

    # Normalizar cuartiles
    if "Quartile_std" not in df.columns:
        df["Quartile_std"] = "Sin cuartil"

    # Normalizar departamento
    if "Departamento" not in df.columns:
        df["Departamento"] = "Sin asignar"

    # Normalizar Open Access
    if "Open Access" not in df.columns:
        df["Open Access"] = "Desconocido"

    return df

# =============================
# CARGA ARCHIVO
# =============================
st.sidebar.header("📂 Datos base")
uploaded_file = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])
if uploaded_file:
    df = load_data(uploaded_file)
else:
    if Path(DEFAULT_XLSX).exists():
        df = load_data()
    else:
        st.error("No se encontró el archivo base. Sube un XLSX.")
        st.stop()

# =============================
# FILTROS
# =============================
st.sidebar.header("Filtros")

# Rango de años
min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Selecciona rango de años", min_year, max_year, (min_year, max_year))

# Open Access
oa_opts = ["Todos", "Open Access", "Closed Access"]
oa_filter = st.sidebar.radio("Open Access", oa_opts)

# Cuartiles
quartile_opts = sorted(df["Quartile_std"].dropna().unique().tolist())
quartile_sel = st.sidebar.multiselect("Cuartil JCR/SJR", quartile_opts, default=quartile_opts)

# Departamentos
dept_opts = sorted(df["Departamento"].dropna().unique().tolist())
dept_sel = st.sidebar.multiselect("Departamento", dept_opts, default=dept_opts)

# Búsqueda en título
title_search = st.sidebar.text_input("Buscar en título")

# =============================
# APLICAR FILTROS
# =============================
dff = df[
    (df["Year"].between(year_range[0], year_range[1])) &
    (df["Quartile_std"].isin(quartile_sel)) &
    (df["Departamento"].isin(dept_sel))
]

if oa_filter == "Open Access":
    dff = dff[dff["Open Access"].str.contains("Open", case=False, na=False)]
elif oa_filter == "Closed Access":
    dff = dff[~dff["Open Access"].str.contains("Open", case=False, na=False)]

if title_search:
    dff = dff[dff["Title"].str.contains(title_search, case=False, na=False)]

# =============================
# DASHBOARD
# =============================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total publicaciones", len(dff))
with col2:
    pct_oa = (dff["Open Access"].str.contains("Open", case=False, na=False).mean() * 100) if len(dff) > 0 else 0
    st.metric("% Open Access", f"{pct_oa:.1f}%")
with col3:
    if "Tipo" in dff.columns:
        ensayos = dff[dff["Tipo"].str.contains("clinical trial", case=False, na=False)]
        st.metric("Ensayos clínicos detectados", len(ensayos))
    else:
        st.metric("Ensayos clínicos detectados", 0)
with col4:
    if "Funding sponsor" in dff.columns:
        sponsors = dff[dff["Funding sponsor"].notna()]
        st.metric("Publicaciones con sponsor detectado", len(sponsors))
    else:
        st.metric("Publicaciones con sponsor detectado", 0)

# =============================
# GRÁFICOS
# =============================
st.subheader("📈 Publicaciones por año")
pubs_year = dff.groupby("Year").size().reset_index(name="Publicaciones")
fig_year = px.bar(pubs_year, x="Year", y="Publicaciones")
st.plotly_chart(fig_year, use_container_width=True)

st.subheader("📊 Distribución por cuartil")
quartile_counts = dff["Quartile_std"].fillna("Sin cuartil").value_counts()
fig_q = px.pie(
    names=quartile_counts.index,
    values=quartile_counts.values,
    hole=0.4,
    color=quartile_counts.index,
    color_discrete_map={
        "Q1": "green", "Q2": "yellow", "Q3": "orange", "Q4": "darkred", "Sin cuartil": "lightgrey"
    }
)
st.plotly_chart(fig_q, use_container_width=True)

st.subheader("📊 Distribución Open Access")
oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
fig_oa = px.pie(names=oa_counts.index, values=oa_counts.values, hole=0.4)
st.plotly_chart(fig_oa, use_container_width=True)

st.subheader("🏥 Distribución por departamento")
dept_counts = dff["Departamento"].fillna("Sin asignar").value_counts().reset_index()
dept_counts.columns = ["Departamento", "Publicaciones"]
fig_dept = px.bar(dept_counts, x="Departamento", y="Publicaciones")
st.plotly_chart(fig_dept, use_container_width=True)