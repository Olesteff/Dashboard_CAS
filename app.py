# app.py — Dashboard CAS-UDD (completo)

from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================
# Config general
# =========================
st.set_page_config(
    page_title="Dashboard Cienciométrico CAS-UDD",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"  # archivo por defecto
DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)

# Candidatos de columnas (alias frecuentes)
CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["_Year", "Year", "Publication Year", "PY", "Year_clean"],
    "doi": ["DOI", "Doi"],
    "link": ["Link", "URL", "Full Text URL"],
    "journal": ["Journal_norm", "Source title", "Source Title", "Publication Name", "Journal"],
    "dept": ["Departamento", "Dept_CAS_list", "Dept_FMUDD_list", "Department"],
    "authors": ["Author Full Names", "Author full names", "Authors"],
    "cited": ["Times Cited", "Cited by", "TimesCited"],
    "pmid": ["PMID_norm", "PubMed ID", "PMID"],
    "eid": ["EID", "Scopus EID"],
    "wos": ["Web of Science Record", "Unique WOS ID", "UT (Unique WOS ID)"],
    "oa_flags": ["OpenAccess_flag", "OA_Scopus", "OA_WoS", "OA_PubMed", "OA"],
    "quartile": ["JCR_Quartile", "JIF Quartile", "JCI Quartile"],
    "jif": ["Journal Impact Factor", "JIF", "Impact Factor"],
    "sponsor": ["Has_Sponsor", "Funding_info"],
    "trial": ["ClinicalTrial_flag"],
}

# =========================
# Utilidades
# =========================
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

def _sheet_name_or_first(pathlike) -> str:
    try:
        xf = pd.ExcelFile(pathlike)
        return xf.sheet_names[0] if xf.sheet_names else "Sheet1"
    except Exception:
        return "Sheet1"

# =========================
# Carga (cache)
# =========================
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded) -> pd.DataFrame:
    if uploaded is not None:
        # Tomar SIEMPRE la 1.ª hoja del archivo subido
        try:
            xf = pd.ExcelFile(uploaded)
            sn = xf.sheet_names[0]
            return pd.read_excel(uploaded, sheet_name=sn, dtype=str)
        except Exception:
            return pd.read_excel(uploaded, dtype=str)

    if Path(DEFAULT_XLSX).exists():
        try:
            xf = pd.ExcelFile(DEFAULT_XLSX)
            sn = xf.sheet_names[0]
            st.sidebar.success(f"Hoja detectada: {sn}")
            return pd.read_excel(DEFAULT_XLSX, sheet_name=sn, dtype=str)
        except Exception:
            return pd.read_excel(DEFAULT_XLSX, dtype=str)

    raise FileNotFoundError(
        f"No se encontró {DEFAULT_XLSX}. Sube el XLSX desde la barra lateral."
    )

