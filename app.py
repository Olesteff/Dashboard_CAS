# /app/app.py
# Dashboard Cienciométrico con Tabs + Merge/Dedup + PDF (experimental)

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

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
DEFAULT_SHEET = None   # ✅ Siempre toma la primera hoja

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
def load_dataframe(uploaded, sheet_name=DEFAULT_SHEET) -> Tuple[pd.DataFrame, str]:
    if uploaded is not None:
        xl = pd.ExcelFile(uploaded)
        sheet = xl.sheet_names[0] if sheet_name is None else sheet_name
        return pd.read_excel(xl, sheet_name=sheet, dtype=str), sheet
    if Path(DEFAULT_XLSX).exists():
        xl = pd.ExcelFile(DEFAULT_XLSX)
        sheet = xl.sheet_names[0] if sheet_name is None else sheet_name
        return pd.read_excel(xl, sheet_name=sheet, dtype=str), sheet
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
# Carga dataset
# -----------------------------
try:
    base_df, loaded_sheet = load_dataframe(None)
    st.sidebar.success(f"📑 Hoja detectada: {loaded_sheet}")
except Exception as e:
    st.error(str(e))
    st.stop()

df = normalize_dataset(base_df)
st.success(f"Dataset cargado con {len(df):,} filas ✅")