import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------
# CONFIGURACIÓN DE PÁGINA
# -------------------------
st.set_page_config(
    page_title="Dashboard Cienciométrico — CAS–UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# ENCABEZADO
# -------------------------
st.markdown(
    """
    <h1 style="text-align: center; color: #004080;">
        📊 Dashboard Cienciométrico
    </h1>
    <h3 style="text-align: center; color: #666;">
        Facultad de Medicina Clínica Alemana – Universidad del Desarrollo
    </h3>
    """,
    unsafe_allow_html=True
)

# -------------------------
# CARGA DE DATOS
# -------------------------
@st.cache_data
def load_data():
    return pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS.xlsx")

df = load_data()

# Normalizamos columnas importantes
df.columns = df.columns.str.strip()
if "Year" not in df.columns:
    st.error("No se encontró la columna 'Year' en el dataset.")
else:
    # -------------------------
    # PESTAÑAS PRINCIPALES
    # -------------------------
    tab1, tab2, tab3 = st.tabs(["📂 Datos", "📊 Indicadores", "📈 Gráficos"])

    # TAB 1 - DATOS
    with tab1:
        st.subheader("Vista previa del dataset")
        st.dataframe(df.head(20))

        st.download_button(
            label="📥 Descargar dataset completo (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="dataset_cas_udd.csv",
            mime="text/csv"
        )

    # TAB 2 - INDICADORES
    with tab2:
        st.subheader("Indicadores clave")

        # Métricas rápidas
        total_pubs = len(df)
        q1_q2 = df[df["JCR Quartile"].isin(["Q1", "Q2"])] if "JCR Quartile" in df.columns else df
        pct_q1_q2 = len(q1_q2) / total_pubs if total_pubs > 0 else 0
        intl = df[df["International Collaboration"] == "Yes"] if "International Collaboration" in df.columns else df
        pct_intl = len(intl) / total_pubs if total_pubs > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("📚 Total publicaciones", total_pubs)
        col2.metric("⭐ Revistas Q1–Q2", f"{pct_q1_q2:.0%}")
        col3.metric("🌍 Colaboración internacional", f"{pct_intl:.0%}")

    # TAB 3 - GRÁFICOS
    with tab3:
        st.subheader("Tendencias de publicación")

        # Publicaciones por año
        pubs_year = df.groupby("Year").size().reset_index(name="Publicaciones")
        fig1 = px.bar(pubs_year, x="Year", y="Publicaciones", title="Publicaciones por año")
        st.plotly_chart(fig1, use_container_width=True)

        # Si existe columna JIF, mostramos tendencia acumulada
        if "JIF" in df.columns:
            jif_year = df.groupby("Year")["JIF"].sum().reset_index()
            jif_year["JIF acumulado"] = jif_year["JIF"].cumsum()
            fig2 = px.line(jif_year, x="Year", y="JIF acumulado", title="Evolución acumulada del JIF")
            st.plotly_chart(fig2, use_container_width=True)

        # Botones de descarga
        st.download_button(
            label="📥 Descargar publicaciones por año (CSV)",
            data=pubs_year.to_csv(index=False).encode("utf-8"),
            file_name="publicaciones_por_ano.csv",
            mime="text/csv"
        )