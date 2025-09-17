import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from unidecode import unidecode
from io import BytesIO
from wordcloud import WordCloud

st.set_page_config(page_title="Dashboard CAS–UDD", layout="wide")

# =========================
# Configuración inicial
# =========================
DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = 0

# -------------------------
# Funciones de utilidad
# -------------------------
def load_data(uploaded=None, sheet_name=DEFAULT_SHEET):
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name)
    return pd.DataFrame()

def normalize_oa(df, col_binary="Open Access", col_detail="Open Access"):
    # 1) Flag binario
    if col_binary in df.columns:
        df["OA_flag"] = df[col_binary].astype(str).str.lower().map({
            "true": True, "false": False
        }).fillna(False)
    else:
        df["OA_flag"] = False

    # 2) Categoría
    mapping = {
        "gold": "Gold",
        "hybrid": "Hybrid",
        "green": "Green",
        "bronze": "Bronze"
    }
    def simplify(val):
        if pd.isna(val): 
            return "Desconocido"
        val_low = str(val).lower()
        for k, v in mapping.items():
            if k in val_low:
                return v
        return "Desconocido"
    if col_detail in df.columns:
        df["OA_Category"] = df[col_detail].apply(simplify)
    else:
        df["OA_Category"] = "Desconocido"

    return df

def normalize_quartiles(df):
    def std_quartile(val):
        val = str(val).strip().upper()
        return val if val in ["Q1","Q2","Q3","Q4"] else "Sin cuartil"
    if "JCR_Quartile" in df.columns:
        df["Quartile_std"] = df["JCR_Quartile"].apply(std_quartile)
    elif "SJR_Quartile" in df.columns:
        df["Quartile_std"] = df["SJR_Quartile"].apply(std_quartile)
    else:
        df["Quartile_std"] = "Sin cuartil"
    return df

def deduplicate(df):
    # ID final: DOI > PMID > UT > título+fuente+año
    def build_id(row):
        for col in ["DOI", "PMID", "UT"]:
            if col in df.columns and pd.notna(row.get(col,"")):
                return str(row[col])
        parts = [
            unidecode(str(row.get("Title",""))).lower(),
            unidecode(str(row.get("Source title",""))).lower(),
            str(row.get("Year",""))
        ]
        return "NOID::" + "_".join(parts)
    df["ID_final"] = df.apply(build_id, axis=1)
    return df.drop_duplicates(subset=["ID_final"], keep="first")

def wordcloud_png(df, col="Title"):
    text = " ".join([str(t) for t in df[col].dropna()])
    wc = WordCloud(width=1200, height=600, background_color="black",
                   colormap="Set2").generate(text)
    buf = BytesIO()
    wc.to_image().save(buf, format="PNG")
    return buf

# =========================
# Carga de datos
# =========================
st.sidebar.header("📂 Datos base")
uploaded = st.sidebar.file_uploader("Sube un XLSX", type="xlsx")
df = load_data(uploaded)

if df.empty:
    st.warning("Sube un archivo XLSX para comenzar.")
    st.stop()

# Normalizaciones
df = normalize_oa(df)
df = normalize_quartiles(df)
df = deduplicate(df)

# =========================
# Filtros
# =========================
st.sidebar.header("Filtros")
min_year, max_year = int(df["Year"].min()), int(df["Year"].max())
year_range = st.sidebar.slider("Selecciona rango de años",
                               min_year, max_year,
                               (min_year, max_year))
oa_filter = st.sidebar.radio("Open Access", ["Todos","Open Access","Closed Access"])
quartile_opts = st.sidebar.multiselect("Cuartil JCR/SJR",
                                       options=["Q1","Q2","Q3","Q4","Sin cuartil"],
                                       default=["Q1","Q2","Q3","Q4","Sin cuartil"])
dept_opts = st.sidebar.multiselect("Departamento", options=df["Departamento"].dropna().unique())
title_search = st.sidebar.text_input("Buscar en título")

