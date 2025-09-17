# app.py
# Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================================
# Config general
# =========================================
st.set_page_config(
    page_title="Dashboard Producción Científica CAS-UDD",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

TITLE = "Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo"
DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"  # 1ª hoja

# Candidatos de columnas
CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["_Year", "Year", "Publication Year", "PY"],
    "doi": ["DOI", "Doi"],
    "pmid": ["PMID_norm", "PMID", "PubMed ID"],
    "eid": ["EID", "Scopus EID"],
    "journal": ["Journal_norm", "Source Title", "Publication Name", "Journal"],
    "authors": ["Author Full Names", "Author full names", "Authors"],
    "oa_flag": ["OpenAccess_flag", "Open Access", "OA", "OA_flag"],
    "quartile": ["Quartile_std", "Quartile", "JCR Quartile", "SJR Quartile"],
    "jif": ["JIF", "Journal Impact Factor", "JCR IF", "Impact Factor"],
    "dept": ["Departamento", "Dept_CAS_list", "Dept_FMUDD_list", "Department"],
    "clinical": ["ClinicalTrial_flag", "ClinicalTrial", "Ensayo_clínico"],
    "sponsor": ["Has_Sponsor", "Sponsor_flag", "Sponsor"],
    "affils": ["Affiliations", "Authors with affiliations", "Author Affiliations"],
}

