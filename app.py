import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ========================
# CONFIGURACIÓN GENERAL
# ========================
st.set_page_config(
    page_title="Dashboard Cienciométrico — CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================
# ENCABEZADO CON LOGO
# ========================
st.markdown("""
<div style="display:flex;align-items:center;justify-content:center;margin-bottom:20px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/7/73/Logo_Universidad_del_Desarrollo.png" 
         alt="Logo UDD" width="120" style="margin-right:20px;">
    <h1 style="color:#1E3A8A;">📊 Dashboard Cienciométrico</h1>
</div>
<h3 style="text-align:center;color:#555;margin-top:-10px;">
    Facultad de Medicina Clínica Alemana – Universidad del Desarrollo
</h3>
""", unsafe_allow_html=True)

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
    st.warning("⚠️ No se encontró dataset. Se usará un ejemplo.")
    df = pd.DataFrame({
        "Year": [2018, 2019, 2020, 2021],
        "Publications": [120, 150, 210, 300],
        "JIF": [200, 250, 320, 500]
    })

# ========================
# INDICADORES CLAVE
# ========================
st.markdown("## 📊 Indicadores clave")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f"""
        <div style="background-color:#1E3A8A;padding:20px;border-radius:12px;text-align:center;color:white;">
            <h3>📚 Publicaciones</h3>
            <p style="font-size:32px;font-weight:bold;">{len(df)}</p>
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown(
        f"""
        <div style="background-color:#065F46;padding:20px;border-radius:12px;text-align:center;color:white;">
            <h3>⭐ Revistas Q1-Q2</h3>
            <p style="font-size:32px;font-weight:bold;">82%</p>
        </div>
        """, unsafe_allow_html=True)

with col3:
    st.markdown(
        f"""
        <div style="background-color:#2563EB;padding:20px;border-radius:12px;text-align:center;color:white;">
            <h3>🌍 Colaboración internacional</h3>
            <p style="font-size:32px;font-weight:bold;">61%</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ========================
# GRÁFICOS
# ========================
st.markdown("## 📈 Tendencias de publicación")

if "Year" in df.columns:
    pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
    fig1 = px.bar(
        pubs_per_year,
        x="Year",
        y="Publications",
        title="📅 Publicaciones por año",
        color_discrete_sequence=["#1E3A8A"]
    )
    fig1.update_layout(
        xaxis_title="Año",
        yaxis_title="Publicaciones",
        title_x=0.5,
        plot_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig1, use_container_width=True)

if "JIF" in df.columns:
    try:
        df["JIF"] = pd.to_numeric(df["JIF"], errors="coerce")
        df_sorted = df.dropna(subset=["Year", "JIF"]).sort_values("Year")
        df_sorted["JIF_cumulative"] = df_sorted["JIF"].cumsum()
        fig2 = px.line(
            df_sorted,
            x="Year",
            y="JIF_cumulative",
            title="📈 Evolución acumulada del JIF",
            markers=True,
            color_discrete_sequence=["#10B981"]
        )
        fig2.update_layout(
            xaxis_title="Año",
            yaxis_title="JIF acumulado",
            title_x=0.5,
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ No se pudo calcular el JIF acumulado: {e}")

# ========================
# VISTA PREVIA DEL DATASET
# ========================
st.markdown("## 📑 Vista previa del dataset")
st.dataframe(df.head(20))