from pathlib import Path
# app_cas_dashboard.py
# Dashboard Cienciométrico — Clínica Alemana / FM-UDD

import os, re
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from io import BytesIO  # ← para ExcelFile desde uploader y para descargas
import plotly.express as px

# -----------------------------------------
# CONFIG
# -----------------------------------------
st.set_page_config(
    page_title="Dashboard Cienciométrico — Facultad de Medicina Clínica Alemana, Universidad del Desarrollo",
    layout="wide",
)
DEFAULT_FILE  = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = "Consolidado_enriq"

st.title("Dashboard Cienciométrico — Facultad de Medicina Clínica Alemana, Universidad del Desarrollo")

# === Helpers de descarga (NUEVO) ===============================================
def make_png_download(fig, label, fname, key):
    try:
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        buf.seek(0)
        st.download_button(f"⬇️ {label} (PNG)", buf.getvalue(), file_name=fname, mime="image/png", key=key)
    except Exception as e:
        st.caption(f"No pude exportar la figura: {e}")

def df_to_xlsx_bytes(df, sheet_name="Datos"):
    for engine in ("xlsxwriter","openpyxl"):
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as writer:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
            buf.seek(0)
            return buf.getvalue()
        except ModuleNotFoundError:
            continue
    return None

# -----------------------------------------
# CARGA DE DATOS + UPLOADERS (en sidebar)
# -----------------------------------------
with st.sidebar:
    st.subheader("Datos")
    up = st.file_uploader("Sube el Excel unificado (.xlsx)", type=["xlsx"])
    st.caption("Límite 200MB · Formato XLSX")

    st.markdown("—")
    st.caption("Diccionario de departamentos (opcional) — CSV con columnas: `pattern,department[,scope]`")
    dep_dict_up = st.file_uploader("Cargar CSV diccionario", type=["csv"], key="depdict")

@st.cache_data(show_spinner=True)
def load_excel(file_or_path):
    try:
        return pd.read_excel(file_or_path, sheet_name=DEFAULT_SHEET, dtype=str)
    except Exception:
        return pd.read_excel(file_or_path, dtype=str)

if up is not None:
    df = load_excel(up);        source_file = up.name
elif os.path.exists(DEFAULT_FILE):
    df = load_excel(DEFAULT_FILE); source_file = DEFAULT_FILE
else:
    st.warning("Coloca `dataset_unificado_enriquecido_jcr_PLUS.xlsx` en la carpeta o súbelo desde la barra lateral.")
    st.stop()

# === Handle del libro para posibles hojas lookup (JCR/JIF) ===
xls_handle = None
try:
    if up is not None:
        raw = up.getvalue()
        xls_handle = pd.ExcelFile(BytesIO(raw))
    elif os.path.exists(DEFAULT_FILE):
        xls_handle = pd.ExcelFile(DEFAULT_FILE)
except Exception:
    xls_handle = None

# Aplanar MultiIndex de columnas si lo hubiera y limpiar duplicados
if isinstance(df.columns, pd.MultiIndex):
    df.columns = [" ".join([str(c) for c in tup if str(c) != "nan"]).strip() for tup in df.columns]
df.columns = df.columns.astype(str).str.strip()
df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]

# -----------------------------------------
# HELPERS / NORMALIZADORES
# -----------------------------------------
TRUE_SET = {"true","1","t","yes","y","si","sí"}

def _to_bool_series(obj, length=None):
    if isinstance(obj, pd.DataFrame):
        s = obj.apply(lambda r: any(str(x).strip().lower() in TRUE_SET for x in r), axis=1)
        return s.fillna(False).astype(bool)
    elif isinstance(obj, pd.Series):
        return obj.map(lambda x: str(x).strip().lower() in TRUE_SET if pd.notna(x) else False).fillna(False).astype(bool)
    else:
        if length is None: length = len(df)
        return pd.Series([False]*length, index=df.index, dtype=bool)

def _base_name(c):  # p.ej. 'has_CAS.1' → 'hascas'
    return re.sub(r"[^a-z0-9]+", "", c.lower())

def _pick_bool(std_name, aliases=None):
    aliases = aliases or []
    wanted_bases = {_base_name(std_name)} | {_base_name(a) for a in aliases}
    cols = [c for c in df.columns if _base_name(c) in wanted_bases]
    if not cols:
        cols = [c for c in df.columns if any(a in c.lower() for a in [std_name.lower(), *[a.lower() for a in aliases]])]
    if not cols:
        df[std_name] = False
        return df[std_name]
    s = df[cols] if len(cols) > 1 else df[cols[0]]
    s = _to_bool_series(s)
    df[std_name] = s
    for c in cols:
        if c != std_name:
            try: df.drop(columns=c, inplace=True)
            except: pass
    return s

def first_existing(*cands):
    for name in cands:
        if name and name in df.columns:
            return name
    return None

def to_num(s): return pd.to_numeric(s, errors="coerce")

try:
    from unidecode import unidecode
except Exception:
    def unidecode(x): return x

# -----------------------------------------
# NORMALIZACIONES BÁSICAS (año, título, DOI, SJR)
# -----------------------------------------
year_col = first_existing("_Year","Year","Publication Year","PubYear","PY")
if year_col and "_Year" not in df.columns:
    df["_Year"] = df[year_col]

title_col = first_existing("Title","Document Title","Document title","TI")
if title_col and title_col != "Title" and "Title" not in df.columns:
    df["Title"] = df[title_col]

# DOI base y DOI unificado desde cualquier columna relacionada
if "DOI" in df.columns and "DOI_norm" not in df.columns:
    df["DOI_norm"] = df["DOI"].str.strip().str.lower()

DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
def _extract_doi(x):
    if pd.isna(x): return np.nan
    m = DOI_REGEX.search(str(x))
    return m.group(0).lower() if m else np.nan

doi_candidates = [c for c in df.columns if re.search(r"\bdoi\b", c, re.I) or re.search(r"(link|url)", c, re.I)]
base_doi = df["DOI_norm"] if "DOI_norm" in df.columns else pd.Series(np.nan, index=df.index)
if doi_candidates:
    extra_doi = df[doi_candidates].astype(str).apply(
        lambda row: next((d for d in (_extract_doi(v) for v in row.values) if pd.notna(d)), np.nan),
        axis=1
    )
    df["_DOI_norm"] = base_doi.where(base_doi.notna(), extra_doi)
else:
    df["_DOI_norm"] = base_doi


# -----------------------------------------
# ACTUALIZAR CON NUEVAS PUBLICACIONES (opcional)
# -----------------------------------------
with st.sidebar:
    st.subheader("Actualizar con nuevas publicaciones")
    st.caption("Carga uno o varios CSV/XLSX con nuevas filas para unir al dataset base.")
    new_files = st.file_uploader(
        "Nuevos datasets (CSV/XLSX)",
        type=["csv", "xlsx"], accept_multiple_files=True, key="newpubs"
    )
    save_over = st.checkbox("Sobrescribir archivo base al aplicar (si existe en disco)", value=False)
    btn_preview = st.button("Previsualizar unión")
    btn_apply   = st.button("Aplicar actualización", type="primary")

def _read_any_table(file_obj):
    try:
        name = (getattr(file_obj, "name", "") or "").lower()
        if name.endswith(".csv"):
            return pd.read_csv(file_obj, dtype=str)
        # XLSX → primera hoja
        return pd.read_excel(file_obj, dtype=str)
    except Exception as e:
        st.warning(f"No pude leer {getattr(file_obj,'name','archivo')}: {e}")
        return None

