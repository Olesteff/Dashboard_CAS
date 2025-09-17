# /app/app.py
# Dashboard Cienciométrico — 1ª hoja XLSX, WordCloud, Cuartiles (con mapeo externo), KPIs y gráficos — keys únicas

from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =============================
# Config
# =============================
st.set_page_config(page_title="Dashboard Cienciométrico", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = 0  # 1ª hoja siempre
DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)

CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "_Year", "Year_clean"],
    "doi": ["DOI", "Doi"],
    "link": ["Link", "URL", "Full Text URL"],
    "journal": ["Journal_norm", "Source title", "Source Title", "Publication Name", "Journal", "Source Title"],
    "dept": ["Departamento", "Dept_CAS_list", "Dept_FMUDD_list", "Department"],
    "authors": ["Author full names", "Author Full Names", "Authors"],
    "cited": ["Cited by", "Times Cited", "TimesCited"],
    "pmid": ["PubMed ID", "PMID"],
    "wos": ["Web of Science Record", "Unique WOS ID", "UT (Unique WOS ID)"],
    "eid": ["EID", "Scopus EID"],
    "oa_flags": ["OpenAccess_flag", "OA_Scopus", "OA_WoS", "OA_PubMed", "OA"],
}

# =============================
# Helpers UI — keys únicas
# =============================
def ukey(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"

def show_plot(fig, name: str):
    st.plotly_chart(fig, use_container_width=True, key=ukey(f"plt_{name}"))

def dl_button(label: str, data: bytes, file_name: str, mime: str = "", name: str = "dl"):
    st.download_button(label, data, file_name=file_name, mime=mime or "application/octet-stream", key=ukey(f"btn_{name}"))

# =============================
# Utils datos/texto
# =============================
def _first_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for c in names:
        if c in df.columns:
            return c
    return None

def _extract_doi(val: object) -> Optional[str]:
    if pd.isna(val): return None
    m = DOI_REGEX.search(str(val)); return m.group(0).lower() if m else None

def _norm_text(s: object) -> str:
    if pd.isna(s): return ""
    t = str(s).strip()
    return re.sub(r"\s+", " ", t)

def _title_key(s: object) -> str:
    if pd.isna(s): return ""
    t = re.sub(r"[^A-Za-z0-9 ]", " ", str(s).lower())
    return re.sub(r"\s+", " ", t).strip()

def _bool_from_str_series(s: pd.Series) -> pd.Series:
    if s is None: return pd.Series(False, index=pd.RangeIndex(0))
    x = s.astype(str).str.lower().str.strip()
    true_vals = {"1","true","t","yes","y","si","sí"}; false_vals = {"0","false","f","no","n",""}
    out = pd.Series(index=x.index, dtype=bool)
    out.loc[x.isin(true_vals)] = True; out.loc[x.isin(false_vals)] = False
    return out.fillna(False)

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    for engine in ("xlsxwriter","openpyxl"):
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as w: df.to_excel(w, index=False, sheet_name=sheet_name)
            buf.seek(0); return buf.getvalue()
        except Exception: continue
    return None

def _plotly_png(fig) -> Optional[bytes]:
    try:
        buf = BytesIO(); fig.write_image(buf, format="png", scale=3); buf.seek(0); return buf.getvalue()
    except Exception:
        return None

# =============================
# WordCloud
# =============================
def _strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")

def build_stopwords(extra_csv: str = "") -> set:
    en = {"a","an","the","and","or","but","if","then","else","for","to","of","in","on","at","by","with","from","as",
          "is","are","was","were","be","been","being","it","its","this","that","these","those","we","you","they","i",
          "he","she","them","his","her","their","our","us","my","your","not","no","yes","do","does","did","done",
          "can","could","may","might","must","should","would","will","there","here","than","also","et","al"}
    es = {"el","la","los","las","un","una","unos","unas","y","o","u","pero","si","entonces","sino","como","de","del",
          "en","con","por","para","a","al","que","se","su","sus","es","son","fue","fueron","ser","ha","han","hay",
          "este","esta","estos","estas","eso","esa","esos","esas","lo"}
    extras = {w.strip().lower() for w in extra_csv.split(",") if w.strip()}
    short = set([chr(c) for c in range(ord('a'), ord('z')+1)]) | {"de","el","la","los","las","y","o","u","en","al","si","no"}
    return en | es | extras | short

def tokenize_titles(series: pd.Series, min_len: int, stop: set, bigrams: bool = False) -> Counter:
    cnt: Counter = Counter()
    for raw in series.dropna().astype(str):
        t = _strip_accents(raw.lower())
        t = re.sub(r"[^a-z0-9 ]+", " ", t)
        words = [w for w in t.split() if len(w) >= min_len and w not in stop]
        if not words: continue
        cnt.update(words)
        if bigrams and len(words) >= 2:
            cnt.update([f"{words[i]} {words[i+1]}" for i in range(len(words)-1)])
    return cnt

def wordcloud_png(freq: Dict[str, int], width: int = 1600, height: int = 900) -> Optional[bytes]:
    try:
        from wordcloud import WordCloud
        wc = WordCloud(width=width, height=height, background_color="white",
                       collocations=False, normalize_plurals=False, prefer_horizontal=0.9, random_state=42)
        img = wc.generate_from_frequencies(freq).to_image()
        buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0); return buf.getvalue()
    except Exception:
        return None

