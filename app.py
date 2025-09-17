import streamlit as st
import pandas as pd
import plotly.express as px

# =========================
# 📥 Carga de datos
# =========================
@st.cache_data
def load_data():
    file_path = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
    df = pd.read_excel(file_path)

    # Normalizar año a enteros
    if "Year_clean" in df.columns:
        df["Year_clean"] = pd.to_numeric(df["Year_clean"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["Year_clean"])

    return df

df = load_data()

# =========================
# 🎛️ Filtros en sidebar
# =========================
st.sidebar.header("Filtros")

# --- Filtro de años con slider ---
min_year = int(df["Year_clean"].min())
max_year = int(df["Year_clean"].max())
year_range = st.sidebar.slider(
    "Selecciona rango de años",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
    step=1
)
df = df[(df["Year_clean"] >= year_range[0]) & (df["Year_clean"] <= year_range[1])]

# --- Filtro Open Access ---
oa_filter = st.sidebar.radio("Open Access", ["Todos", "Open Access", "Closed Access"])
if oa_filter == "Open Access":
    df = df[df["OpenAccess_flag"] == True]
elif oa_filter == "Closed Access":
    df = df[df["OpenAccess_flag"] == False]

# --- Filtro de cuartil JCR ---
quartiles = df["JCR_Quartile"].dropna().unique().tolist()
selected_quartiles = st.sidebar.multiselect("Cuartil JCR", options=quartiles, default=quartiles)
if selected_quartiles:
    df = df[df["JCR_Quartile"].isin(selected_quartiles)]

# =========================
# 📊 Layout con tabs
# =========================
st.title("📊 Dashboard Producción Científica CAS-UDD")

tab1, tab2, tab3 = st.tabs(["📌 Resumen general", "📚 Revistas", "🔓 Open Access"])

# --- Resumen General ---
with tab1:
    st.subheader("📌 Resumen General")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total publicaciones", len(df))
    with col2:
        pct_oa = (df["OpenAccess_flag"].mean() * 100) if "OpenAccess_flag" in df.columns else 0
        st.metric("% Open Access", f"{pct_oa:.1f}%")
    with col3:
        if "Journal Impact Factor" in df.columns:
            st.metric("Promedio JIF", f"{df['Journal Impact Factor'].mean():.2f}")
        else:
            st.metric("Promedio JIF", "N/A")

    # Gráfico cuartiles JCR
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
        fig_q.update_traces(textposition="inside", textinfo="percent+label", pull=[0.05]*len(quartile_counts))
        st.plotly_chart(fig_q, use_container_width=True)

    # Publicaciones por año
    pubs_per_year = df.groupby("Year_clean").size().reset_index(name="N° Publicaciones")
    fig_pub_year = px.bar(
        pubs_per_year,
        x="Year_clean",
        y="N° Publicaciones",
        title="📈 Publicaciones por año"
    )
    st.plotly_chart(fig_pub_year, use_container_width=True)

# --- Revistas ---
with tab2:
    st.subheader("📚 Revistas con más publicaciones")
    if "Source title" in df.columns:
        top_journals = df["Source title"].value_counts().head(10).reset_index()
        top_journals.columns = ["Revista", "N° Publicaciones"]
        fig_journals = px.bar(top_journals, x="Revista", y="N° Publicaciones", text="N° Publicaciones")
        fig_journals.update_traces(textposition="outside")
        st.plotly_chart(fig_journals, use_container_width=True)
        st.dataframe(top_journals)

# --- Open Access ---
with tab3:
    st.subheader("🔓 Evolución del Open Access")
    if "OpenAccess_flag" in df.columns:
        oa_trend = df.groupby("Year_clean")["OpenAccess_flag"].mean().reset_index()
        oa_trend["OpenAccess_flag"] *= 100
        fig_oa = px.line(
            oa_trend,
            x="Year_clean",
            y="OpenAccess_flag",
            title="📈 Evolución de % OA por año"
        )
        fig_oa.update_traces(mode="lines+markers")
        st.plotly_chart(fig_oa, use_container_width=True)