def _standardize_minimal(df2: pd.DataFrame) -> pd.DataFrame:
    """Ajustes mínimos para facilitar el merge."""
    df2 = df2.copy()
    df2.columns = df2.columns.astype(str)
    # Renombres suaves a nombres canónicos si existen
    ren = {}
    # Título
    for c in df2.columns:
        if re.fullmatch(r"(title|document title|ti)", c, flags=re.I):
            ren[c] = "Title"; break
    # Año
    for c in df2.columns:
        if re.search(r"(?:^| )(?:(pub.*)?year|py)(?:$| )", c, flags=re.I):
            ren[c] = "_Year"; break
    # DOI
    for c in df2.columns:
        if re.search(r"\bdoi\b", c, flags=re.I):
            ren[c] = "DOI"; break
    # PMID
    for c in df2.columns:
        if re.search(r"\bpmid\b", c, flags=re.I):
            ren[c] = "PMID"; break
    # EID (Scopus)
    for c in df2.columns:
        if re.search(r"\beid\b", c, flags=re.I):
            ren[c] = "EID"; break
    df2 = df2.rename(columns=ren)

    # Normalización rápida de DOI/PMID
    if "DOI" in df2.columns:
        df2["DOI_norm"] = df2["DOI"].astype(str).str.strip().str.lower()

    # Extrae DOI desde posibles columnas de URL/enlace
    url_like = [c for c in df2.columns if re.search(r"(link|url)", c, re.I)]
    if url_like:
        def _first_doi_from_row(row):
            for v in row.values:
                m = DOI_REGEX.search(str(v))  # ← usa el regex ya definido arriba
                if m: return m.group(0).lower()
            return np.nan
        extra = df2[url_like].astype(str).apply(_first_doi_from_row, axis=1)
        base  = df2.get("DOI_norm", pd.Series(index=df2.index, dtype=object))
        df2["DOI_norm"] = base.where(base.notna() & (base.astype(str)!=""), extra)

    if "PMID" in df2.columns:
        df2["PMID_norm"] = (
            df2["PMID"].astype(str).str.replace(r"\D+", "", regex=True).replace("", np.nan)
        )

    return df2

def _title_key(s):
    if pd.isna(s): return ""
    t = unidecode(str(s)).lower()  # unidecode ya importado arriba
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _coalesce_series(series_list):
    """Devuelve la 1ª serie no vacía por fila (prioridad izquierda→derecha)."""
    out = pd.Series(np.nan, index=series_list[0].index, dtype=object)
    for s in series_list:
        s2 = s.astype(str).replace({"nan":"", "None":""})
        out = out.where(out.notna(), s2.mask(s2=="", np.nan))
    return out

def _build_dedup_key(df_like: pd.DataFrame) -> pd.Series:
    """Clave para deduplicación: DOI → PMID → EID → Título+Año."""
    idx = df_like.index
    # Candidatos
    cands = []

    # DOI
    if "_DOI_norm" in df_like.columns:
        cands.append(df_like["_DOI_norm"].astype(str))
    elif "DOI_norm" in df_like.columns:
        cands.append(df_like["DOI_norm"].astype(str))

    # PMID
    pmid_col = next((c for c in ["PMID_norm","PMID"] if c in df_like.columns), None)
    if pmid_col:
        cands.append("PMID:" + df_like[pmid_col].astype(str))

    # EID
    eid_col = next((c for c in ["EID","Scopus EID","EID_norm"] if c in df_like.columns), None)
    if eid_col:
        cands.append("EID:" + df_like[eid_col].astype(str))

    # Título + Año (fallback)
    ycol = next((c for c in ["_Year","Year","Publication Year","PY","PubYear"] if c in df_like.columns), None)
    tcol = next((c for c in ["Title","Document Title","TI","Document title"] if c in df_like.columns), None)
    if ycol and tcol:
        cands.append("TY:" + df_like[ycol].astype(str).fillna("") + "|" + df_like[tcol].map(_title_key))

    if not cands:
        return pd.Series(np.nan, index=idx, dtype=object)

    return _coalesce_series(cands)

def _make_download_bytes(df_all: pd.DataFrame):
    """Intenta XLSX; si no hay motor, cae a CSV."""
    for engine in ("xlsxwriter","openpyxl"):
        try:
            bio = BytesIO()
            with pd.ExcelWriter(bio, engine=engine) as writer:
                df_all.to_excel(writer, index=False, sheet_name=DEFAULT_SHEET)
            bio.seek(0)
            return bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "dataset_actualizado.xlsx"
        except ModuleNotFoundError:
            continue
    return df_all.to_csv(index=False).encode("utf-8"), "text/csv", "dataset_actualizado.csv"

# ——— Lógica de preview / apply
if new_files and (btn_preview or btn_apply):
    # 1) Leer y estandarizar nuevos
    frames = []
    for f in new_files:
        tmp = _read_any_table(f)
        if tmp is None or tmp.empty:
            continue
        frames.append(_standardize_minimal(tmp))
    if not frames:
        st.warning("No se pudo leer ningún archivo nuevo.")
    else:
        df_new = pd.concat(frames, ignore_index=True, sort=False)

        # 2) Claves de duplicado
        base_keys = _build_dedup_key(df).dropna()
        pre_set   = set(base_keys.unique().tolist())
        new_keys  = _build_dedup_key(df_new)
        only_new_mask = new_keys.map(lambda k: (pd.notna(k) and (k not in pre_set)))

        # 3) Vista previa
        if btn_preview and len(df_new):
            n_new = int(only_new_mask.sum())
            n_dup = int(len(df_new) - n_new)
            st.info(f"Vista previa: {n_new} candidatas nuevas · {n_dup} posibles duplicados.")
            cols_preview = [c for c in ["Title","_Year","DOI_norm","PMID_norm","EID"] if c in df_new.columns]
            st.dataframe(df_new.loc[only_new_mask, cols_preview].head(150), use_container_width=True, height=260)

        # 4) Aplicar
        if btn_apply:
            merged = pd.concat([df, df_new], ignore_index=True, sort=False)
            merged["_dedup_key"]  = _build_dedup_key(merged)
            merged["_title_key"]  = merged.get("Title", pd.Series("", index=merged.index)).map(_title_key)
            merged["__tmp_key__"] = merged["_dedup_key"].fillna("") + "|" + merged["_title_key"].fillna("")
            before = len(merged)
            merged = merged.drop_duplicates(subset="__tmp_key__", keep="first")
            merged.drop(columns=["__tmp_key__"], inplace=True, errors="ignore")
            added = merged.shape[0] - df.shape[0]
            df = merged  # ← actualiza el dataset que seguirá usando TODO el app
            st.success(f"Actualización aplicada: +{max(0, added)} registros nuevos (total {len(df):,}).")

            # Descarga inmediata del dataset actualizado
            bytes_data, mime, fname = _make_download_bytes(df)
            st.download_button("Descargar dataset ACTUALIZADO", bytes_data, file_name=fname, mime=mime, key="dl_updated_ds")

            # Guardado sobre el archivo base (opcional)
            if save_over:
                try:
                    if os.path.exists(DEFAULT_FILE):
                        # Ojo: esto sobrescribe SOLO la hoja de datos principal
                        with pd.ExcelWriter(DEFAULT_FILE, engine="openpyxl", mode="w") as writer:
                            df.to_excel(writer, index=False, sheet_name=DEFAULT_SHEET)
                        st.success(f"Archivo base sobrescrito: {DEFAULT_FILE}")
                    else:
                        st.warning("El archivo base no existe en disco. Descarga el actualizado y reemplázalo manualmente.")
                except Exception as e:
                    st.error(f"No se pudo sobrescribir el archivo base: {e}")
                    

# SJR a numérico (si existe alguna columna)
SJR_CANDS = ["SJR","SJR_score","SJR (Scimago)"]
df["_SJR_num"] = pd.to_numeric(pd.Series(np.nan, index=df.index), errors="coerce")
for c in SJR_CANDS:
    if c in df.columns:
        df["_SJR_num"] = pd.to_numeric(df[c], errors="coerce")
        break