# Aplicar filtros
dff = df.copy()
dff = dff[(dff["Year"] >= year_range[0]) & (dff["Year"] <= year_range[1])]
if oa_filter == "Open Access":
    dff = dff[dff["OA_flag"] == True]
elif oa_filter == "Closed Access":
    dff = dff[dff["OA_flag"] == False]
dff = dff[dff["Quartile_std"].isin(quartile_opts)]
if dept_opts:
    dff = dff[dff["Departamento"].isin(dept_opts)]
if title_search:
    dff = dff[dff["Title"].str.contains(title_search, case=False, na=False)]

# =========================
# Dashboard principal
# =========================
st.title("📊 Dashboard de Producción Científica – CAS–UDD")

total_pubs = len(dff)
pct_oa = dff["OA_flag"].mean()*100 if total_pubs>0 else 0
st.subheader("📌 Resumen general")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total publicaciones", total_pubs)
c2.metric("% Open Access", f"{pct_oa:.1f}%")
c3.metric("Ensayos clínicos detectados", int(dff.get("ClinicalTrial_flag",pd.Series()).sum()))
c4.metric("Publicaciones con sponsor", int(dff.get("Has_Sponsor",pd.Series()).sum()))

# =========================
# Tabs
# =========================
tabs = st.tabs(["📈 Publicaciones","📊 Cuartiles","🔓 Open Access",
                "🏥 Departamentos","📚 Revistas","👩‍⚕️ Autores","☁️ Wordcloud"])

# --- Publicaciones
with tabs[0]:
    st.subheader("Publicaciones por año")
    pubs = dff.groupby("Year").size().reset_index(name="Nº Publicaciones")
    fig = px.bar(pubs, x="Year", y="Nº Publicaciones")
    st.plotly_chart(fig, use_container_width=True)

# --- Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil")
    qcounts = dff["Quartile_std"].value_counts().reset_index()
    qcounts.columns = ["Cuartil","Publicaciones"]
    fig_q = px.pie(qcounts, names="Cuartil", values="Publicaciones",
                   hole=0.4,
                   color="Cuartil",
                   color_discrete_map={
                       "Q1":"green","Q2":"yellow","Q3":"orange",
                       "Q4":"darkred","Sin cuartil":"lightgrey"
                   })
    st.plotly_chart(fig_q, use_container_width=True)
    st.dataframe(qcounts)

# --- Open Access
with tabs[2]:
    st.subheader("Distribución Open Access")
    oac = dff["OA_Category"].value_counts().reset_index()
    oac.columns = ["OA_Category","Publicaciones"]
    fig_oa = px.pie(oac, names="OA_Category", values="Publicaciones", hole=0.4)
    st.plotly_chart(fig_oa, use_container_width=True)
    st.dataframe(oac)

# --- Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    deptc = dff["Departamento"].value_counts().reset_index()
    deptc.columns = ["Departamento","Publicaciones"]
    fig_d = px.bar(deptc, x="Departamento", y="Publicaciones")
    st.plotly_chart(fig_d, use_container_width=True)
    st.dataframe(deptc)

# --- Revistas
with tabs[4]:
    st.subheader("Top Revistas")
    if "Source title" in dff.columns:
        revc = dff["Source title"].value_counts().head(20).reset_index()
        revc.columns = ["Revista","Publicaciones"]
        st.dataframe(revc)

# --- Autores
with tabs[5]:
    st.subheader("Top Autores")
    if "Authors" in dff.columns:
        authc = dff["Authors"].str.split(";").explode().str.strip().value_counts().head(20).reset_index()
        authc.columns = ["Autor","Publicaciones"]
        st.dataframe(authc)

# --- Wordcloud
with tabs[6]:
    st.subheader("Nube de palabras (títulos)")
    buf = wordcloud_png(dff,"Title")
    st.image(buf)