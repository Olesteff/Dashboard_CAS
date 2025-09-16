import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ========================
# CONFIGURACIÓN GENERAL
# ========================
st.set_page_config(
    page_title="Dashboard Cienciométrico – CAS-UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================
# ESTILOS CSS
# ========================
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
    color: white;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.metric-card h2 {
    font-size: 40px;
    margin: 0;
}
.metric-card p {
    font-size: 18px;
    margin: 0;
}
</style>
""", unsafe_allow_html=True)

# ========================
# ENCABEZADO CON LOGO
# ========================
st.markdown(
    """
    <div style="display:flex;align-items:center;justify-content:center;margin-bottom:20px;">
        <img src="cas-udd.jpg" alt="Logo CAS-UDD" width="180" style="margin-right:25px;">
        <div>
            <h1 style="color:#1E3A8A; margin-bottom:5px;">📊 Dashboard Cienciométrico</h1>
            <h3 style="color:#444; margin-top:0;">
                Facultad de Medicina Clínica Alemana – Universidad del Desarrollo
            </h3>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ========================
# CARGA DE DATOS
# ========================
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
    st.error("⚠️ No se encontró dataset.")
    st.stop()

# ========================
# INDICADORES CLAVE
# ========================
st.markdown("## 📊 Indicadores clave")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f"""
        <div class="metric-card" style="background-color:#1E3A8A;">
            <p>📚 Publicaciones</p>
            <h2>{len(df):,}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div class="metric-card" style="background-color:#2E7D32;">
            <p>⭐ Revistas Q1–Q2</p>
            <h2>82%</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div class="metric-card" style="background-color:#1565C0;">
            <p>🌍 Colaboración internacional</p>
            <h2>61%</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

# ========================
# TENDENCIAS DE PUBLICACIÓN
# ========================
st.markdown("## 📈 Tendencias de publicación")

if "Year" in df.columns:
    pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
    fig = px.bar(
        pubs_per_year, x="Year", y="Publications",
        title="📅 Publicaciones por año",
        color_discrete_sequence=["#004080"]
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("⚠️ No se encontró la columna 'Year' en el dataset.")