# -----------------------------------------
# FUENTES (Scopus/WoS/PubMed) desde "Sources", si existe
# -----------------------------------------
def parse_sources_cell(s: str) -> pd.Series:
    if pd.isna(s):
        return pd.Series({"in_Scopus":False,"in_WoS":False,"in_PubMed":False,"Sources_clean":np.nan})
    t = str(s).strip().lower().strip("[]").replace("'", "").replace('"', "")
    tokens = [re.sub(r"\s+"," ", x).strip() for x in re.split(r"[;,+/&|]+", t) if x.strip()]
    seen = set()
    for tok in tokens:
        if tok == "scopus": seen.add("Scopus")
        elif tok in ("wos","web of science","web of science core collection","woscc"): seen.add("WoS")
        elif tok in ("pubmed","medline"): seen.add("PubMed")
    return pd.Series({
        "in_Scopus": "Scopus" in seen,
        "in_WoS":    "WoS"    in seen,
        "in_PubMed": "PubMed" in seen,
        "Sources_clean": "; ".join(sorted(seen)) if seen else np.nan,
    })

if "Sources" in df.columns:
    flags = df["Sources"].apply(parse_sources_cell)
    df["in_Scopus"]     = flags["in_Scopus"].fillna(False).astype(bool)
    df["in_WoS"]        = flags["in_WoS"].fillna(False).astype(bool)
    df["in_PubMed"]     = flags["in_PubMed"].fillna(False).astype(bool)
    df["Sources_clean"] = flags["Sources_clean"]
else:
    for c in ["in_Scopus","in_WoS","in_PubMed"]:
        if c not in df.columns: df[c] = False

st.caption("Publicaciones por fuente (post-normalización) → " + ", ".join(
    f"{k}:{int(df[k].sum())}" for k in ["in_Scopus","in_WoS","in_PubMed"] if k in df.columns
))

# Cuartil bucket
def build_quartile_bucket(row):
    q = (row.get("JCR_Quartile") or row.get("SJR_BestQuartile") or row.get("BestQuartile_combined"))
    if pd.isna(q) or not str(q).strip(): return "Sin cuartil"
    q = str(q).upper().strip()
    if q in {"Q1","Q2","Q3","Q4"}: return q
    m = re.search(r"([1234])", q)
    return f"Q{m.group(1)}" if m else "Sin cuartil"
if "_QuartileBucket" not in df.columns:
    df["_QuartileBucket"] = df.apply(build_quartile_bucket, axis=1)

# -----------------------------------------
# REVISTAS (mejorado) → _JournalDisplay
# -----------------------------------------
def _clean_issn(val):
    """
    Robust: acepta str, None, lista/tupla/set o numpy.ndarray.
    Devuelve 'XXXX-XXXX' o NaN.
    """
    if isinstance(val, (list, tuple, set)):
        val = next(iter(val), None)
    elif isinstance(val, np.ndarray):
        val = (val.flat[0] if val.size else None)

    if val is None:
        return np.nan

    s = str(val).strip().upper()
    if s in {"", "NAN", "<NA>", "NONE"}:
        return np.nan

    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"[^0-9X-]", "", s)
    m = re.search(r"([0-9X]{4})-?([0-9X]{4})", s)
    if not m:
        return np.nan
    return f"{m.group(1)}-{m.group(2)}"

def _all_issn_from_row(r):
    vals = []
    for c in df.columns:
        if "issn" in c.lower():
            vals += re.findall(r"[0-9Xx]{4}-?[0-9Xx]{4}", str(r.get(c, "")))
    vals = [_clean_issn(v) for v in vals]
    return sorted({v for v in vals if pd.notna(v)})

def _norm_journal(x):
    if pd.isna(x): return np.nan
    s = unidecode(str(x)).lower().replace("&"," and ")
    s = re.sub(r"\(.*?\)"," ", s)
    s = re.sub(r"[^a-z0-9 ]"," ", s)
    s = re.sub(r"\b(the|journal|revista|of|de|la|el|and|on|for)\b"," ", s)
    s = re.sub(r"\s+"," ", s).strip()
    return s or np.nan

jr_cols = [c for c in ["Journal_canon","Source title","Source Title","Journal","Journal Title","Publication Name"] if c in df.columns]
df["_JournalRaw"]  = (df[jr_cols].bfill(axis=1).iloc[:,0] if jr_cols else np.nan)
df["_JournalNorm"] = df["_JournalRaw"].apply(_norm_journal)

# todas las variantes de ISSN por fila
df["_ISSN_list"] = df.apply(_all_issn_from_row, axis=1)

# prioridad: ISSN-L si existe, si no el primero disponible (con fallback si queda NaN)
issn_l_col = next((c for c in df.columns if re.search(r"issn[-_ ]?l", c, re.I)), None)
df["_ISSN_any"] = np.nan
if issn_l_col:
    df["_ISSN_any"] = df[issn_l_col].apply(_clean_issn)
miss_issn = pd.isna(df["_ISSN_any"])
if miss_issn.any():
    df.loc[miss_issn, "_ISSN_any"] = df.loc[miss_issn, "_ISSN_list"].map(
        lambda xs: xs[0] if isinstance(xs, (list, tuple)) and len(xs) > 0 else np.nan
    )

# clave estable por ISSN; si no hay, por título normalizado
df["_JournalKey"] = np.where(df["_ISSN_any"].notna(),
                             "ISSN:"+df["_ISSN_any"],
                             "TIT:"+df["_JournalNorm"].fillna(""))

def _titlecase(s):
    if pd.isna(s): return s
    s = unidecode(str(s)).strip()
    out = s.title()
    for token in ["JAMA","NEJM","BMJ","PLOS","PLoS","IEEE","ACS","AJR","JACC","JAMA Dermatology"]:
        out = re.sub(rf"\b{token}\b", token, out, flags=re.I)
    return out

name_map = (df.groupby("_JournalKey")["_JournalRaw"]
              .agg(lambda s: s.mode().iat[0] if not s.mode().empty
                   else s.dropna().iloc[0] if s.notna().any() else np.nan)).map(_titlecase)
df["_JournalDisplay"] = df["_JournalKey"].map(name_map)

# -----------------------------------------
# JIF unificado (columnas internas + hoja lookup si existe)
# -----------------------------------------
def _num(x):
    if pd.isna(x): return np.nan
    s = str(x).strip().replace(",", ".")
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else np.nan

# 1) consolidar JIF desde columnas del dataset
jif_cols = [c for c in df.columns if re.search(r"\b(jif|impact\s*factor|journal impact factor)\b", c, re.I)]
if jif_cols:
    year_of = {c: (max(map(int, re.findall(r"(20\d{2})", c))) if re.findall(r"(20\d{2})", c) else -1) for c in jif_cols}
    jif_cols_sorted = sorted(jif_cols, key=lambda c: year_of[c], reverse=True)
    jif_mat = df[jif_cols_sorted].applymap(_num)
    df["JIF_unif"] = jif_mat.bfill(axis=1).iloc[:,0]
else:
    df["JIF_unif"] = np.nan

# 2) intentar rellenar con una hoja lookup JCR/JIF del mismo Excel (si existe)
lookup, lookup_sheet = None, "—"
if xls_handle is not None:
    for nm in xls_handle.sheet_names:
        if nm == DEFAULT_SHEET:
            continue
        if re.search(r"\b(jcr|jif|impact)\b", nm, re.I):
            try:
                tmp = pd.read_excel(xls_handle, sheet_name=nm, dtype=str)
                if tmp.shape[1] >= 2:
                    lookup, lookup_sheet = tmp, nm
                    break
            except Exception:
                pass

