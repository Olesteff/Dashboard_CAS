# /app/app.py
# Dashboard Cienciométrico CAS–UDD con carga automática de la primera hoja

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
DEFAULT_SHEET = None  # ← ahora seleccionamos la primera hoja automáticamente

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
def load_dataframe(uploaded) -> pd.DataFrame:
    if uploaded is not None:
        xls = pd.ExcelFile(uploaded)
        sheet = xls.sheet_names[0]  # primera hoja
        st.sidebar.success(f"📄 Hoja detectada: {sheet}")
        df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
        return df
    if Path(DEFAULT_XLSX).exists():
        xls = pd.ExcelFile(DEFAULT_XLSX)
        sheet = xls.sheet_names[0]
        st.sidebar.success(f"📄 Hoja detectada: {sheet}")
        return pd.read_excel(xls, sheet_name=sheet, dtype=str)
    raise FileNotFoundError("⚠️ No se encontró archivo Excel. Sube el XLSX desde la barra lateral.")

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

    pmid_col = _first_col(df, CAND["pmid"])
    if pmid_col and "PMID_norm" not in df.columns:
        df["PMID_norm"] = df[pmid_col].astype(str).str.replace(r"\D+", "", regex=True).replace("", np.nan)

    eid_col = _first_col(df, CAND["eid"])
    if eid_col and "EID" not in df.columns:
        df["EID"] = df[eid_col].astype(str)

    df["in_PubMed"] = df[pmid_col].notna() if pmid_col else False
    df["in_WoS"] = df[_first_col(df, CAND["wos"])].notna() if _first_col(df, CAND["wos"]) else False
    df["in_Scopus"] = False
    if "Times Cited" in df.columns:
        df["in_Scopus"] = df["Times Cited"].notna()
    if "OA_Scopus" in df.columns:
        df["in_Scopus"] = df["in_Scopus"] | df["OA_Scopus"].notna()

    oa_cols = [c for c in CAND["oa_flags"] if c in df.columns]
    if oa_cols:
        oa_any = pd.concat([_bool_from_str_series(df[c]) for c in oa_cols], axis=1).any(axis=1)
        df["Open Access"] = oa_any.map({True: "OA", False: "No OA"})
    else:
        df["Open Access"] = "Desconocido"

    return df

# -----------------------------
# Filtros (sidebar)
# -----------------------------
try:
    base_df = load_dataframe(st.sidebar.file_uploader("📂 Sube el XLSX", type=["xlsx"]))
    df = normalize_dataset(base_df)
    st.sidebar.success(f"✅ Dataset cargado con {len(df):,} filas")
except Exception as e:
    st.error(str(e))
    st.stop()

mask = pd.Series(True, index=df.index)

with st.sidebar:
    if "_Year" in df.columns and df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int)
        y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("📅 Selecciona rango de años", y_min, y_max, (y_min, y_max))
        mask &= df["_Year"].astype(float).between(y1, y2)

    src_opts = [c for c in ["in_Scopus", "in_WoS", "in_PubMed"] if c in df.columns]
    sel_src = st.multiselect("📚 Fuente", options=src_opts, default=src_opts)
    if sel_src:
        mask &= df[sel_src].fillna(False).any(axis=1)

    if "Open Access" in df.columns:
        oa_vals = ["OA", "No OA", "Desconocido"]
        sel_oa = st.multiselect("🔓 Open Access", oa_vals, default=oa_vals)
        mask &= df["Open Access"].isin(sel_oa)

    query = st.text_input("🔍 Buscar en título", "")
    if query and "Title" in df.columns:
        mask &= df["Title"].fillna("").str.contains(query, case=False, na=False)

    if "Departamento" in df.columns and df["Departamento"].notna().any():
        dep_pool = df["Departamento"].dropna().astype(str).str.split(r"\s*;\s*").explode().dropna()
        dep_pool = sorted(set([d for d in dep_pool if d]))
        sel_dep = st.multiselect("🏥 Departamento", dep_pool, default=[])
        if sel_dep:
            rgx = "|".join(map(re.escape, sel_dep))
            mask &= df["Departamento"].fillna("").str.contains(rgx)

dff = df[mask].copy()
dff = dff.loc[:, ~pd.Index(dff.columns).duplicated(keep="last")]

st.subheader(f"Resultados filtrados: {len(dff):,} publicaciones")

