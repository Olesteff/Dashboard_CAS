import streamlit as st
import pandas as pd
import plotly.express as px

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
        <img src="https://upload.wikimedia.org/wikipedia/commons/6/6a/Logo_Universidad_del_Desarrollo.png"
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

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype=str)
    st.success("✅ Dataset cargado correctamente")
else:
    st.warning("⚠️ No se ha cargado ningún dataset. Se usará un ejemplo.")
    data = {"Year": [2018, 2019, 2020, 2021, 2022, 2023],
            "Publications": [120, 150, 210, 300, 450, 380],
            "JIF": [200, 250, 320, 400, 600, 720]}
    df = pd.DataFrame(data)

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
    st.metric(label="", value="82%")  # puedes conectar a tu cálculo real

with col3:
    st.markdown("🌍 **Colaboración internacional**")
    st.metric(label="", value="61%")  # puedes conectar a tu cálculo real

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
    pubs_per_year = df.groupby("Year").size().reset_index(name="Publications")
    st.dataframe(pubs_per_year)

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

    # JIF acumulado (ejemplo si existe columna JIF)
    if "JIF" in df.columns:
        df["JIF_cumulative"] = df["JIF"].cumsum()
        fig2 = px.line(
            df, x="Year", y="JIF_cumulative",
            title="📈 Evolución acumulada del JIF",
            markers=True,
            color_discrete_sequence=["#009688"]
        )
        st.plotly_chart(fig2, use_container_width=True)