def _first(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for c in names:
        if c in df.columns:
            return c
    return None

def _norm_bool_series(s: pd.Series) -> pd.Series:
    """Normaliza a boolean: True/False, tolera strings/num/nan."""
    if s is None:
        return pd.Series(False, index=pd.RangeIndex(0))
    x = s.astype(str).str.lower().str.strip()
    true_vals = {"1","true","t","yes","y","si","sí"}
    false_vals = {"0","false","f","no","n"}
    out = pd.Series(index=s.index, dtype=bool)
    out.loc[x.isin(true_vals)] = True
    out.loc[x.isin(false_vals)] = False
    out = out.fillna(False)
    # si son números (0/1) reconocibles
    try:
        out = s.astype(float).fillna(0).astype(int).astype(bool)
    except Exception:
        pass
    return out.fillna(False)

def _split_semicolon_series(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
         .fillna("")
         .replace({"nan": ""})
         .str.split(r"\s*;\s*")
    )

def _xlsx_bytes(df: pd.DataFrame, sheet: str = "Datos") -> Optional[bytes]:
    for engine in ("xlsxwriter", "openpyxl"):
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as w:
                df.to_excel(w, index=False, sheet_name=sheet)
            buf.seek(0)
            return buf.getvalue()
        except Exception:
            continue
    return None

# =========================================
# Carga base (cache)
# =========================================
@st.cache_data(show_spinner=False)
def load_data(uploaded: Optional[BytesIO]) -> pd.DataFrame:
    """Lee XLSX (1ª hoja). Si no suben nada, usa DEFAULT_XLSX."""
    if uploaded is not None:
        df = pd.read_excel(uploaded, dtype=str)
    else:
        df = pd.read_excel(DEFAULT_XLSX, dtype=str)
    # limpiar duplicados de nombres
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]
    return df

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nombres/formatos mínimos que usa el dashboard."""
    df = df.copy()

    # Year
    ycol = _first(df, CAND["year"])
    if ycol and ycol != "_Year":
        df["_Year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")
    elif not ycol:
        df["_Year"] = pd.Series(pd.NA, index=df.index, dtype="Int64")

    # Title
    tcol = _first(df, CAND["title"])
    if tcol and tcol != "Title":
        df["Title"] = df[tcol]

    # OA flag (boolean)
    ocol = _first(df, CAND["oa_flag"])
    if ocol:
        df["OpenAccess_flag"] = _norm_bool_series(df[ocol])
    else:
        df["OpenAccess_flag"] = False

    # Quartile_std
    qcol = _first(df, CAND["quartile"])
    if qcol and qcol != "Quartile_std":
        df["Quartile_std"] = df[qcol]
    if "Quartile_std" in df.columns:
        df["Quartile_std"] = (
            df["Quartile_std"]
            .fillna("")
            .replace({"nan": ""})
            .str.upper()
            .str.extract(r"(Q[1-4])", expand=False)
            .fillna("Sin cuartil")
        )
    else:
        df["Quartile_std"] = "Sin cuartil"

    # JIF
    jcol = _first(df, CAND["jif"])
    if jcol and jcol != "JIF":
        df["JIF"] = df[jcol]
    if "JIF" in df.columns:
        df["JIF"] = pd.to_numeric(df["JIF"], errors="coerce")
    else:
        df["JIF"] = np.nan

    # Departamento
    dcol = _first(df, CAND["dept"])
    if dcol and dcol != "Departamento":
        df["Departamento"] = df[dcol]
    if "Departamento" not in df.columns:
        # fallback: intenta detectar desde affiliations de forma muy simple
        acol = _first(df, CAND["affils"])
        if acol:
            def _dept_guess(s: str) -> str:
                s = str(s).lower()
                if "neurolog" in s or "psiquiatr" in s:
                    return "Neurología y Psiquiatría"
                if "oncolog" in s:
                    return "Oncología"
                if "pediatr" in s:
                    return "Pediatría"
                if "gineco" in s or "obstetri" in s:
                    return "Ginecología y Obstetricia"
                if "dermato" in s:
                    return "Dermatología"
                if "traumato" in s or "ortopedia" in s:
                    return "Traumatología y Ortopedia"
                if "imagen" in s or "radiolog" in s:
                    return "Imágenes"
                if "anatom" in s or "patolog" in s or "banco de sangre" in s or "laboratorio" in s:
                    return "Laboratorio, Banco de Sangre y Anatomía Patológica"
                if "clínica alemana" in s:
                    return "Clínica Alemana (General)"
                return "Sin asignar"
            df["Departamento"] = df[acol].map(_dept_guess)
        else:
            df["Departamento"] = "Sin asignar"

    # Clinical / Sponsor
    ccol = _first(df, CAND["clinical"])
    if ccol and ccol != "ClinicalTrial_flag":
        df["ClinicalTrial_flag"] = _norm_bool_series(df[ccol])
    elif "ClinicalTrial_flag" in df.columns:
        df["ClinicalTrial_flag"] = _norm_bool_series(df["ClinicalTrial_flag"])
    else:
        df["ClinicalTrial_flag"] = False

    scol = _first(df, CAND["sponsor"])
    if scol and scol != "Has_Sponsor":
        df["Has_Sponsor"] = _norm_bool_series(df[scol])
    elif "Has_Sponsor" in df.columns:
        df["Has_Sponsor"] = _norm_bool_series(df["Has_Sponsor"])
    else:
        df["Has_Sponsor"] = False

    # Journal
    jn = _first(df, CAND["journal"])
    if jn and jn != "Journal_norm":
        df["Journal_norm"] = df[jn]

    # Authors
    an = _first(df, CAND["authors"])
    if an and an != "Author Full Names":
        df["Author Full Names"] = df[an]

    return df

# =========================================
# Sidebar: carga + merge + filtros
# =========================================
st.sidebar.header("Datos base")
up = st.sidebar.file_uploader("Sube un XLSX (usa la 1ª hoja)", type=["xlsx"])
df_raw = load_data(up)
df = normalize(df_raw)

# --- Módulo de actualización/merge ---
st.sidebar.markdown("---")
st.sidebar.subheader("Actualizar dataset (merge)")
new_files = st.sidebar.file_uploader("Nuevos CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=True)
colA, colB = st.sidebar.columns(2)
btn_prev = colA.button("👀 Previsualizar")
btn_apply = colB.button("✅ Aplicar")
save_over = st.sidebar.checkbox("Sobrescribir archivo base al aplicar", value=False)

def _read_any(file_obj) -> pd.DataFrame:
    name = (getattr(file_obj, "name", "") or "").lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(file_obj, dtype=str)
        return pd.read_excel(file_obj, dtype=str)
    except Exception:
        return pd.DataFrame()

def _title_key(s: str) -> str:
    s = str(s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _build_key(df_like: pd.DataFrame) -> pd.Series:
    # key por DOI, PMID, EID, o (Title+Year)
    parts = []
    if "DOI" in df_like.columns:
        parts.append(df_like["DOI"].fillna("").str.lower())
    if "PMID_norm" in df_like.columns:
        parts.append("PMID:" + df_like["PMID_norm"].fillna(""))
    if "EID" in df_like.columns:
        parts.append("EID:" + df_like["EID"].fillna("").astype(str))
    ycol = _first(df_like, CAND["year"])
    tcol = _first(df_like, CAND["title"])
    if ycol and tcol:
        y = pd.to_numeric(df_like[ycol], errors="coerce").fillna(-1).astype(int).astype(str)
        t = df_like[tcol].map(_title_key).fillna("")
        parts.append("TY:" + y + "|" + t)
    if not parts:
        return pd.Series("", index=df_like.index, dtype="object")
    key = parts[0].astype(str)
    for p in parts[1:]:
        key = key.where(key.astype(bool), p.astype(str))
    return key

# Vista previa / Aplicar merge
if new_files:
    news = []
    for f in new_files:
        t = _read_any(f)
        if not t.empty:
            news.append(normalize(t))
    new_df = pd.concat(news, ignore_index=True, sort=False) if news else pd.DataFrame()

    if not new_df.empty:
        base_keys = _build_key(df)
        base_set = set([k for k in base_keys if isinstance(k, str) and k])
        cand_keys = _build_key(new_df)
        is_new = cand_keys.map(lambda k: (isinstance(k, str) and (k not in base_set) and k != ""))

        if btn_prev:
            st.sidebar.info(f"Vista previa: {int(is_new.sum())} nuevos · {int(len(new_df)-int(is_new.sum()))} duplicados.")
            cols = [c for c in ["Title","_Year","DOI","PMID_norm","EID"] if c in new_df.columns]
            st.sidebar.dataframe(new_df.loc[is_new, cols].head(120), height=300, use_container_width=True)

        if btn_apply:
            merged = pd.concat([df, new_df], ignore_index=True, sort=False)
            merged["_dkey"] = _build_key(merged)
            before = len(merged)
            merged = merged.drop_duplicates(subset="_dkey", keep="first").drop(columns=["_dkey"], errors="ignore")
            st.success(f"Actualizado: +{len(merged)-len(df)} registros nuevos. Total {len(merged):,}")
            # persistir en sesión y como XLSX
            st.session_state["__df__"] = merged
            xbytes = _xlsx_bytes(merged, sheet="Consolidado_enriq")
            if xbytes:
                st.sidebar.download_button(
                    "⬇️ Descargar dataset ACTUALIZADO (XLSX)",
                    xbytes,
                    "dataset_actualizado.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_updated"
                )
            if save_over and Path(DEFAULT_XLSX).exists():
                try:
                    merged.to_excel(DEFAULT_XLSX, index=False)
                    st.sidebar.success(f"Se sobrescribió {DEFAULT_XLSX}.")
                except Exception as e:
                    st.sidebar.error(f"No se pudo sobrescribir: {e}")

# Si ya hay actualizado en sesión, úsalo
if "__df__" in st.session_state:
    df = st.session_state["__df__"]

# =========================================
# Filtros
# =========================================
st.sidebar.markdown("---")
st.sidebar.header("Filtros")

# Rango de años (no parte en 0)
if "_Year" in df.columns and df["_Year"].notna().any():
    ys = df["_Year"].dropna().astype(int)
    y_min, y_max = int(ys.min()), int(ys.max())
    y1, y2 = st.sidebar.slider("Selecciona rango de años", y_min, y_max, (y_min, y_max))
else:
    y1, y2 = (None, None)

# Open Access (True/False desde OpenAccess_flag)
oa_mode = st.sidebar.radio(
    "Open Access",
    options=["Todos", "Solo Open Access", "Solo Closed Access"],
    index=0,
    horizontal=False
)

# Filtro cuartil
quartile_vals = ["Q1","Q2","Q3","Q4","Sin cuartil"]
sel_quart = st.sidebar.multiselect("Cuartil JCR/SJR", quartile_vals, default=quartile_vals)

# Departamento
if "Departamento" in df.columns:
    dep_pool = (
        df["Departamento"].fillna("")
          .astype(str)
          .str.split(r"\s*;\s*").explode().dropna()
    )
    dep_opts = sorted(set([x for x in dep_pool if x != ""]))
else:
    dep_opts = []
sel_dep = st.sidebar.multiselect("Departamento", dep_opts, default=[])

# Buscar en título
query = st.sidebar.text_input("Buscar en título", "")

# Construir máscara
mask = pd.Series(True, index=df.index)
if y1 is not None and y2 is not None:
    mask &= df["_Year"].astype(float).between(y1, y2)

# OA
if oa_mode == "Solo Open Access":
    mask &= df["OpenAccess_flag"].fillna(False)
elif oa_mode == "Solo Closed Access":
    mask &= ~df["OpenAccess_flag"].fillna(False)

# Cuartil
if "Quartile_std" in df.columns:
    mask &= df["Quartile_std"].fillna("Sin cuartil").isin(sel_quart)

# Departamento
if sel_dep and "Departamento" in df.columns:
    rgx = "|".join(map(re.escape, sel_dep))
    mask &= df["Departamento"].fillna("").str.contains(rgx)

# Título
tcol = _first(df, CAND["title"]) or "Title"
if query and tcol in df.columns:
    mask &= df[tcol].fillna("").str.contains(query, case=False, na=False)

dff = df.loc[mask].copy()

# =========================================
# Título + KPIs
# =========================================
st.title(TITLE)

k1, k2, k3, k4 = st.columns(4)
total = len(dff)
k1.metric("🧾 Total publicaciones", f"{total:,}")

# % OA
pct_oa = (dff["OpenAccess_flag"].sum() / len(dff) * 100) if len(dff) else 0
k2.metric("🔐 % Open Access", f"{pct_oa:.1f}%")

# Suma total JIF (numérico)
jif_total = pd.to_numeric(dff.get("JIF", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
k3.metric("⭐ Suma total JIF", f"{jif_total:,.1f}")

# Ensayos clínicos y sponsor si existen
n_trials = int(_norm_bool_series(dff.get("ClinicalTrial_flag", pd.Series(False))).sum())
n_sponsor = int(_norm_bool_series(dff.get("Has_Sponsor", pd.Series(False))).sum())
k4.metric("🩺 Ensayos clínicos (flag) / 🏷 Sponsor", f"{n_trials:,} / {n_sponsor:,}")

# =========================================
# Tabs
# =========================================
tabs = st.tabs([
    "📈 Publicaciones",
    "📊 Cuartiles",
    "🔓 Open Access",
    "🏥 Departamentos",
    "📚 Revistas",
    "🧑‍🔬 Autores",
    "☁️ Nube de palabras",
    "⭐ JIF",
])

# --- Publicaciones (por año)
with tabs[0]:
    st.subheader("Publicaciones por año")
    if "_Year" in dff.columns and dff["_Year"].notna().any():
        g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
        fig = px.bar(x=g.index, y=g.values, labels={"x":"Year","y":"Publicaciones"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de año.")
    # Descargas
    csv_bytes = dff.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ CSV — Resultados filtrados", csv_bytes, "resultados_filtrados.csv", "text/csv", key="dl_pub_csv")
    xbytes = _xlsx_bytes(dff, "Filtrados")
    if xbytes:
        st.download_button("⬇️ XLSX — Resultados filtrados", xbytes,
                           "resultados_filtrados.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_pub_xlsx")

# --- Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil")
    q = dff["Quartile_std"].fillna("Sin cuartil")
    if not q.empty:
        vc = q.value_counts()
        fig = px.pie(names=vc.index, values=vc.values, hole=0.5)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(vc.rename_axis("Cuartil").reset_index(name="Publicaciones"),
                     use_container_width=True, height=360)
    else:
        st.info("No hay columna de cuartil.")

# --- Open Access
with tabs[2]:
    st.subheader("Distribución Open Access (flag)")
    if "OpenAccess_flag" in dff.columns:
        vc = dff["OpenAccess_flag"].map({True:"Open Access", False:"Closed Access"}).value_counts()
        fig = px.pie(names=vc.index, values=vc.values, hole=0.5)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(vc.rename_axis("OA").reset_index(name="Publicaciones"),
                     use_container_width=True, height=320)
    else:
        st.info("No hay columna OpenAccess_flag.")

# --- Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    if "Departamento" in dff.columns and dff["Departamento"].notna().any():
        top = dff["Departamento"].fillna("Sin asignar").value_counts().head(20)
        fig = px.bar(top.sort_values(), x=top.sort_values().values, y=top.sort_values().index,
                     orientation="h", labels={"x":"Publicaciones","y":"Departamento"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(top.rename_axis("Departamento").reset_index(name="Publicaciones"),
                     use_container_width=True, height=360)
    else:
        st.info("No hay columna Departamento.")

# --- Revistas
with tabs[4]:
    st.subheader("Top revistas")
    jn = _first(dff, CAND["journal"]) or "Journal_norm"
    if jn in dff.columns:
        top = dff[jn].fillna("—").value_counts().head(20)
        fig = px.bar(top.sort_values(), x=top.sort_values().values, y=top.sort_values().index,
                     orientation="h", labels={"x":"Publicaciones","y":"Revista"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(top.rename_axis("Revista").reset_index(name="Publicaciones"),
                     use_container_width=True, height=360)
    else:
        st.info("No hay columna de revista.")

# --- Autores
with tabs[5]:
    st.subheader("Top autores")
    acol = _first(dff, CAND["authors"]) or "Author Full Names"
    if acol in dff.columns:
        s = _split_semicolon_series(dff[acol])
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        if authors:
            top = pd.Series(authors).value_counts().head(20)
            fig = px.bar(top.sort_values(), x=top.sort_values().values, y=top.sort_values().index,
                         orientation="h", labels={"x":"Publicaciones","y":"Autor"})
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(top.rename_axis("Autor").reset_index(name="Publicaciones"),
                         use_container_width=True, height=360)
        else:
            st.info("No se pudieron parsear autores.")
    else:
        st.info("No hay columna de autores.")

# --- Nube de palabras (títulos)
with tabs[6]:
    st.subheader("Nube de palabras (títulos)")
    try:
        from wordcloud import WordCloud
        text = " ".join([str(x) for x in dff.get("Title", pd.Series(dtype=str)).dropna().tolist()])
        if text.strip():
            wc = WordCloud(width=1200, height=500, background_color="white").generate(text)
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10,4))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig, use_container_width=True)
        else:
            st.info("No hay títulos para generar la nube.")
    except Exception:
        st.info("Para la nube instala `wordcloud` (opcional).")

# --- JIF
with tabs[7]:
    st.subheader("Suma de JIF por año")
    if "JIF" in dff.columns and "_Year" in dff.columns:
        tmp = dff.copy()
        tmp["JIF"] = pd.to_numeric(tmp["JIF"], errors="coerce").fillna(0)
        tmp["_Year"] = pd.to_numeric(tmp["_Year"], errors="coerce")
        g = tmp.groupby(tmp["_Year"]).agg(JIF_sum=("JIF","sum")).reset_index()
        g = g.dropna(subset=["_Year"])
        if not g.empty:
            fig = px.line(g.sort_values("_Year"), x="_Year", y="JIF_sum", markers=True,
                          labels={"_Year":"Year", "JIF_sum":"Suma JIF"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay valores de JIF para graficar.")
    else:
        st.info("No hay columnas JIF/_Year en los datos.")