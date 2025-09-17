import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud

# =========================
# CONFIGURACIÓN
# =========================
st.set_page_config(
    page_title="Dashboard de Producción Científica – Clínica Alemana – Universidad del Desarrollo",
    layout="wide"
)
st.title("📊 Dashboard de Producción Científica – Clínica Alemana – Universidad del Desarrollo")

# =========================
# FUNCIONES AUXILIARES
# =========================
def _first_col(df, candidates):
    """Devuelve la primera columna existente en df dentro de candidates"""
    for c in candidates:
        if c in df.columns:
            return c
    return None

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nombres y asegura columnas clave"""
    df = df.copy()
    df.columns = df.columns.astype(str)

    # Normalizar año
    year_col = _first_col(df, ["Year", "Año", "Publication Year", "Year_Published"])
    if year_col:
        df = df.rename(columns={year_col: "Year"})
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

    # Normalizar OA
    if "OpenAccess_flag" in df.columns:
        df["OpenAccess_flag"] = df["OpenAccess_flag"].astype(str).str.lower().map({"true": True, "false": False})
    else:
        df["OpenAccess_flag"] = False

    # Normalizar cuartiles
    q_col = _first_col(df, ["JCR Quartile", "JCR_Quartile", "Quartile", "quartile_std"])
    if q_col:
        df["Quartile_std"] = df[q_col].fillna("Sin cuartil").astype(str)
    else:
        df["Quartile_std"] = "Sin cuartil"

    # Normalizar JIF
    jif_col = _first_col(df, ["Journal Impact Factor", "Impact Factor", "JIF"])
    if jif_col:
        df["Journal Impact Factor"] = pd.to_numeric(df[jif_col], errors="coerce").fillna(0)
    else:
        df["Journal Impact Factor"] = 0

    # Departamentos dinámicos
    def detect_departments(aff: str) -> str:
        a = str(aff or "").lower()
        rules = [
            ("oncolog", "Oncología"),
            ("pediatr", "Pediatría"),
            ("neurolog", "Neurología"),
            ("psiquiatr", "Psiquiatría"),
            ("radiolog", "Imágenes"),
            ("imagen", "Imágenes"),
            ("ginecol", "Ginecología y Obstetricia"),
            ("obstet", "Ginecología y Obstetricia"),
            ("traumatolog", "Traumatología y Ortopedia"),
            ("ortoped", "Traumatología y Ortopedia"),
            ("dermatolog", "Dermatología"),
            ("hematolog", "Hematología"),
            ("urolog", "Urología"),
            ("farmac", "Farmacología"),
            ("psicol", "Psicología"),
            ("medicina interna", "Medicina Interna"),
            ("internal medicine", "Medicina Interna"),
            ("urgenc", "Urgencias"),
            ("intensiv", "Cuidados Intensivos"),
            ("anestesi", "Anestesiología"),
            ("cardiol", "Cardiología"),
            ("endocrin", "Endocrinología"),
            ("nefrol", "Nefrología"),
            ("neumol", "Neumología"),
            ("rehabilit", "Rehabilitación"),
            ("odont", "Odontología"),
            ("alemana", "Clínica Alemana (General)"),
            ("universidad del desarrollo", "Clínica Alemana (General)"),
            ("udd", "Clínica Alemana (General)"),
        ]
        found = [dep for kw, dep in rules if kw in a]
        return "; ".join(sorted(set(found))) if found else "Sin asignar"

    aff_col = _first_col(df, ["Authors with affiliations", "Author Affiliations", "Affiliations", "C1", "Author Information"])
    if aff_col:
        df["Departamento"] = df[aff_col].map(detect_departments)
    else:
        df["Departamento"] = "Sin asignar"

    # Ensayos clínicos
    def detect_clinical_trial(row) -> bool:
        text = " ".join([str(row.get(c, "")) for c in ["Publication Type", "Title", "Abstract", "Author Keywords"]]).lower()
        keywords = ["clinical trial", "ensayo clínico", "randomized", "phase i", "phase ii", "phase iii"]
        return any(k in text for k in keywords)
    df["Clinical_trial_flag"] = df.apply(detect_clinical_trial, axis=1)

    return df

# =========================
# CARGA DE DATOS
# =========================
@st.cache_data
def load_data():
    df = pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS.xlsx", sheet_name=0)
    return normalize_columns(df)

df = load_data()

# =========================
# SIDEBAR - FILTROS
# =========================
st.sidebar.header("🔎 Filtros")
year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Año de publicación", min_value=year_min, max_value=year_max,
                               value=(year_min, year_max))
oa_filter = st.sidebar.selectbox("Open Access", ["Todos", "Solo OA", "Solo No OA"])
quartile_filter = st.sidebar.multiselect("Cuartiles JCR", options=sorted(df["Quartile_std"].unique()))
dept_filter = st.sidebar.multiselect("Departamentos", options=sorted(df["Departamento"].unique()))
search_term = st.sidebar.text_input("Buscar en títulos", "")

dff = df[(df["Year"].between(year_range[0], year_range[1]))]
if oa_filter == "Solo OA":
    dff = dff[dff["OpenAccess_flag"] == True]
elif oa_filter == "Solo No OA":
    dff = dff[dff["OpenAccess_flag"] == False]
if quartile_filter:
    dff = dff[dff["Quartile_std"].isin(quartile_filter)]
if dept_filter:
    dff = dff[dff["Departamento"].isin(dept_filter)]
if search_term:
    dff = dff[dff["Article Title"].str.contains(search_term, case=False, na=False)]

# =========================
# KPIs
# =========================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total publicaciones", len(dff))
oa_pct = 100 * dff["OpenAccess_flag"].mean() if len(dff) else 0
c2.metric("% Open Access", f"{oa_pct:.1f}%")
c3.metric("Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
c4.metric("Ensayos clínicos", int(dff["Clinical_trial_flag"].sum()))

# =========================
# TABS
# =========================
tabs = st.tabs([
    "📈 Publicaciones por año",
    "📊 Cuartiles",
    "📖 Open Access",
    "🏥 Departamentos",
    "📚 Revistas",
    "👥 Autores",
    "☁️ Wordcloud"
])

# Publicaciones por año + gráfico JIF
with tabs[0]:
    pubs_year = dff.groupby("Year").size().reset_index(name="Publicaciones")
    fig = px.bar(pubs_year, x="Year", y="Publicaciones", title="Publicaciones por año")
    st.plotly_chart(fig, use_container_width=True)

    jif_year = dff.groupby("Year")["Journal Impact Factor"].sum().reset_index()
    fig_jif = px.line(jif_year, x="Year", y="Journal Impact Factor", title="Suma JIF por año")
    st.plotly_chart(fig_jif, use_container_width=True)

# Cuartiles
with tabs[1]:
    q_counts = dff["Quartile_std"].value_counts().reset_index()
    q_counts.columns = ["Quartile", "Count"]
    fig_q = px.pie(q_counts, names="Quartile", values="Count", title="Distribución por cuartiles")
    st.plotly_chart(fig_q, use_container_width=True)

# OA
with tabs[2]:
    oa_counts = dff["OpenAccess_flag"].value_counts().reset_index()
    oa_counts.columns = ["OA", "Count"]
    fig_oa = px.pie(oa_counts, names="OA", values="Count", title="Distribución OA")
    st.plotly_chart(fig_oa, use_container_width=True)

# Departamentos
with tabs[3]:
    dept_counts = dff["Departamento"].value_counts().reset_index()
    dept_counts.columns = ["Departamento", "Count"]
    fig_dept = px.bar(dept_counts, x="Departamento", y="Count", title="Distribución por Departamento")
    st.plotly_chart(fig_dept, use_container_width=True)

# Revistas
with tabs[4]:
    journal_col = _first_col(dff, ["Source title", "Journal", "Journal Name"])
    if journal_col:
        top_journals = dff[journal_col].value_counts().head(15).reset_index()
        top_journals.columns = ["Journal", "Count"]
        fig_j = px.bar(top_journals, x="Journal", y="Count", title="Top 15 Revistas")
        st.plotly_chart(fig_j, use_container_width=True)
    else:
        st.warning("No hay columna de revistas.")

# Autores
with tabs[5]:
    auth_col = _first_col(dff, ["Author Full Names", "Authors"])
    if auth_col:
        authors_series = dff[auth_col].dropna().astype(str).str.split(";|,|\|").explode().str.strip()
        top_authors = authors_series.value_counts().head(15).reset_index()
        top_authors.columns = ["Autor", "Count"]
        fig_a = px.bar(top_authors, x="Autor", y="Count", title="Top 15 Autores")
        st.plotly_chart(fig_a, use_container_width=True)
    else:
        st.warning("No hay columna de autores.")

# Wordcloud
with tabs[6]:
    if "Article Title" in dff and not dff["Article Title"].dropna().empty:
        text = " ".join(dff["Article Title"].dropna().tolist())
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