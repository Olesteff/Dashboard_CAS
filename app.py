# app.py
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

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = None  # usa la 1ª hoja

# =========================
# Utilidades
# =========================
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _norm_text(s: object) -> str:
    if pd.isna(s):
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()

def _title_key(s: object) -> str:
    t = str(s or "").lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _coerce_bool(sr: pd.Series) -> pd.Series:
    if sr is None:
        return pd.Series([False]*0, dtype=bool)
    x = sr.astype(str).str.lower().str.strip()
    true_vals = {"1","true","t","yes","y","si","sí"}
    false_vals = {"0","false","f","no","n","nan",""}
    out = pd.Series(index=sr.index, dtype=bool)
    out.loc[x.isin(true_vals)] = True
    out.loc[x.isin(false_vals)] = False
    return out.fillna(False)

def _coerce_num(sr: pd.Series) -> pd.Series:
    try:
        return pd.to_numeric(sr, errors="coerce")
    except Exception:
        return pd.Series([np.nan]*len(sr), index=sr.index)

def _best_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for n in names:
        if n in df.columns:
            return n
    return None

def _extract_sheet_name(xlsx_path: str) -> Optional[str]:
    try:
        xl = pd.ExcelFile(xlsx_path)
        return xl.sheet_names[0] if xl.sheet_names else None
    except Exception:
        return None

# =========================
# Carga de datos
# =========================
@st.cache_data(show_spinner=False)
def load_data(uploaded=None) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=0, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        sheet = 0 if DEFAULT_SHEET is None else DEFAULT_SHEET
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet, dtype=str)
    raise FileNotFoundError(
        f"No se encontró {DEFAULT_XLSX}. Sube un XLSX desde la barra lateral."
    )

# =========================
# Normalización mínima (no borra columnas)
# =========================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str)
    # Año
    year_col = _best_col(df, ["_Year", "Year", "Publication Year", "PY"])
    if year_col:
        df["_Year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    else:
        df["_Year"] = pd.NA

    # Título
    title_col = _best_col(df, ["Title", "Document Title", "TI"])
    if title_col and "Title" not in df.columns:
        df["Title"] = df[title_col].astype(str)

    # Open Access flag
    oa_col = _best_col(df, ["OpenAccess_flag", "Open Access", "OA"])
    if oa_col:
        df["OpenAccess_flag"] = _coerce_bool(df[oa_col])
    else:
        df["OpenAccess_flag"] = False

    # Clinical trials
    ct_col = _best_col(df, ["ClinicalTrial_flag", "Clinical Trial", "Ensayo_clinico"])
    if ct_col:
        df["ClinicalTrial_flag"] = _coerce_bool(df[ct_col])
    else:
        df["ClinicalTrial_flag"] = False

    # Sponsor
    sp_col = _best_col(df, ["Has_Sponsor", "Sponsor_flag", "Sponsor"])
    if sp_col:
        df["Has_Sponsor"] = _coerce_bool(df[sp_col])
    else:
        df["Has_Sponsor"] = False

    # JIF (varios nombres posibles)
    jif_col = _best_col(df, ["JIF","JIF_2023","Impact Factor","JCR_IF","Journal Impact Factor"])
    if jif_col:
        df["_JIF_num"] = _coerce_num(df[jif_col]).fillna(0.0)
    else:
        df["_JIF_num"] = 0.0

    # Cuartil
    q_col = _best_col(df, ["quartile_std","Quartile","JCR_Quartile","SJR_Quartile","Quartile_JCR"])
    if q_col:
        q = df[q_col].astype(str).str.upper().str.strip()
        q = q.where(q.isin(["Q1","Q2","Q3","Q4"]), "Sin cuartil")
        df["quartile_std"] = q
    else:
        df["quartile_std"] = "Sin cuartil"

    # Departamento
    if "Departamento" not in df.columns:
        # intenta de listas separadas por ';' u otros
        dep_like = [c for c in df.columns if "dept" in c.lower() or "depart" in c.lower()]
        dep = None
        for c in dep_like:
            tmp = df[c].dropna().astype(str)
            if not tmp.empty:
                dep = c
                break
        if dep:
            df["Departamento"] = df[dep].astype(str)
        else:
            df["Departamento"] = "Sin asignar"
    else:
        df["Departamento"] = df["Departamento"].fillna("Sin asignar").astype(str)

    # IDs
    for name in ["DOI","DOI_norm","PMID","PMID_norm","EID"]:
        if name not in df.columns:
            df[name] = pd.NA

    # Título clave
    if "Title" in df.columns:
        df["_title_key"] = df["Title"].map(_title_key)
    else:
        df["_title_key"] = ""

    return df

# =========================
# Dedup/MatchKey por capas
# =========================
def build_match_key(df: pd.DataFrame) -> pd.Series:
    # capa 1: DOI
    if "DOI_norm" in df.columns:
        doi = df["DOI_norm"].fillna("").astype(str)
    else:
        doi = df["DOI"].fillna("").astype(str) if "DOI" in df.columns else pd.Series([""]*len(df))
    # capa 2: PMID
    pmid = df["PMID_norm"].fillna("").astype(str) if "PMID_norm" in df.columns else (df["PMID"].fillna("").astype(str) if "PMID" in df.columns else pd.Series([""]*len(df)))
    # capa 3: EID
    eid = df["EID"].fillna("").astype(str) if "EID" in df.columns else pd.Series([""]*len(df))
    # capa 4: TY (titulo normalizado + año)
    y = df["_Year"].fillna(-1).astype("Int64").astype(str)
    t = df["_title_key"].fillna("")
    ty = "TY:" + y + "|" + t

    key = doi.where(doi != "", "PMID:" + pmid)
    key = key.where(key != "PMID:", "EID:" + eid)
    key = key.where(~key.isin(["","PMID:","EID:"]), ty)
    return key

def merge_preview(old_df: pd.DataFrame, new_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str,int]]:
    # Construye claves
    old = old_df.copy()
    new = new_df.copy()
    old["_mk"] = build_match_key(old)
    new["_mk"] = build_match_key(new)

    old_set = set(x for x in old["_mk"] if isinstance(x,str) and x)
    new["_is_new"] = ~new["_mk"].isin(old_set)

    # cuenta por capas
    def layer(k: str) -> str:
        if k.startswith("10."): return "DOI"
        if k.startswith("PMID:") and len(k)>5: return "PMID"
        if k.startswith("EID:") and len(k)>4: return "EID"
        if k.startswith("TY:"): return "TY"
        return "VACÍO"

    layer_counts = new.loc[~new["_is_new"], "_mk"].map(layer).value_counts().to_dict()
    return new, layer_counts

