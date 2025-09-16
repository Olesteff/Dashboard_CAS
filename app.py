import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
st.set_page_config(
    page_title="Dashboard Cienciométrico — CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================
# LOGO + TÍTULO
# ==============================
st.markdown("""
<div style="display:flex;align-items:center;justify-content:center;margin-bottom:20px;">
    <img src="https://raw.githubusercontent.com/Olesteff/Dashboard_CAS/main/cas-udd.jpg" 
         alt="Logo CAS-UDD" width="120" style="margin-right:20px;">
    <h1 style="color:#004080;margin:0;">📊 Dashboard Cienciométrico</h1>
</div>
<h3 style="text-align:center;color:#777;margin-top:0;">
    Facultad de Medicina Clínica Alemana – Universidad del Desarrollo
</h3>
""", unsafe_allow_html=True)

# ==============================
# ARCHIVO POR DEFECTO
# ==============================
DEFAULT_FILE = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

st.sidebar.header("📂 Subir archivo Excel")
uploaded_file = st.sidebar.file_uploader(
    "Carga el dataset consolidado (.xlsx)", type=["xlsx"]
)

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype=str)
    st.success("✅ Dataset cargado correctamente")
elif os.path.exists(DEFAULT_FILE):
    df = pd.read_excel(DEFAULT_FILE, dtype=str)
    st.info(f"ℹ️ Usando dataset por defecto: {DEFAULT_FILE}")
else:
    st.error("❌ No se encontró dataset. Sube un archivo Excel.")
    st.stop()

# Convertir columnas numéricas si existen
for col in ["JIF", "Citas"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ==============================
# TABS PRINCIPALES
# ==============================
tab1, tab2, tab3 = st.tabs(["📑 Datos", "📊 Indicadores", "📈 Gráficos"])

# ==============================
# TAB 1: DATOS
# ==============================
with tab1:
    st.subheader("📑 Vista previa del dataset")
    st.dataframe(df.head(20), use_container_width=True)
    st.download_button(
        "📥 Descargar dataset completo (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        "dataset_export.csv",
        "text/csv"
    )

# ==============================
# TAB 2: INDICADORES
# ==============================
with tab2:
    st.subheader("📊 Indicadores clave")

    total_pubs = len(df)
    q1q2_pct = (
        (df["Cuartil_JCR"].isin(["Q1", "Q2"]).mean() * 100)
        if "Cuartil_JCR" in df.columns else None
    )
    intl_pct = (
        (df["Colaboración"].eq("Internacional").mean() * 100)
        if "Colaboración" in df.columns else None
    )
    total_citas = int(df["Citas"].sum()) if "Citas" in df.columns else None
    avg_jif = round(df["JIF"].mean(), 2) if "JIF" in df.columns else None
    autores_unicos = (
        df["Authors"].str.split(";").explode().nunique()
        if "Authors" in df.columns else None
    )
    departamentos = (
        df["Departamento"].nunique()
        if "Departamento" in df.columns else None
    )

    # GRID DE CARDS
    st.markdown("<div style='display:flex;flex-wrap:wrap;gap:20px;'>", unsafe_allow_html=True)

    def card(label, value, color, emoji=""):
        if value is None:
            return ""
        return f"""
        <div style="flex:1;min-width:200px;padding:20px;
                    background:{color};border-radius:12px;
                    text-align:center;box-shadow:0 4px 8px rgba(0,0,0,0.2);">
            <div style="font-size:20px;">{emoji} {label}</div>
            <div style="font-size:28px;font-weight:bold;margin-top:10px;">{value}</div>
        </div>
        """

    metrics_html = ""
    metrics_html += card("Publicaciones", f"{total_pubs:,}", "#1E40AF", "📚")
    if avg_jif is not None:
        metrics_html += card("Promedio JIF", avg_jif, "#DC2626", "📈")
    if q1q2_pct is not None:
        metrics_html += card("Revistas Q1–Q2", f"{q1q2_pct:.1f}%", "#059669", "⭐")
    if intl_pct is not None:
        metrics_html += card("Colaboración internacional", f"{intl_pct:.1f}%", "#2563EB", "🌍")
    if total_citas is not None:
        metrics_html += card("Total de citas", f"{total_citas:,}", "#7C3AED", "📝")
    if autores_unicos is not None:
        metrics_html += card("Autores únicos", f"{autores_unicos:,}", "#F59E0B", "👨‍🔬")
    if departamentos is not None:
        metrics_html += card("Departamentos", departamentos, "#9333EA", "🏥")

    st.markdown(metrics_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ==============================
# TAB 3: GRÁFICOS
# ==============================
with tab3:
    st.subheader("📈 Tendencias de publicación")

    if "Year" in df.columns:
        pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
        fig1 = px.bar(
            pubs_per_year, x="Year", y="Publications",
            title="📅 Publicaciones por año",
            color_discrete_sequence=["#004080"]
        )
        st.plotly_chart(fig1, use_container_width=True)

    if "JIF" in df.columns and "Year" in df.columns:
        df_sorted = df.dropna(subset=["Year", "JIF"]).copy()
        df_sorted["JIF"] = pd.to_numeric(df_sorted["JIF"], errors="coerce")
        df_sorted = df_sorted.groupby("Year")["JIF"].mean().reset_index()
        fig2 = px.line(
            df_sorted, x="Year", y="JIF",
            title="📈 Evolución promedio del JIF",
            markers=True,
            color_discrete_sequence=["#009688"]
        )
        st.plotly_chart(fig2, use_container_width=True)