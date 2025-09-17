import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ================================
# Configuración de la app
# ================================
st.set_page_config(page_title="Dashboard de Producción Científica – Clínica Alemana – Universidad del Desarrollo",
                   layout="wide")

st.title("📊 Dashboard de Producción Científica – Clínica Alemana – Universidad del Desarrollo")

# ================================
# Funciones auxiliares
# ================================
def detectar_departamento(texto):
    if pd.isna(texto):
        return "Sin asignar"
    texto_low = str(texto).lower()
    if "neurolog" in texto_low or "psiquiatr" in texto_low:
        return "Neurología y Psiquiatría"
    if "pediatr" in texto_low:
        return "Pediatría"
    if "ginecolog" in texto_low or "obstetr" in texto_low:
        return "Ginecología y Obstetricia"
    if "oncolog" in texto_low:
        return "Oncología"
    if "cirug" in texto_low:
        return "Cirugía"
    if "medicina interna" in texto_low:
        return "Medicina Interna"
    if "cardio" in texto_low:
        return "Enfermedades Cardiovasculares"
    return "Clínica Alemana"

def detectar_ensayo_clinico(row):
    texto = " ".join([str(row.get("Publication Type", "")),
                      str(row.get("Title", "")),
                      str(row.get("Author Keywords", ""))]).lower()
    if "clinical trial" in texto or "ensayo clínico" in texto:
        return True
    return False

# ================================
# Carga de datos
# ================================
@st.cache_data
def load_data(path="dataset_unificado_enriquecido_jcr_PLUS.xlsx"):
    df = pd.read_excel(path)
    # Normalizar columnas
    posibles_quartiles = [c for c in df.columns if "quartile" in c.lower()]
    if posibles_quartiles:
        df["Quartile"] = df[posibles_quartiles[0]]
    else:
        df["Quartile"] = "Sin cuartil"

    if "Journal Impact Factor" in df.columns:
        df["JIF"] = pd.to_numeric(df["Journal Impact Factor"], errors="coerce").fillna(0)
    else:
        df["JIF"] = 0

    if "OpenAccess_flag" in df.columns:
        df["OpenAccess_flag"] = df["OpenAccess_flag"].astype(bool)
    else:
        df["OpenAccess_flag"] = False

    if "Departamento" not in df.columns:
        df["Departamento"] = df["Affiliations"].apply(detectar_departamento)

    if "EnsayoClinico" not in df.columns:
        df["EnsayoClinico"] = df.apply(detectar_ensayo_clinico, axis=1)

    return df

df = load_data()

# ================================
# Filtros
# ================================
st.sidebar.header("Filtros")
years = df["Year"].dropna().astype(int)
min_year, max_year = years.min(), years.max()
year_range = st.sidebar.slider("Selecciona rango de años", int(min_year), int(max_year),
                               (int(min_year), int(max_year)))

oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo Open Access", "Solo Closed Access"])
quartiles = ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
selected_quartiles = st.sidebar.multiselect("Cuartil JCR/SJR", quartiles, default=quartiles)
departamentos = df["Departamento"].unique().tolist()
selected_deptos = st.sidebar.multiselect("Departamento", departamentos, default=departamentos)

# ================================
# Aplicar filtros
# ================================
df_filtered = df[(df["Year"].between(year_range[0], year_range[1]))]

if oa_filter == "Solo Open Access":
    df_filtered = df_filtered[df_filtered["OpenAccess_flag"]]
elif oa_filter == "Solo Closed Access":
    df_filtered = df_filtered[~df_filtered["OpenAccess_flag"]]

df_filtered = df_filtered[df_filtered["Quartile"].isin(selected_quartiles)]
df_filtered = df_filtered[df_filtered["Departamento"].isin(selected_deptos)]

# ================================
# KPIs
# ================================
col1, col2, col3, col4 = st.columns(4)
col1.metric("📚 Total publicaciones", len(df_filtered))
oa_percent = 100 * df_filtered["OpenAccess_flag"].mean() if len(df_filtered) > 0 else 0
col2.metric("🔓 % Open Access", f"{oa_percent:.1f}%")
col3.metric("⭐ Suma total JIF", f"{df_filtered['JIF'].sum():,.2f}")
col4.metric("🧪 Ensayos clínicos detectados", df_filtered["EnsayoClinico"].sum())

# ================================
# Gráficos
# ================================
st.subheader("📈 Publicaciones por año")
pubs_year = df_filtered.groupby("Year").size().reset_index(name="Publicaciones")
fig_year = px.line(pubs_year, x="Year", y="Publicaciones", markers=True)
st.plotly_chart(fig_year, use_container_width=True)

st.subheader("📊 Distribución por cuartil")
quart_counts = df_filtered["Quartile"].value_counts().reset_index()
quart_counts.columns = ["Quartil", "Publicaciones"]
fig_quart = px.pie(quart_counts, names="Quartil", values="Publicaciones", hole=0.4)
st.plotly_chart(fig_quart, use_container_width=True)

st.subheader("📊 Distribución por departamento")
dept_counts = df_filtered["Departamento"].value_counts().reset_index()
dept_counts.columns = ["Departamento", "Publicaciones"]
fig_dept = px.bar(dept_counts, x="Departamento", y="Publicaciones")
st.plotly_chart(fig_dept, use_container_width=True)
