# app_dashboard.py
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import unidecode

# =========================
# Config
# =========================
st.set_page_config(
    page_title="📊 Dashboard de Producción Científica",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# Encabezado
# =========================
if Path("LOGO CAS_UDD.png").exists():
    import base64
    with open("LOGO CAS_UDD.png", "rb") as f:
        logo_bytes = f.read()
    logo_base64 = base64.b64encode(logo_bytes).decode()
    st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; padding: 20px 0; margin: 10px 0;">
            <img src="data:image/png;base64,{logo_base64}" style="width: 220px; height: auto; display: block;">
        </div>
    """, unsafe_allow_html=True)
else:
    st.warning("Logo no encontrado: LOGO CAS_UDD.png")

st.markdown("""
    <div style="background-color:#f0f2f6;padding:25px;border-radius:10px;margin-bottom:25px;border-left:5px solid #1f77b4">
        <h1 style="color:#1f77b4;text-align:center;margin:0;">📊 Dashboard de Producción Científica</h1>
        <p style="text-align:center;color:#555;margin:10px 0 5px 0;font-size:18px;">
            Facultad de Medicina Clínica Alemana - Universidad del Desarrollo
        </p>
        <p style="text-align:center;color:#666;margin:5px 0 0 0;font-size:14px;font-style:italic;">
            Análisis creado con técnicas de big data y ciencia de datos a partir de Scopus, Web of Science, Pubmed, Incites y Scimago
        </p>
    </div>
""", unsafe_allow_html=True)

st.markdown(
    """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    @media (max-width: 768px) {
        .main .block-container { padding: 1rem; }
        .stButton > button { width: 100%; margin: 5px 0; }
        .stDataFrame { font-size: 12px; }
        [data-testid="column"] { width: 100% !important; flex: unset !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] { padding: 8px 12px; font-size: 12px; height: auto; min-height: 32px; }
        [data-testid="stMetricValue"] { font-size: 14px; }
        [data-testid="stMetricLabel"] { font-size: 12px; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET_INDEX = 0

# =========================
# Utils base
# =========================
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", unidecode.unidecode(str(s).lower())).strip()

# Reglas de detección de departamento — nombres oficiales CAS (MMCAS 2026)
# Orden importa: ICIM-UDD va ANTES que keywords clínicos
_DEPT_RULES: List[tuple] = [
    # ── ICIM-UDD ─────────────────────────────────────────────
    ("instituto de ciencias",         "ICIM-UDD"),
    ("icim",                          "ICIM-UDD"),
    ("centro de bioetica",            "ICIM-UDD"),
    ("bioetica",                      "ICIM-UDD"),
    ("bioethics",                     "ICIM-UDD"),
    ("centro de epidemiologia",       "ICIM-UDD"),
    ("centro de genetica",            "ICIM-UDD"),
    ("center for genetics",           "ICIM-UDD"),
    ("center for human genetics",     "ICIM-UDD"),
    ("genetica humana",               "ICIM-UDD"),
    ("human genetics",                "ICIM-UDD"),
    ("genomica",                      "ICIM-UDD"),
    ("genomics",                      "ICIM-UDD"),
    ("neurocics",                     "ICIM-UDD"),
    ("complejidad social",            "ICIM-UDD"),
    ("centro de salud global",        "ICIM-UDD"),
    ("salud global",                  "ICIM-UDD"),
    ("global health",                 "ICIM-UDD"),
    ("epidemiologia",                 "ICIM-UDD"),
    ("epidemiology",                  "ICIM-UDD"),
    ("politicas de salud",            "ICIM-UDD"),
    ("health policy",                 "ICIM-UDD"),
    ("salud publica",                 "ICIM-UDD"),
    ("public health",                 "ICIM-UDD"),
    ("neuropsicolog",                  "Departamento de Neurología y Salud Mental"),
    ("neuropsycholog",                "Departamento de Neurología y Salud Mental"),
    ("psicolog",                      "ICIM-UDD"),
    ("psychology",                    "ICIM-UDD"),
    ("medicina regenerativa",         "ICIM-UDD"),
    ("regenerative medicine",         "ICIM-UDD"),
    ("fisiologia celular",            "ICIM-UDD"),
    ("cellular physiology",           "ICIM-UDD"),
    ("quimica medica",                "ICIM-UDD"),
    ("medical chemistry",             "ICIM-UDD"),
    ("comunicacion celular",          "ICIM-UDD"),
    ("cellular communication",        "ICIM-UDD"),
    ("estudios sociales en salud",    "ICIM-UDD"),
    ("investigacion y ensayos",       "ICIM-UDD"),
    ("programa de estudios",          "ICIM-UDD"),
    ("cancer prevention",             "ICIM-UDD"),
    ("data science",                  "ICIM-UDD"),
    ("kinesiolog",                    "ICIM-UDD"),
    ("kinesiology",                   "ICIM-UDD"),
    ("physiotherapy",                 "ICIM-UDD"),
    ("physical therapy",              "ICIM-UDD"),
    ("school of physical",            "ICIM-UDD"),
    # ── Departamentos CAS (nombres oficiales MMCAS 2026) ─────
    ("neurolog",          "Departamento de Neurología y Salud Mental"),
    ("psiquiatr",         "Departamento de Neurología y Salud Mental"),
    ("psychiatr",         "Departamento de Neurología y Salud Mental"),
    ("salud mental",      "Departamento de Neurología y Salud Mental"),
    ("mental health",     "Departamento de Neurología y Salud Mental"),
    ("oncolog",           "Departamento de Oncología"),
    ("radioterapia",      "Departamento de Oncología"),
    ("radiotherapy",      "Departamento de Oncología"),
    ("pediatr",           "Departamento de Pediatría"),
    ("neonat",            "Departamento de Pediatría"),
    ("ginecol",           "Departamento de Ginecología y Obstetricia"),
    ("obstetr",           "Departamento de Ginecología y Obstetricia"),
    ("obstetric",         "Departamento de Ginecología y Obstetricia"),
    ("gestion clinica de la mujer",   "Departamento de Ginecología y Obstetricia"),
    ("trauma",            "Departamento de Traumatología y Ortopedia"),
    ("ortoped",           "Departamento de Traumatología y Ortopedia"),
    ("orthoped",          "Departamento de Traumatología y Ortopedia"),
    ("orthopaedic",       "Departamento de Traumatología y Ortopedia"),
    ("knee unit",         "Departamento de Traumatología y Ortopedia"),
    ("imagen",            "Departamento de Imágenes"),
    ("radiolog",          "Departamento de Imágenes"),
    ("radiology",         "Departamento de Imágenes"),
    ("medicina nuclear",  "Departamento de Imágenes"),
    ("nuclear medicine",  "Departamento de Imágenes"),
    ("medicina interna",  "Departamento de Medicina Interna"),
    ("internal medicine", "Departamento de Medicina Interna"),
    ("departamento de medicina", "Departamento de Medicina Interna"),
    ("department of medicine",   "Departamento de Medicina Interna"),
    ("gastroenterol",     "Departamento de Medicina Interna"),
    ("endocrinol",        "Departamento de Medicina Interna"),
    ("reumatol",          "Departamento de Medicina Interna"),
    ("rheumatol",         "Departamento de Medicina Interna"),
    ("infectol",          "Departamento de Medicina Interna"),
    ("neumol",            "Departamento de Medicina Interna"),
    ("pulmonol",          "Departamento de Medicina Interna"),
    ("hematol",           "Departamento de Medicina Interna"),
    ("geriatr",           "Departamento de Medicina Interna"),
    ("nutricion",         "Departamento de Medicina Interna"),
    ("nutrition",         "Departamento de Medicina Interna"),
    ("rehabilitacion",    "Departamento de Medicina Interna"),
    ("rehabilitation",    "Departamento de Medicina Interna"),
    ("medicina fisica",   "Departamento de Medicina Interna"),
    ("physical medicine", "Departamento de Medicina Interna"),
    ("fisiatria",         "Departamento de Medicina Interna"),
    ("physiatry",         "Departamento de Medicina Interna"),
    ("trasplante",        "Departamento de Medicina Interna"),
    ("transplant",        "Departamento de Medicina Interna"),
    ("obesidad",          "Departamento de Medicina Interna"),
    ("obesity",           "Departamento de Medicina Interna"),
    ("diabetes",          "Departamento de Medicina Interna"),
    ("inmunol",           "Departamento de Medicina Interna"),
    ("immunol",           "Departamento de Medicina Interna"),
    ("cardiol",                       "Departamento de Enfermedades Cardiovasculares"),
    ("cardiovascul",                  "Departamento de Enfermedades Cardiovasculares"),
    ("enfermedades cardiovasculares", "Departamento de Enfermedades Cardiovasculares"),
    ("anestesi",          "Departamento de Pabellones Quirúrgicos"),
    ("anesthesi",         "Departamento de Pabellones Quirúrgicos"),
    ("pabellon",          "Departamento de Pabellones Quirúrgicos"),
    ("urgenc",            "Departamento de Urgencia General"),
    ("emergency",         "Departamento de Urgencia General"),
    ("laboratorio clinico", "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("clinical laboratory", "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("laboratorio",       "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("laboratory",        "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("banco de sangre",   "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("anatomia patol",    "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("servicio de anatomia", "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("patholog",          "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("paciente critico",       "Departamento de Paciente Crítico"),
    ("critical care",          "Departamento de Paciente Crítico"),
    ("critical patient",       "Departamento de Paciente Crítico"),
    ("cuidados intensivos",    "Departamento de Paciente Crítico"),
    ("intensive care",         "Departamento de Paciente Crítico"),
    ("unidad de tratamiento intensivo", "Departamento de Paciente Crítico"),
    ("cirug",       "Departamento de Cirugía"),
    ("surgery",     "Departamento de Cirugía"),
    ("dermatol",    "Departamento de Cirugía"),
    ("urolog",      "Departamento de Cirugía"),
    ("urology",     "Departamento de Cirugía"),
    ("oftalmol",    "Departamento de Cirugía"),
    ("ophthalmol",  "Departamento de Cirugía"),
    ("otorrinol",   "Departamento de Cirugía"),
    ("otolaryngol", "Departamento de Cirugía"),
    ("neurociru",   "Departamento de Cirugía"),
    ("neurosurg",   "Departamento de Cirugía"),
    ("maxilofac",   "Departamento de Cirugía"),
    ("odontol",     "Servicio de Odontología"),
    ("dentist",     "Servicio de Odontología"),
    ("dental",      "Servicio de Odontología"),
    ("odont",       "Servicio de Odontología"),
]

def detect_department(affiliation: str) -> str:
    """Detecta departamento desde UN segmento de afiliación CAS (nombres oficiales MMCAS 2026)."""
    if not isinstance(affiliation, str):
        return "Sin depto. especificado"
    t = _norm_text(affiliation)
    for kw, dep in _DEPT_RULES:
        if kw in t:
            return dep
    return "Sin depto. especificado"


# ──────────────────────────────────────────────────────────────────────────────
# FIX #2: get_cas_departments — retorna LISTA de deptos por paper
# Filtra primero por afiliación CAS/UDD, luego detecta depto en cada segmento.
# ──────────────────────────────────────────────────────────────────────────────
def get_cas_departments(affil_str: str, include_udd: bool = True) -> List[str]:
    """Retorna lista de departamentos CAS/UDD presentes en el paper (puede ser >1)."""
    deps: set = set()
    for seg in _chunk_authors_with_affils(affil_str):
        if not _is_cas_affil(seg, include_udd):
            continue
        dep = detect_department(seg)
        deps.add(dep)
    return sorted(deps) if deps else ["Sin depto. especificado"]


def detect_clinical_trial(row: pd.Series) -> bool:
    text = ""
    for col in ["Title", "Abstract", "Publication Type", "Keywords"]:
        if col in row and pd.notna(row[col]):
            text += " " + str(row[col])
    text = text.lower()
    ct_regex = r"(ensayo\s*cl[ií]nico|clinical\s*trial|randomi[sz]ed|phase\s*[i1v]+|double\s*blind|placebo\-controlled)"
    return bool(re.search(ct_regex, text))

# =========================
# Autores CAS
# =========================
def _is_cas_affil(text: str, include_udd: bool) -> bool:
    t = _norm_text(text)
    cas_hits = ["clinica alemana", "alemana clinic"]
    udd_hits: List[str] = []
    if include_udd:
        udd_hits = [
            "universidad del desarrollo", "udd",
            "facultad de medicina clinica alemana",
            "instituto de ciencias e innovacion en medicina",
            "icim", "cegen",
        ]
    return any(h in t for h in cas_hits + udd_hits)

_name_regex = re.compile(r"^\s*([^,;|]+)\s*,\s*([^,;|]+)")

def _chunk_authors_with_affils(affils: str) -> Iterable[str]:
    if not isinstance(affils, str) or not affils.strip():
        return []
    return [c.strip() for c in re.split(r";", affils) if c.strip()]

def extract_cas_authors_list(affiliations: str, include_udd: bool) -> List[str]:
    out: List[str] = []
    for seg in _chunk_authors_with_affils(affiliations):
        if not _is_cas_affil(seg, include_udd):
            continue
        m = _name_regex.match(seg)
        if not m:
            continue
        last = m.group(1).strip()
        given = m.group(2).strip()
        if last:
            out.append(f"{last}, {given}")
    return out

def author_to_initials(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""
    name = " ".join(name.split())
    if "," in name:
        last, given = [p.strip() for p in name.split(",", 1)]
        tok = re.split(r"[ \-]", given.strip())
        initial = (tok[0][0].upper() + ".") if tok and tok[0] else ""
        return f"{last}, {initial}"
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[-1]}, {parts[0][0].upper()}."
    return name.title()

def author_to_full(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""
    name = " ".join(name.split())
    if "," in name:
        last, given = [p.strip() for p in name.split(",", 1)]
        return f"{last.title()}, {given.title()}"
    parts = name.split()
    if len(parts) >= 2:
        last = parts[-1].title()
        given = " ".join(parts[:-1]).title()
        return f"{last}, {given}"
    return name.title()

def _looks_like_initials(s: str) -> bool:
    s = str(s).strip().replace(" ", "")
    if not s:
        return False
    parts = [p for p in re.split(r"\.", s) if p]
    if not parts:
        return False
    return all(len(p) <= 2 for p in parts) and sum(ch.isalpha() for ch in s) <= 5

def _clean_author_name(name: str) -> str:
    name = str(name).strip()
    if not name or name.lower() in {"nan", "none"}:
        return ""
    name = re.sub(r"\s*\([^\)]*\)\s*$", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip(" ,;|")
    return name

def _normalize_author_name(name: str) -> str:
    name = _clean_author_name(name)
    if not name:
        return ""
    if "," in name:
        left, right = [p.strip() for p in name.split(",", 1)]
        if not left or not right:
            return name
        if _looks_like_initials(left) and not _looks_like_initials(right):
            surname, given = right, left
        else:
            surname, given = left, right
        return f"{surname}, {given}"
    m = re.match(r"^(?P<surname>.+?)\s+(?P<initials>[A-Z](?:\.?[A-Z]){0,4}\.?)$", name)
    if m:
        surname = m.group("surname").strip()
        given = m.group("initials").strip()
        return f"{surname}, {given}"
    return name

def canon_author(name: str) -> str:
    name = _normalize_author_name(name)
    if not name:
        return ""
    if "," in name:
        last, given = [p.strip() for p in name.split(",", 1)]
    else:
        parts = [p for p in re.split(r"\s+", name) if p]
        if len(parts) >= 2:
            last = parts[-1]
            given = " ".join(parts[:-1])
        else:
            return _norm_text(name)
    last_norm = _norm_text(last)
    given_norm = _norm_text(given)
    first_alpha = ""
    for ch in given_norm:
        if ch.isalpha():
            first_alpha = ch
            break
    return f"{last_norm}|{first_alpha}"


def _strip_scopus_id(name: str) -> str:
    """Elimina el ID de Scopus entre paréntesis: 'Lavados, Pablo Manuel (123)' → 'Lavados, Pablo Manuel'"""
    return re.sub(r"\s*\([^)]+\)\s*$", "", name.strip()).strip()

def _build_fullname_lookup(dff: pd.DataFrame) -> dict:
    """
    Construye dict canon_key → nombre completo usando Author full names.
    'Author full names' tiene formato: 'Apellido, Nombre (ScopusID); ...'
    """
    lookup: dict = {}
    fn_col = _first_col(dff, ["Author full names", "Author Full Names"])
    if not fn_col:
        return lookup
    for val in dff[fn_col].dropna():
        for entry in str(val).split(";"):
            name = _strip_scopus_id(entry)
            if not name or name.lower() in {"nan", "none"}:
                continue
            key = canon_author(name)
            if key and key not in lookup:
                lookup[key] = name
    return lookup


# ──────────────────────────────────────────────────────────────────────────────
# build_cas_ranking — filtro a nivel PAPER (igual que el original) +
# nombres completos desde Author full names (sin IDs de Scopus).
# ──────────────────────────────────────────────────────────────────────────────
def build_cas_ranking(
    dff: pd.DataFrame,
    include_udd: bool,
    fmt: str,
    top_n: int,
    aff_col: Optional[str],
    author_col: Optional[str],
) -> pd.DataFrame:

    # 1) Construir lookup de nombres completos
    fullname_lookup = _build_fullname_lookup(dff)

    # 2) Determinar columna de ID único
    work = dff.copy()
    id_col = _first_col(work, ["ID_final", "DOI", "EID", "UT", "PMID"])
    if not id_col:
        work["_id"] = work.index.astype(str)
        id_col = "_id"

    # 3) Filtrar papers con CAS/UDD en CUALQUIER columna de afiliación
    def _paper_has_cas(row) -> bool:
        for col in [aff_col, "Affiliations", "Addresses"]:
            if col and col in row.index:
                val = row.get(col)
                if pd.notna(val) and _is_cas_affil(str(val), include_udd):
                    return True
        return False

    cas_mask = work.apply(_paper_has_cas, axis=1)
    work = work.loc[cas_mask].copy()

    if work.empty:
        return pd.DataFrame()

    # 4) Columna de autores: preferir Author full names, fallback a Authors
    auth_col = _first_col(work, ["Author full names", "Author Full Names", "Authors"])

    # 5) Expandir autores → publicaciones + trackear departamentos por autor
    rows = []
    author_dept_sets: dict = {}   # canon_key → set de departamentos del autor

    for _, row in work.iterrows():
        pub_id = row[id_col]
        raw_authors = str(row.get(auth_col, "")) if auth_col and pd.notna(row.get(auth_col)) else ""
        if not raw_authors or raw_authors.lower() == "nan":
            continue

        # Departamentos de este paper
        dept_list = row.get("Departamentos_lista", ["Sin depto. especificado"])
        if not isinstance(dept_list, list):
            dept_list = ["Sin depto. especificado"]

        seen_in_pub: set = set()
        for entry in raw_authors.split(";"):
            name = _strip_scopus_id(entry)
            if not name:
                continue
            key = canon_author(name)
            if not key or key in seen_in_pub:
                continue
            seen_in_pub.add(key)
            # Preferir nombre completo del lookup global
            display = fullname_lookup.get(key, name)
            rows.append({"Autor_original": display, "Autor_key": key, "Pub_ID": pub_id})
            # Acumular departamentos de este autor
            if key not in author_dept_sets:
                author_dept_sets[key] = set()
            author_dept_sets[key].update(dept_list)

    if not rows:
        return pd.DataFrame()

    df_auth = pd.DataFrame(rows)

    counts = (
        df_auth.groupby("Autor_key", as_index=False)["Pub_ID"]
        .nunique()
        .rename(columns={"Pub_ID": "Publicaciones"})
    )

    def pick_name(series: pd.Series) -> str:
        vals = series.dropna().astype(str)
        vals = vals[(vals != "") & (~vals.str.lower().isin(["nan", "none"]))]
        if vals.empty:
            return ""
        scored = []
        for v in vals.tolist():
            has_comma = "," in v
            if has_comma:
                _, given = v.split(",", 1)
                given = given.strip()
            else:
                given = ""
            score = (1 if has_comma else 0, 0 if _looks_like_initials(given) else 1, len(given), len(v))
            scored.append((score, v))
        best = sorted(scored, key=lambda x: x[0], reverse=True)[0][1]
        shown = author_to_initials(best) if fmt == "initials" else author_to_full(best)
        shown = str(shown).strip()
        return "" if not shown or shown.lower() in {"nan", "none"} else shown

    names = (
        df_auth.groupby("Autor_key")["Autor_original"]
        .apply(pick_name)
        .reset_index(name="Autor")
    )

    result = counts.merge(names, on="Autor_key", how="left")
    result["Autor"] = result["Autor"].fillna("").astype(str).str.strip()
    result = result[result["Autor"] != ""].copy()

    # Flag ICIM-only: autor cuyos papers clasificados NO incluyen ningún depto clínico
    def _is_icim_only(key: str) -> bool:
        depts = author_dept_sets.get(key, set())
        clinical = depts - {"ICIM-UDD", "Sin depto. especificado"}
        return "ICIM-UDD" in depts and len(clinical) == 0

    result["ICIM_only"] = result["Autor_key"].map(_is_icim_only)

    return (
        result[["Autor", "Publicaciones", "ICIM_only"]]
        .sort_values(["Publicaciones", "Autor"], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )


# =========================
# Colaboración
# =========================
def _extract_countries(affil_str: str) -> List[str]:
    """Extrae países desde cadena de afiliaciones (último token de cada segmento)."""
    countries = []
    for seg in _chunk_authors_with_affils(affil_str):
        parts = [p.strip() for p in seg.split(",") if p.strip()]
        if parts:
            last = parts[-1]
            # Descartar códigos postales o números
            if last and not re.match(r"^\d+", last):
                countries.append(last)
    return list(set(countries))

def _has_external_collab(affil_str: str, include_udd: bool) -> bool:
    """True si el paper tiene al menos un autor NO CAS."""
    for seg in _chunk_authors_with_affils(affil_str):
        if not _is_cas_affil(seg, include_udd):
            return True
    return False

def _has_international_collab(affil_str: str) -> bool:
    """True si hay más de un país en las afiliaciones."""
    countries = _extract_countries(affil_str)
    return len(countries) > 1


# =========================
# Normalización de columnas
# =========================
def _pick_best_year(df: pd.DataFrame) -> pd.Series:
    for c in ["Year_clean", "Publication Year", "PY", "Year", "_Year"]:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() > 0:
                return s
    return pd.Series([np.nan] * len(df))

def _pick_best_journal(df: pd.DataFrame) -> pd.Series:
    for c in ["Journal_norm_inc", "Name", "Source title", "Source Title", "Journal", "Publication Name"]:
        if c in df.columns:
            return df[c].astype(str)
    return pd.Series([""] * len(df))

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Year
    df["Year"] = _pick_best_year(df)

    # Open Access
    oa_main = _first_col(df, ["OpenAccess_flag", "Open Access", "OA"])
    if oa_main:
        sr = df[oa_main].astype(str).str.lower().str.strip()
        df["OpenAccess_flag"] = sr.isin({"1", "true", "t", "yes", "y", "si", "sí"})
    else:
        df["OpenAccess_flag"] = False

    # JIF
    jif_col = _first_col(df, ["Journal Impact Factor", "Impact Factor", "JIF", "JIF_2023", "JCR_IF"])
    df["Journal Impact Factor"] = pd.to_numeric(df[jif_col], errors="coerce").fillna(0) if jif_col else 0

    # Cuartil
    sjr_col   = _first_col(df, ["SJR Best Quartile", "Best Quartile"])
    jif_q_col = _first_col(df, ["JIF Quartile", "JCR Quartile"])
    jci_q_col = _first_col(df, ["JCI Quartile"])

    def norm_q(x):
        x = str(x).upper().strip()
        if x in ["Q1", "Q2", "Q3", "Q4"]:
            return x
        if x in ["1", "2", "3", "4"]:
            return f"Q{x}"
        return None

    quart_final = []
    for i in range(len(df)):
        q_val = None
        if sjr_col and sjr_col in df.columns:
            q_val = norm_q(df.iloc[i][sjr_col])
        if not q_val and jif_q_col and jif_q_col in df.columns:
            q_val = norm_q(df.iloc[i][jif_q_col])
        if not q_val and jci_q_col and jci_q_col in df.columns:
            q_val = norm_q(df.iloc[i][jci_q_col])
        quart_final.append(q_val or "Sin cuartil")
    df["Quartile"] = quart_final

    # ── FIX #2: Departamentos como LISTA filtrada por afiliación CAS/UDD ──
    aff_col = _first_col(df, [
        "Authors with affiliations", "Affiliations", "Author Affiliations",
        "Affiliation(s)", "Affiliation", "Author Affiliation",
        "Correspondence Address", "Address", "Reprint Address"
    ])
    if aff_col:
        df["Departamentos_lista"] = df[aff_col].apply(
            lambda x: get_cas_departments(str(x) if pd.notna(x) else "", include_udd=True)
        )
        # Columna de texto para display en listado (primer depto o unión)
        df["Departamento"] = df["Departamentos_lista"].apply(
            lambda lst: lst[0] if lst and lst != ["Sin depto. especificado"] else "Sin depto. especificado"
        )
        # Colaboración
        df["Colab_externa"] = df[aff_col].fillna("").apply(
            lambda x: _has_external_collab(x, include_udd=True)
        )
        df["Colab_internacional"] = df[aff_col].fillna("").apply(_has_international_collab)
    else:
        df["Departamentos_lista"] = [["Sin depto. especificado"]] * len(df)
        df["Departamento"] = "Sin depto. especificado"
        df["Colab_externa"] = False
        df["Colab_internacional"] = False

    # Ensayos clínicos
    df["ClinicalTrial_flag"] = df.apply(detect_clinical_trial, axis=1)

    # Revistas
    jbest = _pick_best_journal(df).fillna("").astype(str).str.strip()

    def fmt_journal(s: str) -> str:
        if not s or s.lower() in {"nan", "none"}:
            return ""
        base = unidecode.unidecode(s.strip().lower())
        fixed = {
            "revista medica de chile": "Revista Médica de Chile",
            "medica chile": "Revista Médica de Chile",
            "rev med chile": "Revista Médica de Chile",
            "plos one": "PLOS ONE",
            "bmj": "BMJ",
            "nejm": "NEJM",
            "the lancet": "The Lancet",
            "lancet": "The Lancet",
        }
        if base in fixed:
            return fixed[base]
        keep_revista = s.strip().lower().startswith("revista ")
        words = re.sub(r"\s+", " ", s.strip()).split(" ")
        lower_exceptions = {"de", "del", "la", "las", "los", "y", "en", "of", "and", "the"}
        titled = " ".join(
            w.capitalize() if w.lower() not in lower_exceptions else w.lower()
            for w in words
        )
        titled = re.sub(r"\bBmj\b", "BMJ", titled)
        titled = re.sub(r"\bNejm\b", "NEJM", titled)
        titled = re.sub(r"\bPlos One\b", "PLOS ONE", titled)
        if keep_revista and not titled.lower().startswith("revista "):
            titled = "Revista " + titled
        return titled

    df["Journal_display"] = jbest.map(fmt_journal)

    # Autores (cadena para display)
    a_col = _first_col(df, ["Author Full Names", "Author full names", "Authors", "Author Names", "Author", "Author(s)"])
    df["Authors_norm"] = df[a_col].fillna("").astype(str) if a_col else ""

    return df


# =========================
# Carga
# =========================
@st.cache_data(show_spinner=False)
def load_data(uploaded=None) -> pd.DataFrame:
    if uploaded is not None:
        base = pd.read_excel(uploaded, sheet_name=DEFAULT_SHEET_INDEX)
    elif Path(DEFAULT_XLSX).exists():
        base = pd.read_excel(DEFAULT_XLSX, sheet_name=DEFAULT_SHEET_INDEX)
    else:
        st.error(f"No se encontró `{DEFAULT_XLSX}`. Sube un XLSX en la barra lateral.")
        st.stop()
    return normalize_columns(base)


# =========================
# Filtros
# =========================
def setup_filters(df):
    st.sidebar.header("🔎 Filtros")

    with st.sidebar.expander("📅 Rango de años", expanded=False):
        if df["Year"].notna().any():
            y_min, y_max = int(df["Year"].min()), int(df["Year"].max())
        else:
            y_min, y_max = 1900, 2100
        year_range = st.slider("Años", y_min, y_max, (y_min, y_max), key="year_slider")

    with st.sidebar.expander("🔓 Open Access", expanded=False):
        oa_filter = st.radio("Open Access", ["Todos", "Solo OA", "No OA"], key="oa_radio")

    with st.sidebar.expander("📊 Cuartiles", expanded=False):
        quart_vals = [q for q in ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"] if q in df["Quartile"].unique().tolist()] or ["Sin cuartil"]
        quart_filter = st.multiselect("Cuartiles", quart_vals, default=quart_vals, key="quart_multiselect")

    with st.sidebar.expander("🏥 Departamentos", expanded=False):
        # Explotar lista para obtener todos los valores únicos
        all_deps = sorted(set(
            dep
            for lst in df["Departamentos_lista"]
            for dep in lst
            if dep != "Sin depto. especificado"
        ))
        dept_filter = st.multiselect("Departamentos", all_deps, default=None, key="dept_multiselect")

    with st.sidebar.expander("📄 Tipo de Documento", expanded=False):
        doc_col = _first_col(df, ["Document Type", "Publication Type", "DT", "Type", "Tipo"])
        if doc_col:
            doc_types = sorted(df[doc_col].dropna().astype(str).unique())
            doc_filter = st.multiselect("Tipos de documento", doc_types, default=None, key="doc_multiselect")
        else:
            doc_filter = None
            st.info("No se encontró columna de tipo de documento.")

    with st.sidebar.expander("🔍 Búsqueda", expanded=False):
        search_term = st.text_input("Buscar en títulos", key="search_input")

    return year_range, oa_filter, quart_filter, dept_filter, search_term, doc_filter


# =========================
# MAIN
# =========================
def main():
    up = st.sidebar.file_uploader("📂 Sube un XLSX", type=["xlsx"])
    df = load_data(up)

    st.sidebar.header("📊 Información del Dataset")
    st.sidebar.write(f"📄 Total de publicaciones: {len(df)}")
    if df["Year"].notna().any():
        st.sidebar.write(f"📅 Años: {int(df['Year'].min())} - {int(df['Year'].max())}")
    # Contar deptos únicos desde la lista expandida
    all_deps_unique = set(
        dep for lst in df["Departamentos_lista"] for dep in lst if dep != "Sin depto. especificado"
    )
    st.sidebar.write(f"🏥 Departamentos únicos: {len(all_deps_unique)}")

    year_range, oa_filter, quart_filter, dept_filter, search_term, doc_filter = setup_filters(df)

    mask = pd.Series(True, index=df.index)
    yr_ok = df["Year"].between(year_range[0], year_range[1], inclusive="both")
    mask &= (df["Year"].isna() | yr_ok)

    if oa_filter == "Solo OA":
        mask &= df["OpenAccess_flag"]
    elif oa_filter == "No OA":
        mask &= ~df["OpenAccess_flag"]

    mask &= df["Quartile"].isin(quart_filter)

    # FIX #2: filtro por departamento sobre la lista
    if dept_filter:
        mask &= df["Departamentos_lista"].apply(
            lambda lst: any(d in dept_filter for d in lst)
        )

    if doc_filter:
        doc_col = _first_col(df, ["Document Type", "Publication Type", "DT", "Type", "Tipo"])
        if doc_col:
            mask &= df[doc_col].astype(str).isin(doc_filter)

    if search_term.strip():
        mask &= df["Title"].fillna("").str.contains(search_term, case=False, na=False)

    dff = df.loc[mask].copy()
    st.sidebar.write(f"🔍 Registros después de filtrar: {len(dff)}")

    # =========================
    # KPIs
    # =========================
    st.header("📊 Métricas Principales")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("📚 Publicaciones", f"{len(dff)} / {len(df)}")
    with col2: st.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
    with col3: st.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
    with col4: st.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

    citas_col = None
    for col in ["Cited by", "Times Cited", "Citation Count", "Citas"]:
        if col in dff.columns:
            citas_col = col
            break

    total_citas = pd.to_numeric(dff[citas_col], errors="coerce").fillna(0) if citas_col else pd.Series([0] * len(dff))

    h_index = 0
    if len(total_citas) > 0:
        sorted_citas = total_citas.sort_values(ascending=False).reset_index(drop=True)
        h_index = int(sum(sorted_citas >= (np.arange(len(sorted_citas)) + 1)))

    col5, col6, col7, col8 = st.columns(4)
    with col5: st.metric("📖 Total citas", int(total_citas.sum()))
    with col6: st.metric("📖 Promedio citas", f"{total_citas.mean():.1f}")
    with col7: st.metric("🏆 % en Q1", f"{100 * (dff['Quartile'] == 'Q1').mean():.1f}%")
    with col8: st.metric("📊 h-index", h_index)

    # KPI colaboración
    if "Colab_externa" in dff.columns:
        col9, col10 = st.columns(2)
        with col9: st.metric("🤝 % Colab. externa", f"{100 * dff['Colab_externa'].mean():.1f}%")
        with col10: st.metric("🌍 % Colab. internacional", f"{100 * dff['Colab_internacional'].mean():.1f}%")

    # =========================
    # Pestañas
    # =========================
    tabs = st.tabs([
        "📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
        "🏥 Departamentos", "📑 Revistas", "👥 Autores",
        "🌍 Colaboración", "🔬 Áreas Temáticas",
        "📋 Listado", "☁️ Wordcloud", "📖 Citas"
    ])

    # ── Tab 0: Publicaciones ──────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("📅 Publicaciones por año")
        g = dff.copy()
        g["Year_int"] = pd.to_numeric(g["Year"], errors="coerce").astype("Int64")
        gg = (
            g[g["Year_int"].notna()]
            .groupby("Year_int").size()
            .reset_index(name="Publicaciones")
            .sort_values("Year_int")
        )
        if not gg.empty:
            fig = px.bar(gg, x="Year_int", y="Publicaciones",
                         title="Publicaciones por Año", text="Publicaciones")
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10),
                              xaxis=dict(title="Año", dtick=1), yaxis=dict(title="Publicaciones"))
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos con año válido.")

        st.subheader("📈 Suma JIF por año")
        j = dff.copy()
        current_year = datetime.now().year
        j["Year_int"] = pd.to_numeric(j["Year"], errors="coerce").astype("Int64")
        j = j[j["Year_int"].notna() & (j["Year_int"] <= current_year)]
        if not j.empty:
            jj = (
                j.groupby("Year_int")["Journal Impact Factor"]
                 .sum(min_count=1).reset_index()
                 .rename(columns={"Year_int": "Year", "Journal Impact Factor": "Suma JIF"})
            )
            y_min_jif = int(jj["Year"].min())
            full_years = pd.DataFrame({"Year": range(y_min_jif, current_year + 1)})
            jj = full_years.merge(jj, on="Year", how="left").fillna({"Suma JIF": 0})
            jj["Suma JIF"] = jj["Suma JIF"].round(1)
            fig = px.line(jj, x="Year", y="Suma JIF", markers=True,
                          title="Suma JIF por Año", text="Suma JIF")
            fig.update_traces(textposition="top center")
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10),
                              xaxis=dict(title="Año", dtick=1, range=[y_min_jif, current_year]),
                              yaxis=dict(title="Suma JIF"))
            st.plotly_chart(fig, use_container_width=True)

    # ── Tab 1: Cuartiles ─────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("📊 Distribución global por cuartiles")
        _Q_ORDER = ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
        _Q_COLORS = {"Q1":"#27ae60","Q2":"#f1c40f","Q3":"#e67e22","Q4":"#922b21","Sin cuartil":"#bdc3c7"}
        cts = dff["Quartile"].value_counts().reset_index()
        cts.columns = ["Quartile", "Publicaciones"]
        # Reordenar para que la leyenda salga Q1→Q2→Q3→Q4→Sin cuartil
        cts["_order"] = cts["Quartile"].map({q: i for i, q in enumerate(_Q_ORDER)})
        cts = cts.sort_values("_order").drop(columns="_order")
        fig = px.pie(cts, names="Quartile", values="Publicaciones", hole=0.4,
                     color="Quartile",
                     color_discrete_map=_Q_COLORS,
                     category_orders={"Quartile": _Q_ORDER})
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)

        # NUEVO: cuartiles por año (stacked bar)
        st.subheader("📊 Cuartiles por año")
        q_year = dff.copy()
        q_year["Year_int"] = pd.to_numeric(q_year["Year"], errors="coerce").astype("Int64")
        q_year = q_year[q_year["Year_int"].notna() & (q_year["Quartile"] != "Sin cuartil")]
        if not q_year.empty:
            pivot = (
                q_year.groupby(["Year_int", "Quartile"])
                .size().reset_index(name="n")
            )
            fig2 = px.bar(pivot, x="Year_int", y="n", color="Quartile",
                          title="Publicaciones por cuartil y año",
                          color_discrete_map={"Q1":"#27ae60","Q2":"#f1c40f","Q3":"#e67e22","Q4":"#922b21"},
                          category_orders={"Quartile": ["Q1","Q2","Q3","Q4"]})
            fig2.update_layout(barmode="stack", xaxis=dict(dtick=1, title="Año"),
                               yaxis=dict(title="Publicaciones"),
                               margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Sin datos suficientes para cuartiles por año.")

    # ── Tab 2: Open Access ───────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("🔓 Publicaciones Open Access")
        oa = dff["OpenAccess_flag"].map({True: "Open Access", False: "Closed"}).value_counts().reset_index()
        oa.columns = ["Estado", "Publicaciones"]
        fig = px.pie(oa, names="Estado", values="Publicaciones", hole=0.4,
                     color="Estado",
                     color_discrete_map={"Open Access":"#27ae60","Closed":"#95a5a6"})
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)

        # NUEVO: evolución OA por año
        st.subheader("📈 Evolución Open Access por año")
        oa_yr = dff.copy()
        oa_yr["Year_int"] = pd.to_numeric(oa_yr["Year"], errors="coerce").astype("Int64")
        oa_yr = oa_yr[oa_yr["Year_int"].notna()]
        if not oa_yr.empty:
            oa_agg = (
                oa_yr.groupby("Year_int")
                .agg(Total=("OpenAccess_flag", "count"),
                     OA=("OpenAccess_flag", "sum"))
                .reset_index()
            )
            oa_agg["% OA"] = (oa_agg["OA"] / oa_agg["Total"] * 100).round(1)
            fig_oa = px.bar(
                oa_agg, x="Year_int", y="% OA",
                title="Porcentaje Open Access por año", text="% OA",
                labels={"Year_int": "Año", "% OA": "% Open Access"}
            )
            fig_oa.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_oa.update_layout(xaxis=dict(dtick=1), yaxis=dict(range=[0, 110]),
                                 margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig_oa, use_container_width=True)

    # ── Tab 3: Departamentos (CORREGIDO) ──────────────────────────────────────
    with tabs[3]:
        st.subheader("🏥 Publicaciones por Departamento CAS/UDD")
        st.caption("Cada publicación puede contarse en más de un departamento si tiene autores de distintas unidades.")

        # Explotar la lista de departamentos
        dep_exploded = dff[["Departamentos_lista", "Year"]].copy()
        dep_exploded = dep_exploded.explode("Departamentos_lista")
        dep_exploded = dep_exploded.rename(columns={"Departamentos_lista": "Departamento"})
        dep_exploded = dep_exploded[dep_exploded["Departamento"] != "Sin depto. especificado"]

        dep = dep_exploded["Departamento"].value_counts().reset_index()
        dep.columns = ["Departamento", "Publicaciones"]

        def _short_dept(name: str) -> str:
            return (name
                    .replace("Departamento de ", "")
                    .replace("Servicio de ", "")
                    .strip())

        if not dep.empty:
            dep_display = dep.copy()
            dep_display["Depto_corto"] = dep_display["Departamento"].map(_short_dept)

            fig = px.bar(
                dep_display.sort_values("Publicaciones"),
                x="Publicaciones", y="Depto_corto",
                orientation="h",
                title="Publicaciones por Departamento", text="Publicaciones"
            )
            fig.update_traces(textposition="inside", insidetextanchor="start")
            fig.update_layout(
                yaxis=dict(categoryorder="total ascending", title=""),
                margin=dict(l=220, r=10, t=50, b=10),
                height=max(400, 40 * len(dep_display) + 100),
                font=dict(size=11)
            )
            st.plotly_chart(fig, use_container_width=True)

            # Evolución por departamento y año
            st.subheader("📈 Evolución por departamento y año")
            dep_yr = dep_exploded.copy()
            dep_yr["Year_int"] = pd.to_numeric(dep_yr["Year"], errors="coerce").astype("Int64")
            dep_yr = dep_yr[dep_yr["Year_int"].notna()]
            if not dep_yr.empty:
                top_deps = dep["Departamento"].head(8).tolist()
                dep_yr_top = dep_yr[dep_yr["Departamento"].isin(top_deps)].copy()
                dep_yr_top["Depto_corto"] = dep_yr_top["Departamento"].map(_short_dept)
                pivot_dep = dep_yr_top.groupby(["Year_int","Depto_corto"]).size().reset_index(name="n")
                fig2 = px.line(pivot_dep, x="Year_int", y="n", color="Depto_corto",
                               markers=True, title="Top 8 departamentos por año")
                fig2.update_layout(xaxis=dict(dtick=1, title="Año"),
                                   yaxis=dict(title="Publicaciones"),
                                   legend=dict(title="Departamento"),
                                   margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No se detectaron departamentos CAS/UDD en el subconjunto filtrado.")

    # ── Tab 4: Revistas ───────────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("📑 Revistas más frecuentes (Top 20)")
        journals = (
            dff["Journal_display"]
            .replace({"nan": "", "None": "", "—": ""})
            .astype(str).str.strip()
        )
        journals = journals[journals != ""]
        jr = journals.value_counts().head(20).reset_index()
        jr.columns = ["Revista", "Publicaciones"]

        if not jr.empty:
            fig = px.bar(
                jr.sort_values("Publicaciones"),
                x="Publicaciones", y="Revista", orientation="h",
                title="Top 20 Revistas", text="Publicaciones"
            )
            fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                              margin=dict(l=260, r=10, t=50, b=10), height=560,
                              yaxis_tickfont=dict(size=12), font=dict(size=10))
            fig.update_traces(textposition="inside", insidetextanchor="start")
            st.plotly_chart(fig, use_container_width=True)

        # tabla revistas con JIF y cuartil
        st.subheader("📋 Revistas con métricas (JIF / Cuartil)")
        jif_col_name = _first_col(dff, ["Journal Impact Factor"])
        if jif_col_name and "Journal_display" in dff.columns:
            rev_metrics = (
                dff.groupby("Journal_display")
                .agg(
                    Publicaciones=("Journal_display", "count"),
                    JIF_promedio=(jif_col_name, "mean"),
                    Cuartil=("Quartile", lambda x: x.mode()[0] if not x.empty else "—"),
                )
                .reset_index()
                .rename(columns={"Journal_display": "Revista", "JIF_promedio": "JIF Promedio"})
                .sort_values("Publicaciones", ascending=False)
                .head(30)
            )
            rev_metrics["JIF Promedio"] = rev_metrics["JIF Promedio"].round(3)
            st.dataframe(rev_metrics, use_container_width=True, height=400)

            csv_rev = rev_metrics.to_csv(index=False).encode("utf-8-sig")
            st.download_button("⬇️ Descargar tabla revistas (CSV)", data=csv_rev,
                               file_name="revistas_metricas.csv", mime="text/csv")

    # ── Tab 5: Autores CAS (CORREGIDO) ────────────────────────────────────────
    with tabs[5]:
        st.subheader("👥 Autores CAS (solo autores con afiliación a Clínica Alemana/UDD)")
        aff_col = _first_col(dff, [
            "Authors with affiliations", "Affiliations", "Author Affiliations",
            "Affiliation(s)", "Affiliation", "Author Affiliation"
        ])
        if not aff_col:
            st.warning("No se encontró la columna de afiliaciones.")
        else:
            colA, colB, colC = st.columns([1.2, 1.6, 1])
            with colA:
                fmt_choice = st.radio("Formato:", ["Apellido, Inicial", "Apellido, Nombre(s)"],
                                      horizontal=True, index=0)
            with colB:
                include_udd = st.checkbox("Incluir UDD/ICIM/F. Medicina además de Clínica Alemana",
                                          value=True)
            with colC:
                top_n = st.slider("Top N", min_value=10, max_value=100, value=50, step=5)

            fmt_key = "initials" if fmt_choice == "Apellido, Inicial" else "full"
            author_col = _first_col(dff, ["Author full names", "Author Full Names", "Authors"])
            ranking = build_cas_ranking(dff, include_udd, fmt_key, top_n, aff_col, author_col)

            if ranking.empty:
                st.info("No se detectaron autores CAS en el subconjunto filtrado.")
            else:
                # Checkbox para ocultar autores cuyas publicaciones son exclusivamente ICIM-UDD
                n_icim_only = int(ranking.get("ICIM_only", pd.Series(dtype=bool)).sum())
                mostrar_icim = st.checkbox(
                    f"Mostrar autores solo ICIM-UDD ({n_icim_only})",
                    value=True,
                    help="Desmarcar oculta autores cuyas publicaciones clasificadas pertenecen únicamente a ICIM-UDD (ej. Ezquer, Cabieses).",
                )
                if not mostrar_icim and "ICIM_only" in ranking.columns:
                    ranking = ranking[~ranking["ICIM_only"]].reset_index(drop=True)

                plot_df = ranking.sort_values("Publicaciones", ascending=True)
                max_label_len = int(plot_df["Autor"].astype(str).str.len().max())
                left_margin = min(520, 160 + max_label_len * 7)

                # Columnas solo para display (sin ICIM_only)
                display_cols = [c for c in plot_df.columns if c != "ICIM_only"]
                fig = px.bar(plot_df[display_cols], x="Publicaciones", y="Autor", orientation="h",
                             title=f"Top {len(plot_df)} Autores CAS · {fmt_choice}",
                             text="Publicaciones")
                fig.update_layout(
                    yaxis=dict(categoryorder="total ascending", automargin=True, title="Autor"),
                    margin=dict(l=left_margin, r=20, t=60, b=40),
                    height=max(500, 20 * len(plot_df) + 160), font=dict(size=12)
                )
                fig.update_traces(textposition="inside", insidetextanchor="start")
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📋 Ranking (tabla)")
                table_cols = [c for c in ranking.columns if c != "ICIM_only"]
                st.dataframe(ranking[table_cols], use_container_width=True, height=400)

                csv_bytes = ranking[table_cols].to_csv(index=False).encode("utf-8-sig")
                st.download_button("⬇️ Descargar ranking CAS (CSV)", data=csv_bytes,
                                   file_name=f"ranking_autores_CAS_top{len(plot_df)}.csv",
                                   mime="text/csv")

    # ── Tab 6: Colaboración (NUEVO) ───────────────────────────────────────────
    with tabs[6]:
        st.subheader("🌍 Análisis de Colaboración")

        if "Colab_externa" not in dff.columns:
            st.info("No hay datos de colaboración disponibles.")
        else:
            c1, c2, c3 = st.columns(3)
            n_total = len(dff)
            n_ext = dff["Colab_externa"].sum()
            n_int_only = (~dff["Colab_externa"]).sum()
            n_intl = dff["Colab_internacional"].sum()

            with c1:
                st.metric("🏛️ Solo interna", f"{n_int_only} ({100*n_int_only/n_total:.1f}%)")
            with c2:
                st.metric("🤝 Con colab. externa", f"{n_ext} ({100*n_ext/n_total:.1f}%)")
            with c3:
                st.metric("🌍 Con colab. internacional", f"{n_intl} ({100*n_intl/n_total:.1f}%)")

            # Torta tipo colaboración
            collab_counts = pd.Series({
                "Solo interna": int(n_int_only),
                "Colab. nacional": int(n_ext - n_intl) if n_ext >= n_intl else 0,
                "Colab. internacional": int(n_intl),
            })
            collab_counts = collab_counts[collab_counts > 0].reset_index()
            collab_counts.columns = ["Tipo", "Publicaciones"]
            fig_col = px.pie(collab_counts, names="Tipo", values="Publicaciones",
                             hole=0.4, title="Distribución por tipo de colaboración",
                             color="Tipo",
                             color_discrete_map={
                                 "Solo interna": "#3498db",
                                 "Colab. nacional": "#2ecc71",
                                 "Colab. internacional": "#e67e22"
                             })
            fig_col.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=11))
            st.plotly_chart(fig_col, use_container_width=True)

            # Evolución colaboración por año
            st.subheader("📈 Evolución de colaboración por año")
            cyr = dff.copy()
            cyr["Year_int"] = pd.to_numeric(cyr["Year"], errors="coerce").astype("Int64")
            cyr = cyr[cyr["Year_int"].notna()]
            if not cyr.empty:
                cyr_agg = (
                    cyr.groupby("Year_int")
                    .agg(
                        Total=("Colab_externa", "count"),
                        Externa=("Colab_externa", "sum"),
                        Internacional=("Colab_internacional", "sum"),
                    )
                    .reset_index()
                )
                cyr_agg["% Externa"] = (cyr_agg["Externa"] / cyr_agg["Total"] * 100).round(1)
                cyr_agg["% Internacional"] = (cyr_agg["Internacional"] / cyr_agg["Total"] * 100).round(1)

                fig_cyr = go.Figure()
                fig_cyr.add_trace(go.Scatter(
                    x=cyr_agg["Year_int"], y=cyr_agg["% Externa"],
                    mode="lines+markers", name="% Colab. externa", line=dict(color="#2ecc71")
                ))
                fig_cyr.add_trace(go.Scatter(
                    x=cyr_agg["Year_int"], y=cyr_agg["% Internacional"],
                    mode="lines+markers", name="% Colab. internacional", line=dict(color="#e67e22")
                ))
                fig_cyr.update_layout(
                    title="Evolución de colaboración (%)", xaxis=dict(dtick=1, title="Año"),
                    yaxis=dict(title="%", range=[0, 105]),
                    margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10)
                )
                st.plotly_chart(fig_cyr, use_container_width=True)

    # ── Tab 7: Áreas Temáticas (NUEVO) ────────────────────────────────────────
    with tabs[7]:
        st.subheader("🔬 Áreas Temáticas")

        # WoS Categories
        wos_cat_col = _first_col(dff, ["WoS Categories", "Research Areas", "Areas", "Categories"])
        if wos_cat_col:
            cats_raw = (
                dff[wos_cat_col]
                .dropna().astype(str)
                .str.split(r";|,|\|")
                .explode()
                .str.strip()
                .str.title()
            )
            cats_raw = cats_raw[cats_raw.str.len() > 2]
            top_cats = cats_raw.value_counts().head(20).reset_index()
            top_cats.columns = ["Área", "Publicaciones"]

            if not top_cats.empty:
                fig_cat = px.bar(
                    top_cats.sort_values("Publicaciones"),
                    x="Publicaciones", y="Área", orientation="h",
                    title="Top 20 Áreas Temáticas", text="Publicaciones"
                )
                fig_cat.update_layout(
                    yaxis=dict(categoryorder="total ascending"),
                    margin=dict(l=280, r=10, t=50, b=10),
                    height=max(450, 35 * len(top_cats) + 100),
                    font=dict(size=10)
                )
                fig_cat.update_traces(textposition="inside", insidetextanchor="start")
                st.plotly_chart(fig_cat, use_container_width=True)
                st.dataframe(top_cats, use_container_width=True, height=300)
        else:
            st.info("No se encontró columna de áreas temáticas (WoS Categories / Research Areas).")

        # Scimago Areas
        sjr_areas_col = _first_col(dff, ["Areas"])
        if sjr_areas_col and sjr_areas_col != wos_cat_col:
            st.subheader("Áreas Scimago")
            sjr_cats = (
                dff[sjr_areas_col].dropna().astype(str)
                .str.split(r";|,|\|").explode()
                .str.strip().str.title()
            )
            sjr_cats = sjr_cats[sjr_cats.str.len() > 2]
            top_sjr = sjr_cats.value_counts().head(15).reset_index()
            top_sjr.columns = ["Área", "Publicaciones"]
            if not top_sjr.empty:
                fig_sjr = px.bar(
                    top_sjr.sort_values("Publicaciones"),
                    x="Publicaciones", y="Área", orientation="h",
                    title="Top 15 Áreas Scimago", text="Publicaciones"
                )
                fig_sjr.update_layout(
                    yaxis=dict(categoryorder="total ascending"),
                    margin=dict(l=260, r=10, t=50, b=10),
                    height=max(400, 35 * len(top_sjr) + 100), font=dict(size=10)
                )
                fig_sjr.update_traces(textposition="inside", insidetextanchor="start")
                st.plotly_chart(fig_sjr, use_container_width=True)

    # ── Tab 8: Listado ────────────────────────────────────────────────────────
    with tabs[8]:
        st.subheader("📋 Listado de publicaciones")
        basic_candidates = [
            "Title", "Journal_display", "Source title", "Year", "DOI",
            "Authors", "Author full names", "Author Full Names",
            "Quartile", "Journal Impact Factor", "Departamento",
            "Cited by", "Times Cited", "OpenAccess_flag"
        ]
        selected_cols = [c for c in basic_candidates if c in dff.columns]
        display_df = dff[selected_cols].copy() if selected_cols else dff.copy()

        if "OpenAccess_flag" in display_df.columns:
            display_df["OpenAccess_flag"] = display_df["OpenAccess_flag"].map(
                {True: "Open Access", False: "Closed"}).fillna("Closed")

        rename_map = {
            "Title": "Título", "Journal_display": "Revista", "Source title": "Journal",
            "Year": "Año", "DOI": "DOI", "Authors": "Autores",
            "Author full names": "Autores_nombre_completo",
            "Author Full Names": "Autores_nombre_completo_2",
            "Quartile": "Cuartil", "Journal Impact Factor": "JIF",
            "Departamento": "Departamento", "Cited by": "Citas_scopus",
            "Times Cited": "Citas_wos", "OpenAccess_flag": "Open Access"
        }
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})

        cols = pd.Index(display_df.columns)
        if cols.duplicated().any():
            counts_d: dict = {}
            new_cols = []
            for c in cols:
                if c not in counts_d:
                    counts_d[c] = 0
                    new_cols.append(c)
                else:
                    counts_d[c] += 1
                    new_cols.append(f"{c}_{counts_d[c]}")
            display_df.columns = new_cols

        preferred_display_cols = [
            "Título", "Journal", "Año", "DOI", "Autores",
            "Cuartil", "JIF", "Departamento", "Citas_scopus", "Open Access"
        ]
        final_cols = [c for c in preferred_display_cols if c in display_df.columns]
        if final_cols:
            display_df = display_df[final_cols].copy()

        st.caption(f"Mostrando {len(display_df)} publicaciones del subconjunto filtrado.")
        display_df = display_df.reset_index(drop=True)
        display_df.index = display_df.index + 1
        st.dataframe(display_df, use_container_width=True, height=500)

        csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            display_df.to_excel(writer, index=False, sheet_name="Listado")
        excel_bytes = excel_buffer.getvalue()

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("⬇️ Descargar listado (CSV)", data=csv_bytes,
                               file_name="listado_publicaciones.csv", mime="text/csv")
        with col_dl2:
            st.download_button("⬇️ Descargar listado (Excel)", data=excel_bytes,
                               file_name="listado_publicaciones.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ── Tab 9: Wordcloud ──────────────────────────────────────────────────────
    with tabs[9]:
        st.subheader("☁️ Wordcloud")
        try:
            from wordcloud import WordCloud, STOPWORDS
            import matplotlib.pyplot as plt

            custom_stop = set(STOPWORDS)
            custom_stop.update([
                "el","la","los","las","un","una","unos","unas","de","del","y","en",
                "por","para","con","the","a","an","of","for","to","with","on","at",
                "by","from","they","their","this","that","these","those"
            ])

            st.markdown("**Keywords**")
            kw_cols = ["Author Keywords","Author keywords","Keywords","Index Keywords","Keywords Plus"]
            kws = []
            for c in kw_cols:
                if c in dff.columns:
                    kws.append(dff[c].dropna().astype(str))
            if kws:
                kw_text = " ; ".join(pd.concat(kws).tolist())
                if kw_text.strip():
                    wc_kw = WordCloud(width=1200, height=500, background_color="white",
                                      stopwords=custom_stop).generate(kw_text)
                    fig_kw, ax_kw = plt.subplots(figsize=(10, 4))
                    ax_kw.imshow(wc_kw, interpolation="bilinear")
                    ax_kw.axis("off")
                    st.pyplot(fig_kw, use_container_width=True, clear_figure=True)
                else:
                    st.info("No hay keywords para construir la nube.")
            else:
                st.info("No se encontraron columnas de keywords.")

            st.markdown("---")
            st.markdown("**Títulos**")
            if "Title" in dff.columns:
                title_text = " ".join(dff["Title"].dropna().astype(str).tolist())
                if title_text.strip():
                    wc_title = WordCloud(width=1200, height=500, background_color="white",
                                         stopwords=custom_stop).generate(title_text)
                    fig_title, ax_title = plt.subplots(figsize=(10, 4))
                    ax_title.imshow(wc_title, interpolation="bilinear")
                    ax_title.axis("off")
                    st.pyplot(fig_title, use_container_width=True, clear_figure=True)
        except Exception as e:
            st.info(f"Instala `wordcloud` para ver esta sección. Error: {e}")

    # ── Tab 10: Citas ─────────────────────────────────────────────────────────
    with tabs[10]:
        st.subheader("📖 Citas por año")
        if citas_col and not total_citas.empty and (total_citas > 0).any():
            dff_tmp = dff.copy()
            dff_tmp["Year_int"] = pd.to_numeric(dff_tmp["Year"], errors="coerce").astype("Int64")
            dff_tmp["Citas"] = pd.to_numeric(dff_tmp[citas_col], errors="coerce").fillna(0)
            citas_year = (
                dff_tmp[dff_tmp["Year_int"].notna()]
                .groupby("Year_int")["Citas"].sum()
                .reset_index().rename(columns={"Year_int": "Year"})
            )
            if not citas_year.empty:
                fig = px.bar(citas_year, x="Year", y="Citas", title="Citas por Año", text="Citas")
                fig.update_traces(textposition="outside")
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10),
                                  font=dict(size=10), xaxis=dict(dtick=1))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de citas en este dataset.")


if __name__ == "__main__":
    main()