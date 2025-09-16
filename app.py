import streamlit as st
import pandas as pd
import plotly.express as px
import os

# =========================
# CONFIGURACIÓN DE LA APP
# =========================
st.set_page_config(
    page_title="Dashboard Cienciométrico — CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# ENCABEZADO CON LOGO
# =========================
st.markdown(
    """
    <div style="display:flex;align-items:center;justify-content:center;margin-bottom:20px;">
        <img src="https://www.google.com/url?sa=i&url=https%3A%2F%2Fes.wikipedia.org%2Fwiki%2FFacultad_de_Medicina_Cl%25C3%25ADnica_Alemana_-_Universidad_del_Desarrollo&psig=AOvVaw04HqL3sDmCIUy64aw3ILVj&ust=1758079706376000&source=images&cd=vfe&opi=89978449&ved=0CBUQjRxqFwoTCJj86Lar3I8DFQAAAAAdAAAAABAE"
             alt="Logo UDD" width="90" style="margin-right:20px;">
        <h1 style="color:#004080;margin:0;">Dashboard Cienciométrico</h1>
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
    st.error("❌ No se encontró dataset. Por favor, sube un archivo válido.")
    st.stop()

# =========================
# INDICADORES CLAVE
# =========================
st.subheader("📊 Indicadores clave")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("📚 **Total publicaciones**")
    st.metric(label="", value=f"{len(df)}")

with col2:
    st.markdown("⭐ **Revistas Q1–Q2**")
    st.metric(label="", value="82%")  # TODO: conectar a cálculo real

with col3:
    st.markdown("🌍 **Colaboración internacional**")
    st.metric(label="", value="61%")  # TODO: conectar a cálculo real

# =========================
# PESTAÑAS
# =========================
tab1, tab2, tab3 = st.tabs(["📂 Datos", "📊 Indicadores", "📈 Gráficos"])

# --- TAB 1: Vista previa del dataset ---
with tab1:
    st.subheader("📂 Vista previa del dataset")
    st.dataframe(df.head(20), use_container_width=True)
    st.download_button(
        label="📥 Descargar dataset completo (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="dataset_cienciometrico.csv",
        mime="text/csv"
    )

# --- TAB 2: Indicadores detallados ---
with tab2:
    st.subheader("📊 Distribución por año")
    if "Year" in df.columns:
        pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
        st.dataframe(pubs_per_year)
    else:
        st.warning("⚠️ No se encontró la columna 'Year' en el dataset.")

# --- TAB 3: Gráficos ---
with tab3:
    st.subheader("📈 Tendencias de publicación")

    # Publicaciones por año
    if "Year" in df.columns:
        pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
        fig1 = px.bar(
            pubs_per_year, x="Year", y="Publications",
            title="📈 Publicaciones por año",
            color_discrete_sequence=["#004080"]
        )
        st.plotly_chart(fig1, use_container_width=True)

    # JIF acumulado (si existe columna JIF)
    if "JIF" in df.columns:
        try:
            df["JIF"] = pd.to_numeric(df["JIF"], errors="coerce")
            df_sorted = df.dropna(subset=["Year", "JIF"]).sort_values("Year")
            df_sorted["JIF_cumulative"] = df_sorted["JIF"].cumsum()
            fig2 = px.line(
                df_sorted, x="Year", y="JIF_cumulative",
                title="📈 Evolución acumulada del JIF",
                markers=True,
                color_discrete_sequence=["#009688"]
            )
            st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.warning(f"⚠️ No se pudo calcular el JIF acumulado: {e}")