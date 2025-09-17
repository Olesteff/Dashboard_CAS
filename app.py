import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import unicodedata as ud
from typing import Dict

st.set_page_config(page_title="Dashboard CAS", layout="wide")

# ======================================
# Funciones auxiliares
# ======================================
def _first_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

CAND = {
    "year": ["Year", "Año", "PY"],
    "oa": ["Open Access", "OA"],
    "quartile": ["JCR_Quartile", "Quartile", "Q"],
    "sponsor": ["Has_Sponsor"],
    "clinical": ["ClinicalTrial_flag"],
    "title": ["Title", "Article Title", "Título"],
    "cites": ["Times Cited", "Cited by"],
}

def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"

    # %OA
    if "Open Access" in dff.columns and len(dff):
        kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%"
    else:
        kpis["% OA"] = "—"

    # Citas
    ccol = _first_col(dff, CAND["cites"])
    if ccol:
        kpis["Mediana citas"] = f"{pd.to_numeric(dff[ccol], errors='coerce').median():.0f}"
    else:
        kpis["Mediana citas"] = "—"

    # Sponsors
    scol = _first_col(dff, CAND["sponsor"])
    if scol:
        kpis["Con sponsor"] = f"{int(dff[scol].sum()):,}"
    else:
        kpis["Con sponsor"] = "0"

    # Ensayos clínicos
    ctrial = _first_col(dff, CAND["clinical"])
    if ctrial:
        kpis["Ensayos clínicos"] = f"{int(dff[ctrial].sum()):,}"
    else:
        kpis["Ensayos clínicos"] = "0"

    return kpis

def _fig_evolucion(dff):
    ycol = _first_col(dff, CAND["year"])
    if not ycol: return None
    ev = dff[ycol].value_counts().sort_index()
    return px.bar(x=ev.index, y=ev.values, labels={"x":"Año", "y":"Nº publicaciones"})

def _fig_oa(dff):
    if "Open Access" not in dff.columns: return None
    counts = dff["Open Access"].fillna("Desconocido").value_counts()
    return px.pie(names=counts.index, values=counts.values, hole=0.4)

def _fig_quartiles(dff):
    qcol = _first_col(dff, CAND["quartile"])
    if not qcol: return None
    qcounts = dff[qcol].fillna("Sin cuartil").value_counts()
    return px.pie(names=qcounts.index, values=qcounts.values, hole=0.4)

def _fig_quartiles_year(dff):
    qcol = _first_col(dff, CAND["quartile"])
    ycol = _first_col(dff, CAND["year"])
    if not qcol or not ycol: return None
    df_qy = dff.copy()
    df_qy[qcol] = df_qy[qcol].fillna("Sin cuartil")
    grp = df_qy.groupby([ycol, qcol]).size().reset_index(name="count")
    return px.bar(grp, x=ycol, y="count", color=qcol, barmode="stack", 
                  labels={ycol:"Año", "count":"Nº publicaciones", qcol:"Cuartil"})

def _wordcloud(dff):
    tcol = _first_col(dff, CAND["title"])
    if not tcol: return None
    text = " ".join(dff[tcol].dropna().astype(str))
    wc = WordCloud(width=800, height=400, background_color="white").generate(text)
    fig, ax = plt.subplots(figsize=(10,5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    return fig

# ======================================
# Sidebar: carga de datos
# ======================================
st.sidebar.header("Datos base")
base_file = st.sidebar.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])
if base_file is not None:
    df = pd.read_excel(base_file, sheet_name=0)
else:
    st.stop()

# ======================================
# Filtros
# ======================================
mask = pd.Series(True, index=df.index)

# Año
ycol = _first_col(df, CAND["year"])
if ycol:
    ys = df[ycol].dropna().astype(int)
    y_min, y_max = int(ys.min()), int(ys.max())
    y1, y2 = st.sidebar.slider("Año", y_min, y_max, (y_min, y_max))
    mask &= df[ycol].astype(float).between(y1, y2)

# Fuente
src_opts = [c for c in ["in_Scopus", "in_WoS", "in_PubMed"] if c in df.columns]
sel_src = st.sidebar.multiselect("Fuente", options=src_opts, default=src_opts)
if sel_src:
    mask &= df[sel_src].fillna(False).any(axis=1)

# Open Access
if "Open Access" in df.columns:
    oa_vals = ["OA", "No OA", "Desconocido"]
    sel_oa = st.sidebar.multiselect("Open Access", oa_vals, default=oa_vals)
    mask &= df["Open Access"].fillna("Desconocido").isin(sel_oa)

# Departamento
if "Departamento" in df.columns:
    dep_pool = df["Departamento"].dropna().unique().tolist()
    sel_dep = st.sidebar.multiselect("Departamento", sorted(dep_pool), default=[])
    if sel_dep:
        mask &= df["Departamento"].isin(sel_dep)

# Cuartiles
qcol = _first_col(df, CAND["quartile"])
if qcol:
    q_vals = ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
    sel_q = st.sidebar.multiselect("Cuartil JCR", q_vals, default=q_vals)
    mask &= df[qcol].fillna("Sin cuartil").isin(sel_q)

# Aplicar
dff = df[mask].copy()

# ======================================
# Tabs principales
# ======================================
tabs = st.tabs(["📊 Resumen", "📈 Evolución", "📗 OA", "🏅 Cuartiles", "☁️ Wordcloud"])

# KPIs
with tabs[0]:
    KP = _kpis_summary(dff)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"])
    k2.metric("% OA", KP["% OA"])
    k3.metric("Mediana citas", KP["Mediana citas"])
    k4.metric("Con sponsor", KP["Con sponsor"])
    k5.metric("Ensayos clínicos", KP["Ensayos clínicos"])

# Evolución
with tabs[1]:
    fig_ev = _fig_evolucion(dff)
    if fig_ev: st.plotly_chart(fig_ev, use_container_width=True, key="fig_ev")

# OA
with tabs[2]:
    fig_oa = _fig_oa(dff)
    if fig_oa: st.plotly_chart(fig_oa, use_container_width=True, key="fig_oa")

# Cuartiles
with tabs[3]:
    fig_q = _fig_quartiles(dff)
    fig_qy = _fig_quartiles_year(dff)
    if fig_q: st.plotly_chart(fig_q, use_container_width=True, key="fig_q")
    if fig_qy: st.plotly_chart(fig_qy, use_container_width=True, key="fig_qy")

# Wordcloud
with tabs[4]:
    fig_wc = _wordcloud(dff)
    if fig_wc: st.pyplot(fig_wc)

    