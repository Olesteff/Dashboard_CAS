import streamlit as st
import pandas as pd
import plotly.express as px
import os

# =========================
# CONFIGURACIÓN GENERAL
# =========================
st.set_page_config(
    page_title="Dashboard Cienciométrico – CAS-UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# ENCABEZADO CON LOGO
# =========================
st.markdown(
    """
    <div style="display:flex;align-items:center;justify-content:center;margin-bottom:20px;">
        <img src="cas-udd.jpg" alt="Logo CAS-UDD" width="120" style="margin-right:25px;">
        <h1 style="color:#004080;margin:0;">📊 Dashboard Cienciométrico</h1>
    </div>
    <h3 style="text-align:center;color:#777;margin-top:0;">
        Facultad de Medicina Clínica Alemana – Universidad del Desarrollo
    </h3>
    """,
    unsafe_allow_html=True
)

# =========================
# CARGA DE DATOS
# =========================
st.sidebar.header("📂 Subir archivo Excel")
uploaded_file = st.sidebar.file_uploader("Carga el dataset consolidado (.xlsx)", type=["xlsx"])

DEFAULT_FILE = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype=str)
    st.success("✅ Dataset cargado correctamente")
elif os.path.exists(DEFAULT_FILE):
    df = pd.read_excel(DEFAULT_FILE, dtype=str)
    st.info(f"ℹ️ Usando dataset por defecto: {DEFAULT_FILE}")
else:
    st.error("❌ No se encontró dataset. Sube un archivo para continuar.")
    st.stop()

# Convertir numéricas si existen
for col in ["JIF", "Citations"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# =========================
# FUNCIONES DE MÉTRICAS
# =========================
def safe_metric(label, value, icon="ℹ️", color="#333"):
    return f"""
    <div style="
        background:{color};
        padding:20px;
        border-radius:12px;
        text-align:center;
        box-shadow:0 4px 12px rgba(0,0,0,0.2);
        color:white;
        ">
        <div style="font-size:22px;margin-bottom:8px;">{icon} {label}</div>
        <div style="font-size:28px;font-weight:bold;">{value}</div>
    </div>
    """

# =========================
# INDICADORES CLAVE
# =========================
st.markdown("## 📊 Indicadores clave")

metrics = []

# Total publicaciones
metrics.append(safe_metric("Publicaciones", f"{len(df):,}", "📚", "#004080"))

# Revistas Q1-Q2 (si existe columna Quartile)
if "Quartile" in df.columns:
    q12 = (df["Quartile"].isin(["Q1", "Q2"])).mean() * 100
    metrics.append(safe_metric("Revistas Q1-Q2", f"{q12:.1f}%", "⭐", "#00703c"))

# Colaboración internacional (si existe columna Countries o Similar)
if "Countries" in df.columns:
    intl = df["Countries"].apply(lambda x: "," in str(x)).mean() * 100
    metrics.append(safe_metric("Colaboración internacional", f"{intl:.1f}%", "🌍", "#0066cc"))

# Total de citas
if "Citations" in df.columns:
    total_cites = int(df["Citations"].sum())
    metrics.append(safe_metric("Total de citas", f"{total_cites:,}", "📑", "#5a189a"))

# Promedio JIF
if "JIF" in df.columns:
    avg_jif = df["JIF"].mean()
    metrics.append(safe_metric("Promedio JIF", f"{avg_jif:.2f}", "📈", "#d00000"))

# Autores únicos
if "Authors" in df.columns:
    unique_authors = set()
    df["Authors"].dropna().apply(lambda x: unique_authors.update(a.strip() for a in str(x).split(",")))
    metrics.append(safe_metric("Autores únicos", len(unique_authors), "👩‍🔬", "#ff8800"))

# Departamentos (si existe columna Department)
if "Department" in df.columns:
    n_departments = df["Department"].nunique()
    metrics.append(safe_metric("Departamentos", n_departments, "🏥", "#0096c7"))

# Render en cuadrícula
cols = st.columns(len(metrics))
for i, m in enumerate(metrics):
    cols[i].markdown(m, unsafe_allow_html=True)

# =========================
# GRÁFICOS
# =========================
st.markdown("## 📈 Tendencias de publicación")

if "Year" in df.columns:
    pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
    fig1 = px.bar(
        pubs_per_year, x="Year", y="Publications",
        title="📅 Publicaciones por año",
        color_discrete_sequence=["#004080"]
    )
    st.plotly_chart(fig1, use_container_width=True)