# -----------------------------
# KPIs + figuras
# -----------------------------
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"
    if "DOI_norm" in dff.columns and len(dff):
        kpis["% con DOI"] = f"{(dff['DOI_norm'].notna().mean() * 100):.1f}%"
    else:
        kpis["% con DOI"] = "—"
    if "Open Access" in dff.columns and len(dff):
        kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%"
    else:
        kpis["% OA"] = "—"
    if "Times Cited" in dff.columns and len(dff):
        kpis["Mediana citas"] = f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}"
    else:
        kpis["Mediana citas"] = "—"
    return kpis

def _fig_year_counts(dff: pd.DataFrame):
    g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
    return px.bar(x=g.index, y=g.values, labels={"x": "Año", "y": "Nº publicaciones"}, title="📈 Publicaciones por año")

def _fig_oa_pie(dff: pd.DataFrame):
    oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
    fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="🔓 Proporción OA / No OA")
    fig.update_traces(textinfo="percent+label")
    return fig

# -----------------------------
# Tabs
# -----------------------------
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📚 Revistas", "🧑‍🔬 Autores", "🟢 OA", "⭐ Citas"])

# 📌 RESUMEN
with tabs[0]:
    k1, k2, k3, k4 = st.columns(4)
    KP = _kpis_summary(dff)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"])
    k2.metric("% con DOI", KP["% con DOI"])
    k3.metric("% OA", KP["% OA"])
    k4.metric("Mediana citas", KP["Mediana citas"])

    st.subheader("📈 Publicaciones por año")
    if "_Year" in dff.columns and dff["_Year"].notna().any():
        st.plotly_chart(_fig_year_counts(dff), use_container_width=True)

    st.subheader("🟢 Open Access (resumen)")
    if "Open Access" in dff.columns and len(dff):
        st.plotly_chart(_fig_oa_pie(dff), use_container_width=True)

# 📄 DATOS
with tabs[1]:
    st.subheader("Resultados filtrados (máx 1000 filas)")
    st.dataframe(dff.head(1000), use_container_width=True, height=420)
    csv_bytes = dff.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ CSV — Resultados", csv_bytes, "resultados_filtrados.csv", "text/csv")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ XLSX — Resultados", xlsx_bytes, "resultados_filtrados.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# 📚 REVISTAS
with tabs[2]:
    st.subheader("Top 20 Revistas")
    jr_col = "Journal_norm" if "Journal_norm" in dff.columns else _first_col(dff, CAND["journal"])
    if jr_col and dff[jr_col].notna().any():
        top_jr = dff[jr_col].fillna("—").value_counts().head(20).rename_axis("Journal").reset_index(name="N")
        fig_jr = px.bar(top_jr.sort_values("N"), x="N", y="Journal", orientation="h", title="Top 20 revistas")
        st.plotly_chart(fig_jr, use_container_width=True)
        st.dataframe(top_jr, use_container_width=True, height=420)
    else:
        st.info("⚠️ No hay columna de revista.")

# 🧑‍🔬 AUTORES
with tabs[3]:
    st.subheader("Top 20 Autores")
    acol = "Author Full Names" if "Author Full Names" in dff.columns else _first_col(dff, CAND["authors"])
    if acol and dff[acol].notna().any():
        s = dff[acol].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        top_auth = pd.Series(authors).value_counts().head(20).rename_axis("Autor").reset_index(name="N° Publicaciones")
        fig_auth = px.bar(top_auth.sort_values("N° Publicaciones"), x="N° Publicaciones", y="Autor",
                          orientation="h", title="Top 20 autores")
        st.plotly_chart(fig_auth, use_container_width=True)
        st.dataframe(top_auth, use_container_width=True, height=420)
    else:
        st.info("⚠️ No hay columna de autores.")

# 🟢 OPEN ACCESS
with tabs[4]:
    st.subheader("Open Access")
    if "Open Access" in dff.columns and len(dff):
        st.plotly_chart(_fig_oa_pie(dff), use_container_width=True)
        st.dataframe(dff[["Title", "_Year", "Open Access"]].dropna(how="all"), use_container_width=True, height=420)
    else:
        st.info("⚠️ No hay columna de OA.")

# ⭐ CITAS
with tabs[5]:
    st.subheader("Más citadas")
    if "Times Cited" in dff.columns:
        tmp = dff.copy()
        tmp["Times Cited"] = pd.to_numeric(tmp["Times Cited"], errors="coerce")
        top_cited = tmp.sort_values("Times Cited", ascending=False).head(20)
        cols_show = [c for c in ["Title", "Author Full Names", "Times Cited", "_Year", "DOI_norm"] if c in top_cited.columns]
        st.dataframe(top_cited[cols_show], use_container_width=True, height=520)
    else:
        st.info("⚠️ No hay columna de citas (‘Times Cited’/‘Cited by’).")