if lookup is not None:
    lookup.columns = lookup.columns.astype(str)

    # clave por ISSN en lookup
    issn_cols_lkp = [c for c in lookup.columns if "issn" in c.lower()]
    def _issn_key_from_row(r):
        vals = []
        for c in issn_cols_lkp:
            vals += re.findall(r"[0-9Xx]{4}-?[0-9Xx]{4}", str(r.get(c, "")))
        vals = [_clean_issn(v) for v in vals]
        vals = [v for v in vals if pd.notna(v)]
        return vals[0] if vals else np.nan
    lookup["_issn_key"] = lookup.apply(_issn_key_from_row, axis=1)

    # título normalizado en lookup (fallback si no hay ISSN)
    tcol_lkp = next((c for c in lookup.columns if re.search(r"(journal|source|publication).*(title|name)", c, re.I)), None)
    if tcol_lkp:
        lookup["_jnorm"] = lookup[tcol_lkp].map(lambda s: re.sub(r"\s+"," ", unidecode(str(s)).lower().replace("&"," and ")).strip())

    # JIF más reciente en lookup
    jif_cols_lkp = [c for c in lookup.columns if re.search(r"\b(jif|impact\s*factor|journal impact factor)\b", c, re.I)]
    if jif_cols_lkp:
        year_of = {c: (max(map(int, re.findall(r"(20\d{2})", c))) if re.findall(r"(20\d{2})", c) else -1) for c in jif_cols_lkp}
        jif_cols_sorted = sorted(jif_cols_lkp, key=lambda c: year_of[c], reverse=True)
        lookup["_JIF_lookup"] = lookup[jif_cols_sorted].applymap(_num).bfill(axis=1).iloc[:,0]
    else:
        lookup["_JIF_lookup"] = np.nan

    # merge por ISSN primero
    df["_issn_key"] = df["_ISSN_any"].str.upper()
    df = df.merge(lookup[["_issn_key","_JIF_lookup"]], on="_issn_key", how="left")

    # fallback por título normalizado
    if tcol_lkp:
        miss = df["_JIF_lookup"].isna()
        if miss.any():
            df = df.merge(
                lookup.loc[:, ["_jnorm","_JIF_lookup"]].rename(columns={"_JIF_lookup":"_JIF_lookup_title"}),
                left_on="_JournalNorm", right_on="_jnorm", how="left"
            )
            df["_JIF_lookup"] = df["_JIF_lookup"].where(df["_JIF_lookup"].notna(), df["_JIF_lookup_title"])
            for c in ["_jnorm","_JIF_lookup_title"]:
                if c in df.columns:
                    try: df.drop(columns=c, inplace=True)
                    except: pass

    # Consolidar JIF final
    df["JIF"] = df["JIF_unif"].where(df["JIF_unif"].notna(), df["_JIF_lookup"])
else:
    df["JIF"] = df["JIF_unif"]

# limpieza y pequeña telemetría
for c in ["_JIF_lookup"]:
    if c in df.columns:
        try: df.drop(columns=c, inplace=True)
        except: pass
st.caption(f"JIF cobertura: {int(df['JIF'].notna().sum())}/{len(df)} "
           f"({df['JIF'].notna().mean():.0%}) · hoja lookup: {lookup_sheet}")

# ==== Helper: JIF por año (suma y acumulado) ==================================
def render_jif_year_section(df_like, title="JIF por año (suma y acumulado)", key=None):
    st.subheader(title)
    if df_like is None or not isinstance(df_like, pd.DataFrame) or df_like.empty:
        st.caption("No hay datos para calcular el acumulado.")
        return
    needed = {"_Year", "JIF"}
    if not needed.issubset(df_like.columns):
        st.caption("No hay columnas '_Year' y 'JIF' para calcular el acumulado.")
        return

    tmp = df_like.copy()
    tmp["_y"]   = pd.to_numeric(tmp["_Year"], errors="coerce")
    tmp["_jif"] = to_num(tmp["JIF"])
    tmp = tmp.dropna(subset=["_y", "_jif"])
    if tmp.empty:
        st.caption("No hay JIF numérico disponible.")
        return

    jif_year = tmp.groupby("_y")["_jif"].sum(min_count=1).sort_index()
    years = np.arange(int(jif_year.index.min()), int(jif_year.index.max()) + 1)
    jif_year = jif_year.reindex(years, fill_value=0.0)
    jif_cum  = jif_year.cumsum()

    c1, c2 = st.columns(2)
    with c1:
        fig_a, axa = plt.subplots(figsize=(10, 4))
        axa.bar(years.astype(int), jif_year.values)
        axa.set_title("Suma de JIF por año"); axa.set_xlabel("Año"); axa.set_ylabel("Suma JIF")
        plt.tight_layout()
        st.pyplot(fig_a)
        make_png_download(fig_a, "Descargar gráfico 'JIF por año'", "jif_por_anio.png", key=f"png_jif_year_{key or 'k'}")
    with c2:
        fig_b, axb = plt.subplots(figsize=(10, 4))
        axb.plot(years.astype(int), jif_cum.values, marker="o")
        axb.set_title("Suma acumulada de JIF"); axb.set_xlabel("Año"); axb.set_ylabel("JIF acumulado")
        plt.tight_layout()
        st.pyplot(fig_b)
        make_png_download(fig_b, "Descargar gráfico 'JIF acumulado'", "jif_acumulado.png", key=f"png_jif_cum_{key or 'k'}")

    jif_tbl = pd.DataFrame({
        "Año": years.astype(int),
        "JIF anual (suma)": jif_year.values,
        "JIF acumulado": jif_cum.values,
    })
    st.dataframe(jif_tbl, use_container_width=True, height=260)

    # clave única para evitar DuplicateElementId entre llamadas
    slug = re.sub(r"[^a-z0-9]+", "_", (key or title).lower()).strip("_")
    st.download_button(
        "Descargar JIF anual y acumulado (CSV)",
        jif_tbl.to_csv(index=False).encode("utf-8"),
        file_name="jif_anual_y_acumulado.csv",
        mime="text/csv",
        key=f"dl_jif_{slug}"
    )

# === Llamado GLOBAL (dataset completo, sin filtros) ===
render_jif_year_section(df, "JIF por año (suma y acumulado) — dataset completo", key="full")

# -----------------------------------------
# AFILIACIONES (CAS / FM-UDD / ICIM) + Departamentos
# -----------------------------------------
def _norm_txt(s):
    if pd.isna(s): return ""
    s = unidecode(str(s)).lower()
    return re.sub(r"\s+"," ", s).strip()

def _split_affi(s):
    if not s: return []
    return [p.strip() for p in re.split(r"[;\n]|(?<!\d)\.(?!\d)", s) if p.strip()]

INST_PAT = {
    "CAS":   [r"\bclinica alemana\b", r"\bclinica alemana de santiago\b", r"\bclinica alemana santiago\b"],
    "FMUDD": [r"\bfacultad de medicina\b.*\b(universidad del desarrollo|udd)\b",
              r"\b(universidad del desarrollo|udd)\b.*\b(facultad|school|faculty) of medicine\b",
              r"\bfacultad de medicina clinica alemana\b",
              r"\bclinica alemana\b.*\b(universidad del desarrollo|udd)\b"],
    "ICIM":  [r"\bicim\b", r"\binstituto de ciencias e innovacion en medicina\b",
              r"\binstitute of science(s)? and innovation in medicine\b"],
}
INST_PAT = {k:[re.compile(p) for p in v] for k,v in INST_PAT.items()}

