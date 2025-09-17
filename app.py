# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt

st.set_page_config(page_title="Dashboard CAS-UDD", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_excel("dataset_unificado_enriquecido_jcr_PLUS-10.xlsx", sheet_name="Consolidado_enriq")
    
    # Normalizar año
    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce").fillna(0).astype(int)
    
    # Normalizar OA
    if "OpenAccess_flag" in df.columns:
        df["OpenAccess_flag"] = df["OpenAccess_flag"].astype(bool)
    else:
        df["OpenAccess_flag"] = False

    # Normalizar cuartiles
    if "Quartile_std" in df.columns:
        df["Quartile_std"] = df["Quartile_std"].astype(str).str.upper().replace({
            "1": "Q1", "2": "Q2", "3": "Q3", "4": "Q4", "SIN CUARTIL": "Sin cuartil"
        })
    else:
        df["Quartile_std"] = "Sin cuartil"

    # Normalizar depto
    if "Departamento" not in df.columns:
        df["Departamento"] = "Sin asignar"
    
    # Flags
    for col in ["Has_Sponsor", "ClinicalTrial_flag"]:
        if col not in df.columns:
            df[col] = False
    
    return df

df = load_data()

# -------------------- Sidebar filtros --------------------
st.sidebar.header("Filtros")

years = sorted(df["Year"].dropna().unique())
year_min, year_max = st.sidebar.select_slider("Rango de años", options=years, value=(min(years), max(years)))
df = df[(df["Year"] >= year_min) & (df["Year"] <= year_max)]

oa_filter = st.sidebar.multiselect("Open Access", ["Sí", "No"])
if oa_filter:
    if "Sí" in oa_filter:
        df = df[df["OpenAccess_flag"] == True]
    if "No" in oa_filter:
        df = df[df["OpenAccess_flag"] == False]

quartiles = st.sidebar.multiselect("Cuartiles", df["Quartile_std"].unique())
if quartiles:
    df = df[df["Quartile_std"].isin(quartiles)]

departamentos = st.sidebar.multiselect("Departamentos", df["Departamento"].unique())
if departamentos:
    df = df[df["Departamento"].isin(departamentos)]

search_title = st.sidebar.text_input("Buscar en títulos")
if search_title:
    df = df[df["Title"].str.contains(search_title, case=False, na=False)]

# -------------------- KPIs --------------------
st.title("📊 Dashboard Producción Científica CAS-UDD")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total publicaciones", len(df))
col2.metric("Open Access (%)", f"{df['OpenAccess_flag'].mean()*100:.1f}%")
col3.metric("Ensayos clínicos", int(df["ClinicalTrial_flag"].sum()))
col4.metric("Con sponsor", int(df["Has_Sponsor"].sum()))

# -------------------- Tabs --------------------
tabs = st.tabs([
    "📈 Publicaciones por año",
    "🧩 Distribución por cuartiles",
    "🔓 Open Access",
    "🏥 Departamentos",
    "📚 Revistas",
    "👩‍🔬 Autores",
    "☁️ Nube de palabras"
])

# 1. Publicaciones por año
with tabs[0]:
    pubs_year = df.groupby("Year").size().reset_index(name="Publicaciones")
    fig = px.bar(pubs_year, x="Year", y="Publicaciones", title="Publicaciones por año")
    st.plotly_chart(fig, use_container_width=True)

# 2. Cuartiles
with tabs[1]:
    quartile_counts = df["Quartile_std"].value_counts()
    fig = px.pie(names=quartile_counts.index, values=quartile_counts.values, hole=0.4,
                 title="Distribución por cuartiles")
    st.plotly_chart(fig, use_container_width=True)

# 3. Open Access
with tabs[2]:
    oa_counts = df["OpenAccess_flag"].map({True:"OA", False:"No OA"}).value_counts()
    fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="Open Access")
    st.plotly_chart(fig, use_container_width=True)

# 4. Departamentos
with tabs[3]:
    dept_counts = df["Departamento"].value_counts().nlargest(15)
    fig = px.bar(x=dept_counts.index, y=dept_counts.values, title="Top departamentos")
    st.plotly_chart(fig, use_container_width=True)

# 5. Revistas
with tabs[4]:
    if "Source title" in df.columns:
        journal_counts = df["Source title"].value_counts().nlargest(15)
        fig = px.bar(x=journal_counts.index, y=journal_counts.values, title="Top revistas")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No se encontró columna 'Source title'")

# 6. Autores
with tabs[5]:
    if "Authors" in df.columns:
        authors_split = df["Authors"].dropna().str.split(", ")
        authors_flat = [a for sublist in authors_split for a in sublist]
        authors_series = pd.Series(authors_flat).value_counts().nlargest(15)
        fig = px.bar(x=authors_series.index, y=authors_series.values, title="Top autores")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No se encontró columna 'Authors'")

# 7. Wordcloud
with tabs[6]:
    if "Title" in df.columns:
        text = " ".join(df["Title"].dropna())
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        fig, ax = plt.subplots(figsize=(10,5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
    else:
        st.warning("No se encontró columna 'Title'")
        