def merge_apply(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    a = old_df.copy()
    b = new_df.copy()
    a["_mk"] = build_match_key(a)
    b["_mk"] = build_match_key(b)

    z = pd.concat([a, b], ignore_index=True, sort=False)
    z["_title_key"] = z["_title_key"].fillna("")
    z["_dedup"] = z["_mk"].fillna("") + "|" + z["_title_key"]
    z = z.drop_duplicates(subset="_dedup", keep="first").drop(columns=["_dedup"], errors="ignore")
    return z

# =========================
# Sidebar: subida base y merge
# =========================
with st.sidebar:
    st.header("Datos base")
    up = st.file_uploader("Sube un XLSX", type=["xlsx"])
    st.caption(f"Por defecto: `{DEFAULT_XLSX}` (primera hoja)")

df_raw = load_data(up)
df = normalize_columns(df_raw)

# Módulo de merge
with st.sidebar:
    st.markdown("---")
    st.header("Actualizar dataset (merge)")
    new_files = st.file_uploader("Nuevos CSV/XLSX (se deduplican)", type=["csv","xlsx"], accept_multiple_files=True)
    btn_prev = st.button("👀 Previsualizar unión")
    btn_apply = st.button("✅ Aplicar actualización", type="primary")
    save_over = st.checkbox("Sobrescribir archivo base al aplicar", value=False)

if new_files:
    new_tables = []
    for f in new_files:
        try:
            if f.name.lower().endswith(".csv"):
                new_tables.append(pd.read_csv(f, dtype=str))
            else:
                new_tables.append(pd.read_excel(f, dtype=str))
        except Exception:
            pass
    new_df = pd.concat(new_tables, ignore_index=True, sort=False) if new_tables else pd.DataFrame()
else:
    new_df = pd.DataFrame()

if not new_df.empty and btn_prev:
    prev, lc = merge_preview(df, normalize_columns(new_df))
    n_new = int(prev["_is_new"].sum())
    n_dup = int(len(prev) - n_new)
    st.sidebar.success(f"Vista previa: **{n_new}** nuevos · **{n_dup}** duplicados.")
    st.sidebar.write("Cruces por capa:", lc)

if not new_df.empty and btn_apply:
    merged = merge_apply(df, normalize_columns(new_df))
    st.sidebar.success(f"Unión aplicada. Registros ahora: {len(merged):,}")
    if save_over and Path(DEFAULT_XLSX).exists():
        try:
            merged.to_excel(DEFAULT_XLSX, index=False)
            st.sidebar.success(f"Sobrescrito `{DEFAULT_XLSX}`.")
        except Exception as e:
            st.sidebar.error(f"No se pudo sobrescribir: {e}")
    # usa merged en sesión
    df = merged

# =========================
# Filtros
# =========================
with st.sidebar:
    st.header("Filtros")
    # Años
    if df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int)
        lo, hi = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Selecciona rango de años", lo, hi, (lo, hi))
    else:
        y1, y2 = (0, 9999)

    # OA
    oa_choice = st.radio("Open Access", ["Todos","Solo Open Access","Solo Closed Access"], index=0)

    # Cuartiles
    qs = ["Q1","Q2","Q3","Q4","Sin cuartil"]
    sel_q = st.multiselect("Cuartil JCR/SJR", qs, default=qs)

    # Departamentos
    dep_pool = (
        df["Departamento"]
        .fillna("Sin asignar")
        .astype(str)
        .str.split(r"\s*;\s*")
        .explode()
        .dropna()
        .unique()
        .tolist()
    )
    dep_pool = sorted([d for d in dep_pool if d])
    dep_sel = st.multiselect("Departamento", dep_pool, default=[])

    # Búsqueda título
    qtxt = st.text_input("Buscar en título", "")

