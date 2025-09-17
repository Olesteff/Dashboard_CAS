import streamlit as st
import pandas as pd
import plotly.express as px

from pathlib import Path

# ================================
# Configuración inicial
# ================================
st.set_page_config(
    page_title="Dashboard CAS–UDD",
    layout="wide",
    page_icon="📊"
)

st.title("📊 Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo")

# ================================
# Carga de datos
# ================================
@st.cache_data
def load_data(path="dataset_unificado_enriquecido_jcr_PLUS.xlsx", sheet="Consolidado_enriq"):
    if not Path(path).exists():
        st.error(f"No se encontró el archivo {path}")
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name=sheet)

df = load_data()

if df.empty:
    st.stop()

# ================================
# Normalización de columnas
# ================================
# Año
if "Year" in df.columns:
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

# Open Access
oa_col = None
for cand in ["Open Access", "OA_flag", "oa"]:
    if cand in df.columns:
        oa_col = cand
        break

if oa_col:
    df[oa_col] = df[oa_col].astype(str).str.strip()

# Cuartiles
quart_col = None
for cand in ["JCR_Quartile", "SJR_Quartile", "Quartile_std"]:
    if cand in df.columns:
        quart_col = cand
        break

if quart_col:
    df[quart_col] = df[quart_col].fillna("Sin cuartil")
    df[quart_col] = df[quart_col].replace(
        {"Q1":"Q1", "Q2":"Q2", "Q3":"Q3", "Q4":"Q4"}
    )
else:
    df["Quartile_std"] = "Sin cuartil"
    quart_col = "Quartile_std"

# ================================
# Filtros
# ================================
st.sidebar.header("📂 Datos base")
uploaded = st.sidebar.file_uploader("Sube un XLSX", type="xlsx")
if uploaded is not None:
    df = pd.read_excel(uploaded, sheet_name=sheet)

st.sidebar.header("Filtros")

year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider(
    "Selecciona rango de años",
    min_value=year_min,
    max_value=year_max,
    value=(year_min, year_max)
)

oa_opts = ["Todos"] + sorted(df[oa_col].dropna().unique().tolist()) if oa_col else ["Todos"]
oa_choice = st.sidebar.radio("Open Access", oa_opts, index=0)

quart_opts = df[quart_col].dropna().unique().tolist()
quart_filter = st.sidebar.multiselect("Cuartil JCR/SJR", quart_opts, default=quart_opts)

dept_col = None
for cand in ["Departamento", "Department", "Dept"]:
    if cand in df.columns:
        dept_col = cand
        break
dept_choice = []
if dept_col:
    dept_choice = st.sidebar.multiselect("Departamento", sorted(df[dept_col].dropna().unique().tolist()))

title_search = st.sidebar.text_input("Buscar en título")

# ================================
# Aplicar filtros
# ================================
fdf = df.copy()
fdf = fdf[(fdf["Year"] >= year_range[0]) & (fdf["Year"] <= year_range[1])]

if oa_choice != "Todos" and oa_col:
    fdf = fdf[fdf[oa_col] == oa_choice]

if quart_filter:
    fdf = fdf[fdf[quart_col].isin(quart_filter)]

if dept_choice and dept_col:
    fdf = fdf[fdf[dept_col].isin(dept_choice)]

if title_search:
    fdf = fdf[fdf["Title"].str.contains(title_search, case=False, na=False)]

# ================================
# KPIs
# ================================
total_pubs = len(fdf)
pct_oa = 0
if oa_col:
    pct_oa = (fdf[oa_col].isin(["Open Access", "OA", "True", "1"])).mean() * 100

st.subheader("📌 Resumen general")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total publicaciones", total_pubs)
k2.metric("% Open Access", f"{pct_oa:.1f}%")
k3.metric("Ensayos clínicos detectados", int(fdf["Clinical Trial"].sum()) if "Clinical Trial" in fdf.columns else 0)
k4.metric("Publicaciones con sponsor", int(fdf["Funding sponsor"].notna().sum()) if "Funding sponsor" in fdf.columns else 0)

# ================================
# Tabs
# ================================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👩‍🔬 Autores", "☁️ Wordcloud"])

# --- Publicaciones ---
with tabs[0]:
    st.subheader("Publicaciones por año")
    pubs = fdf.groupby("Year").size().reset_index(name="Publicaciones")
    fig = px.bar(pubs, x="Year", y="Publicaciones")
    st.plotly_chart(fig, use_container_width=True)

# --- Cuartiles ---
with tabs[1]:
    st.subheader("Distribución por cuartil")
    quart_counts = fdf[quart_col].value_counts()
    fig_q = px.pie(
        names=quart_counts.index,
        values=quart_counts.values,
        hole=0.4,
        color=quart_counts.index,
        color_discrete_map={
            "Q1":"green", "Q2":"yellow", "Q3":"orange", "Q4":"red", "Sin cuartil":"lightgrey"
        }
    )
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(quart_counts.reset_index().rename(columns={"index":"Cuartil","Quartile_std":"Publicaciones"}))

# --- Open Access ---
with tabs[2]:
    st.subheader("Distribución Open Access")
    if oa_col:
        oa_counts = fdf[oa_col].value_counts()
        fig_oa = px.pie(names=oa_counts.index, values=oa_counts.values, hole=0.4)
        st.plotly_chart(fig_oa, use_container_width=True)
        st.dataframe(oa_counts.reset_index().rename(columns={"index":"Open Access","count":"Publicaciones"}))
    else:
        st.warning("No se encontró columna de Open Access")

# --- Departamentos ---
with tabs[3]:
    st.subheader("Distribución por departamento")
    if dept_col:
        dept_counts = fdf[dept_col].value_counts()
        fig_d = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values)
        st.plotly_chart(fig_d, use_container_width=True)
        st.dataframe(dept_counts.reset_index().rename(columns={"index":"Departamento", dept_col:"Publicaciones"}))
    else:
        st.warning("No se encontró columna de departamento")

# --- Revistas ---
with tabs[4]:
    st.subheader("Publicaciones por revista")
    if "Source title" in fdf.columns:
        rev_counts = fdf["Source title"].value_counts().head(20)
        st.bar_chart(rev_counts)
    else:
        st.warning("No se encontró columna de revista")

# --- Autores ---
with tabs[5]:
    st.subheader("Autores con más publicaciones")
    if "Authors" in fdf.columns:
        auth_counts = fdf["Authors"].value_counts().head(20)
        st.bar_chart(auth_counts)
    else:
        st.warning("No se encontró columna de autores")

# --- Wordcloud ---
with tabs[6]:
    st.subheader("Nube de palabras en títulos")
    if "Title" in fdf.columns:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
        text = " ".join(fdf["Title"].dropna().astype(str))
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        fig, ax = plt.subplots()
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
    else:
        st.warning("No se encontró columna de títulos")