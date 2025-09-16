import streamlit as st
import pandas as pd
import plotly.express as px
import os

# =========================
# CONFIGURACIÓN GENERAL
# =========================
st.set_page_config(
    page_title="Dashboard Cienciométrico — CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# ESTILOS CSS
# =========================
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            max-width: 1400px;
        }
        h1, h2, h3 {
            font-family: "Segoe UI", sans-serif;
        }
        .metric-card {
            padding: 20px;
            border-radius: 12px;
            background-color: #1e1e1e;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            text-align: center;
        }
        .metric-label {
            font-size: 16px;
            color: #aaa;
        }
        .metric-value {
            font-size: 28px;
            font-weight: bold;
            color: #ffffff;
        }
    </style>
""", unsafe_allow_html=True)

# =========================
# ENCABEZADO
# =========================
st.markdown("""
<div style="display:flex;align-items:center;gap:15px;margin-bottom:15px;">
    <img src="https://i.ibb.co/gT4XM4R/logo-udd.png" alt="Logo UDD" width="70">
    <div>
        <h1 style="margin:0;color:#004080;">Dashboard Cienciométrico</h1>
        <h3 style="margin:0;color:#888;">Facultad de Medicina Clínica Alemana – Universidad del Desarrollo</h3>
    </div>
</div>
""", unsafe_allow_html=True)

# =========================
# CARGA DE DATOS
# =========================
st.sidebar.header("📂 Subir archivo Excel")
uploaded_file = st.sidebar.file_uploader("Carga el dataset consolidado (.xlsx)", type=["xlsx"])

DEFAULT_FILE = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype=str)
    st.sidebar.success("✅ Dataset cargado correctamente")
elif os.path.exists(DEFAULT_FILE):
    df = pd.read_excel(DEFAULT_FILE, dtype=str)
    st.sidebar.info(f"ℹ️ Usando dataset por defecto: {DEFAULT_FILE}")
else:
    st.error("❌ No se encontró ningún dataset disponible")
    st.stop()

# =========================
# PROCESAMIENTO SIMPLE
# =========================
if "Year" in df.columns:
    pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
else:
    pubs_per_year = pd.DataFrame(columns=["Year", "Publications"])

# =========================
# INDICADORES CLAVE
# =========================
st.subheader("📊 Indicadores clave")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">📚 Total publicaciones</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">{len(df)}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">⭐ Revistas Q1–Q2</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">82%</div>', unsafe_allow_html=True)  # placeholder
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">🌍 Colaboración internacional</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-value">61%</div>', unsafe_allow_html=True)  # placeholder
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# GRÁFICOS
# =========================
st.subheader("📈 Tendencias de publicación")

if not pubs_per_year.empty:
    fig = px.bar(
        pubs_per_year, x="Year", y="Publications",
        title="📅 Publicaciones por año",
        color_discrete_sequence=["#004080"]
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("⚠️ No se encontró la columna 'Year' en el dataset.")

# =========================
# VISTA PREVIA DEL DATASET
# =========================
st.subheader("🗂️ Vista previa del dataset")
st.dataframe(df.head(20), use_container_width=True)