mask = pd.Series(True, index=df.index)

# años
mask &= df["_Year"].fillna(-1).astype(int).between(y1, y2)

# OA
if oa_choice == "Solo Open Access":
    mask &= df["OpenAccess_flag"]
elif oa_choice == "Solo Closed Access":
    mask &= ~df["OpenAccess_flag"]

# Cuartiles
if sel_q:
    mask &= df["quartile_std"].isin(sel_q)

# Departamentos
if dep_sel:
    patt = "|".join(re.escape(x) for x in dep_sel)
    mask &= df["Departamento"].fillna("").str.contains(patt)

# Búsqueda
if qtxt and "Title" in df.columns:
    mask &= df["Title"].fillna("").str.contains(qtxt, case=False, na=False)

dff = df.loc[mask].copy()

# =========================
# KPIs
# =========================
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total publicaciones", f"{len(dff):,}")

pct_oa = (dff["OpenAccess_flag"].mean() * 100) if len(dff) else 0.0
c2.metric("% Open Access", f"{pct_oa:.1f}%")

sum_jif = float(dff["_JIF_num"].sum()) if "_JIF_num" in dff.columns else 0.0
c3.metric("⭐ Suma total JIF", f"{sum_jif:,.1f}")

n_ct = int(dff["ClinicalTrial_flag"].sum()) if "ClinicalTrial_flag" in dff.columns else 0
c4.metric("🧪 Ensayos clínicos detectados", f"{n_ct:,}")

n_sp = int(dff["Has_Sponsor"].sum()) if "Has_Sponsor" in dff.columns else 0
c5.metric("🤝 Publicaciones con sponsor", f"{n_sp:,}")

# =========================
# Tabs
# =========================
tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos", "📚 Revistas", "👤 Autores", "☁️ Nube de palabras"])

# 1) Publicaciones
with tabs[0]:
    st.subheader("Publicaciones por año")
    if dff["_Year"].notna().any():
        g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
        fig = px.bar(x=g.index, y=g.values, labels={"x":"Year","y":"Publicaciones"}, title="Conteo por año")
        st.plotly_chart(fig, use_container_width=True, key="pubs_year")
    st.dataframe(dff.head(1000), use_container_width=True, height=420)
    # descarga
    xbuf = BytesIO()
    dff.to_csv(xbuf, index=False)
    st.download_button("⬇️ CSV filtrado", xbuf.getvalue(), file_name="resultados_filtrados.csv", mime="text/csv")

