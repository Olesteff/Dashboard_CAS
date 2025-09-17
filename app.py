# /app/app_modular.py
# Dashboard Cienciométrico con Tabs + Departamentos + Ensayos clínicos + Sponsors

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

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
    if pd.isna(val):
        return None
    m = DOI_REGEX.search(str(val))
    return m.group(0).lower() if m else None

def _norm_text(s: object) -> str:
    if pd.isna(s):
        return ""
    t = str(s).strip()
    t = re.sub(r"\s+", " ", t)
    return t

def _title_key(s: object) -> str:
    if pd.isna(s):
        return ""
    t = re.sub(r"[^A-Za-z0-9 ]", " ", str(s).lower())
    return re.sub(r"\s+", " ", t).strip()

def _bool_from_str_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(False, index=pd.RangeIndex(0))
    x = s.astype(str).str.lower().str.strip()
    true_vals = {"1", "true", "t", "yes", "y", "si", "sí"}
    false_vals = {"0", "false", "f", "no", "n", ""}
    out = pd.Series(index=x.index, dtype=bool)
    out.loc[x.isin(true_vals)] = True
    out.loc[x.isin(false_vals)] = False
    return out.fillna(False)

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    for engine in ("xlsxwriter", "openpyxl"):
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as w:
                df.to_excel(w, index=False, sheet_name=sheet_name)
            buf.seek(0)
            return buf.getvalue()
        except Exception:
            continue
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
# Carga (cache)
# -----------------------------
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded, sheet_name=DEFAULT_SHEET) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name, dtype=str)
    raise FileNotFoundError(f"No se encontró {DEFAULT_XLSX}. Sube el XLSX desde la barra lateral.")

# -----------------------------
# Normalización
# -----------------------------
def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]

    ycol = _first_col(df, CAND["year"])
    if ycol:
        df["_Year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")

    tcol = _first_col(df, CAND["title"])
    if tcol and tcol != "Title":
        df["Title"] = df[tcol].astype(str)

    dcol = _first_col(df, CAND["doi"])
    lcol = _first_col(df, CAND["link"])
    doi_base = df[dcol].astype(str).str.strip().str.lower() if dcol else pd.Series(np.nan, index=df.index)
    doi_from_link = df[lcol].astype(str).map(_extract_doi) if lcol else pd.Series(np.nan, index=df.index)
    df["DOI_norm"] = doi_base.where(doi_base.notna() & (doi_base != ""), doi_from_link)

    jcol = _first_col(df, CAND["journal"])
    if jcol:
        df["Journal_norm"] = df[jcol].map(_norm_text)

    dpt = _first_col(df, CAND["dept"])
    if dpt:
        df["Departamento"] = df[dpt]

    acol = _first_col(df, CAND["authors"])
    if acol and acol != "Author Full Names":
        df["Author Full Names"] = df[acol]

    ccol = _first_col(df, CAND["cited"])
    if ccol and ccol != "Times Cited":
        df["Times Cited"] = pd.to_numeric(df[ccol], errors="coerce")

    return df

# -----------------------------
# Sidebar – carga y filtros
# -----------------------------
with st.sidebar:
    st.subheader("Datos base")
    up = st.file_uploader("Sube el XLSX (Sheet1)", type=["xlsx"])
    st.caption(f"Por defecto: `{DEFAULT_XLSX}` / hoja `{DEFAULT_SHEET}`")
    st.markdown("---")
    st.subheader("Filtros")

# Carga inicial
try:
    base_df = load_dataframe(up)
except Exception as e:
    st.error(str(e))
    st.stop()

df = normalize_dataset(base_df)

mask = pd.Series(True, index=df.index)

with st.sidebar:
    if "_Year" in df.columns and df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int)
        y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Año", y_min, y_max, (y_min, y_max))
        mask &= df["_Year"].astype(float).between(y1, y2)

    if "Open Access" in df.columns:
        oa_vals = ["OA", "No OA", "Desconocido"]
        sel_oa = st.multiselect("Open Access", oa_vals, default=oa_vals)
        mask &= df["Open Access"].isin(sel_oa)

    if "Departamento" in df.columns and df["Departamento"].notna().any():
        dep_pool = df["Departamento"].dropna().astype(str).str.split(r"\s*;\s*").explode().dropna()
        dep_pool = sorted(set([d for d in dep_pool if d]))
        sel_dep = st.multiselect("Departamento", dep_pool, default=[])
        if sel_dep:
            rgx = "|".join(map(re.escape, sel_dep))
            mask &= df["Departamento"].fillna("").str.contains(rgx)