# =========================
# Normalización dataset
# =========================
def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]

    # Año
    ycol = _first_col(df, CAND["year"])
    if ycol and "_Year" not in df.columns:
        df["_Year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")
    elif "_Year" in df.columns:
        df["_Year"] = pd.to_numeric(df["_Year"], errors="coerce").astype("Int64")

    # Título
    tcol = _first_col(df, CAND["title"])
    if tcol and tcol != "Title":
        df["Title"] = df[tcol].astype(str)

    # DOI normalizado
    dcol = _first_col(df, CAND["doi"])
    lcol = _first_col(df, CAND["link"])
    doi_base = df[dcol].astype(str).str.strip().str.lower() if dcol else pd.Series(np.nan, index=df.index)
    doi_from_link = df[lcol].astype(str).map(_extract_doi) if lcol else pd.Series(np.nan, index=df.index)
    df["DOI_norm"] = doi_base.where(doi_base.notna() & (doi_base != ""), doi_from_link)

    # Revista
    jcol = _first_col(df, CAND["journal"])
    if jcol and jcol != "Journal_norm":
        df["Journal_norm"] = df[jcol].astype(str)

    # Departamento
    dpt = _first_col(df, CAND["dept"])
    if dpt and dpt != "Departamento":
        df["Departamento"] = df[dpt]

    # Autores
    acol = _first_col(df, CAND["authors"])
    if acol and acol != "Author Full Names":
        df["Author Full Names"] = df[acol]

    # Citas
    ccol = _first_col(df, CAND["cited"])
    if ccol and ccol != "Times Cited":
        df["Times Cited"] = pd.to_numeric(df[ccol], errors="coerce")

    # IDs y presencia por fuente
    pmid_col = _first_col(df, CAND["pmid"])
    if pmid_col and "PMID_norm" not in df.columns:
        df["PMID_norm"] = df[pmid_col].astype(str).str.replace(r"\D+", "", regex=True).replace("", np.nan)

    eid_col = _first_col(df, CAND["eid"])
    if eid_col and "EID" not in df.columns:
        df["EID"] = df[eid_col].astype(str)

    df["in_PubMed"] = df[pmid_col].notna() if pmid_col else False
    df["in_WoS"] = df[_first_col(df, CAND["wos"])].notna() if _first_col(df, CAND["wos"]) else False
    # 'in_Scopus' aproximado si no viene explícito
    df["in_Scopus"] = False
    if "Times Cited" in df.columns:
        df["in_Scopus"] = df["Times Cited"].notna() | df["Times Cited"].ge(0)

    # Open Access
    oa_cols = [c for c in CAND["oa_flags"] if c in df.columns]
    if oa_cols:
        oa_any = pd.concat([_bool_from_str_series(df[c]) for c in oa_cols], axis=1).any(axis=1)
        df["Open Access"] = oa_any.map({True: "OA", False: "No OA"})
    else:
        df["Open Access"] = "Desconocido"

    # Cuartil JCR — normalizar a Q1–Q4 + Sin cuartil
    qcol = _first_col(df, CAND["quartile"])
    if qcol and qcol != "JCR_Quartile":
        df["JCR_Quartile"] = df[qcol]
    if "JCR_Quartile" in df.columns:
        q = df["JCR_Quartile"].astype(str).str.upper()
        q = q.str.extract(r"(Q[1-4])", expand=False)
        df["JCR_Quartile"] = q.fillna("Sin cuartil")

    # JIF (si existe)
    jif_col = _first_col(df, CAND["jif"])
    if jif_col and jif_col != "Journal Impact Factor":
        df["Journal Impact Factor"] = pd.to_numeric(df[jif_col], errors="coerce")

    # Sponsor (si hay info)
    if "Has_Sponsor" not in df.columns:
        s_col = _first_col(df, CAND["sponsor"])
        if s_col:
            # True si hay texto que sugiere sponsor
            df["Has_Sponsor"] = df[s_col].astype(str).str.strip().ne("")
        else:
            df["Has_Sponsor"] = False

    # Ensayo clínico (si existe)
    if "ClinicalTrial_flag" not in df.columns:
        tri_col = _first_col(df, CAND["trial"])
        df["ClinicalTrial_flag"] = _bool_from_str_series(df[tri_col]) if tri_col else False

    return df

# =========================
# Deduplicación (para merge)
# =========================
def _build_dedup_key(df_like: pd.DataFrame) -> pd.Series:
    parts: List[pd.Series] = []
    if "DOI_norm" in df_like.columns:
        parts.append(df_like["DOI_norm"].fillna(""))
    if "PMID_norm" in df_like.columns:
        parts.append("PMID:" + df_like["PMID_norm"].fillna(""))
    if "EID" in df_like.columns:
        parts.append("EID:" + df_like["EID"].astype(str).fillna(""))

    ycol = _first_col(df_like, CAND["year"]) or "_Year"
    tcol = _first_col(df_like, CAND["title"]) or "Title"
    if ycol in df_like.columns and tcol in df_like.columns:
        y = pd.to_numeric(df_like[ycol], errors="coerce").fillna(-1).astype(int).astype(str)
        t = df_like[tcol].map(_title_key).fillna("")
        parts.append("TY:" + y + "|" + t)

    if not parts:
        return pd.Series("", index=df_like.index, dtype="object")
    key = parts[0].astype(str)
    for p in parts[1:]:
        key = key.where(key.astype(bool), p.astype(str))
    return key

def _read_any(file_obj) -> pd.DataFrame:
    name = (getattr(file_obj, "name", "") or "").lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(file_obj, dtype=str)
        return pd.read_excel(file_obj, dtype=str)
    except Exception:
        return pd.DataFrame()