# 2) Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil")
    cts = dff["quartile_std"].value_counts()
    if not cts.empty:
        fig = px.pie(names=cts.index, values=cts.values, hole=0.5, title="Cuartiles")
        st.plotly_chart(fig, use_container_width=True, key="quart_pie")
        st.dataframe(cts.rename_axis("Cuartil").reset_index(name="Publicaciones"), use_container_width=True, height=360)
    else:
        st.info("Sin datos de cuartil.")

# 3) OA
with tabs[2]:
    st.subheader("Distribución Open Access")
    s = dff["OpenAccess_flag"].map({True:"Open Access", False:"Closed Access"}).value_counts()
    if not s.empty:
        fig = px.pie(names=s.index, values=s.values, hole=0.5, title="% OA vs Closed")
        st.plotly_chart(fig, use_container_width=True, key="oa_pie")
        st.dataframe(s.rename_axis("Estado").reset_index(name="Publicaciones"), use_container_width=True, height=360)
    else:
        st.info("No hay columna OpenAccess_flag.")

# 4) Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    s = dff["Departamento"].fillna("Sin asignar").astype(str)
    s = s.str.split(r"\s*;\s*").explode().value_counts()
    if not s.empty:
        fig = px.bar(s.sort_values(), orientation="h", title="Top departamentos")
        st.plotly_chart(fig, use_container_width=True, key="dep_bar")
        st.dataframe(s.rename_axis("Departamento").reset_index(name="Publicaciones"), use_container_width=True, height=420)
    else:
        st.info("No hay columna de Departamento.")

# 5) Revistas
with tabs[4]:
    st.subheader("Top revistas")
    jr_col = _best_col(dff, ["Journal_norm","Journal","Source Title","Publication Name"])
    if jr_col:
        s = dff[jr_col].fillna("—").value_counts().head(30)
        fig = px.bar(s.sort_values(), orientation="h", title="Top revistas (30)")
        st.plotly_chart(fig, use_container_width=True, key="jr_bar")
        st.dataframe(s.rename_axis("Revista").reset_index(name="Publicaciones"), use_container_width=True, height=420)
    else:
        st.info("No hay columna de revista.")

# 6) Autores
with tabs[5]:
    st.subheader("Top autores")
    a_col = _best_col(dff, ["Author Full Names","Author full names","Authors"])
    if a_col:
        s = dff[a_col].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        if authors:
            vc = pd.Series(authors).value_counts().head(30)
            fig = px.bar(vc.sort_values(), orientation="h", title="Top autores (30)")
            st.plotly_chart(fig, use_container_width=True, key="auth_bar")
            st.dataframe(vc.rename_axis("Autor").reset_index(name="Publicaciones"), use_container_width=True, height=420)
        else:
            st.info("No hay autores parseables.")
    else:
        st.info("No hay columna de autores.")

# 7) Nube de palabras (opcional si está instalado 'wordcloud')
with tabs[6]:
    st.subheader("Nube de palabras (títulos)")
    try:
        from wordcloud import WordCloud
        text = " ".join(dff.get("Title", pd.Series(dtype=str)).dropna().astype(str).tolist())
        if text.strip():
            wc = WordCloud(width=1200, height=500, background_color="white").generate(text)
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10,4))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig, use_container_width=True, clear_figure=True)
        else:
            st.info("No hay títulos para construir la nube.")
    except Exception:
        st.info("Instala `wordcloud` para ver esta pestaña:  `pip install wordcloud`")

# =========================
# Suma de JIF por año (abajo del todo para evitar IDs duplicados)
# =========================
st.markdown("---")
st.subheader("Suma de JIF por año")
if "_JIF_num" in dff.columns and dff["_Year"].notna().any():
    j = (
        dff.dropna(subset=["_Year"])
           .assign(_Year=dff["_Year"].astype(int))
           .groupby("_Year")["_JIF_num"].sum()
           .sort_index()
    )
    fig = px.line(x=j.index, y=j.values, labels={"x":"Year","y":"Suma JIF"})
    st.plotly_chart(fig, use_container_width=True, key="jif_line")
else:
    st.info("No hay datos suficientes para calcular suma de JIF por año.")