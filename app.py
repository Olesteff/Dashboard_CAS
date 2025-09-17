import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import re

st.set_page_config(
    page_title="Dashboard de Producción Científica",
    layout="wide"
)

st.title("📊 Dashboard de Producción Científica – Clínica Alemana – Universidad del Desarrollo")

# =========================
# FUNCIONES DE APOYO
# =========================

def detect_department(affiliation: str) -> str:
    """Detecta departamento desde texto de afiliaciones."""
    if not isinstance(affiliation, str):
        return "Sin asignar"
    aff = affiliation.lower()
    if "neurolog" in aff or "psiquiatr" in aff:
        return "Neurología y Psiquiatría"
    if "oncolog" in aff:
        return "Oncología"
    if "pediatr" in aff:
        return "Pediatría"
    if "ginecol" in aff or "obstetr" in aff:
        return "Ginecología y Obstetricia"
    if "medicina interna" in aff:
        return "Medicina Interna"
    if "trauma" in aff or "ortoped" in aff:
        return "Traumatología y Ortopedia"
    if "enfermer" in aff:
        return "Enfermería"
    if "imagen" in aff or "radiolog" in aff:
        return "Imágenes"
    if "urgenc" in aff:
        return "Urgencias"
    if "cirug" in aff:
        return "Cirugía"
    return "Clínica Alemana"