DEPT_PAT = {
    "Anestesia":[r"anestesi",r"anesthesiolog"],
    "Cardiologia":[r"cardiolog"],
    "Cirugia":[r"cirugi",r"surg(ery|ical)"],
    "Dermatologia":[r"dermatolog"],
    "Ginecologia y Obstetricia":[r"ginecolog",r"obstetri",r"gynecol"],
    "Infectologia":[r"infectolog",r"infectious diseases?"],
    "Medicina Interna":[r"medicina interna",r"internal medicine"],
    "Neurologia":[r"neurolog"],
    "Pediatria":[r"pediatr"],
    "Radiologia":[r"radiolog"],
    "Urgencia":[r"urgenci",r"emergency medicine"],
    "Traumatologia y Ortopedia":[r"traumatolog",r"orthopa?ed"],
    "Oncologia":[r"oncolog"],
    "Gastroenterologia":[r"gastroenterolog"],
    "Nefrologia":[r"nephrolog",r"nefrolog"],
    "Endocrinologia":[r"endocrinolog"],
    "Reumatologia":[r"rheumatolog",r"reumatolog"],
    "Oftalmologia":[r"ophthalmolog",r"oftalmolog"],
    "Urologia":[r"urolog"],
    "Patologia":[r"patholog",r"patolog"],
}
DEPT_PAT = {k:[re.compile(p) for p in v] for k,v in DEPT_PAT.items()}

AFFI_CANDS = [c for c in df.columns if re.search(r"(affil|affiliation|addresses?|^c1$|authors? with affiliations?)", c, re.I)]
if AFFI_CANDS:
    df["_affi_norm"] = (df[AFFI_CANDS].astype(str)
                        .apply(lambda r: " ; ".join(
                            [str(v) for v in r.values if pd.notna(v) and str(v).strip().lower() != "nan"]
                        ), axis=1)
                        .apply(_norm_txt))
else:
    df["_affi_norm"] = ""

def _any(text, compiled_list): return any(rx.search(text) for rx in compiled_list)

def _find_depts(text):
    hits = []
    for dep,pats in DEPT_PAT.items():
        if any(rx.search(text) for rx in pats):
            hits.append(dep)
    return sorted(set(hits))

# --- Departamento principal por mayoría SOLO en segmentos CAS/FM-UDD ---
def _analyze_majority(text):
    if not text or not str(text).strip():
        return pd.Series({
            "has_CAS_aff": False, "has_FMUDD_aff": False, "has_ICIM_aff": False,
            "Dept_CAS_list": np.nan, "Dept_FMUDD_list": np.nan, "Dept_primary": np.nan
        })

    has_cas = has_fm = has_icim = False
    cas_hits, fm_hits = [], []

    for seg in _split_affi(text):
        s = seg.strip()
        if not s:
            continue
        is_cas   = _any(s, INST_PAT["CAS"])
        is_fmudd = _any(s, INST_PAT["FMUDD"])
        is_icim  = _any(s, INST_PAT["ICIM"])

        has_cas  |= is_cas
        has_fm   |= is_fmudd
        has_icim |= is_icim

        if not (is_cas or is_fmudd):
            continue

        depts = _find_depts(s)
        if not depts:
            continue

        if is_cas:
            cas_hits.extend(depts)
        if is_fmudd:
            fm_hits.extend(depts)

    cas_list = "; ".join(sorted(set(cas_hits))) if cas_hits else np.nan
    fm_list  = "; ".join(sorted(set(fm_hits)))  if fm_hits  else np.nan

    from collections import Counter
    total_counts = Counter(cas_hits) + Counter(fm_hits)

    if not total_counts:
        primary = np.nan
    else:
        max_n = max(total_counts.values())
        empatados = sorted([d for d,c in total_counts.items() if c == max_n])
        if len(empatados) == 1:
            primary = empatados[0]
        else:
            # desempate: prioriza si aparece en CAS; luego en FM-UDD; si no, alfabético
            emp_cas = [d for d in empatados if d in set(cas_hits)]
            if emp_cas:
                primary = sorted(emp_cas)[0]
            else:
                emp_fm = [d for d in empatados if d in set(fm_hits)]
                primary = sorted(emp_fm)[0] if emp_fm else empatados[0]

    return pd.Series({
        "has_CAS_aff": has_cas,
        "has_FMUDD_aff": has_fm,
        "has_ICIM_aff": has_icim,
        "Dept_CAS_list": cas_list,
        "Dept_FMUDD_list": fm_list,
        "Dept_primary": primary
    })

# Analizar afiliaciones y limpiar duplicados
aff_features = df["_affi_norm"].apply(_analyze_majority)
df = pd.concat([df, aff_features], axis=1)
df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]

# === APLICAR DICCIONARIO DE DEPARTAMENTOS (opcional) ===
def _read_dep_dict(handle_or_path):
    try:    return pd.read_csv(handle_or_path, dtype=str)
    except: return None

dep_dict = None
if dep_dict_up is not None:
    dep_dict = _read_dep_dict(dep_dict_up)
elif os.path.exists("departamentos_diccionario.csv"):
    dep_dict = _read_dep_dict("departamentos_diccionario.csv")

if dep_dict is not None and "_affi_norm" in df.columns:
    dd = (dep_dict.rename(columns=str.lower)
                  .rename(columns={"dept":"department"})
                  .dropna(subset=["pattern","department"]))
    dd["pattern"]    = dd["pattern"].map(lambda x: str(x).strip())
    dd["department"] = dd["department"].map(lambda x: str(x).strip())
    dd["scope"]      = dd.get("scope","ambos").str.lower().fillna("ambos")

    cas_hits, fm_hits = [], []
    for s in df["_affi_norm"].fillna(""):
        dep_cas, dep_fm = set(), set()
        for _,row in dd.iterrows():
            pat, dept, sco = row["pattern"], row["department"], row["scope"]
            if re.search(pat, s):
                if sco in ("cas","ambos"):             dep_cas.add(dept)
                if sco in ("fm-udd","fmudd","ambos"):  dep_fm.add(dept)
        cas_hits.append("; ".join(sorted(dep_cas)) if dep_cas else np.nan)
        fm_hits.append("; ".join(sorted(dep_fm)) if dep_fm else np.nan)

    df["Dept_CAS_list"]   = df.get("Dept_CAS_list", pd.Series(np.nan, index=df.index)).combine_first(pd.Series(cas_hits, index=df.index))
    df["Dept_FMUDD_list"] = df.get("Dept_FMUDD_list", pd.Series(np.nan, index=df.index)).combine_first(pd.Series(fm_hits, index=df.index))

# Flags finales de afiliación (archivo OR inferido)
df["has_CAS"]   = _to_bool_series(df.get("has_CAS",False))   | _to_bool_series(df.get("has_CAS_aff",False))
df["has_FMUDD"] = _to_bool_series(df.get("has_FMUDD",False)) | _to_bool_series(df.get("has_FMUDD_aff",False))
df["has_ICIM"]  = _to_bool_series(df.get("has_ICIM",False))  | _to_bool_series(df.get("has_ICIM_aff",False))

# _DeptDisplay (estricto, solo CAS/FM-UDD)
def _to_dept_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, pd.Series):
        v = v.dropna()
        if v.empty: return []
        v = "; ".join(map(str, v.astype(str).str.strip()))
    s = str(v).strip()
    if s == "" or s.lower() in {"nan", "<na>"}:
        return []
    return [t.strip() for t in re.split(r"\s*;\s*", s) if t.strip()]

def _merge_depts(row):
    cas = _to_dept_list(row.get("Dept_CAS_list"))
    fm  = _to_dept_list(row.get("Dept_FMUDD_list"))
    merged = sorted(set(cas + fm))
    return "; ".join(merged) if merged else np.nan

