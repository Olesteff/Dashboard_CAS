# /app/app.py
# Dashboard Cienciométrico con Tabs + Merge/Dedup + PDF + Wordcloud

from __future__ import annotations
import re, os
from pathlib import Path
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
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

# -----------------------------
# Utilidades
# -----------------------------
def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    try:
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

def _plotly_png(fig) -> Optional[bytes]:
    try:
        buf = BytesIO()
        fig.write_image(buf, format="png", scale=3)  # requiere kaleido
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

# -----------------------------
# Sidebar – Carga y Merge
# -----------------------------
st.sidebar.header("📂 Datos base")

uploaded_file = st.sidebar.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])

if uploaded_file is not None:
    df_base = pd.read_excel(uploaded_file, sheet_name=0, dtype=str)
    base_name = uploaded_file.name
else:
    if os.path.exists(DEFAULT_XLSX):
        df_base = pd.read_excel(DEFAULT_XLSX, sheet_name=0, dtype=str)
        base_name = DEFAULT_XLSX
    else:
        st.error("⚠️ No se encontró dataset base. Sube un archivo XLSX.")
        st.stop()

st.sidebar.markdown(f"**Por defecto:** `{base_name}` (se leerá la 1ª hoja)")

# Merge
st.sidebar.subheader("🔄 Actualizar dataset (merge)")
new_files = st.sidebar.file_uploader("Nuevos CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=True)
btn_preview = st.sidebar.button("👀 Previsualizar unión")
btn_apply = st.sidebar.button("✅ Aplicar actualización")
overwrite = st.sidebar.checkbox("Sobrescribir archivo base al aplicar (si existe)")

df_all = df_base.copy()

if new_files:
    dfs_new = []
    for nf in new_files:
        if nf.name.endswith(".csv"):
            dfs_new.append(pd.read_csv(nf, dtype=str))
        else:
            dfs_new.append(pd.read_excel(nf, dtype=str))
    df_new = pd.concat(dfs_new, ignore_index=True)

    if btn_preview:
        st.info(f"Vista previa: {df_new.shape[0]} filas nuevas")
        st.dataframe(df_new.head(50), use_container_width=True)

    if btn_apply:
        before = df_all.shape[0]
        df_all = pd.concat([df_all, df_new], ignore_index=True).drop_duplicates()
        after = df_all.shape[0]
        st.success(f"✔️ Merge aplicado: {after-before} filas nuevas (total {after})")

        if overwrite:
            df_all.to_excel(DEFAULT_XLSX, index=False)
            st.sidebar.info(f"💾 Archivo sobrescrito: {DEFAULT_XLSX}")

# -----------------------------
# Filtros
# -----------------------------
mask = pd.Series(True, index=df_all.index)

if "_Year" in df_all.columns and df_all["_Year"].notna().any():
    ys = pd.to_numeric(df_all["_Year"], errors="coerce").dropna()
    if not ys.empty:
        y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.sidebar.slider("Selecciona rango de años", y_min, y_max, (y_min, y_max))
        mask &= pd.to_numeric(df_all["_Year"], errors="coerce").between(y1, y2)

if "Open Access" in df_all.columns:
    oa_vals = sorted(df_all["Open Access"].dropna().unique())
    sel_oa = st.sidebar.multiselect("Open Access", oa_vals, default=oa_vals)
    if sel_oa:
        mask &= df_all["Open Access"].isin(sel_oa)

if "Departamento" in df_all.columns:
    dep_vals = sorted(df_all["Departamento"].dropna().unique())
    sel_dep = st.sidebar.multiselect("Departamento", dep_vals, default=[])
    if sel_dep:
        mask &= df_all["Departamento"].isin(sel_dep)

dff = df_all[mask].copy()

# -----------------------------
# KPIs
# -----------------------------
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"
    kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean()*100):.1f}%" if "Open Access" in dff else "—"
    kpis["Mediana citas"] = (
        f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}"
        if "Times Cited" in dff else "—"
    )
    kpis["Con sponsor"] = f"{int(dff['Has_Sponsor'].sum()):,}" if "Has_Sponsor" in dff else "0"
    kpis["Ensayos clínicos"] = f"{int(dff['ClinicalTrial_flag'].sum()):,}" if "ClinicalTrial_flag" in dff else "0"
    return kpis

# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📚 Revistas", "🧑‍🔬 Autores", "🟢 OA", "⭐ Citas", "🏥 Departamentos", "☁️ Wordcloud"])

# RESUMEN
with tabs[0]:
    k1, k2, k3, k4, k5 = st.columns(5)
    KP = _kpis_summary(dff)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"])
    k2.metric("% OA", KP["% OA"])
    k3.metric("Mediana citas", KP["Mediana citas"])
    k4.metric("Con sponsor", KP["Con sponsor"])
    k5.metric("Ensayos clínicos", KP["Ensayos clínicos"])

    if "_Year" in dff.columns:
        g = pd.to_numeric(dff["_Year"], errors="coerce").dropna().astype(int).value_counts().sort_index()
        fig_year = px.bar(x=g.index, y=g.values, labels={"x": "Año", "y": "Nº publicaciones"}, title="Publicaciones por año")
        st.plotly_chart(fig_year, use_container_width=True)

# DATOS
with tabs[1]:
    st.dataframe(dff.head(1000), use_container_width=True)
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ Descargar XLSX", xlsx_bytes, "resultados_filtrados.xlsx")

# REVISTAS
with tabs[2]:
    if "Journal_norm" in dff:
        top_jr = dff["Journal_norm"].fillna("—").value_counts().head(20)
        fig_jr = px.bar(top_jr.sort_values(), orientation="h", title="Top 20 Revistas")
        st.plotly_chart(fig_jr, use_container_width=True)

# AUTORES
with tabs[3]:
    if "Author Full Names" in dff:
        s = dff["Author Full Names"].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        top_auth = pd.Series(authors).value_counts().head(20)
        fig_auth = px.bar(top_auth.sort_values(), orientation="h", title="Top 20 Autores")
        st.plotly_chart(fig_auth, use_container_width=True)

# OA
with tabs[4]:
    if "Open Access" in dff:
        oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
        fig_oa = px.pie(names=oa_counts.index, values=oa_counts.values, title="Proporción OA / No OA")
        st.plotly_chart(fig_oa, use_container_width=True)

# CITAS
with tabs[5]:
    if "Times Cited" in dff:
        tmp = dff.copy()
        tmp["Times Cited"] = pd.to_numeric(tmp["Times Cited"], errors="coerce")
        top_cited = tmp.sort_values("Times Cited", ascending=False).head(20)
        st.dataframe(top_cited[["Title", "Author Full Names", "Times Cited"]], use_container_width=True)

# DEPARTAMENTOS
with tabs[6]:
    if "Departamento" in dff:
        dep_counts = dff["Departamento"].fillna("—").value_counts()
        fig_dep = px.bar(dep_counts.sort_values(), orientation="h", title="Publicaciones por Departamento")
        st.plotly_chart(fig_dep, use_container_width=True)

# WORDCLOUD
with tabs[7]:
    if "Title" in dff:
        text = " ".join(dff["Title"].dropna().astype(str))
        wc = WordCloud(width=800, height=400, background_color="white").generate(text)
        fig, ax = plt.subplots(figsize=(10,5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)