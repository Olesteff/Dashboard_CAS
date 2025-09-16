import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="Dashboard Cienciométrico — Facultad de Medicina Clínica Alemana, Universidad del Desarrollo",
    layout="wide",
)

st.title("📊 Dashboard Cienciométrico — Facultad de Medicina Clínica Alemana, Universidad del Desarrollo")

# ==========================
# 📂 Carga de datos
# ==========================
uploaded_file = st.sidebar.file_uploader("Sube el Excel enriquecido", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
else:
    st.warning("Sube un archivo Excel para comenzar")
    st.stop()


# ==========================
# 🎛️ Filtros en sidebar
# ==========================
st.sidebar.header("Filtros")

# Año
if "Year" in df.columns:
    years = sorted(df["Year"].dropna().unique())
    year_range = st.sidebar.slider("Año de publicación", int(min(years)), int(max(years)), (int(min(years)), int(max(years))))
    df = df[(df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])]

# Cuartiles
if "JCR_Quartile" in df.columns:
    quartiles = df["JCR_Quartile"].fillna("Sin cuartil").unique().tolist()
    selected_quartiles = st.sidebar.multiselect("Cuartiles", quartiles, default=quartiles)
    df = df[df["JCR_Quartile"].fillna("Sin cuartil").isin(selected_quartiles)]

# ==========================
# 📈 Métricas principales
# ==========================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total publicaciones", len(df))

with col2:
    q1pct = (df["JCR_Quartile"].eq("Q1").mean() * 100) if "JCR_Quartile" in df.columns else 0
    st.metric("% en Q1", f"{q1pct:.1f}%")

with col3:
    if "Times Cited" in df.columns:
        st.metric("Máx. citas", int(df["Times Cited"].max()))
    else:
        st.metric("Máx. citas", "—")

with col4:
    if "DOI" in df.columns:
        st.metric("Con DOI", df["DOI"].notna().sum())
    else:
        st.metric("Con DOI", "—")

# ==========================
# 🥧 Gráfico de cuartiles
# ==========================
if "JCR_Quartile" in df.columns:
    quartile_counts = df["JCR_Quartile"].fillna("Sin cuartil").value_counts()
    fig_q = px.pie(
        names=quartile_counts.index,
        values=quartile_counts.values,
        hole=0.4,
        color=quartile_counts.index,
        color_discrete_map={
            "Q1": "green",
            "Q2": "yellow",
            "Q3": "orange",
            "Q4": "darkred",
            "Sin cuartil": "lightgrey"
        }
    )
    fig_q.update_traces(textinfo="percent+label", pull=[0.05]*len(quartile_counts))
    st.plotly_chart(fig_q, use_container_width=True)

# ==========================
# 📜 Tabla de resultados
# ==========================
st.subheader("📜 Registros filtrados")
st.dataframe(df, use_container_width=True)

# ==========================
# 💾 Descargar resultados
# ==========================
st.download_button("⬇️ Descargar resultados (CSV)", df.to_csv(index=False).encode("utf-8"), "resultados.csv", "text/csv")
