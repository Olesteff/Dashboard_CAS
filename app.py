import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Dashboard Producción Científica CAS-UDD",
                   layout="wide")

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = 0

# =========================
# FUNCIONES AUXILIARES
# =========================
def detectar_departamento(row):
    """Detecta el departamento en base a las afiliaciones."""
    text = str(row.get("Authors with affiliations", "")) + " " + str(row.get("Affiliations", ""))
    text = text.lower()

    if "neurolog" in text or "psiquiatr" in text:
        return "Neurología y Psiquiatría"
    if "oncolog" in text:
        return "Oncología"
    if "pediatr" in text:
        return "Pediatría"
    if "ginecolog" in text or "obstet" in text:
        return "Ginecología y Obstetricia"
    if "cirug" in text:
        return "Cirugía"
    if "trauma" in text or "ortop" in text:
        return "Traumatología y Ortopedia"
    if "medicina interna" in text:
        return "Medicina Interna"
    if "enfermer" in text:
        return "Enfermería"
    if "imágenes" in text or "radiolog" in text:
        return "Imágenes"
    # Agregar más reglas según se necesiten
    return "Sin asignar"

def detectar_ensayo_clinico(row):
    """Marca publicaciones que son ensayos clínicos."""
    text = str(row.get("Publication Type", "")) + " " + str(row.get("Article Title", ""))
    text = text.lower()
    if "clinical trial" in text or "ensayo clínico" in text:
        return True
    return False

# =========================
# CARGA DE DATOS
# =========================
@st.cache_data
def load_data(uploaded=None):
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=DEFAULT_SHEET)

    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=DEFAULT_SHEET)

    return pd.DataFrame()

df = load_data()

if not df.empty:
    # Detectar departamentos y ensayos clínicos
    df["Departamento_detectado"] = df.apply(detectar_departamento, axis=1)
    df["Ensayo_clinico_flag"] = df.apply(detectar_ensayo_clinico, axis=1)

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filtros")

year_min = int(df["Year"].min()) if "Year" in df else 1980
year_max = int(df["Year"].max()) if "Year" in df else 2025

year_range = st.sidebar.slider("Selecciona rango de años", year_min, year_max, (year_min, year_max))

oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo Open Access", "Solo Closed Access"])

quartile_filter = st.sidebar.multiselect(
    "Cuartil JCR/SJR",
    options=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"],
    default=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
)

depart_filter = st.sidebar.multiselect(
    "Departamento",
    options=df["Departamento_detectado"].unique() if "Departamento_detectado" in df else [],
    default=[]
)

title_filter = st.sidebar.text_input("Buscar en título")

# =========================
# APLICAR FILTROS
# =========================
dff = df.copy()

if "Year" in dff:
    dff = dff[(dff["Year"] >= year_range[0]) & (dff["Year"] <= year_range[1])]

if oa_filter == "Solo Open Access" and "OpenAccess_flag" in dff:
    dff = dff[dff["OpenAccess_flag"] == True]
elif oa_filter == "Solo Closed Access" and "OpenAccess_flag" in dff:
    dff = dff[dff["OpenAccess_flag"] == False]

if "JCR_Quartile" in dff:
    dff["Quartile_std"] = dff["JCR_Quartile"].fillna("Sin cuartil")
    dff = dff[dff["Quartile_std"].isin(quartile_filter)]

if depart_filter:
    dff = dff[dff["Departamento_detectado"].isin(depart_filter)]

if title_filter:
    dff = dff[dff["Article Title"].str.contains(title_filter, case=False, na=False)]

# =========================
# KPIs
# =========================
total_pubs = len(dff)
pct_oa = round((dff["OpenAccess_flag"].mean() * 100), 1) if "OpenAccess_flag" in dff else 0
suma_jif = dff["Journal Impact Factor"].sum() if "Journal Impact Factor" in dff else 0
ensayos = dff["Ensayo_clinico_flag"].sum() if "Ensayo_clinico_flag" in dff else 0

st.title("📊 Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total publicaciones", total_pubs)
col2.metric("% Open Access", f"{pct_oa}%")
col3.metric("Suma total JIF", round(suma_jif, 2))
col4.metric("Ensayos clínicos detectados", ensayos)

# =========================
# GRAFICOS
# =========================
st.subheader("📊 Distribución por cuartiles (JCR/SJR)")
if "Quartile_std" in dff:
    quartile_counts = dff["Quartile_std"].value_counts()
    fig_q = px.pie(
        names=quartile_counts.index,
        values=quartile_counts.values,
        hole=0.4,
        color=quartile_counts.index,
        color_discrete_map={"Q1": "green", "Q2": "yellow", "Q3": "orange", "Q4": "red", "Sin cuartil": "lightgrey"}
    )
    st.plotly_chart(fig_q, use_container_width=True)