for col in ("Dept_CAS_list", "Dept_FMUDD_list"):
    if col not in df.columns:
        df[col] = np.nan

df["_DeptDisplay"] = df.apply(_merge_depts, axis=1)

# Caption de afiliaciones
st.caption(
    "Afiliaciones (CAS / FM-UDD / ICIM) detectadas en columnas: "
    + (", ".join(AFFI_CANDS) if AFFI_CANDS else "—")
    + f" | Conteo → CAS:{int(df['has_CAS'].sum())}, FM-UDD:{int(df['has_FMUDD'].sum())}, ICIM:{int(df['has_ICIM'].sum())}"
)
st.caption(f"Filas con _DeptDisplay: {int(df['_DeptDisplay'].notna().sum())}")
st.caption("Departamento (estricto CAS/FM-UDD) activo")

# -----------------------------------------
# Ensayos clínicos y funding (heurístico)
# -----------------------------------------
def _has_ct(text):
    if pd.isna(text): return False
    t = str(text).lower()
    pats = [r"\bclinical trial\b", r"\brandomi[sz]ed\b", r"\btrial registration\b",
            r"\bclinicaltrials\.gov\b", r"\bnct\d{8}\b"]
    return any(re.search(p, t) for p in pats)

pubtype_col  = next((c for c in df.columns if re.search(r"(publication\s*type|types?)", c, re.I)), None)
abstract_col = next((c for c in df.columns if re.search(r"abstract", c, re.I)), None)
mesh_col     = next((c for c in df.columns if re.search(r"mesh", c, re.I)), None)
fund_col     = next((c for c in df.columns if re.search(r"(fund|grant|sponsor)", c, re.I)), None)

txt_ct = df[pubtype_col] if pubtype_col else df.get(mesh_col, pd.Series("", index=df.index))
if abstract_col: txt_ct = txt_ct.fillna("") + " " + df[abstract_col].fillna("")
df["is_ClinicalTrial"] = txt_ct.apply(_has_ct)
df["has_FundingText"]  = df[fund_col].notna() if fund_col else df.get("Funding text wos", pd.Series(False, index=df.index)).notna()
st.caption(f"Detectados como Clinical Trial: {int(df['is_ClinicalTrial'].sum())} | Con texto de funding: {int(df['has_FundingText'].sum())}")

# -----------------------------------------
# FILTROS + DATASET FILTRADO
# -----------------------------------------
df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]

mask = pd.Series(True, index=df.index)
with st.sidebar:
    st.subheader("Filtros")
    if "_Year" in df.columns:
        years = pd.to_numeric(df["_Year"], errors="coerce").dropna().astype(int)
        if not years.empty:
            y_min, y_max = int(years.min()), int(years.max())
            y1, y2 = st.slider("Año de publicación", y_min, y_max, (y_min, y_max))
            mask &= df["_Year"].astype(float).between(y1, y2)

    q_vals = ["Q1","Q2","Q3","Q4","Sin cuartil"]
    sel_q  = st.multiselect("Cuartil", q_vals, default=q_vals)
    mask  &= df["_QuartileBucket"].isin(sel_q)

    cats = []
    for c in ["SJR_Categories","JCR_Category","Subject Areas"]:
        if c in df.columns:
            cats += df[c].dropna().str.split(r"\s*;\s*").explode().dropna().tolist()
    cats = sorted(set(cats))
    sel_cats = st.multiselect("Áreas temáticas (SJR/JCR)", cats, default=[])
    if sel_cats:
        rgx = "|".join(map(re.escape, sel_cats))
        cond = False
        for c in ["SJR_Categories","JCR_Category","Subject Areas"]:
            if c in df.columns: cond = cond | df[c].fillna("").str.contains(rgx)
        mask &= cond

    only_scopus = st.checkbox("Solo Scopus", value=False)
    only_wos    = st.checkbox("Solo WoS", value=False)
    only_pubmed = st.checkbox("Solo PubMed", value=False)
    if only_scopus: mask &= df["in_Scopus"]
    if only_wos:    mask &= df["in_WoS"]
    if only_pubmed: mask &= df["in_PubMed"]

    title_query = st.text_input("Buscar en título", "")

    st.markdown("### Afiliación")
    if st.checkbox("Solo Clínica Alemana (CAS)", value=False):         mask &= df["has_CAS"]
    if st.checkbox("Solo Facultad de Medicina UDD", value=False):      mask &= df["has_FMUDD"]
    if st.checkbox("Solo autoría ICIM", value=False):                  mask &= df["has_ICIM"]

    dept_pool = []
    if "_DeptDisplay" in df.columns:
        dept_pool += df["_DeptDisplay"].dropna().str.split(r"\s*;\s*").explode().tolist()
    dept_pool = sorted(set([d for d in dept_pool if d]))
    sel_depts = st.multiselect("Departamento (CAS / FM-UDD)", dept_pool, default=[])
    if sel_depts:
        rgx = "|".join(map(re.escape, sel_depts))
        mask &= df["_DeptDisplay"].fillna("").str.contains(rgx)

# Buscar por título (solo si existe la columna)
if title_query and "Title" in df.columns:
    mask &= df["Title"].fillna("").str.contains(title_query, case=False, na=False)

dff = df[mask].copy()
dff = dff.loc[:, ~pd.Index(dff.columns).duplicated(keep="last")]

st.subheader(f"Resultados encontrados: {len(dff):,}")

with st.sidebar:
    if st.button("🔄 Limpiar caché y recargar"):
        st.cache_data.clear()
        st.experimental_rerun()

# -----------------------------------------
# KPIs
# -----------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    q1pct = (dff["_QuartileBucket"].eq("Q1").mean() * 100.0) if len(dff) else 0
    st.metric("% Q1", f"{q1pct:.1f}%")

with col2:
    q2pct = (dff["_QuartileBucket"].eq("Q2").mean() * 100.0) if len(dff) else 0
    st.metric("% Q2", f"{q2pct:.1f}%")

with col3:
    st.metric(
        "Mediana JIF",
        f"{to_num(dff.get('JIF')).median():.2f}" if 'JIF' in dff.columns else "—"
    )

with col4:
    doi_count = int(dff.get("_DOI_norm", pd.Series(index=dff.index)).notna().sum())
    st.metric("Con DOI", doi_count)

# Campo de visualización de DOI (unificado)
dff = dff.copy()
dff["DOI_display"] = dff["_DOI_norm"].where(dff["_DOI_norm"].notna(), dff.get("DOI"))

# -----------------------------------------
# COMPOSICIÓN POR CUARTIL (stacked)
# -----------------------------------------
if "_Year" in dff.columns and not dff.empty:
    g = (dff.dropna(subset=["_Year"])
           .groupby(["_Year","_QuartileBucket"]).size()
           .unstack(fill_value=0))
    for col in ["Q1","Q2","Q3","Q4","Sin cuartil"]:
        if col not in g.columns: g[col] = 0
    g = g[["Q1","Q2","Q3","Q4","Sin cuartil"]].sort_index()
    xs = g.index.astype(int).tolist()

    fig, ax = plt.subplots(figsize=(10,4))
    bottom = np.zeros(len(g))
    for col in ["Q4","Q3","Q2","Q1","Sin cuartil"]:
        vals = g[col].values
        ax.bar(xs, vals, bottom=bottom, label=col); bottom += vals
    ax.set_title("Composición por cuartil"); ax.set_xlabel("Año"); ax.set_ylabel("Nº")
    ax.legend(ncol=5, bbox_to_anchor=(0.5,1.02), loc="lower center")
    plt.tight_layout()
    st.pyplot(fig)
    make_png_download(fig, "Descargar 'Composición por cuartil'", "composicion_cuartil.png", key="png_quartiles")