# =============================
# Carga (1ª hoja)
# =============================
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded, sheet_name=DEFAULT_SHEET) -> pd.DataFrame:
    if uploaded is not None: return pd.read_excel(uploaded, sheet_name=sheet_name, dtype=str)
    if Path(DEFAULT_XLSX).exists(): return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name, dtype=str)
    raise FileNotFoundError(f"No se encontró {DEFAULT_XLSX}. Sube el XLSX desde la barra lateral.")

# =============================
# Normalización base
# =============================
def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]

    ycol = _first_col(df, CAND["year"])
    if ycol: df["_Year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")

    tcol = _first_col(df, CAND["title"])
    if tcol and tcol != "Title": df["Title"] = df[tcol].astype(str)

    dcol = _first_col(df, CAND["doi"]); lcol = _first_col(df, CAND["link"])
    doi_base = df[dcol].astype(str).str.strip().str.lower() if dcol else pd.Series(np.nan, index=df.index)
    doi_from_link = df[lcol].astype(str).map(_extract_doi) if lcol else pd.Series(np.nan, index=df.index)
    df["DOI_norm"] = doi_base.where(doi_base.notna() & (doi_base != ""), doi_from_link)

    jcol = _first_col(df, CAND["journal"])
    if jcol: df["Journal_norm"] = df[jcol].map(_norm_text)

    dpt = _first_col(df, CAND["dept"])
    if dpt: df["Departamento"] = df[dpt]

    acol = _first_col(df, CAND["authors"])
    if acol and acol != "Author Full Names": df["Author Full Names"] = df[acol]

    ccol = _first_col(df, CAND["cited"])
    if ccol and ccol != "Times Cited": df["Times Cited"] = pd.to_numeric(df[ccol], errors="coerce")

    pmid_col = _first_col(df, CAND["pmid"])
    if pmid_col and "PMID_norm" not in df.columns:
        df["PMID_norm"] = df[pmid_col].astype(str).str.replace(r"\D+", "", regex=True).replace("", np.nan)

    eid_col = _first_col(df, CAND["eid"])
    if eid_col and "EID" not in df.columns: df["EID"] = df[eid_col].astype(str)

    df["in_PubMed"] = df[pmid_col].notna() if pmid_col else False
    df["in_WoS"] = df[_first_col(df, CAND["wos"])].notna() if _first_col(df, CAND["wos"]) else False
    df["in_Scopus"] = False
    if "Times Cited" in df.columns: df["in_Scopus"] = df["Times Cited"].notna()
    if "OA_Scopus" in df.columns: df["in_Scopus"] = df["in_Scopus"] | df["OA_Scopus"].notna()

    # Cuartil (por defecto: sin datos hasta enriquecer)
    if "Quartile" not in df.columns: df["Quartile"] = "Sin cuartil"

    # ISSN normalizado auxiliar
    for c in ["ISSN_key", "ISSN", "eISSN"]:
        if c in df.columns:
            df["ISSN_key"] = df[c]
            break
    if "ISSN_key" in df.columns:
        df["ISSN_key"] = df["ISSN_key"].astype(str).str.replace(r"\D", "", regex=True).str.slice(0, 8)
        df["ISSN_key"] = df["ISSN_key"].where(df["ISSN_key"].str.len() == 8, np.nan)

    return df