dff = df[mask].copy()
dff = dff.loc[:, ~pd.Index(dff.columns).duplicated(keep="last")]

st.subheader(f"Resultados: {len(dff):,}")

# -----------------------------
# KPIs + figuras
# -----------------------------
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"
    if "Open Access" in dff.columns and len(dff):
        kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%"
    else:
        kpis["% OA"] = "—"
    if "Times Cited" in dff.columns and len(dff):
        kpis["Mediana citas"] = f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}"
    else:
        kpis["Mediana citas"] = "—"
    return kpis

# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs([
    "📌 Resumen", "📄 Datos", "📚 Revistas", "🧑‍🔬 Autores",
    "🟢 OA", "⭐ Citas", "🏥 Departamentos", "🧪 Ensayos clínicos", "💰 Sponsors"
])

# RESUMEN
with tabs[0]:
    KP = _kpis_summary(dff)
    k1, k2, k3 = st.columns(3)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"])
    k2.metric("% OA", KP["% OA"])
    k3.metric("Mediana citas", KP["Mediana citas"])

# DATOS
with tabs[1]:
    st.subheader("Resultados filtrados")
    st.dataframe(dff.head(1000), use_container_width=True, height=420)
    csv_bytes = dff.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ CSV — Resultados", csv_bytes, "resultados_filtrados.csv", "text/csv")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ XLSX — Resultados", xlsx_bytes, "resultados_filtrados.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# REVISTAS
with tabs[2]:
    if "Journal_norm" in dff.columns:
        top_jr = dff["Journal_norm"].fillna("—").value_counts().head(15).rename_axis("Journal").reset_index(name="N")
        fig = px.bar(top_jr.sort_values("N"), x="N", y="Journal", orientation="h", title="Top 15 revistas")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(top_jr)

# AUTORES
with tabs[3]:
    if "Author Full Names" in dff.columns:
        s = dff["Author Full Names"].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        top_auth = pd.Series(authors).value_counts().head(15).rename_axis("Autor").reset_index(name="N")
        fig = px.bar(top_auth.sort_values("N"), x="N", y="Autor", orientation="h", title="Top 15 autores")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(top_auth)

# OA
with tabs[4]:
    if "Open Access" in dff.columns:
        oa_counts = dff["Open Access"].value_counts()
        fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="Distribución Open Access")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dff[["_Year", "Title", "Open Access"]])

# CITAS
with tabs[5]:
    if "Times Cited" in dff.columns:
        tmp = dff.copy()
        tmp["Times Cited"] = pd.to_numeric(tmp["Times Cited"], errors="coerce")
        top_cited = tmp.sort_values("Times Cited", ascending=False).head(20)
        st.dataframe(top_cited[["Title","Author Full Names","Times Cited","_Year"]])

# DEPARTAMENTOS
with tabs[6]:
    if "Departamento" in dff.columns:
        top_dep = dff["Departamento"].fillna("—").value_counts().head(15).rename_axis("Departamento").reset_index(name="N")
        fig = px.bar(top_dep.sort_values("N"), x="N", y="Departamento", orientation="h", title="Top 15 departamentos")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(top_dep)

# ENSAYOS CLÍNICOS
with tabs[7]:
    if "ClinicalTrial_flag" in dff.columns:
        trials = dff[dff["ClinicalTrial_flag"] == True]
        st.metric("Nº Ensayos clínicos", len(trials))
        st.dataframe(trials[["Title","_Year","Journal_norm","Departamento"]].head(50))

# SPONSORS
with tabs[8]:
    if "Has_Sponsor" in dff.columns:
        sponsor_df = dff[dff["Has_Sponsor"] == True]
        st.metric("Nº publicaciones con sponsor", len(sponsor_df))
        st.dataframe(sponsor_df[["Title","_Year","Journal_norm","Departamento","Funding_info"]].head(50))