# === Llamado CON FILTROS ===
render_jif_year_section(dff, "JIF por año (suma y acumulado) — con filtros", key="filtered")

# -----------------------------------------
# OVERLAP POR FUENTE
# -----------------------------------------
st.subheader("Overlap por fuente (con filtros)")
cols_present = [c for c in ("in_Scopus","in_WoS","in_PubMed") if c in dff.columns]
if not cols_present:
    st.info("No se encontraron columnas de fuente.")
else:
    counts = {c:int(dff[c].fillna(False).astype(bool).sum()) for c in cols_present}
    st.caption("Publicaciones por fuente (con filtros) → " + ", ".join(f"{k}:{v}" for k,v in counts.items()))
    if sum(counts.values()) == 0:
        st.info("No hay publicaciones para mostrar.")
    else:
        ind = dff[cols_present].fillna(False).astype(bool).rename(columns={
            "in_Scopus":"Scopus","in_WoS":"WoS","in_PubMed":"PubMed"
        })
        plotted = False
        try:
            from upsetplot import UpSet, from_indicators
            data = from_indicators(ind.columns.tolist(), ind)
            fig_u = plt.figure(figsize=(9,6))
            UpSet(data, show_counts=True, sort_by="cardinality", subset_size="count").plot(fig=fig_u)
            st.pyplot(fig_u); plotted = True
            make_png_download(fig_u, "Descargar 'Overlap por fuente (UpSet)'", "overlap_fuentes_upset.png", key="png_upset")
        except Exception as e:
            st.caption(f"UpSet no disponible o falló ({e}). Muestro barra de combinaciones.")

        combos  = ind.apply(lambda r: "+".join([n for n,v in r.items() if v]) or "Ninguna", axis=1)
        summary = combos.value_counts().sort_values(ascending=False)

        if not plotted and not summary.empty:
            fig_b, axb = plt.subplots(figsize=(9,4))
            axb.bar(summary.index, summary.values)
            axb.set_title("Combinaciones de fuentes"); axb.set_ylabel("Nº"); axb.set_xlabel("Fuentes")
            plt.xticks(rotation=45, ha="right"); plt.tight_layout()
            st.pyplot(fig_b)
            make_png_download(fig_b, "Descargar 'Overlap por fuente (barras)'", "overlap_fuentes_barras.png", key="png_overlap_bar")

        series = None
        try:
            from upsetplot import from_indicators
            series = from_indicators(ind.columns.tolist(), ind).reset_index().rename(columns={0:"N"})
        except Exception:
            series = summary.rename_axis("Combo").reset_index(name="N")
        st.dataframe(series, use_container_width=True, height=220)
        st.download_button("Descargar intersecciones (CSV)",
                           series.to_csv(index=False).encode("utf-8"),
                           file_name="overlap_fuentes.csv", mime="text/csv")

# -----------------------------------------
# TOP REVISTAS
# -----------------------------------------
st.subheader("Top revistas (cuenta)")
if "_JournalDisplay" in dff.columns and dff["_JournalDisplay"].notna().any():
    topn = (dff["_JournalDisplay"].fillna("—").value_counts().head(15)
            .rename_axis("Journal").reset_index(name="N"))
    fig2, ax2 = plt.subplots(figsize=(10,5))
    ax2.barh(topn["Journal"][::-1], topn["N"][::-1])
    ax2.set_title("Top revistas (cuenta)"); ax2.set_xlabel("Nº"); ax2.set_ylabel("")
    plt.tight_layout()
    st.pyplot(fig2)
    make_png_download(fig2, "Descargar 'Top revistas'", "top_revistas.png", key="png_top_journals")
else:
    st.caption("No hay revistas para mostrar con el filtro actual.")

# -----------------------------------------
# TOP DEPARTAMENTOS
# -----------------------------------------
st.subheader("Top departamentos (CAS / FM-UDD)")
if "_DeptDisplay" in dff.columns and dff["_DeptDisplay"].notna().any():
    topd = (dff["_DeptDisplay"].dropna().str.split(r"\s*;\s*").explode()
            .value_counts().head(15).rename_axis("Departamento").reset_index(name="N"))
    figd, axd = plt.subplots(figsize=(10,5))
    axd.barh(topd["Departamento"][::-1], topd["N"][::-1])
    axd.set_xlabel("Nº publicaciones"); axd.set_ylabel("")
    plt.tight_layout()
    st.pyplot(figd)
    make_png_download(figd, "Descargar 'Top departamentos'", "top_departamentos.png", key="png_top_deps")
else:
    st.caption("No hay departamentos CAS/FM-UDD para el filtro actual.")

# -----------------------------------------
# Análisis de títulos — palabras / n-gramas (frecuencia + barras + wordcloud)
# -----------------------------------------
st.subheader("Títulos: palabras y frases frecuentes")

if "Title" not in df.columns or df["Title"].dropna().empty:
    st.info("No hay columna 'Title' con datos para analizar.")
else:
    # Scope: con filtros (dff) o dataset completo (df)
    c0, c1, c2, c3 = st.columns([1,1,1,1.6])
    with c0:
        usar_filtros = st.toggle("Usar filtros", value=True, help="Si está apagado usa TODO el dataset.")
    scope_titles = dff if (usar_filtros and len(dff)) else df

    with c1:
        top_n = st.slider("Top N", 10, 80, 30, help="Cuántos términos mostrar")
    with c2:
        tipo_ng = st.radio("N-grama", ["Palabras", "Bigrams"], horizontal=True)
    with c3:
        stop_extra = st.text_input(
            "Stopwords extra (coma separadas)",
            "study,analysis,clinical,trial,case,report,review,effect,role,"
            "de,la,el,los,las,del,con,para,por,una,un,en,y"
        )

    normalize_txt = st.checkbox("Normalizar (minúsculas y sin acentos)", True)

    # ---- Limpieza y tokenización
    def _norm(s: str) -> str:
        if pd.isna(s): return ""
        t = str(s)
        if normalize_txt:
            try:
                from unidecode import unidecode
                t = unidecode(t)
            except Exception:
                pass
            t = t.lower()
        # dejar letras/núm/espacios
        t = re.sub(r"[^a-z0-9 áéíóúüñ]", " ", t, flags=re.I)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    titles_norm = scope_titles["Title"].astype(str).map(_norm)

    # stopwords base compacta ES/EN + extras
    STOP = {
        # ES
        "el","la","los","las","de","del","y","en","para","por","con","sin","al","una","un",
        "como","sobre","entre","desde","hasta","segun","según","esto","esta","este","estos","estas",
        # EN
        "the","of","and","in","for","on","to","a","an","as","with","from","by","at","or","not"
    }
    STOP |= {w.strip().lower() for w in stop_extra.split(",") if w.strip()}

    # generar tokens
    def tokens_palabras(text: str):
        toks = re.findall(r"[a-záéíóúüñ]{3,}", text, flags=re.I)
        return [t for t in toks if t not in STOP]

    def tokens_bigrams(text: str):
        toks = [t for t in re.findall(r"[a-záéíóúüñ]{3,}", text, flags=re.I) if t not in STOP]
        return [f"{a} {b}" for a, b in zip(toks, toks[1:]) if a != b]

    all_tokens = []
    if tipo_ng == "Palabras":
        for t in titles_norm: all_tokens.extend(tokens_palabras(t))
    else:
        for t in titles_norm: all_tokens.extend(tokens_bigrams(t))

    if not all_tokens:
        st.info("No se encontraron términos (ajusta las stopwords o desactiva normalización).")
    else:
        # Frecuencias
        from collections import Counter
        freq = Counter(all_tokens)
        freq_df = (pd.DataFrame(freq.items(), columns=["Término","N"])
                     .sort_values("N", ascending=False)
                     .head(top_n)
                     .reset_index(drop=True))

        # Tabla
        st.dataframe(freq_df, use_container_width=True, height=320)
        # ↓↓↓ NUEVO: descargar top términos a Excel
        xlsx_freq = df_to_xlsx_bytes(freq_df, sheet_name="Top_terminos")
        if xlsx_freq is not None:
            st.download_button("⬇️ Descargar top términos (XLSX)", xlsx_freq,
                               file_name=f"top_terminos_{'bigrams' if tipo_ng=='Bigrams' else 'palabras'}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.download_button(
            "Descargar frecuencias (CSV)",
            freq_df.to_csv(index=False).encode("utf-8"),
            file_name=f"frecuencias_titulos_{'bigrams' if tipo_ng=='Bigrams' else 'palabras'}.csv",
            mime="text/csv"
        )

        # Barras horizontales
        fig, ax = plt.subplots(figsize=(9, 6))
        y = freq_df["Término"][::-1]
        x = freq_df["N"][::-1]
        ax.barh(y, x)
        for i, v in enumerate(x):
            ax.text(v + max(1, v*0.01), i, str(v), va="center", fontsize=9)
        ax.set_title(f"Top {top_n} {'bigrams' if tipo_ng=='Bigrams' else 'palabras'} en títulos", fontsize=13, weight="bold")
        ax.set_xlabel("Frecuencia"); ax.set_ylabel("")
        plt.tight_layout()
        st.pyplot(fig)
        # ↓↓↓ NUEVO: descargar barras de términos a PNG
        make_png_download(fig, "Descargar 'Top términos (barras)'", f"top_terminos_{'bigrams' if tipo_ng=='Bigrams' else 'palabras'}.png",
                          key=f"png_terms_{'bigrams' if tipo_ng=='Bigrams' else 'unigrams'}")

        # WordCloud (opcional, ya tenía descarga PNG propia)
        try:
            from wordcloud import WordCloud
            wc = WordCloud(
                width=1600, height=900, background_color="white",
                collocations=False, normalize_plurals=False, prefer_horizontal=0.9,
                random_state=42
            ).generate_from_frequencies(dict(zip(freq_df["Término"], freq_df["N"])))
            img = wc.to_image()
            st.image(img, use_container_width=True)
            buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
            st.download_button("Descargar WordCloud (PNG)", buf.getvalue(),
                               file_name=f"wordcloud_titulos_{'bigrams' if tipo_ng=='Bigrams' else 'palabras'}.png",
                               mime="image/png")
        except Exception as e:
            st.caption(f"WordCloud no disponible ({e}). Instala 'wordcloud' para verlo.")

