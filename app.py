# app_final.py
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================
# Config
# =========================
st.set_page_config(
    page_title="Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"  # 1ª hoja (por defecto)
DEFAULT_SHEET_INDEX = 0  # usa la primera hoja

# =========================
# Utils base
# =========================
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _coerce_bool(sr: pd.Series | None) -> pd.Series:
    if sr is None:
        return pd.Series([False]*0, dtype=bool)
    x = sr.astype(str).str.lower().str.strip()
    true_vals = {"1","true","t","yes","y","si","sí"}
    out = pd.Series(False, index=sr.index)
    out.loc[x.isin(true_vals)] = True
    return out.fillna(False)

def _coerce_num(sr: pd.Series | None) -> pd.Series:
    if sr is None:
        return pd.Series(dtype=float)
    try:
        return pd.to_numeric(sr, errors="coerce")
    except Exception:
        return pd.Series([np.nan]*len(sr), index=sr.index)

def _title_key(s: object) -> str:
    t = str(s or "").lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    for engine in ("xlsxwriter","openpyxl"):
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as w:
                df.to_excel(w, index=False, sheet_name=sheet_name)
            buf.seek(0)
            return buf.getvalue()
        except Exception:
            continue
    return None

# =========================
# Carga
# =========================
@st.cache_data(show_spinner=False)
def load_data(uploaded=None) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=DEFAULT_SHEET_INDEX, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=DEFAULT_SHEET_INDEX, dtype=str)
    raise FileNotFoundError(
        f"No se encontró {DEFAULT_XLSX}. Sube un XLSX desde la barra lateral."
    )

