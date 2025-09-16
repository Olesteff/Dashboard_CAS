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
    background-color: #1e1e1e;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    text-align: center;
    margin: 10px;
}
.metric-label {
    font-size: 16px;
    color: #aaa;
}
.metric-value {
    font-size: 28px;
    font-weight: bold;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ========================
# ENCABEZADO CON LOGO
# ========================
st.markdown(
    """
    <div style="display:flex;align-items:center;justify-content:center;margin-bottom:20px;">
        <img src="cas-udd.jpg" width="90" style="margin-right:20px;">
        <h1 style="color:#004080;margin:0;">📊 Dashboard Cienciométrico</h1>
    </div>
    <h3 style="text-align:center;color:#777;margin-top:0;">
        Facultad de Medicina Clínica Alemana – Universidad del Desarrollo
    </h3>
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
    st.error("❌ No se encontró ningún dataset.")
    st.stop()

# Convertir numéricas
for col in ["Year", "JIF", "Citations"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ========================
# MÉTRICAS CLAVE
# ========================
st.markdown("## 📊 Indicadores clave")

total_pubs = len(df)
q1q2_ratio = (df["Quartile"].isin(["Q1", "Q2"]).mean() * 100) if "Quartile" in df.columns else 0
intl_collab = (df["International_collab"].mean() * 100) if "International_collab" in df.columns else 0
total_citations = int(df["Citations"].sum()) if "Citations" in df.columns else 0
avg_jif = round(df["JIF"].mean(), 2) if "JIF" in df.columns else 0
unique_authors = df["Authors"].nunique() if "Authors" in df.columns else 0
unique_departments = df["Department"].nunique() if "Department" in df.columns else 0

cols = st.columns(4)

with cols[0]:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>📚 Publicaciones</div>
            <div class='metric-value'>{total_pubs:,}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with cols[1]:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>⭐ Revistas Q1-Q2</div>
            <div class='metric-value'>{q1q2_ratio:.0f}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with cols[2]:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>🌍 Colaboración internacional</div>
            <div class='metric-value'>{intl_collab:.0f}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with cols[3]:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>📑 Total de citas</div>
            <div class='metric-value'>{total_citations:,}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

cols2 = st.columns(3)

with cols2[0]:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>📈 Promedio JIF</div>
            <div class='metric-value'>{avg_jif}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with cols2[1]:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>👩‍🔬 Autores únicos</div>
            <div class='metric-value'>{unique_authors}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with cols2[2]:
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-label'>🏥 Departamentos</div>
            <div class='metric-value'>{unique_departments}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ========================
# GRÁFICOS
# ========================
st.markdown("## 📈 Tendencias de publicación")

if "Year" in df.columns:
    pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
    fig = px.bar(
        pubs_per_year,
        x="Year",
        y="Publications",
        title="📅 Publicaciones por año",
        color_discrete_sequence=["#004080"]
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("⚠️ No se encontró la columna 'Year' en el dataset.")