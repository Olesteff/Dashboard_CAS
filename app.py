import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# =========================
# CONFIGURACIÓN INICIAL
# =========================
st.set_page_config(
    page_title="Dashboard de Producción Científica",
    layout="wide",
    page_icon="📊"
)

st.title("📊 Dashboard de Producción Científica Clínica Alemana - Universidad del Desarrollo")

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = "Consolidado_enriq"

# =========================
# CARGA DE DATOS
# =========================
@st.cache_data
def load_data(uploaded=None, sheet_name=DEFAULT_SHEET):
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name)
    elif Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name)
    else:
        st.error("⚠️ No se encontró ningún archivo válido.")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.stop()

# Normalizar columnas clave
df.columns = df.columns.astype(str).str.strip()
if "Year" in df.columns:
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

# =========================
# SIDEBAR - FILTROS
# =========================
st.sidebar.header("Filtros")

# Año
min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Selecciona rango de años", min_year, max_year, (min_year, max_year))
df = df[(df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])]

# Open Access (usando OpenAccess_flag)
oa_choice = st.sidebar.radio("Open Access", ["Todos", "Open Access", "Closed Access"])
if oa_choice == "Open Access":
    df = df[df["OpenAccess_flag"] == True]
elif oa_choice == "Closed Access":
    df = df[df["OpenAccess_flag"] == False]

# Cuartiles
if "Quartile" in df.columns:
    quartiles = df["Quartile"].dropna().unique().tolist()
    q_selected = st.sidebar.multiselect("Cuartil JCR/SJR", quartiles, default=quartiles)
    df = df[df["Quartile"].isin(q_selected)]

# Departamentos
if "Departamento" in df.columns:
    depts = df["Departamento"].dropna().unique().tolist()
    d_selected = st.sidebar.multiselect("Departamento", depts, default=depts)
    df = df[df["Departamento"].isin(d_selected)]

# Buscar en título
search_term = st.sidebar.text_input("Buscar en título")
if search_term:
    df = df[df["Title"].str.contains(search_term, case=False, na=False)]

# =========================
# KPIs PRINCIPALES
# =========================
total_pubs = len(df)
pct_oa = (df["OpenAccess_flag"].sum() / len(df) * 100) if len(df) > 0 else 0
total_jif = df["JIF"].sum(min_count=1) if "JIF" in df.columns else 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("📑 Total publicaciones", total_pubs)
kpi2.metric("🔓 % Open Access", f"{pct_oa:.1f}%")
kpi3.metric("⭐ Suma total JIF", f"{total_jif:.1f}")

# =========================
# PESTAÑAS
# =========================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
                "🏥 Departamentos", "📚 Revistas", "👩‍🔬 Autores", "☁️ Wordcloud"])

# -------------------------
# Publicaciones por año
# -------------------------
with tabs[0]:
    st.subheader("📊 Publicaciones y JIF por año")

    pubs = df.groupby("Year").size().reset_index(name="Publicaciones")
    jif_sum = df.groupby("Year")["JIF"].sum(min_count=1).reset_index(name="Suma JIF")

    fig_pubs = px.bar(pubs, x="Year", y="Publicaciones", text="Publicaciones",
                      title="Publicaciones por año")
    fig_jif = px.line(jif_sum, x="Year", y="Suma JIF", markers=True,
                      title="Suma de JIF por año")

    st.plotly_chart(fig_pubs, use_container_width=True)
    st.plotly_chart(fig_jif, use_container_width=True)

# -------------------------
# Cuartiles
# -------------------------
with tabs[1]:
    st.subheader("Distribución por cuartil")
    if "Quartile" in df.columns:
        quartile_counts = df["Quartile"].fillna("Sin cuartil").value_counts()
        fig_q = px.pie(names=quartile_counts.index, values=quartile_counts.values,
                       hole=0.4, title="Distribución por cuartil")
        st.plotly_chart(fig_q, use_container_width=True)

# -------------------------
# Open Access
# -------------------------
with tabs[2]:
    st.subheader("Distribución Open Access")
    if "OpenAccess_flag" in df.columns:
        oa_counts = df["OpenAccess_flag"].map({True: "Open Access", False: "Closed Access"}).value_counts()
        fig_oa = px.pie(names=oa_counts.index, values=oa_counts.values,
                        hole=0.4, title="Distribución Open Access")
        st.plotly_chart(fig_oa, use_container_width=True)

# -------------------------
# Departamentos
# -------------------------
with tabs[3]:
    st.subheader("Distribución por departamento")
    if "Departamento" in df.columns:
        dept_counts = df["Departamento"].value_counts()
        fig_dept = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values,
                          title="Publicaciones por departamento")
        st.plotly_chart(fig_dept, use_container_width=True)

# -------------------------
# Revistas
# -------------------------
with tabs[4]:
    st.subheader("Revistas con más publicaciones")
    if "Source title" in df.columns:
        rev_counts = df["Source title"].value_counts().head(20)
        fig_rev = px.bar(rev_counts, x=rev_counts.index, y=rev_counts.values,
                         title="Top 20 revistas", text=rev_counts.values)
        st.plotly_chart(fig_rev, use_container_width=True)

# -------------------------
# Autores
# -------------------------
with tabs[5]:
    st.subheader("Autores con más publicaciones")
    if "Authors" in df.columns:
        auth_counts = df["Authors"].value_counts().head(20)
        fig_auth = px.bar(auth_counts, x=auth_counts.index, y=auth_counts.values,
                          title="Top 20 autores", text=auth_counts.values)
        st.plotly_chart(fig_auth, use_container_width=True)

# -------------------------
# Wordcloud
# -------------------------
with tabs[6]:
    st.subheader("Nube de palabras en títulos")
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt

        text = " ".join(df["Title"].dropna().astype(str))
        wc = WordCloud(width=1600, height=800, background_color="white").generate(text)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
    except Exception as e:
        st.error(f"⚠️ No se pudo generar Wordcloud: {e}")