
import streamlit as st
import pandas as pd
import plotly.express as px

# =========================
# ⚙️ Configuración de página
# =========================
st.set_page_config(
    page_title="CAS-UDD Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# 📥 Carga de datos
# =========================
@st.cache_data
def load_data():
    return pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS.xlsx", sheet_name="Consolidado_enriq")

df = load_data()

# =========================
# 🎛️ Filtros globales
# =========================
st.sidebar.header("Filtros")

years = sorted(df["Year_clean"].dropna().unique().tolist())
selected_years = st.sidebar.multiselect("Año", years, default=years)

oa_options = ["Todos","Open Access","Closed Access"]
selected_oa = st.sidebar.radio("Open Access", oa_options, index=0)

quartiles = sorted(df["JIF Quartile"].dropna().unique().tolist())
selected_quartiles = st.sidebar.multiselect("Cuartil JCR", quartiles, default=quartiles)

df_filtered = df.copy()
if selected_years:
    df_filtered = df_filtered[df_filtered["Year_clean"].isin(selected_years)]
if selected_oa != "Todos":
    if selected_oa == "Open Access":
        df_filtered = df_filtered[df_filtered["OpenAccess_flag"] == True]
    else:
        df_filtered = df_filtered[df_filtered["OpenAccess_flag"] == False]
if selected_quartiles:
    df_filtered = df_filtered[df_filtered["JIF Quartile"].isin(selected_quartiles)]

# =========================
# 🗂️ Pestañas principales
# =========================
tabs = st.tabs(["📊 Resumen general", "📚 Revistas", "👩‍⚕️ Autores/Departamentos", "🔓 Open Access", "📑 Dataset"])

# =========================
# 📊 Resumen General
# =========================
with tabs[0]:
    st.subheader("📊 Resumen General")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total publicaciones", len(df_filtered))
    col2.metric("% Open Access", f"{100*df_filtered['OpenAccess_flag'].mean():.1f}%")
    if "Journal Impact Factor" in df_filtered:
        col3.metric("Promedio JIF", f"{df_filtered['Journal Impact Factor'].mean():.2f}")

    # Donut chart por cuartiles
    if "JIF Quartile" in df_filtered:
        quartile_counts = df_filtered["JIF Quartile"].fillna("Sin cuartil").value_counts()
        fig_q = px.pie(
            names=quartile_counts.index,
            values=quartile_counts.values,
            hole=0.4,
            color=quartile_counts.index,
            color_discrete_map={
                "Q1":"green",
                "Q2":"yellow",
                "Q3":"orange",
                "Q4":"darkred",
                "Sin cuartil":"lightgrey"
            }
        )
        fig_q.update_traces(textposition="inside", textinfo="label+percent")
        st.plotly_chart(fig_q, use_container_width=True)

    # Conteo de publicaciones por año
    if "Year_clean" in df_filtered:
        pubs_by_year = df_filtered.groupby("Year_clean").size()
        fig_year = px.bar(
            pubs_by_year,
            x=pubs_by_year.index,
            y=pubs_by_year.values,
            title="Publicaciones por año",
            labels={"x":"Año", "y":"N° Publicaciones"}
        )
        st.plotly_chart(fig_year, use_container_width=True)

# =========================
# 📚 Revistas
# =========================
with tabs[1]:
    st.subheader("📚 Análisis por Revistas")
    if "Journal Impact Factor" in df_filtered:
        top_jif = (df_filtered[["Source title","Journal Impact Factor"]]
                   .dropna()
                   .drop_duplicates()
                   .sort_values("Journal Impact Factor", ascending=False)
                   .head(10))
        st.write("### Top 10 revistas por JIF")
        st.bar_chart(top_jif.set_index("Source title"))
    if "SJR" in df_filtered:
        top_sjr = (df_filtered[["Source title","SJR"]]
                   .dropna()
                   .drop_duplicates()
                   .sort_values("SJR", ascending=False)
                   .head(10))
        st.write("### Top 10 revistas por SJR")
        st.bar_chart(top_sjr.set_index("Source title"))

# =========================
# 👩‍⚕️ Autores / Departamentos
# =========================
with tabs[2]:
    st.subheader("👩‍⚕️ Autores y Departamentos")
    if "Authors" in df_filtered:
        top_authors = df_filtered["Authors"].value_counts().head(10)
        st.write("### Top 10 autores")
        st.bar_chart(top_authors)
    if "Affiliations" in df_filtered:
        top_dept = df_filtered["Affiliations"].value_counts().head(10)
        st.write("### Top 10 departamentos / afiliaciones")
        st.bar_chart(top_dept)

# =========================
# 🔓 Open Access
# =========================
with tabs[3]:
    st.subheader("🔓 Open Access")
    oa_by_year = df_filtered.groupby("Year_clean")["OpenAccess_flag"].mean().mul(100)
    st.write("### Evolución de % OA por año")
    st.line_chart(oa_by_year)

# =========================
# 📑 Dataset
# =========================
with tabs[4]:
    st.subheader("📑 Dataset filtrado")
    st.dataframe(df_filtered)
    st.download_button("⬇️ Descargar Excel", df_filtered.to_csv(index=False).encode("utf-8"), "dataset_filtrado.csv", "text/csv")