def detect_clinical_trial(row) -> bool:
    """Detecta ensayos clínicos desde columnas de título, resumen, tipo de publicación y keywords."""
    text = ""
    for col in ["Title", "Abstract", "Publication Type", "Keywords"]:
        if col in row and pd.notna(row[col]):
            text += " " + str(row[col])
    text = text.lower()
    ct_regex = r"(ensayo\s*cl[ií]nico|clinical\s*trial|randomi[sz]ed|phase\s*[i1v]+|double\s*blind|placebo\-controlled)"
    return bool(re.search(ct_regex, text))

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas críticas para el dashboard."""
    # Año
    year_cols = ["Year", "Año", "Publication Year", "Year_Published"]
    for col in year_cols:
        if col in df.columns:
            df = df.rename(columns={col: "Year"})
            df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
            break

    # OpenAccess
    if "OpenAccess_flag" in df.columns:
        df["OpenAccess_flag"] = (
            df["OpenAccess_flag"].astype(str).str.lower().map({"true": True, "false": False})
        )

    # JIF
    jif_cols = ["Journal Impact Factor", "Impact Factor", "JIF"]
    for col in jif_cols:
        if col in df.columns:
            df = df.rename(columns={col: "Journal Impact Factor"})
            df["Journal Impact Factor"] = pd.to_numeric(df["Journal Impact Factor"], errors="coerce").fillna(0)
            break
    if "Journal Impact Factor" not in df.columns:
        df["Journal Impact Factor"] = 0

    # Quartiles
    quart_cols = ["JCR Quartile", "JCR_Quartile", "Quartile_std", "Quartile"]
    for col in quart_cols:
        if col in df.columns:
            df = df.rename(columns={col: "Quartile"})
            df["Quartile"] = df["Quartile"].fillna("Sin cuartil")
            break
    if "Quartile" not in df.columns:
        df["Quartile"] = "Sin cuartil"

    # Departamentos
    aff_col = None
    for c in ["Authors with affiliations", "Affiliations", "Author Affiliations"]:
        if c in df.columns:
            aff_col = c
            break
    if aff_col:
        df["Departamento"] = df[aff_col].apply(detect_department)
    else:
        df["Departamento"] = "Sin asignar"

    # Ensayos clínicos
    df["ClinicalTrial_flag"] = df.apply(detect_clinical_trial, axis=1)

    return df

# =========================
# CARGA DE DATOS
# =========================

@st.cache_data
def load_data():
    df = pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS.xlsx", sheet_name=0)
    df = normalize_columns(df)
    return df

df = load_data()

# =========================
# FILTROS
# =========================

st.sidebar.header("🔎 Filtros")

year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Años", year_min, year_max, (year_min, year_max))

oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo OA", "No OA"])
quart_filter = st.sidebar.multiselect("Cuartiles", df["Quartile"].unique(), default=df["Quartile"].unique())
dept_filter = st.sidebar.multiselect("Departamentos", df["Departamento"].unique(), default=df["Departamento"].unique())
search_term = st.sidebar.text_input("Buscar en títulos")

# Aplicar filtros
dff = df[(df["Year"].between(year_range[0], year_range[1])) &
         (df["Quartile"].isin(quart_filter)) &
         (df["Departamento"].isin(dept_filter))]

if oa_filter == "Solo OA":
    dff = dff[dff["OpenAccess_flag"] == True]
elif oa_filter == "No OA":
    dff = dff[dff["OpenAccess_flag"] == False]

if search_term:
    dff = dff[dff["Title"].astype(str).str.contains(search_term, case=False, na=False)]

# =========================
# KPIs
# =========================

col1, col2, col3, col4 = st.columns(4)
col1.metric("📚 Publicaciones", len(dff))
col2.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
col3.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
col4.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

# =========================
# PESTAÑAS
# =========================

tabs = st.tabs(["📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📑 Revistas", "👥 Autores", "☁️ Wordcloud"])

with tabs[0]:
    st.subheader("📅 Publicaciones por año")
    pub_year = dff.groupby("Year").size().reset_index(name="Publicaciones")
    st.plotly_chart(px.bar(pub_year, x="Year", y="Publicaciones", title="Publicaciones por Año"), use_container_width=True)

    st.subheader("📈 Evolución JIF por año")
    jif_year = dff.groupby("Year")["Journal Impact Factor"].sum().reset_index()
    st.plotly_chart(px.line(jif_year, x="Year", y="Journal Impact Factor", markers=True, title="Suma JIF por Año"), use_container_width=True)

with tabs[1]:
    st.subheader("📊 Distribución por cuartiles")
    quart_count = dff["Quartile"].value_counts().reset_index()
    quart_count.columns = ["Quartile", "Publicaciones"]
    st.plotly_chart(px.pie(quart_count, names="Quartile", values="Publicaciones", hole=0.4,
                           title="Distribución de publicaciones por cuartil"), use_container_width=True)

with tabs[2]:
    st.subheader("🔓 Publicaciones Open Access")
    oa_count = dff["OpenAccess_flag"].value_counts().reset_index()
    oa_count.columns = ["OpenAccess", "Publicaciones"]
    st.plotly_chart(px.pie(oa_count, names="OpenAccess", values="Publicaciones", hole=0.4,
                           title="Distribución Open Access"), use_container_width=True)

with tabs[3]:
    st.subheader("🏥 Publicaciones por Departamento")
    dept_count = dff["Departamento"].value_counts().reset_index()
    dept_count.columns = ["Departamento", "Publicaciones"]
    st.plotly_chart(px.bar(dept_count, x="Departamento", y="Publicaciones", title="Publicaciones por Departamento"), use_container_width=True)

with tabs[4]:
    st.subheader("📑 Revistas más frecuentes")
    if "Source title" in dff.columns:
        journal_count = dff["Source title"].value_counts().head(20).reset_index()
        journal_count.columns = ["Revista", "Publicaciones"]
        st.dataframe(journal_count)

with tabs[5]:
    st.subheader("👥 Autores más frecuentes")
    authors_col = None
    for c in ["Author Full Names", "Authors", "Authors with affiliations"]:
        if c in dff.columns:
            authors_col = c
            break
    if authors_col:
        authors = dff[authors_col].dropna().str.split(";|,|\\|").explode().str.strip()
        top_authors = authors.value_counts().head(20).reset_index()
        top_authors.columns = ["Autor", "Publicaciones"]
        st.dataframe(top_authors)
    else:
        st.warning("No hay autores parseables")

with tabs[6]:
    st.subheader("☁️ Wordcloud de títulos")
    if "Title" in dff and not dff["Title"].dropna().empty:
        text = " ".join(dff["Title"].dropna().tolist())
        if text.strip():
            wc = WordCloud(width=800, height=400, background_color="white").generate(text)
            fig, ax = plt.subplots()
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig)
        else:
            st.warning("⚠️ No hay títulos disponibles para generar la nube de palabras.")
    else:
        st.warning("⚠️ No hay títulos disponibles para generar la nube de palabras.")