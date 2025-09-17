
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from io import BytesIO

# ============================
# CONFIGURACIÓN INICIAL
# ============================
st.set_page_config(
    page_title="Dashboard Producción Científica – CAS-UDD",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================
# FUNCIÓN PARA CARGAR DATASET
# ============================
@st.cache_data
def load_data(file):
    df = pd.read_excel(file)
    # Normalizamos nombres de columnas para evitar problemas
    df.columns = df.columns.str.strip()
    return df

# ============================
# UPLOAD DE ARCHIVO
# ============================
st.sidebar.header("📂 Datos base")
uploaded_file = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx"])

if uploaded_file:
    df = load_data(uploaded_file)
else:
    st.warning("⚠️ Por favor, sube un archivo Excel con el dataset consolidado.")
    st.stop()

# ============================
# TÍTULO PRINCIPAL
# ============================
st.title("📊 Dashboard de Producción Científica – Clínica Alemana – Universidad del Desarrollo")

# ============================
# FILTROS
# ============================
st.sidebar.subheader("Filtros")

# Rango de años
min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Selecciona rango de años", min_year, max_year, (min_year, max_year))

# Open Access (usamos OpenAccess_flag con True/False)
oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo Open Access", "Solo Closed Access"])

# Cuartiles
quartiles = df["JCR_Quartile"].dropna().unique().tolist() + ["Sin cuartil"]
selected_quartiles = st.sidebar.multiselect("Cuartil JCR/SJR", quartiles, default=quartiles)

# Departamento dinámico
departamentos = df.get("Departamento", pd.Series(["Sin asignar"])).fillna("Sin asignar").unique().tolist()
selected_deptos = st.sidebar.multiselect("Departamento", departamentos, default=departamentos)

# ============================
# APLICAR FILTROS
# ============================
df_filtered = df[(df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])]

if oa_filter == "Solo Open Access":
    df_filtered = df_filtered[df_filtered["OpenAccess_flag"] == True]
elif oa_filter == "Solo Closed Access":
    df_filtered = df_filtered[df_filtered["OpenAccess_flag"] == False]

if "JCR_Quartile" in df_filtered.columns:
    df_filtered["JCR_Quartile"] = df_filtered["JCR_Quartile"].fillna("Sin cuartil")
    df_filtered = df_filtered[df_filtered["JCR_Quartile"].isin(selected_quartiles)]

if "Departamento" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Departamento"].isin(selected_deptos)]

# ============================
# KPIs
# ============================
total_pubs = len(df_filtered)
pct_oa = (df_filtered["OpenAccess_flag"].mean() * 100) if "OpenAccess_flag" in df_filtered else 0
total_jif = df_filtered["Journal Impact Factor"].fillna(0).sum() if "Journal Impact Factor" in df_filtered else 0
ensayos = df_filtered["Clinical Trial"].sum() if "Clinical Trial" in df_filtered else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("📑 Total publicaciones", total_pubs)
kpi2.metric("🔓 % Open Access", f"{pct_oa:.1f}%")
kpi3.metric("⭐ Suma total JIF", f"{total_jif:,.1f}")
kpi4.metric("🧪 Ensayos clínicos", int(ensayos))

# ============================
# PESTAÑAS
# ============================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👩‍🔬 Autores", "☁️ Wordcloud"])

# TAB 1: Publicaciones
with tabs[0]:
    st.subheader("Publicaciones por año")
    pubs_year = df_filtered.groupby("Year").size().reset_index(name="Publicaciones")
    fig = px.bar(pubs_year, x="Year", y="Publicaciones", text="Publicaciones")
    st.plotly_chart(fig, use_container_width=True)

# TAB 2: Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil")
    quartile_counts = df_filtered["JCR_Quartile"].value_counts()
    fig_q = px.pie(values=quartile_counts.values, names=quartile_counts.index, hole=0.4)
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(quartile_counts.reset_index().rename(columns={"index":"Cuartil","JCR_Quartile":"Publicaciones"}))

# TAB 3: Open Access
with tabs[2]:
    st.subheader("Distribución Open Access")
    if "OpenAccess_flag" in df_filtered.columns:
        oa_counts = df_filtered["OpenAccess_flag"].map({True:"Open Access", False:"Closed Access"}).value_counts()
        fig_oa = px.pie(values=oa_counts.values, names=oa_counts.index, hole=0.4)
        st.plotly_chart(fig_oa, use_container_width=True)
        st.dataframe(oa_counts.reset_index().rename(columns={"index":"Tipo OA","OpenAccess_flag":"Publicaciones"}))

# TAB 4: Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    depto_counts = df_filtered["Departamento"].fillna("Sin asignar").value_counts()
    fig_d = px.bar(depto_counts, x=depto_counts.index, y=depto_counts.values)
    st.plotly_chart(fig_d, use_container_width=True)
    st.dataframe(depto_counts.reset_index().rename(columns={"index":"Departamento","Departamento":"Publicaciones"}))

# TAB 5: Revistas
with tabs[4]:
    st.subheader("Top revistas por publicaciones")
    if "Source title" in df_filtered.columns:
        top_revistas = df_filtered["Source title"].value_counts().head(20)
        fig_r = px.bar(top_revistas, x=top_revistas.values, y=top_revistas.index, orientation="h")
        st.plotly_chart(fig_r, use_container_width=True)
        st.dataframe(top_revistas.reset_index().rename(columns={"index":"Revista","Source title":"Publicaciones"}))

# TAB 6: Autores
with tabs[5]:
    st.subheader("Top autores")
    if "Authors" in df_filtered.columns:
        autores = df_filtered["Authors"].dropna().str.split(",").explode().str.strip().value_counts().head(20)
        fig_a = px.bar(autores, x=autores.values, y=autores.index, orientation="h")
        st.plotly_chart(fig_a, use_container_width=True)
        st.dataframe(autores.reset_index().rename(columns={"index":"Autor","Authors":"Publicaciones"}))

# TAB 7: Wordcloud
with tabs[6]:
    st.subheader("Nube de palabras de títulos")
    if "Title" in df_filtered.columns and df_filtered["Title"].dropna().shape[0] > 0:
        text = " ".join(df_filtered["Title"].dropna().astype(str).tolist())
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        fig, ax = plt.subplots(figsize=(10,5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
    else:
        st.info("⚠️ No hay títulos disponibles para generar la nube de palabras.")
