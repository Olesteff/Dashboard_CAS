# /app/app.py
# Dashboard Cienciométrico CAS-UDD

from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# -----------------------------
# Configuración general
# -----------------------------
st.set_page_config(
    page_title="Dashboard Cienciométrico",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"

CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "_Year", "Year_clean"],
    "doi": ["DOI", "Doi"],
    "journal": ["Journal_norm", "Source title", "Journal"],
    "dept": ["Departamento"],
    "authors": ["Author full names", "Author Full Names", "Authors"],
    "cited": ["Cited by", "Times Cited"],
    "oa_flags": ["OpenAccess_flag", "OA_Scopus", "OA_WoS", "OA_PubMed", "OA"],
    "sponsor": ["Has_Sponsor"],
    "trial": ["ClinicalTrial_flag"]
}

# -----------------------------
# Utilidades
# -----------------------------
def _first_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for c in names:
        if c in df.columns:
            return c
    return None

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.getvalue()

# -----------------------------
# Carga
# -----------------------------
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, dtype=str)
    raise FileNotFoundError("No se encontró dataset base")

df = load_dataframe(None)
df.columns = df.columns.astype(str).str.strip()

# Normalizar año
ycol = _first_col(df, CAND["year"])
if ycol:
    df["_Year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")

# -----------------------------
# Filtros (sidebar)
# -----------------------------
mask = pd.Series(True, index=df.index)

with st.sidebar:
    st.subheader("Filtros")

    if "_Year" in df.columns and df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int)
        y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Selecciona rango de años", y_min, y_max, (y_min, y_max))
        mask &= df["_Year"].between(y1, y2)

    if "Open Access" in df.columns:
        oa_vals = df["Open Access"].dropna().unique().tolist()
        sel_oa = st.multiselect("Open Access", oa_vals, default=oa_vals)
        mask &= df["Open Access"].isin(sel_oa)

    if "Departamento" in df.columns and df["Departamento"].notna().any():
        dep_pool = sorted(df["Departamento"].dropna().unique().tolist())
        sel_dep = st.multiselect("Departamento", dep_pool, default=[])
        if sel_dep:
            mask &= df["Departamento"].isin(sel_dep)

dff = df[mask].copy()

# -----------------------------
# KPIs
# -----------------------------
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"

    # DOI
    if "DOI_norm" in dff.columns and len(dff):
        kpis["% con DOI"] = f"{(dff['DOI_norm'].notna().mean() * 100):.1f}%"
    else:
        kpis["% con DOI"] = "—"

    # Open Access
    if "Open Access" in dff.columns and len(dff):
        kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%"
    else:
        kpis["% OA"] = "—"

    # Citas
    if "Times Cited" in dff.columns and len(dff):
        kpis["Mediana citas"] = f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}"
    else:
        kpis["Mediana citas"] = "—"

    # Sponsors (asegurar booleano)
    if "Has_Sponsor" in dff.columns:
        sponsor_col = dff["Has_Sponsor"].astype(str).str.lower().isin(["true", "1", "yes", "si", "sí"])
        kpis["Con sponsor"] = f"{int(sponsor_col.sum()):,}"
    else:
        kpis["Con sponsor"] = "0"

    # Ensayos clínicos (asegurar booleano)
    if "ClinicalTrial_flag" in dff.columns:
        trial_col = dff["ClinicalTrial_flag"].astype(str).str.lower().isin(["true", "1", "yes", "si", "sí"])
        kpis["Ensayos clínicos"] = f"{int(trial_col.sum()):,}"
    else:
        kpis["Ensayos clínicos"] = "0"

    return kpis


# Mostrar métricas
k1, k2, k3, k4, k5 = st.columns(5)
KP = _kpis_summary(dff)
k1.metric("Nº publicaciones", KP["Nº publicaciones"])
k2.metric("% OA", KP["% OA"])
k3.metric("Mediana citas", KP["Mediana citas"])
k4.metric("Con sponsor", KP["Con sponsor"])
k5.metric("Ensayos clínicos", KP["Ensayos clínicos"])


# -----------------------------
# Figuras
# -----------------------------
def fig_year_counts(dff):
    g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
    return px.bar(x=g.index, y=g.values, labels={"x": "Año", "y": "Nº publicaciones"}, title="Publicaciones por año")

def fig_oa_pie(dff):
    oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
    fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="Proporción OA / No OA")
    fig.update_traces(textinfo="percent+label")
    return fig

def fig_dept_bar(dff):
    g = dff["Departamento"].fillna("Otro").value_counts().head(20)
    return px.bar(x=g.values, y=g.index, orientation="h", labels={"x":"Nº publicaciones","y":"Departamento"}, title="Top 20 Departamentos")