# =========================
# Sidebar — carga + merge + filtros
# =========================
with st.sidebar:
    st.header("Datos base")
    up = st.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])
    if Path(DEFAULT_XLSX).exists():
        st.caption(f"Por defecto: `{DEFAULT_XLSX}` (se leerá la 1ª hoja)")

    st.markdown("---")
    st.header("Actualizar dataset (merge)")
    new_files = st.file_uploader("Nuevos CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=True)
    colA, colB = st.columns([1,1])
    with colA:
        btn_preview = st.button("👀 Previsualizar unión")
    with colB:
        btn_apply = st.button("✅ Aplicar actualización", type="primary")
    save_over = st.checkbox("Sobrescribir archivo base al aplicar (si existe)", value=False)

# Carga + normalización
try:
    base_df = load_dataframe(up)
    st.success(f"Dataset cargado con {len(base_df):,} filas ✅")
except Exception as e:
    st.error(str(e))
    st.stop()

df = normalize_dataset(base_df)

# Dataset actualizado en sesión
if "__df_updated__" in st.session_state and isinstance(st.session_state["__df_updated__"], pd.DataFrame):
    df = st.session_state["__df_updated__"]

# Merge preview / apply
if new_files:
    news: List[pd.DataFrame] = []
    for f in new_files:
        t = _read_any(f)
        if not t.empty:
            news.append(normalize_dataset(t))
    new_df = pd.concat(news, ignore_index=True, sort=False) if news else pd.DataFrame()

    if not new_df.empty:
        pre_keys = _build_dedup_key(df)
        pre_set = set(k for k in pre_keys if isinstance(k, str) and k)
        cand_keys = _build_dedup_key(new_df)
        is_new = cand_keys.map(lambda k: (isinstance(k, str) and k not in pre_set and k != ""))

        if btn_preview:
            n_new = int(is_new.sum())
            n_dup = int(len(new_df) - n_new)
            st.info(f"Vista previa: **{n_new}** nuevos · **{n_dup}** duplicados/ignorados.")
            cols_preview = [c for c in ["Title", "_Year", "DOI_norm", "PMID_norm", "EID"] if c in new_df.columns]
            st.dataframe(new_df.loc[is_new, cols_preview].head(150), use_container_width=True, height=280)

        if btn_apply:
            merged = pd.concat([df, new_df], ignore_index=True, sort=False)
            merged["_dedup_key"] = _build_dedup_key(merged)
            merged["_title_key"] = merged["Title"].map(_title_key) if "Title" in merged.columns else ""
            merged["__tmp__"] = merged["_dedup_key"].fillna("") + "|" + merged["_title_key"].fillna("")
            before = len(merged)
            merged = merged.drop_duplicates(subset="__tmp__", keep="first").drop(columns=["__tmp__"], errors="ignore")
            added = merged.shape[0] - df.shape[0]
            st.success(f"Actualización aplicada: +{max(0, added)} registros nuevos (total {len(merged):,}).")

            st.session_state["__df_updated__"] = merged
            df = merged

            xbytes = _df_to_xlsx_bytes(df)
            if xbytes:
                st.download_button("⬇️ Descargar dataset ACTUALIZADO (XLSX)", xbytes,
                                   file_name="dataset_actualizado.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="dl_updated_ds")

            if save_over and Path(DEFAULT_XLSX).exists():
                try:
                    df.to_excel(DEFAULT_XLSX, index=False)
                    st.success(f"Sobrescrito `{DEFAULT_XLSX}`.")
                except Exception as e:
                    st.error(f"No se pudo sobrescribir: {e}")

# -----------------------------
# Filtros (sidebar)
# -----------------------------
mask = pd.Series(True, index=df.index)

with st.sidebar:
    st.markdown("---")
    st.header("Filtros")

    # Año
    if "_Year" in df.columns and df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int)
        y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Año", y_min, y_max, (y_min, y_max))
        mask &= df["_Year"].astype(float).between(y1, y2)

    # Fuente
    src_opts = [c for c in ["in_Scopus", "in_WoS", "in_PubMed"] if c in df.columns]
    sel_src = st.multiselect("Fuente", options=src_opts, default=src_opts)
    if sel_src:
        mask &= df[sel_src].fillna(False).any(axis=1)

    # OA
    if "Open Access" in df.columns:
        oa_vals = ["OA", "No OA", "Desconocido"]
        sel_oa = st.multiselect("Open Access", oa_vals, default=oa_vals)
        mask &= df["Open Access"].isin(sel_oa)

    # Cuartiles
    if "JCR_Quartile" in df.columns:
        q_vals = ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
        sel_q = st.multiselect("Cuartil JCR", q_vals, default=q_vals)
        mask &= df["JCR_Quartile"].fillna("Sin cuartil").isin(sel_q)

    # Búsqueda por título
    query = st.text_input("Buscar en título", "")
    if query and "Title" in df.columns:
        mask &= df["Title"].fillna("").str.contains(query, case=False, na=False)

    # Departamento
    if "Departamento" in df.columns and df["Departamento"].notna().any():
        dep_pool = df["Departamento"].dropna().astype(str).str.split(r"\s*;\s*").explode().dropna()
        dep_pool = sorted(set([d for d in dep_pool if d]))
        sel_dep = st.multiselect("Departamento", dep_pool, default=[])
        if sel_dep:
            rgx = "|".join(map(re.escape, sel_dep))
            mask &= df["Departamento"].fillna("").str.contains(rgx)

# Dataset filtrado
dff = df[mask].copy()
dff = dff.loc[:, ~pd.Index(dff.columns).duplicated(keep="last")]

st.title("📊 Dashboard Producción Científica CAS-UDD")

# =========================
# KPIs
# =========================
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

    if "Has_Sponsor" in dff.columns:
        kpis["Con sponsor"] = f"{int(pd.Series(dff['Has_Sponsor']).fillna(False).sum()):,}"
    else:
        kpis["Con sponsor"] = "0"

    if "ClinicalTrial_flag" in dff.columns:
        kpis["Ensayos clínicos"] = f"{int(pd.Series(dff['ClinicalTrial_flag']).fillna(False).sum()):,}"
    else:
        kpis["Ensayos clínicos"] = "0"

    return kpis

# =========================
# Figuras
# =========================
def _fig_year_counts(dff: pd.DataFrame):
    if "_Year" not in dff.columns:
        return None
    g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
    fig = px.bar(x=g.index, y=g.values, labels={"x": "Año", "y": "Nº publicaciones"}, title="Publicaciones por año")
    return fig

def _fig_oa_pie(dff: pd.DataFrame):
    if "Open Access" not in dff.columns:
        return None
    oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
    fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="Proporción OA / No OA", hole=0.4)
    fig.update_traces(textinfo="percent+label")
    return fig