# -----------------------------------------
# QC MÉTRICAS POR REVISTA
# -----------------------------------------
st.subheader("Cobertura de métricas por revista (QC)")
if "_JournalDisplay" in dff.columns:
    dff_qc = dff.assign(
        has_JIF = to_num(dff.get("JIF")).notna() if "JIF" in dff.columns else False,
        has_SJR = to_num(dff.get("SJR")).notna() if "SJR" in dff.columns else False,
    )
    qc = (dff_qc.groupby("_JournalDisplay", dropna=False)
                .agg(n=("Title","size"),
                     pct_no_JIF=("has_JIF", lambda s: round(100*(~s).mean(),1)),
                     pct_no_SJR=("has_SJR", lambda s: round(100*(~s).mean(),1)))
                .sort_values("n", ascending=False))
    st.dataframe(qc.head(30), use_container_width=True, height=260)
    st.download_button("Descargar QC (todas las revistas)",
                       qc.to_csv().encode("utf-8"),
                       file_name="qc_metrica_por_revista.csv", mime="text/csv")
else:
    st.info("No encontré columna de revista para QC.")

# -----------------------------------------
# TABLA FINAL + DESCARGA
# -----------------------------------------
st.subheader("Registros")
extra_cols = [c for c in ["has_CAS","has_FMUDD","has_ICIM","_DeptDisplay","Dept_CAS_list","Dept_FMUDD_list","Dept_primary"] if c in dff.columns]
cols_show = [c for c in ["_Year","Title","_JournalDisplay","DOI_display","PMID_norm","WoS ID","EID",
                         "Quartile_used","_QuartileBucket","JIF","SJR","BestQuartile_combined",
                         "SJR_Categories","JCR_Category","Sources_clean"] if c in dff.columns] + extra_cols
cols_show = list(dict.fromkeys(cols_show))  # evitar repetidos

if cols_show:
    st.dataframe(dff[cols_show].reset_index(drop=True), use_container_width=True, height=360)

st.download_button("Descargar resultados (CSV)", dff.to_csv(index=False).encode("utf-8"),
                   file_name="resultados_filtrados.csv", mime="text/csv")

# ===== Exportar TODO el dataset (no filtrado) =====
xlsx_data = df_to_xlsx_bytes(df, sheet_name=DEFAULT_SHEET)
if xlsx_data is not None:
    st.download_button("Descargar dataset completo (XLSX)", data=xlsx_data,
                       file_name="dataset_enriquecido_completo.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.download_button("Descargar dataset completo (CSV)",
                       data=df.to_csv(index=False).encode("utf-8"),
                       file_name="dataset_enriquecido_completo.csv", mime="text/csv")

# Filtro adicional por tipo de documento
doc_types = df["Document Type"].dropna().unique()
selected_doc_types = st.sidebar.multiselect("Filtrar por tipo de documento", options=sorted(doc_types), default=sorted(doc_types))
df = df[df["Document Type"].isin(selected_doc_types)]

# Gráfico de publicaciones con Open Access
st.subheader("📌 Publicaciones con Open Access")

# Reemplazo gráfico de barras por gráfico de torta
if "Open Access" in dff.columns:
    oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
    fig_oa = px.pie(
        names=oa_counts.index,
        values=oa_counts.values,
        title="📌 Proporción de Publicaciones Open Access vs No Open Access",
        color_discrete_sequence=px.colors.sequential.Blues
    )
    fig_oa.update_traces(textinfo='percent+label')
    st.plotly_chart(fig_oa, use_container_width=True)
oa_counts = df["Open Access"].value_counts()
st.bar_chart(oa_counts)

# ============================================
# 📌 Ranking de Autores con más Publicaciones
# ============================================
st.subheader("📌 Ranking de Autores con más Publicaciones")

# Detectar columna de autores
author_col = next(
    (c for c in ["Author full names", "Authors", "Authors with affiliations"] if c in df.columns),
    None
)

if author_col:
    from collections import Counter
    authors_series = df[author_col].dropna().astype(str).str.split(r"[;|,]")
    all_authors = [author.strip() for sublist in authors_series for author in sublist if author.strip()]
    if all_authors:
        top_authors = Counter(all_authors).most_common(10)
        top_authors_df = pd.DataFrame(top_authors, columns=["Autor", "N° Publicaciones"])
        st.dataframe(top_authors_df, use_container_width=True)
    else:
        st.info("No se encontraron autores válidos en la columna seleccionada.")
else:
    st.warning("No se encontró ninguna columna de autores en el dataset.")


# ============================================
# 📌 Publicaciones con más citas
# ============================================
st.subheader("📌 Publicaciones con más citas")

cited_col = "Cited by" if "Cited by" in df.columns else None

if cited_col:
    df[cited_col] = pd.to_numeric(df[cited_col], errors="coerce")
    top_cited_df = df.sort_values(by=cited_col, ascending=False).head(10)
    cols_show = [c for c in ["Title", author_col, cited_col, "Year"] if c in top_cited_df.columns]
    st.dataframe(top_cited_df[cols_show].reset_index(drop=True), use_container_width=True)
else:
    st.warning("No se encontró ninguna columna de citaciones en el dataset.")