def fig_wordcloud(dff):
    text = " ".join(dff[_first_col(dff, CAND["title"])].dropna().astype(str).tolist())
    wc = WordCloud(width=1000, height=500, background_color="white", colormap="viridis").generate(text)
    fig, ax = plt.subplots(figsize=(10,5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    st.pyplot(fig)

# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📚 Revistas", "🧑‍🔬 Autores", "🟢 OA", "⭐ Citas", "🏥 Departamentos", "☁️ WordCloud"])

# RESUMEN
with tabs[0]:
    KP = _kpis_summary(dff)
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Nº publicaciones", KP["Nº publicaciones"])
    c2.metric("% OA", KP["% OA"])
    c3.metric("Mediana citas", KP["Mediana citas"])
    c4.metric("Con sponsor", KP["Con sponsor"])
    c5.metric("Ensayos clínicos", KP["Ensayos clínicos"])
    st.plotly_chart(fig_year_counts(dff), use_container_width=True, key="pubs_anio")
    st.plotly_chart(fig_oa_pie(dff), use_container_width=True, key="oa_resumen")

# DATOS
with tabs[1]:
    st.dataframe(dff.head(1000), use_container_width=True, height=420)
    st.download_button("⬇️ CSV — Resultados", dff.to_csv(index=False).encode("utf-8"), "resultados_filtrados.csv", "text/csv")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ XLSX — Resultados", xlsx_bytes, "resultados_filtrados.xlsx")

# REVISTAS
with tabs[2]:
    jr_col = _first_col(dff, CAND["journal"])
    if jr_col:
        top_jr = dff[jr_col].fillna("—").value_counts().head(20).rename_axis("Journal").reset_index(name="N")
        fig = px.bar(top_jr.sort_values("N"), x="N", y="Journal", orientation="h", title="Top 20 revistas")
        st.plotly_chart(fig, use_container_width=True, key="top_revistas")
        st.dataframe(top_jr, use_container_width=True)

# AUTORES
with tabs[3]:
    acol = _first_col(dff, CAND["authors"])
    if acol:
        s = dff[acol].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        top_auth = pd.Series(authors).value_counts().head(20).rename_axis("Autor").reset_index(name="N")
        fig = px.bar(top_auth.sort_values("N"), x="N", y="Autor", orientation="h", title="Top 20 autores")
        st.plotly_chart(fig, use_container_width=True, key="top_autores")
        st.dataframe(top_auth, use_container_width=True)

# OA
with tabs[4]:
    st.plotly_chart(fig_oa_pie(dff), use_container_width=True, key="oa_tab")
    st.dataframe(dff[["Title", "_Year", "Open Access"]].dropna(how="all"), use_container_width=True, height=420)

# CITAS
with tabs[5]:
    if _first_col(dff, CAND["cited"]):
        tmp = dff.copy()
        tmp["Times Cited"] = pd.to_numeric(tmp[_first_col(dff, CAND["cited"])], errors="coerce")
        top_cited = tmp.sort_values("Times Cited", ascending=False).head(20)
        st.dataframe(top_cited[["Title","Author Full Names","Times Cited","_Year"]], use_container_width=True, height=500)

# DEPARTAMENTOS
with tabs[6]:
    if "Departamento" in dff.columns:
        st.plotly_chart(fig_dept_bar(dff), use_container_width=True, key="dept_bar")
        st.dataframe(dff["Departamento"].value_counts().head(20), use_container_width=True)

# WORDCLOUD
with tabs[7]:
    st.subheader("Nube de palabras — Títulos")
    fig_wordcloud(dff)

    # --- Agregar al diccionario CAND ---
CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "_Year", "Year_clean"],
    "doi": ["DOI", "Doi"],
    "link": ["Link", "URL", "Full Text URL"],
    "journal": ["Journal_norm", "Source title", "Source Title", "Publication Name", "Journal"],
    "dept": ["Departamento", "Dept_CAS_list", "Dept_FMUDD_list", "Department"],
    "authors": ["Author full names", "Author Full Names", "Authors"],
    "cited": ["Cited by", "Times Cited", "TimesCited"],
    "pmid": ["PubMed ID", "PMID"],
    "wos": ["Web of Science Record", "Unique WOS ID", "UT (Unique WOS ID)"],
    "eid": ["EID", "Scopus EID"],
    "oa_flags": ["OpenAccess_flag", "OA_Scopus", "OA_WoS", "OA_PubMed", "OA"],
    "sponsor": ["Has_Sponsor", "Funding_info"]  # 👈 nuevo agregado
}

# --- Sidebar: agregar filtro por cuartil ---
with st.sidebar:
    if _first_col(df, CAND["quartile"]):
        q_vals = df[_first_col(df, CAND["quartile"])].fillna("Sin cuartil").unique().tolist()
        sel_q = st.multiselect("Cuartil JCR", sorted(q_vals), default=q_vals)
        mask &= df[_first_col(df, CAND["quartile"])].fillna("Sin cuartil").isin(sel_q)

# --- Figura cuartiles ---
def fig_quartile_pie(dff):
    qcol = _first_col(dff, CAND["quartile"])
    if not qcol:
        return None
    counts = dff[qcol].fillna("Sin cuartil").value_counts()
    fig = px.pie(names=counts.index, values=counts.values, title="Distribución por cuartiles JCR")
    fig.update_traces(textinfo="percent+label")
    return fig

# --- Agregar pestaña nueva ---
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📚 Revistas", "🧑‍🔬 Autores", 
                "🟢 OA", "⭐ Citas", "🏥 Departamentos", "☁️ WordCloud", "📊 Cuartiles JCR"])

# --- Contenido de la pestaña cuartiles ---
with tabs[8]:
    st.subheader("Distribución por cuartiles JCR")
    qfig = fig_quartile_pie(dff)
    if qfig:
        st.plotly_chart(qfig, use_container_width=True, key="quartiles_pie")
        st.dataframe(
            dff[_first_col(dff, CAND["quartile"])].fillna("Sin cuartil").value_counts(),
            use_container_width=True
        )
    else:
        st.info("No se encontró columna de cuartiles JCR en el dataset.")