def _fig_quartiles(dff: pd.DataFrame):
    if "JCR_Quartile" not in dff.columns:
        return None
    q = dff["JCR_Quartile"].fillna("Sin cuartil")
    # Asegurar orden de categorías
    order = ["Sin cuartil", "Q1", "Q2", "Q3", "Q4"]
    vc = q.value_counts().reindex(order).dropna()
    fig = px.pie(
        names=vc.index, values=vc.values, hole=0.4,
        color=vc.index,
        color_discrete_map={
            "Q1": "green", "Q2": "yellow", "Q3": "orange", "Q4": "darkred", "Sin cuartil": "lightgrey"
        },
        title="Distribución por cuartiles JCR"
    )
    fig.update_traces(textinfo="percent+label")
    return fig

def _fig_jif_por_anio(dff: pd.DataFrame):
    if "Journal Impact Factor" not in dff.columns or "_Year" not in dff.columns:
        return None
    tmp = dff.copy()
    tmp["JIF"] = pd.to_numeric(tmp["Journal Impact Factor"], errors="coerce")
    m = tmp.groupby(tmp["_Year"].astype("Int64"))["JIF"].mean().dropna()
    if m.empty:
        return None
    fig = px.line(x=m.index, y=m.values, labels={"x": "Año", "y": "JIF medio"}, title="Evolución JIF medio por año")
    return fig

# =========================
# Tabs
# =========================
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📚 Revistas", "🧑‍🔬 Autores", "🟢 OA", "⭐ Citas", "🏥 Departamentos", "☁️ Wordcloud"])

# RESUMEN
with tabs[0]:
    k1, k2, k3, k4, k5 = st.columns(5)
    KP = _kpis_summary(dff)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"])
    k2.metric("% con DOI", KP["% con DOI"])
    k3.metric("% OA", KP["% OA"])
    k4.metric("Con sponsor", KP["Con sponsor"])
    k5.metric("Ensayos clínicos", KP["Ensayos clínicos"])

    fig_year = _fig_year_counts(dff)
    if fig_year:
        st.plotly_chart(fig_year, use_container_width=True, key="fig_year_counts")

    cols = st.columns(2)
    with cols[0]:
        fig_oa = _fig_oa_pie(dff)
        if fig_oa:
            st.plotly_chart(fig_oa, use_container_width=True, key="fig_oa_pie")

    with cols[1]:
        fig_q = _fig_quartiles(dff)
        if fig_q:
            st.plotly_chart(fig_q, use_container_width=True, key="fig_quartiles_pie")

    fig_jif = _fig_jif_por_anio(dff)
    if fig_jif:
        st.plotly_chart(fig_jif, use_container_width=True, key="fig_jif_year")