# =========================
# Normalización
# =========================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str)

    # Año
    year_col = _first_col(df, ["Year", "Publication Year", "PY"])
    if year_col:
        df["_Year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    else:
        df["_Year"] = pd.NA

    # Título
    title_col = _first_col(df, ["Title", "Document Title", "Article Title", "TI"])
    if title_col and "Title" not in df.columns:
        df["Title"] = df[title_col].astype(str)
    df["_title_key"] = df.get("Title", pd.Series("", index=df.index)).map(_title_key)

    # Open Access
    oa_col = _first_col(df, ["OpenAccess_flag", "Open Access", "OA"])
    df["OpenAccess_flag"] = _coerce_bool(df[oa_col]) if oa_col else False

    # Clinical trials (detección textual robusta)
    title = df.get("Title", pd.Series("", index=df.index)).astype(str)
    abstract = df.get("Abstract", pd.Series("", index=df.index)).astype(str)
    ptype = df.get("Publication Type", pd.Series("", index=df.index)).astype(str)
    keywords = df.get("Keywords", pd.Series("", index=df.index)).astype(str)

    text = (title + " " + abstract + " " + ptype + " " + keywords).str.lower()
    ct_regex = r"(ensayo\s*cl[ií]nico|clinical\s*trial|randomi[sz]ed|phase\s*[i1v]+|double\s*blind|placebo\-controlled)"
    df["ClinicalTrial_flag"] = text.str.contains(ct_regex, regex=True, na=False)

    # Sponsor (detectado pero no mostrado en pestañas)
    fund_cols = [c for c in df.columns if re.search(r"(fund|grant|sponsor|financ)", c, flags=re.I)]
    if fund_cols:
        fund_text = df[fund_cols].astype(str).agg(" ".join, axis=1)
        df["Has_Sponsor"] = fund_text.astype(str).str.strip().ne("")
    else:
        df["Has_Sponsor"] = False

    # JIF
    jif_col = _first_col(df, ["Journal Impact Factor","JIF","Impact Factor"])
    df["_JIF_num"] = _coerce_num(df[jif_col]).fillna(0.0) if jif_col else 0.0

    # Cuartiles
    q_col = _first_col(df, ["JCR Quartile", "JCR_Quartile","Quartile"])
    if q_col:
        q = df[q_col].astype(str).str.upper().str.extract(r"(Q[1-4])", expand=False)
        df["quartile_std"] = q.fillna("Sin cuartil")
    else:
        df["quartile_std"] = "Sin cuartil"

    # Departamentos
    aff_col = _first_col(df, ["Authors with affiliations","Author Affiliations","Affiliations","C1","Author Information"])
    def detect_department(aff: str) -> str:
        a = str(aff or "").lower()
        rules = [
            ("oncolog", "Oncología"),
            ("pediatr", "Pediatría"),
            ("neurolog", "Neurología y Psiquiatría"),
            ("psiquiatr", "Neurología y Psiquiatría"),
            ("radiolog", "Imágenes"),
            ("imagen", "Imágenes"),
            ("ginecol", "Ginecología y Obstetricia"),
            ("obstet", "Ginecología y Obstetricia"),
            ("traumatolog", "Traumatología y Ortopedia"),
            ("ortoped", "Traumatología y Ortopedia"),
            ("dermatolog", "Dermatología"),
            ("medicina interna", "Medicina Interna"),
            ("internal medicine", "Medicina Interna"),
            ("urgenc", "Urgencias"),
            ("intensiv", "Cuidados Intensivos"),
            ("anestesi", "Anestesiología"),
            ("cardiol", "Cardiología"),
            ("endocrin", "Endocrinología"),
            ("nefrol", "Nefrología"),
            ("neumol", "Neumología"),
            ("rehabilit", "Rehabilitación"),
            ("odont", "Odontología"),
            ("alemana", "Clínica Alemana (General)"),
            ("udd", "Clínica Alemana (General)"),
        ]
        for kw, dep in rules:
            if kw in a:
                return dep
        return "Sin asignar"

    df["Departamento"] = df.get(aff_col, pd.Series("", index=df.index)).map(detect_department)

    return df

# =========================
# Carga dataset
# =========================
df_base = load_data()
df = normalize_columns(df_base)

# =========================
# Sidebar – Filtros
# =========================
st.sidebar.header("Filtros")

# Año
if df["_Year"].notna().any():
    ys = df["_Year"].dropna().astype(int)
    lo, hi = int(ys.min()), int(ys.max())
    y1, y2 = st.sidebar.slider("Rango de años", lo, hi, (lo, hi))
else:
    y1, y2 = (0, 9999)

# OA
oa_choice = st.sidebar.radio("Open Access", ["Todos","Solo OA","Solo No OA"], index=0)

# Cuartil
qs = ["Q1","Q2","Q3","Q4","Sin cuartil"]
sel_q = st.sidebar.multiselect("Cuartil", qs, default=qs)

# Departamento
deps = sorted(df["Departamento"].dropna().unique())
sel_dep = st.sidebar.multiselect("Departamento", deps, default=[])

# Búsqueda
qtxt = st.sidebar.text_input("Buscar en título", "")

# Aplicar filtros
mask = pd.Series(True, index=df.index)
mask &= df["_Year"].fillna(-1).astype(int).between(y1, y2)
if oa_choice == "Solo OA":
    mask &= df["OpenAccess_flag"]
elif oa_choice == "Solo No OA":
    mask &= ~df["OpenAccess_flag"]
if sel_q:
    mask &= df["quartile_std"].isin(sel_q)
if sel_dep:
    dep_series = df["Departamento"].fillna("").astype(str)
    dep_mask = pd.Series(False, index=df.index)
    for dep in sel_dep:
        dep_mask |= dep_series.str.contains(dep, case=False, regex=False)
    mask &= dep_mask
if qtxt.strip():
    mask &= df["Title"].fillna("").str.contains(qtxt, case=False, na=False)

dff = df.loc[mask].copy()

# =========================
# KPIs
# =========================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Publicaciones", f"{len(dff):,}")
c2.metric("% OA", f"{100*dff['OpenAccess_flag'].mean():.1f}%" if len(dff) else "0%")
c3.metric("⭐ Suma JIF", f"{dff['_JIF_num'].sum():,.1f}")
c4.metric("🧪 Ensayos clínicos", f"{int(dff['ClinicalTrial_flag'].sum()):,}")

# =========================
# Tabs
# =========================
tabs = st.tabs([
    "📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos",
    "📚 Revistas", "👤 Autores", "☁️ Wordcloud"
])

# 1) Publicaciones
with tabs[0]:
    st.subheader("Publicaciones por año")
    if dff["_Year"].notna().any():
        g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
        fig = px.bar(x=g.index, y=g.values, labels={"x":"Año","y":"Publicaciones"})
        st.plotly_chart(fig, use_container_width=True)

# 2) Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil")
    cts = dff["quartile_std"].value_counts()
    fig = px.pie(names=cts.index, values=cts.values, hole=0.5)
    st.plotly_chart(fig, use_container_width=True)

# 3) OA
with tabs[2]:
    st.subheader("Distribución Open Access")
    s = dff["OpenAccess_flag"].map({True:"OA", False:"No OA"}).value_counts()
    fig = px.pie(names=s.index, values=s.values, hole=0.5)
    st.plotly_chart(fig, use_container_width=True)

# 4) Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    s = dff["Departamento"].value_counts()
    fig = px.bar(s.sort_values(), orientation="h")
    st.plotly_chart(fig, use_container_width=True)

# 5) Revistas
with tabs[4]:
    jr_col = _first_col(dff, ["Journal","Source Title","Publication Name"])
    if jr_col:
        s = dff[jr_col].fillna("—").value_counts().head(20)
        fig = px.bar(s.sort_values(), orientation="h")
        st.plotly_chart(fig, use_container_width=True)

# 6) Autores
with tabs[5]:
    a_col = _first_col(dff, ["Author Full Names","Authors"])
    if a_col:
        s = dff[a_col].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        vc = pd.Series(authors).value_counts().head(20)
        fig = px.bar(vc.sort_values(), orientation="h")
        st.plotly_chart(fig, use_container_width=True)

# 7) Wordcloud
with tabs[6]:
    st.subheader("Wordcloud")
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
        text = " ".join(dff.get("Title", pd.Series(dtype=str)).dropna().astype(str).tolist())
        if text.strip():
            wc = WordCloud(width=1000, height=400, background_color="white").generate(text)
            fig, ax = plt.subplots(figsize=(10,4))
            ax.imshow(wc, interpolation="bilinear"); ax.axis("off")
            st.pyplot(fig)
    except Exception:
        st.info("Instala `wordcloud` para ver la nube")