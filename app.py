# app_cas_dashboard_final.py

import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re

st.set_page_config(page_title="Dashboard Producción Científica CAS-UDD", layout="wide")

# ================================
# Funciones auxiliares
# ================================
@st.cache_data
def load_data():
    df = pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS.xlsx", sheet_name="Consolidado_enriq")

    # Normalización de columnas clave
    if "OpenAccess_flag" in df.columns:
        df["OpenAccess_flag"] = df["OpenAccess_flag"].astype(str).str.lower().map({"true": True, "false": False})

    if "Quartile_std" not in df.columns and "JCR_Quartile" in df.columns:
        df["Quartile_std"] = df["JCR_Quartile"]

    if "Journal Impact Factor" not in df.columns:
        df["Journal Impact Factor"] = 0

    if "Departamento" not in df.columns:
        df["Departamento"] = df.apply(_infer_department, axis=1)

    # Añadir flag dinámico para ensayos clínicos
    df["Clinical_trial_flag"] = df.apply(_infer_clinical_trial, axis=1)

    return df

def _infer_department(row):
    """
    Lógica para inferir departamento desde Affiliation o Authors with affiliations
    """
    text = " ".join([
        str(row.get("Affiliations", "")),
        str(row.get("Authors with affiliations", "")),
    ]).lower()

    if "neurolog" in text:
        return "Neurología y Psiquiatría"
    if "pediatr" in text:
        return "Pediatría"
    if "gineco" in text or "obstet" in text:
        return "Ginecología y Obstetricia"
    if "oncolog" in text:
        return "Oncología"
    if "cirug" in text:
        return "Cirugía"
    if "medicina interna" in text:
        return "Medicina Interna"
    if "trauma" in text:
        return "Traumatología y Ortopedia"
    if "enfermer" in text:
        return "Enfermería"

    return "Sin asignar"

def _infer_clinical_trial(row):
    """
    Detecta ensayos clínicos a partir de título, abstract y keywords.
    """
    text = " ".join([
        str(row.get("Article Title", "")),
        str(row.get("Abstract", "")),
        str(row.get("Author Keywords", "")),
        str(row.get("Source title", "")),
    ]).lower()

    patterns = [
        r"clinical trial",
        r"ensayo clínico",
        r"phase i\b",
        r"phase ii\b",
        r"phase iii\b",
        r"randomized",
        r"randomised",
        r"intervention",
    ]

    return any(re.search(p, text) for p in patterns)

# ================================
# Cargar datos
# ================================
@st.cache_data
def load_data():
    # Lee siempre la PRIMERA hoja del Excel
    df = pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS.xlsx", sheet_name=0)

    # Normalización de columnas clave
    if "OpenAccess_flag" in df.columns:
        df["OpenAccess_flag"] = df["OpenAccess_flag"].astype(str).str.lower().map({"true": True, "false": False})

    if "Quartile_std" not in df.columns and "JCR_Quartile" in df.columns:
        df["Quartile_std"] = df["JCR_Quartile"]

    if "Journal Impact Factor" not in df.columns:
        df["Journal Impact Factor"] = 0

    if "Departamento" not in df.columns:
        df["Departamento"] = df.apply(_infer_department, axis=1)

    # Añadir flag dinámico para ensayos clínicos
    df["Clinical_trial_flag"] = df.apply(_infer_clinical_trial, axis=1)

    return df

# ================================
# Sidebar
# ================================
st.sidebar.header("📂 Datos base")
st.sidebar.write("Dataset activo: **dataset_unificado_enriquecido_jcr_PLUS.xlsx**")

year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Selecciona rango de años", year_min, year_max, (year_min, year_max))

oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo Open Access", "Solo Closed Access"])