# DATOS
with tabs[1]:
    st.subheader("Resultados filtrados")
    st.dataframe(dff.head(1000), use_container_width=True, height=420)
    csv_bytes = dff.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ CSV — Resultados", csv_bytes, "resultados_filtrados.csv", "text/csv", key="dl_csv_datos")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ XLSX — Resultados", xlsx_bytes, "resultados_filtrados.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xlsx_datos")

# REVISTAS
with tabs[2]:
    st.subheader("Top 20 Revistas")
    jr_col = "Journal_norm" if "Journal_norm" in dff.columns else _first_col(dff, CAND["journal"])
    if jr_col and dff[jr_col].notna().any():
        top_jr = dff[jr_col].fillna("—").value_counts().head(20).rename_axis("Journal").reset_index(name="N")
        fig_jr = px.bar(top_jr.sort_values("N"), x="N", y="Journal", orientation="h", title="Top 20 revistas")
        st.plotly_chart(fig_jr, use_container_width=True, key="fig_top_revistas")
        st.dataframe(top_jr, use_container_width=True, height=420)
    else:
        st.info("No hay columna de revista.")

# AUTORES
with tabs[3]:
    st.subheader("Top 20 Autores")
    acol = "Author Full Names" if "Author Full Names" in dff.columns else _first_col(dff, CAND["authors"])
    if acol and dff[acol].notna().any():
        s = dff[acol].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        if authors:
            top_auth = pd.Series(authors).value_counts().head(20).rename_axis("Autor").reset_index(name="N° Publicaciones")
            fig_auth = px.bar(top_auth.sort_values("N° Publicaciones"), x="N° Publicaciones", y="Autor",
                              orientation="h", title="Top 20 autores")
            st.plotly_chart(fig_auth, use_container_width=True, key="fig_top_autores")
            st.dataframe(top_auth, use_container_width=True, height=420)
        else:
            st.info("No hay autores para mostrar.")
    else:
        st.info("No hay columna de autores.")

# OA
with tabs[4]:
    st.subheader("Open Access")
    fig_oa2 = _fig_oa_pie(dff)
    if fig_oa2:
        st.plotly_chart(fig_oa2, use_container_width=True, key="fig_oa_pie_tab")
    if {"Title", "_Year", "Open Access"}.issubset(dff.columns):
        st.dataframe(dff[["Title", "_Year", "Open Access"]].dropna(how="all"), use_container_width=True, height=420)

# CITAS
with tabs[5]:
    st.subheader("Más citadas")
    if "Times Cited" in dff.columns:
        tmp = dff.copy()
        tmp["Times Cited"] = pd.to_numeric(tmp["Times Cited"], errors="coerce")
        top_cited = tmp.sort_values("Times Cited", ascending=False).head(20)
        cols_show = [c for c in ["Title", "Author Full Names", "Times Cited", "_Year", "DOI_norm"] if c in top_cited.columns]
        st.dataframe(top_cited[cols_show], use_container_width=True, height=520)
    else:
        st.info("No hay columna de citas (‘Times Cited’/‘Cited by’).")

# DEPARTAMENTOS
with tabs[6]:
    st.subheader("Publicaciones por Departamento")
    if "Departamento" in dff.columns and dff["Departamento"].notna().any():
        dep = dff["Departamento"].dropna().astype(str).str.split(r"\s*;\s*").explode()
        vc = dep.value_counts().head(20).rename_axis("Departamento").reset_index(name="N")
        fig_dep = px.bar(vc.sort_values("N"), x="N", y="Departamento", orientation="h", title="Top 20 departamentos")
        st.plotly_chart(fig_dep, use_container_width=True, key="fig_top_departamentos")
        st.dataframe(vc, use_container_width=True, height=420)
    else:
        st.info("No hay columna de ‘Departamento’.")

# WORDCLOUD (opcional)
with tabs[7]:
    st.subheader("Nube de palabras (títulos)")
    try:
        from wordcloud import WordCloud
        text = " ".join(dff.get("Title", pd.Series(dtype=str)).dropna().astype(str).tolist())
        if text.strip():
            wc = WordCloud(width=1200, height=500, background_color="white").generate(text)
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(12, 5))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig, use_container_width=True, clear_figure=True, key="fig_wc")
        else:
            st.info("No hay títulos para generar la nube.")
    except Exception:
        st.info("Para usar la nube de palabras, añade `wordcloud` a tus dependencias.")