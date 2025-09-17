# /app/app.py
# Dashboard Cienciométrico con Tabs + Merge/Dedup + PDF

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
DEFAULT_SHEET = "Sheet1"

DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)

CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "_Year"],
    "doi": ["DOI", "Doi"],
    "link": ["Link", "URL", "Full Text URL"],
    "journal": ["Journal_norm", "Source title", "Publication Name"],
    "dept": ["Departamento", "Dept_CAS_list", "Dept_FMUDD_list"],
    "authors": ["Author full names", "Author Full Names", "Authors"],
    "cited": ["Cited by", "Times Cited"],
    "pmid": ["PubMed ID", "PMID"],
    "wos": ["Web of Science Record", "Unique WOS ID"],
    "eid": ["EID", "Scopus EID"],
    "oa_flags": ["OpenAccess_flag", "OA_Scopus", "OA_WoS", "OA_PubMed", "OA"],
    "quartile": ["JCR_Quartile", "Quartile", "JCR Quartile"]
}

# -----------------------------
# Utilidades
# -----------------------------
def _first_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for c in names:
        if c in df.columns:
            return c
    return None

def _extract_doi(val: object) -> Optional[str]:
    if pd.isna(val): return None
    m = DOI_REGEX.search(str(val))
    return m.group(0).lower() if m else None

def _norm_text(s: object) -> str:
    if pd.isna(s): return ""
    return re.sub(r"\s+", " ", str(s).strip())

def _title_key(s: object) -> str:
    if pd.isna(s): return ""
    t = re.sub(r"[^A-Za-z0-9 ]", " ", str(s).lower())
    return re.sub(r"\s+", " ", t).strip()

def _bool_from_str_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(False, index=pd.RangeIndex(0))
    x = s.astype(str).str.lower().str.strip()
    true_vals = {"1", "true", "t", "yes", "y", "si", "sí"}
    return x.isin(true_vals)

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf.getvalue()

# -----------------------------
# Carga
# -----------------------------
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded, sheet_name=DEFAULT_SHEET) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name, dtype=str)
    st.stop()

def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    ycol = _first_col(df, CAND["year"])
    if ycol: df["_Year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")
    qcol = _first_col(df, CAND["quartile"])
    if qcol: df["JCR_Quartile"] = df[qcol]
    oa_cols = [c for c in CAND["oa_flags"] if c in df.columns]
    if oa_cols: df["Open Access"] = df[oa_cols].apply(lambda r: any(_bool_from_str_series(r)), axis=1)
    else: df["Open Access"] = False
    return df

# -----------------------------
# KPIs
# -----------------------------
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"
    kpis["% con DOI"] = f"{(dff['DOI_norm'].notna().mean()*100):.1f}%" if "DOI_norm" in dff else "—"
    kpis["% OA"] = f"{(dff['Open Access'].mean()*100):.1f}%" if "Open Access" in dff else "—"
    kpis["Mediana citas"] = f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}" if "Times Cited" in dff else "—"
    kpis["Con sponsor"] = f"{int(dff.get('Has_Sponsor', pd.Series([0]*len(dff))).sum()):,}"
    kpis["Ensayos clínicos"] = f"{int(dff.get('ClinicalTrial_flag', pd.Series([0]*len(dff))).sum()):,}"
    return kpis

# -----------------------------
# Figuras
# -----------------------------
def _fig_year_counts(dff): 
    g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
    return px.bar(x=g.index, y=g.values, labels={"x":"Año","y":"Nº publicaciones"}, title="Publicaciones por año")

def _fig_oa_pie(dff):
    counts = dff["Open Access"].map({True:"OA",False:"No OA"}).value_counts()
    return px.pie(names=counts.index, values=counts.values, hole=0.4, title="Proporción OA / No OA")

def _fig_quartiles_year(dff):
    if "JCR_Quartile" not in dff: return None
    tmp = dff.dropna(subset=["_Year","JCR_Quartile"])
    g = tmp.groupby(["_Year","JCR_Quartile"]).size().reset_index(name="N")
    return px.bar(g, x="_Year", y="N", color="JCR_Quartile", barmode="group", title="Publicaciones por año y cuartil")

def _fig_wordcloud(dff):
    txt = " ".join(dff["Title"].dropna().astype(str))
    if not txt: return None
    wc = WordCloud(width=800, height=400, background_color="white").generate(txt)
    fig, ax = plt.subplots(figsize=(10,5)); ax.imshow(wc, interpolation="bilinear"); ax.axis("off")
    return fig

# -----------------------------
# Carga inicial
# -----------------------------
base_df = load_dataframe(None)
df = normalize_dataset(base_df)

# -----------------------------
# Sidebar filtros
# -----------------------------
mask = pd.Series(True, index=df.index)
with st.sidebar:
    st.subheader("Filtros")
    if "_Year" in df: 
        ys = df["_Year"].dropna().astype(int)
        y1,y2 = st.slider("Años",int(ys.min()),int(ys.max()),(int(ys.min()),int(ys.max())))
        mask &= df["_Year"].between(y1,y2)
    if "Open Access" in df:
        sel = st.multiselect("Open Access",["OA","No OA"],default=["OA","No OA"])
        mask &= df["Open Access"].map({True:"OA",False:"No OA"}).isin(sel)
    if "JCR_Quartile" in df:
        opts = df["JCR_Quartile"].dropna().unique().tolist()
        sel = st.multiselect("Cuartiles",opts,default=opts)
        mask &= df["JCR_Quartile"].isin(sel)

dff = df[mask].copy()

# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs(["📌 Resumen","📊 Cuartiles","📄 Datos","🧑‍🔬 Autores","🟢 OA","☁️ Wordcloud"])

# RESUMEN
with tabs[0]:
    KP = _kpis_summary(dff)
    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Nº publicaciones",KP["Nº publicaciones"])
    k2.metric("% DOI",KP["% con DOI"])
    k3.metric("% OA",KP["% OA"])
    k4.metric("Sponsors",KP["Con sponsor"])
    k5.metric("Ensayos clínicos",KP["Ensayos clínicos"])
    st.plotly_chart(_fig_year_counts(dff), use_container_width=True)

# CUARTILES
with tabs[1]:
    st.subheader("Distribución por cuartiles")
    if "JCR_Quartile" in dff:
        counts = dff["JCR_Quartile"].fillna("Sin cuartil").value_counts()
        fig_q = px.pie(names=counts.index, values=counts.values, hole=0.4,
                       color=counts.index,
                       color_discrete_map={"Q1":"green","Q2":"yellow","Q3":"orange","Q4":"darkred","Sin cuartil":"lightgrey"})
        st.plotly_chart(fig_q, use_container_width=True, key="quartiles_pie")
        fig_qy = _fig_quartiles_year(dff)
        if fig_qy: st.plotly_chart(fig_qy, use_container_width=True, key="quartiles_year")

# DATOS
with tabs[2]:
    st.dataframe(dff.head(500), use_container_width=True)

# AUTORES
with tabs[3]:
    if "Author Full Names" in dff:
        s = dff["Author Full Names"].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        top = pd.Series(authors).value_counts().head(20).reset_index()
        top.columns=["Autor","N"]
        st.plotly_chart(px.bar(top,x="N",y="Autor",orientation="h"), use_container_width=True)
        st.dataframe(top)

# OA
with tabs[4]:
    st.plotly_chart(_fig_oa_pie(dff), use_container_width=True)

# WORDCLOUD
with tabs[5]:
    fig_wc = _fig_wordcloud(dff)
    if fig_wc: st.pyplot(fig_wc)