# =============================
# Cuartiles — mapeo externo
# =============================
def _issn_norm(s: object) -> str:
    if pd.isna(s): return ""
    digits = re.sub(r"\D", "", str(s))
    return digits[:8] if len(digits) >= 8 else ""

def _pick_quartile_col(df_map: pd.DataFrame) -> Optional[str]:
    # prioridad por nombre, si no por contenido tipo Q1..Q4
    name_hit = [c for c in df_map.columns if re.search(r"quart|cuart", str(c), re.I)]
    if name_hit: return name_hit[0]
    content_hits = []
    for c in df_map.columns:
        s = df_map[c].astype(str).str.upper()
        rate = s.str.contains(r"\bQ[1-4]\b").mean()
        if rate > 0.02:
            content_hits.append((c, rate))
    return max(content_hits, key=lambda x: x[1])[0] if content_hits else None

def _pick_journal_col(df_map: pd.DataFrame) -> Optional[str]:
    for c in df_map.columns:
        if re.search(r"^journal|source\s*title|revista|journal\s*name", str(c), re.I):
            return c
    return None

def enrich_quartiles(base: pd.DataFrame, df_map: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Devuelve (df_enriquecido, n_enriquecidas). Prefiere match por ISSN; fallback por nombre de revista."""
    out = base.copy()

    qcol = _pick_quartile_col(df_map)
    if not qcol:
        return out, 0

    # Normalizar cuartil y llaves
    dfm = df_map.copy()
    dfm[qcol] = dfm[qcol].astype(str).str.upper().str.extract(r"(Q[1-4])", expand=False)
    dfm = dfm.dropna(subset=[qcol])

    # Por ISSN
    issn_cols = [c for c in dfm.columns if re.search(r"\b(e?issn|issn[_\s-]*key|issn-l)\b", str(c), re.I)]
    dfm["_MAP_ISSN"] = ""
    if issn_cols:
        for c in issn_cols:
            dfm["_MAP_ISSN"] = dfm["_MAP_ISSN"].where(dfm["_MAP_ISSN"].astype(bool), dfm[c].map(_issn_norm))
        dfm_issn = dfm.loc[dfm["_MAP_ISSN"].astype(bool), ["_MAP_ISSN", qcol]].drop_duplicates("_MAP_ISSN")
    else:
        dfm_issn = pd.DataFrame(columns=["_MAP_ISSN", qcol])

    # Por nombre de revista
    jcol = _pick_journal_col(dfm)
    if jcol:
        dfm["_MAP_JR"] = dfm[jcol].astype(str).str.strip().str.lower().str.replace(r"\s+", " ", regex=True)
        dfm_jr = dfm.loc[dfm["_MAP_JR"].astype(bool), ["_MAP_JR", qcol]].drop_duplicates("_MAP_JR")
    else:
        dfm_jr = pd.DataFrame(columns=["_MAP_JR", qcol])

    # Merge por ISSN
    before = out["Quartile"].ne("Sin cuartil").sum()
    if "ISSN_key" in out.columns and not dfm_issn.empty:
        out["_MAP_ISSN"] = out["ISSN_key"].map(_issn_norm)
        out = out.merge(dfm_issn.rename(columns={qcol: "_Q_from_issn"}), on="_MAP_ISSN", how="left")
        out["Quartile"] = out["Quartile"].where(out["Quartile"].ne("Sin cuartil"), out["_Q_from_issn"])
        out = out.drop(columns=["_Q_from_issn"])
    # Merge por Journal
    if "Journal_norm" in out.columns and not dfm_jr.empty:
        out["_MAP_JR"] = out["Journal_norm"].astype(str).str.lower().str.replace(r"\s+", " ", regex=True)
        out = out.merge(dfm_jr.rename(columns={qcol: "_Q_from_journal"}), left_on="_MAP_JR", right_on="_MAP_JR", how="left")
        out["Quartile"] = out["Quartile"].where(out["Quartile"].ne("Sin cuartil"), out["_Q_from_journal"])
        out = out.drop(columns=["_Q_from_journal"])

    # Limpieza
    out["Quartile"] = out["Quartile"].fillna("Sin cuartil")
    out = out.drop(columns=[c for c in ["_MAP_ISSN", "_MAP_JR"] if c in out.columns])

    enriched = out["Quartile"].ne("Sin cuartil").sum() - before
    return out, int(enriched)

# =============================
# Deduplicación / lectura nuevos
# =============================
def _build_dedup_key(df_like: pd.DataFrame) -> pd.Series:
    parts: List[pd.Series] = []
    if "DOI_norm" in df_like.columns: parts.append(df_like["DOI_norm"].fillna(""))
    if "PMID_norm" in df_like.columns: parts.append("PMID:" + df_like["PMID_norm"].fillna(""))
    if "EID" in df_like.columns: parts.append("EID:" + df_like["EID"].astype(str).fillna(""))
    ycol = _first_col(df_like, CAND["year"]); tcol = _first_col(df_like, CAND["title"])
    if ycol and tcol:
        y = pd.to_numeric(df_like[ycol], errors="coerce").fillna(-1).astype(int).astype(str)
        t = df_like[tcol].map(_title_key).fillna("")
        parts.append("TY:" + y + "|" + t)
    if not parts: return pd.Series("", index=df_like.index, dtype="object")
    key = parts[0].astype(str)
    for p in parts[1:]: key = key.where(key.astype(bool), p.astype(str))
    return key

def _read_any(file_obj) -> pd.DataFrame:
    name = (getattr(file_obj, "name", "") or "").lower()
    try:
        if name.endswith(".csv"): return pd.read_csv(file_obj, dtype=str)
        return pd.read_excel(file_obj, dtype=str)
    except Exception:
        return pd.DataFrame()

# =============================
# Sidebar: carga/merge/filtros
# =============================
with st.sidebar:
    st.subheader("Datos base")
    up = st.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])
    st.caption(f"Por defecto: `{DEFAULT_XLSX}` (1ª hoja)")
    st.markdown("---")

    st.subheader("Actualizar dataset (merge)")
    new_files = st.file_uploader("Nuevos CSV/XLSX", type=["csv","xlsx"], accept_multiple_files=True)
    cA, cB = st.columns(2)
    with cA: btn_preview = st.button("👀 Previsualizar unión")
    with cB: btn_apply = st.button("✅ Aplicar actualización", type="primary")
    save_over = st.checkbox("Sobrescribir archivo base al aplicar (si existe)", value=False)
    st.markdown("---")

    st.subheader("Enriquecer cuartiles (opcional)")
    qmap_file = st.file_uploader("Mapeo cuartiles (CSV/XLSX, 1ª hoja)", type=["csv","xlsx"], key="qmap")
    apply_qmap = st.button("📥 Aplicar mapeo cuartiles")

    st.markdown("---")
    st.subheader("Filtros")

# Carga base
try:
    base_df = load_dataframe(up, sheet_name=DEFAULT_SHEET)
except Exception as e:
    st.error(str(e)); st.stop()

df = normalize_dataset(base_df)

# Merge (opcional)
if "__df_updated__" in st.session_state and isinstance(st.session_state["__df_updated__"], pd.DataFrame):
    df = st.session_state["__df_updated__"]

if new_files:
    news: List[pd.DataFrame] = []
    for f in new_files:
        t = _read_any(f)
        if not t.empty: news.append(normalize_dataset(t))
    new_df = pd.concat(news, ignore_index=True, sort=False) if news else pd.DataFrame()
    if not new_df.empty:
        pre_keys = set(k for k in _build_dedup_key(df) if isinstance(k, str) and k)
        is_new = _build_dedup_key(new_df).map(lambda k: (isinstance(k, str) and k not in pre_keys and k != ""))

        if btn_preview:
            n_new = int(is_new.sum()); n_dup = int(len(new_df) - n_new)
            st.info(f"Vista previa: {n_new} nuevos · {n_dup} duplicados/ignorados.")
            cols_preview = [c for c in ["Title","_Year","DOI_norm","PMID_norm","EID"] if c in new_df.columns]
            st.dataframe(new_df.loc[is_new, cols_preview].head(150), use_container_width=True, height=280)

        if btn_apply:
            merged = pd.concat([df, new_df], ignore_index=True, sort=False)
            merged["_dedup_key"] = _build_dedup_key(merged)
            merged["_title_key"] = merged["Title"].map(_title_key) if "Title" in merged.columns else ""
            merged["__tmp__"] = merged["_dedup_key"].fillna("") + "|" + merged["_title_key"].fillna("")
            merged = merged.drop_duplicates(subset="__tmp__", keep="first").drop(columns=["__tmp__"], errors="ignore")
            st.success(f"Actualización aplicada. Total {len(merged):,}.")
            st.session_state["__df_updated__"] = merged
            df = merged
            xbytes = _df_to_xlsx_bytes(df)
            if xbytes:
                dl_button("⬇️ Descargar dataset ACTUALIZADO (XLSX)", xbytes, "dataset_actualizado.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "updated_xlsx")
            if save_over and Path(DEFAULT_XLSX).exists():
                try: df.to_excel(DEFAULT_XLSX, index=False); st.success(f"Sobrescrito `{DEFAULT_XLSX}`.")
                except Exception as e: st.error(f"No se pudo sobrescribir: {e}")

# Aplicar mapeo de cuartiles si se sube archivo
if apply_qmap and qmap_file is not None:
    map_df = _read_any(qmap_file)
    if map_df.empty:
        st.error("No pude leer el archivo de mapeo.")
    else:
        df2, n_new = enrich_quartiles(df, map_df)
        st.session_state["__df_updated__"] = df2
        df = df2
        st.success(f"Cuartiles enriquecidos: {n_new} filas asignadas/actualizadas.")

# =============================
# Filtros
# =============================
mask = pd.Series(True, index=df.index)
with st.sidebar:
    if "_Year" in df.columns and df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int); y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Año", y_min, y_max, (y_min, y_max), key="flt_year")
        mask &= df["_Year"].astype(float).between(y1, y2)

    if "Quartile" in df.columns and df["Quartile"].notna().any():
        q_opts = ["Q1","Q2","Q3","Q4","Sin cuartil"]
        sel_q = st.multiselect("Cuartil (JCR/SJR)", q_opts, default=q_opts, key="flt_quartile")
        mask &= df["Quartile"].isin(sel_q)

    src_opts = [c for c in ["in_Scopus","in_WoS","in_PubMed"] if c in df.columns]
    sel_src = st.multiselect("Fuente", options=src_opts, default=src_opts, key="flt_src")
    if sel_src: mask &= df[sel_src].fillna(False).any(axis=1)

    if "Open Access" in df.columns:
        oa_vals = ["OA","No OA","Desconocido"]
        sel_oa = st.multiselect("Open Access", oa_vals, default=oa_vals, key="flt_oa")
        mask &= df["Open Access"].isin(sel_oa)

    query = st.text_input("Buscar en título", "", key="flt_title")
    if query and "Title" in df.columns: mask &= df["Title"].fillna("").str.contains(query, case=False, na=False)

    if "Departamento" in df.columns and df["Departamento"].notna().any():
        dep_pool = df["Departamento"].dropna().astype(str).str.split(r"\s*;\s*").explode().dropna()
        sel_dep = st.multiselect("Departamento", sorted(set([d for d in dep_pool if d])), default=[], key="flt_dept")
        if sel_dep:
            rgx = "|".join(map(re.escape, sel_dep))
            mask &= df["Departamento"].fillna("").str.contains(rgx)

dff = df[mask].copy()
dff = dff.loc[:, ~pd.Index(dff.columns).duplicated(keep="last")]
st.subheader(f"Resultados: {len(dff):,}")

# =============================
# KPIs + figuras
# =============================
def kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    return {
        "Nº publicaciones": f"{len(dff):,}",
        "% con DOI": f"{(dff['DOI_norm'].notna().mean() * 100):.1f}%" if "DOI_norm" in dff.columns and len(dff) else "—",
        "% OA": f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%" if "Open Access" in dff.columns and len(dff) else "—",
        "% Q1": f"{(dff.get('Quartile','').eq('Q1').mean() * 100):.1f}%" if "Quartile" in dff.columns and len(dff) else "—",
    }

def fig_year_counts(dff: pd.DataFrame):
    g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
    return px.bar(x=g.index, y=g.values, labels={"x":"Año","y":"Nº publicaciones"}, title="Conteo por año")

def fig_oa_pie(dff: pd.DataFrame):
    oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
    fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="Proporción OA / No OA"); fig.update_traces(textinfo="percent+label")
    return fig

def fig_quartile_comp(dff: pd.DataFrame):
    comp = dff["Quartile"].fillna("Sin cuartil").value_counts().reindex(["Q1","Q2","Q3","Q4","Sin cuartil"], fill_value=0)
    return px.bar(comp.rename_axis("Cuartil").reset_index(name="N"), x="Cuartil", y="N", title="Composición por cuartil")

def quartile_pivot(dff: pd.DataFrame) -> pd.DataFrame:
    tmp = dff.dropna(subset=["_Year"]).copy()
    tmp["_Year"] = tmp["_Year"].astype(int)
    tmp["Quartile"] = tmp["Quartile"].fillna("Sin cuartil")
    piv = (tmp.pivot_table(index="_Year", columns="Quartile", values="Title", aggfunc="count", fill_value=0)
             .reindex(columns=["Q1","Q2","Q3","Q4","Sin cuartil"], fill_value=0)
             .sort_index())
    return piv

def fig_quartile_area(piv: pd.DataFrame):
    df_long = piv.reset_index().melt(id_vars="_Year", var_name="Cuartil", value_name="N")
    return px.area(df_long, x="_Year", y="N", color="Cuartil",
                   category_orders={"Cuartil": ["Q1","Q2","Q3","Q4","Sin cuartil"]},
                   title="Cuartiles por año (área apilada)"), df_long

# =============================
# Tabs
# =============================
tabs = st.tabs(["📌 Resumen","📄 Datos","📚 Revistas","🧑‍🔬 Autores","🔎 Títulos","🟢 OA","🏷️ Cuartiles","⭐ Citas"])

# RESUMEN
with tabs[0]:
    k1, k2, k3, k4 = st.columns(4); KP = kpis_summary(dff)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"]); k2.metric("% con DOI", KP["% con DOI"])
    k3.metric("% OA", KP["% OA"]); k4.metric("% Q1", KP["% Q1"])

    st.subheader("📈 Publicaciones por año")
    if dff["_Year"].notna().any():
        fig = fig_year_counts(dff); show_plot(fig, "year_summary")
        png = _plotly_png(fig)
        if png: dl_button("⬇️ PNG — Publicaciones por año", png, "pubs_por_anio.png", "image/png", "dl_year_summary")

    st.subheader("🟢 Open Access (resumen)")
    if "Open Access" in dff.columns and len(dff):
        fig = fig_oa_pie(dff); show_plot(fig, "oa_summary")
        png = _plotly_png(fig)
        if png: dl_button("⬇️ PNG — OA", png, "open_access.png", "image/png", "dl_oa_summary")

    if "Quartile" in dff.columns and dff["Quartile"].notna().any():
        st.subheader("🏷️ Composición por cuartil")
        fig = fig_quartile_comp(dff); show_plot(fig, "quartile_summary")

# DATOS
with tabs[1]:
    st.subheader("Resultados filtrados")
    st.dataframe(dff.head(1000), use_container_width=True, height=420)
    dl_button("⬇️ CSV — Resultados", dff.to_csv(index=False).encode("utf-8"), "resultados_filtrados.csv", "text/csv", "dl_csv_table")
    xbytes = _df_to_xlsx_bytes(dff)
    if xbytes: dl_button("⬇️ XLSX — Resultados", xbytes, "resultados_filtrados.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "dl_xlsx_table")

# REVISTAS
with tabs[2]:
    st.subheader("Top 20 Revistas")
    jr_col = "Journal_norm" if "Journal_norm" in dff.columns else _first_col(dff, CAND["journal"])
    if jr_col and dff[jr_col].notna().any():
        top_jr = dff[jr_col].fillna("—").value_counts().head(20).rename_axis("Journal").reset_index(name="N")
        fig = px.bar(top_jr.sort_values("N"), x="N", y="Journal", orientation="h", title="Top 20 revistas")
        show_plot(fig, "journals"); st.dataframe(top_jr, use_container_width=True, height=420)
        png = _plotly_png(fig)
        if png: dl_button("⬇️ PNG — Top revistas", png, "top_revistas.png", "image/png", "dl_journals")
    else:
        st.info("No hay columna de revista.")

# AUTORES
with tabs[3]:
    st.subheader("Top 20 Autores")
    acol = "Author Full Names" if "Author Full Names" in dff.columns else _first_col(dff, CAND["authors"])
    if acol and dff[acol].notna().any():
        s = dff[acol].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        top_auth = pd.Series(authors).value_counts().head(20).rename_axis("Autor").reset_index(name="N° Publicaciones")
        fig = px.bar(top_auth.sort_values("N° Publicaciones"), x="N° Publicaciones", y="Autor",
                     orientation="h", title="Top 20 autores")
        show_plot(fig, "authors"); st.dataframe(top_auth, use_container_width=True, height=420)
        png = _plotly_png(fig)
        if png: dl_button("⬇️ PNG — Top autores", png, "top_autores.png", "image/png", "dl_authors")
    else:
        st.info("No hay columna de autores.")

# 🔎 TÍTULOS — WordCloud
with tabs[4]:
    st.subheader("🔎 Tendencias en títulos (WordCloud)")
    if "Title" not in df.columns or df["Title"].dropna().empty:
        st.info("No hay columna de títulos.")
    else:
        c1, c2, c3, c4 = st.columns([1.1,1,1.2,2])
        with c1: scope = st.radio("Alcance", ["Filtrado","Todo"], horizontal=True, key="titles_scope")
        with c2: min_len = st.slider("Mín. letras", 2, 6, 3, key="titles_minlen")
        with c3: use_bigrams = st.checkbox("Incluir bigrams", value=False, key="titles_bigrams")
        with c4: stop_extra = st.text_input("Stopwords extra (coma separadas)",
                                            "study,analysis,clinical,trial,case,report,review,role,effect",
                                            key="titles_stop_extra")
        ds = dff if scope == "Filtrado" else df
        stop = build_stopwords(stop_extra)
        freq = tokenize_titles(ds["Title"], min_len=min_len, stop=stop, bigrams=use_bigrams)
        if not freq:
            st.info("No hay términos después de filtrar stopwords.")
        else:
            png_wc = wordcloud_png(dict(freq.most_common(300)))
            if png_wc:
                st.image(png_wc, caption="WordCloud de términos en títulos", use_container_width=True, key=ukey("img_wc"))
                dl_button("⬇️ PNG — WordCloud", png_wc, "wordcloud_titulos.png", "image/png", "dl_wc")
            else:
                st.warning("Instala `wordcloud` para renderizar la nube (pip install wordcloud).")
            top_n = st.slider("Top N términos", 10, 100, 30, key="titles_topn")
            st.dataframe(pd.DataFrame(freq.most_common(top_n), columns=["Término","Frecuencia"]), use_container_width=True, height=360)

# 🟢 OA
with tabs[5]:
    st.subheader("Open Access")
    if "Open Access" in dff.columns and len(dff):
        fig = fig_oa_pie(dff); show_plot(fig, "oa_tab")
        png = _plotly_png(fig)
        if png: dl_button("⬇️ PNG — OA", png, "open_access.png", "image/png", "dl_oa_tab")
        cols = [c for c in ["Title","_Year","Open Access"] if c in dff.columns]
        st.dataframe(dff[cols].dropna(how="all"), use_container_width=True, height=420)
    else:
        st.info("No hay columna de OA.")

# 🏷️ CUARTILES
with tabs[6]:
    st.subheader("Cuartiles (JCR/SJR)")
    if "Quartile" in dff.columns and dff["Quartile"].notna().any():
        c1, c2 = st.columns(2)
        with c1:
            fig = fig_quartile_comp(dff); show_plot(fig, "quartile_comp")
            png = _plotly_png(fig)
            if png: dl_button("⬇️ PNG — Composición cuartiles", png, "cuartiles_composicion.png", "image/png", "dl_quartile_comp")
        with c2:
            if dff["_Year"].notna().any():
                piv = quartile_pivot(dff)
                fig_area, df_long = fig_quartile_area(piv); show_plot(fig_area, "quartile_area")
                png2 = _plotly_png(fig_area)
                if png2: dl_button("⬇️ PNG — Cuartiles por año (área)", png2, "cuartiles_area_anio.png", "image/png", "dl_quartile_area")
                dl_button("⬇️ CSV — Tabla año×cuartil", df_long.to_csv(index=False).encode("utf-8"),
                          "cuartiles_por_anio.csv", "text/csv", "dl_quartile_csv")
        tbl = (dff["Quartile"].fillna("Sin cuartil").value_counts()
               .reindex(["Q1","Q2","Q3","Q4","Sin cuartil"], fill_value=0)
               .rename_axis("Cuartil").reset_index(name="N"))
        st.dataframe(tbl, use_container_width=True, height=260)
    else:
        st.info("Aún no hay cuartiles. Sube un mapeo ISSN/Revista→Cuartil en la barra lateral para enriquecer.")

# ⭐ CITAS
with tabs[7]:
    st.subheader("Más citadas")
    if "Times Cited" in dff.columns:
        tmp = dff.copy(); tmp["Times Cited"] = pd.to_numeric(tmp["Times Cited"], errors="coerce")
        cols_show = [c for c in ["Title","Author Full Names","Times Cited","_Year","DOI_norm"] if c in tmp.columns]
        st.dataframe(tmp.sort_values("Times Cited", ascending=False).head(20)[cols_show], use_container_width=True, height=520)
    else:
        st.info("No hay columna de citas (‘Times Cited’/‘Cited by’).")