quartiles_selected = st.sidebar.multiselect(
    "Cuartil JCR/SJR",
    options=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"],
    default=["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
)

departments_selected = st.sidebar.multiselect(
    "Departamento",
    options=sorted(df["Departamento"].unique()),
    default=sorted(df["Departamento"].unique())
)

title_search = st.sidebar.text_input("Buscar en título")

# ================================
# Filtrar dataset
# ================================
df_filtered = df.copy()
df_filtered = df_filtered[(df_filtered["Year"] >= year_range[0]) & (df_filtered["Year"] <= year_range[1])]

if oa_filter == "Solo Open Access":
    df_filtered = df_filtered[df_filtered["OpenAccess_flag"] == True]
elif oa_filter == "Solo Closed Access":
    df_filtered = df_filtered[df_filtered["OpenAccess_flag"] == False]

df_filtered = df_filtered[df_filtered["Quartile_std"].fillna("Sin cuartil").isin(quartiles_selected)]
df_filtered = df_filtered[df_filtered["Departamento"].isin(departments_selected)]

if title_search:
    df_filtered = df_filtered[df_filtered["Article Title"].str.contains(title_search, case=False, na=False)]

# ================================
# KPIs
# ================================
st.title("📊 Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total publicaciones", len(df_filtered))
with col2:
    st.metric("% Open Access", f"{100*df_filtered['OpenAccess_flag'].mean():.1f}%" if "OpenAccess_flag" in df_filtered else "N/A")
with col3:
    st.metric("⭐ Suma total JIF", round(df_filtered["Journal Impact Factor"].sum(), 1))
with col4:
    st.metric("🧪 Ensayos clínicos", int(df_filtered["Clinical_trial_flag"].sum()))

# ================================
# Tabs
# ================================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👩‍🔬 Autores", "☁️ Wordcloud"])

# --- Publicaciones
with tabs[0]:
    st.subheader("Publicaciones por año")
    pubs_per_year = df_filtered.groupby("Year").size().reset_index(name="Publicaciones")
    fig = px.line(pubs_per_year, x="Year", y="Publicaciones", markers=True)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Suma de JIF por año")
    jif_per_year = df_filtered.groupby("Year")["Journal Impact Factor"].sum().reset_index()
    fig_jif = px.line(jif_per_year, x="Year", y="Journal Impact Factor", markers=True)
    st.plotly_chart(fig_jif, use_container_width=True)

# --- Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil")
    quart_counts = df_filtered["Quartile_std"].fillna("Sin cuartil").value_counts()
    fig_q = px.pie(
        names=quart_counts.index,
        values=quart_counts.values,
        hole=0.4,
        color=quart_counts.index,
        color_discrete_map={"Q1": "green", "Q2": "yellow", "Q3": "orange", "Q4": "red", "Sin cuartil": "lightgrey"}
    )
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(quart_counts.reset_index().rename(columns={"index": "Cuartil", "Quartile_std": "Publicaciones"}))

# --- Open Access
with tabs[2]:
    st.subheader("Distribución Open Access")
    oa_counts = df_filtered["OpenAccess_flag"].value_counts(dropna=False)
    fig_oa = px.pie(
        names=["Open Access" if x else "Closed Access" for x in oa_counts.index],
        values=oa_counts.values,
        hole=0.4,
        color=["Open Access" if x else "Closed Access" for x in oa_counts.index],
        color_discrete_map={"Open Access": "blue", "Closed Access": "darkred"}
    )
    st.plotly_chart(fig_oa, use_container_width=True)

# --- Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    dept_counts = df_filtered["Departamento"].value_counts()
    fig_d = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values)
    st.plotly_chart(fig_d, use_container_width=True)
    st.dataframe(dept_counts.reset_index().rename(columns={"index": "Departamento", "Departamento": "Publicaciones"}))

# --- Revistas
with tabs[4]:
    st.subheader("Top Revistas")
    if "Source title" in df_filtered.columns:
        journal_counts = df_filtered["Source title"].value_counts().head(20)
        fig_j = px.bar(journal_counts, x=journal_counts.values, y=journal_counts.index, orientation="h")
        st.plotly_chart(fig_j, use_container_width=True)
        st.dataframe(journal_counts.reset_index().rename(columns={"index": "Revista", "Source title": "Publicaciones"}))

# --- Autores
with tabs[5]:
    st.subheader("Top Autores")
    if "Authors" in df_filtered.columns:
        authors = df_filtered["Authors"].dropna().str.split(",")
        authors_flat = [a.strip() for sublist in authors for a in sublist]
        author_counts = pd.Series(authors_flat).value_counts().head(20)
        fig_a = px.bar(author_counts, x=author_counts.values, y=author_counts.index, orientation="h")
        st.plotly_chart(fig_a, use_container_width=True)
        st.dataframe(author_counts.reset_index().rename(columns={"index": "Autor", 0: "Publicaciones"}))

# --- Wordcloud
with tabs[6]:
    st.subheader("Nube de palabras")
    if "Author Keywords" in df_filtered.columns and df_filtered["Author Keywords"].notna().any():
        text = " ".join(df_filtered["Author Keywords"].dropna().astype(str))
        if text.strip():
            wc = WordCloud(width=800, height=400, background_color="white").generate(text)
            fig, ax = plt.subplots()
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig)
        else:
            st.info("No hay palabras clave suficientes para generar la nube.")
    else:
        st.info("No hay palabras clave suficientes para generar la nube.")