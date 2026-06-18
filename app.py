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
        <div style="display:flex;justify-content:center;align-items:center;padding:20px 0;margin:10px 0;">
            <img src="data:image/png;base64,{logo_base64}" style="width:220px;height:auto;display:block;">
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

st.markdown("""
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
""", unsafe_allow_html=True)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET_INDEX = 0

# Paleta y orden de cuartiles globales
_Q_ORDER = ["Q1", "Q2", "Q3", "Q4", "Sin cuartil"]
_Q_COLORS = {
    "Q1": "#27ae60", "Q2": "#f1c40f",
    "Q3": "#e67e22", "Q4": "#922b21", "Sin cuartil": "#bdc3c7",
}

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


def _n(n: int) -> str:
    """Formatea enteros con punto como separador de miles (convención chilena)."""
    return f"{int(n):,}".replace(",", ".")


def _short_dept(name: str) -> str:
    """Nombre corto para mostrar en gráficos: quita prefijos largos."""
    return (
        name.replace("Departamento de ", "")
            .replace("Servicio de ", "")
            .strip()
    )


# Normalización de nombres de países para el mapa de colaboración
_COUNTRY_ALIASES: dict = {
    "usa": "United States", "united states of america": "United States",
    "u.s.a.": "United States", "us": "United States",
    "uk": "United Kingdom", "great britain": "United Kingdom",
    "england": "United Kingdom", "scotland": "United Kingdom",
    "peoples r china": "China", "p.r. china": "China",
    "republic of korea": "South Korea", "korea": "South Korea",
    "brasil": "Brazil",
    "espana": "Spain",
    "alemania": "Germany",
    "suiza": "Switzerland", "suisse": "Switzerland",
    "belgica": "Belgium",
    "holanda": "Netherlands", "the netherlands": "Netherlands",
    "nueva zelanda": "New Zealand",
    "mexico": "Mexico",
    "chile": "Chile",
    "iran (islamic republic of)": "Iran",
    "viet nam": "Vietnam",
}


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
    ("neuropsicolog",                 "Departamento de Neurología y Salud Mental"),
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
    # Específicos primero para evitar falsos positivos de "laboratory"
    ("laboratorio clinico", "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("clinical laboratory", "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("banco de sangre",   "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("anatomia patol",    "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("servicio de anatomia", "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("patholog",          "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    # "laboratorio" y "laboratory" al final como fallback
    ("laboratorio",       "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("laboratory",        "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
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
    if not isinstance(affiliation, str):
        return "Sin depto. especificado"
    t = _norm_text(affiliation)
    for kw, dep in _DEPT_RULES:
        if kw in t:
            return dep
    return "Sin depto. especificado"


def get_cas_departments(affil_str: str, include_udd: bool = True) -> List[str]:
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
    ct_regex = r"(ensayo\s*cl[ií]nico|clinical\s*trial|randomi[sz]ed|phase\s*[i1v]+|double\s*blind|placebo\-controlled)"
    return bool(re.search(ct_regex, text, re.IGNORECASE))


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


def _cas_mask_vectorized(work: pd.DataFrame, aff_cols: List[str], include_udd: bool) -> pd.Series:
    """Reemplaza el apply fila a fila — 10× más rápido en datasets grandes."""
    cas_pattern = r"clinica alemana|alemana clinic"
    if include_udd:
        cas_pattern += r"|universidad del desarrollo|\budd\b|icim|cegen|facultad de medicina clinica alemana"
    combined = pd.Series("", index=work.index)
    for col in aff_cols:
        if col in work.columns:
            combined = combined + " " + work[col].fillna("").astype(str).str.lower()
    return combined.str.contains(cas_pattern, regex=True, na=False)


_name_regex = re.compile(r"^\s*([^,;|]+)\s*,\s*([^,;|]+)")


def _chunk_authors_with_affils(affils: str) -> Iterable[str]:
    if not isinstance(affils, str) or not affils.strip():
        return []
    return [c.strip() for c in re.split(r";", affils) if c.strip()]


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
        return f"{m.group('surname').strip()}, {m.group('initials').strip()}"
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
    first_alpha = next((ch for ch in given_norm if ch.isalpha()), "")
    return f"{last_norm}|{first_alpha}"


def _strip_scopus_id(name: str) -> str:
    return re.sub(r"\s*\([^)]+\)\s*$", "", name.strip()).strip()


def _build_fullname_lookup(dff: pd.DataFrame) -> dict:
    lookup: dict = {}
    fn_col = _first_col(dff, ["AuthorNames_consolidated", "Author full names", "Author Full Names"])
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


def build_cas_ranking(
    dff: pd.DataFrame,
    include_udd: bool,
    fmt: str,
    top_n: int,
    aff_col: Optional[str],
    author_col: Optional[str],
) -> pd.DataFrame:
    fullname_lookup = _build_fullname_lookup(dff)

    work = dff.copy()
    id_col = _first_col(work, ["ID_final", "DOI", "EID", "UT", "PMID"])
    if not id_col:
        work["_id"] = work.index.astype(str)
        id_col = "_id"

    # Vectorized CAS mask — reemplaza apply() fila a fila
    aff_cols = [c for c in [aff_col, "Affiliations", "Addresses"] if c]
    cas_mask = _cas_mask_vectorized(work, aff_cols, include_udd)
    work = work.loc[cas_mask].copy()

    if work.empty:
        return pd.DataFrame()

    auth_col = _first_col(work, ["AuthorNames_consolidated", "Author full names", "Author Full Names", "Authors"])
    rows = []
    for _, row in work.iterrows():
        pub_id = row[id_col]
        raw_authors = str(row.get(auth_col, "")) if auth_col and pd.notna(row.get(auth_col)) else ""
        if not raw_authors or raw_authors.lower() == "nan":
            continue
        seen_in_pub: set = set()
        for entry in raw_authors.split(";"):
            name = _strip_scopus_id(entry)
            if not name:
                continue
            key = canon_author(name)
            if not key or key in seen_in_pub:
                continue
            seen_in_pub.add(key)
            display = fullname_lookup.get(key, name)
            rows.append({"Autor_original": display, "Autor_key": key, "Pub_ID": pub_id})

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
            given = v.split(",", 1)[1].strip() if has_comma else ""
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

    return (
        result[["Autor", "Publicaciones"]]
        .sort_values(["Publicaciones", "Autor"], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )


def _author_yearly_evolution(dff: pd.DataFrame, author_display: str) -> pd.DataFrame:
    """Publicaciones por año para un autor dado (busca por nombre display)."""
    auth_col = _first_col(dff, ["AuthorNames_consolidated", "Author full names", "Author Full Names", "Authors"])
    if not auth_col or "Year_int" not in dff.columns:
        return pd.DataFrame()
    key = canon_author(author_display)
    rows = []
    for _, row in dff.iterrows():
        raw = str(row.get(auth_col, "")) if pd.notna(row.get(auth_col)) else ""
        for entry in raw.split(";"):
            name = _strip_scopus_id(entry)
            if canon_author(name) == key and pd.notna(row["Year_int"]):
                rows.append(int(row["Year_int"]))
                break
    if not rows:
        return pd.DataFrame()
    return (
        pd.Series(rows, name="Year_int")
        .value_counts()
        .reset_index()
        .rename(columns={"Year_int": "Año", "count": "Publicaciones"})
        .sort_values("Año")
    )


# =========================
# Colaboración
# =========================

def _extract_countries(affil_str: str) -> List[str]:
    countries = []
    for seg in _chunk_authors_with_affils(affil_str):
        parts = [p.strip() for p in seg.split(",") if p.strip()]
        if not parts:
            continue
        last = parts[-1].strip()
        if not last or re.match(r"^\d+", last):
            continue
        norm = _norm_text(last)
        country = _COUNTRY_ALIASES.get(norm, last.title())
        countries.append(country)
    return list(set(countries))


def _has_external_collab(affil_str: str, include_udd: bool) -> bool:
    segs = _chunk_authors_with_affils(affil_str)
    if not segs:
        return False
    has_cas = any(_is_cas_affil(s, include_udd) for s in segs)
    has_ext = any(not _is_cas_affil(s, include_udd) for s in segs)
    return has_cas and has_ext


def _has_international_collab(affil_str: str) -> bool:
    return len(_extract_countries(affil_str)) > 1


# =========================
# Inferencia de departamento (3 estrategias)
# =========================

# Mapeo área temática WoS → departamento CAS (último recurso)
_AREA_TO_DEPT: List[tuple] = [
    ("cardiol",           "Departamento de Enfermedades Cardiovasculares"),
    ("cardiac",           "Departamento de Enfermedades Cardiovasculares"),
    ("cardiovasc",        "Departamento de Enfermedades Cardiovasculares"),
    ("oncol",             "Departamento de Oncología"),
    ("cancer",            "Departamento de Oncología"),
    ("pediatr",           "Departamento de Pediatría"),
    ("neonat",            "Departamento de Pediatría"),
    ("neurol",            "Departamento de Neurología y Salud Mental"),
    ("neuroscien",        "Departamento de Neurología y Salud Mental"),
    ("psychiatr",         "Departamento de Neurología y Salud Mental"),
    ("obstetric",         "Departamento de Ginecología y Obstetricia"),
    ("gynecol",           "Departamento de Ginecología y Obstetricia"),
    ("orthop",            "Departamento de Traumatología y Ortopedia"),
    ("radiol",            "Departamento de Imágenes"),
    ("nuclear med",       "Departamento de Imágenes"),
    ("medical imaging",   "Departamento de Imágenes"),
    ("gastroenterol",     "Departamento de Medicina Interna"),
    ("endocrinol",        "Departamento de Medicina Interna"),
    ("rheumatol",         "Departamento de Medicina Interna"),
    ("infecti",           "Departamento de Medicina Interna"),
    ("pulmonol",          "Departamento de Medicina Interna"),
    ("respirat",          "Departamento de Medicina Interna"),
    ("hematol",           "Departamento de Medicina Interna"),
    ("geriatr",           "Departamento de Medicina Interna"),
    ("transplant",        "Departamento de Medicina Interna"),
    ("immunol",           "Departamento de Medicina Interna"),
    ("anesthesiol",       "Departamento de Pabellones Quirúrgicos"),
    ("anestesi",          "Departamento de Pabellones Quirúrgicos"),
    ("emergency med",     "Departamento de Urgencia General"),
    ("critical care",     "Departamento de Paciente Crítico"),
    ("intensive care",    "Departamento de Paciente Crítico"),
    ("surg",              "Departamento de Cirugía"),
    ("pathol",            "Departamento de Laboratorio, Banco de Sangre y Anatomía Patológica"),
    ("epidemiol",         "ICIM-UDD"),
    ("public health",     "ICIM-UDD"),
    ("global health",     "ICIM-UDD"),
    ("genetics",          "ICIM-UDD"),
    ("genomic",           "ICIM-UDD"),
    ("bioethic",          "ICIM-UDD"),
    ("kinesiol",          "ICIM-UDD"),
    ("physiother",        "ICIM-UDD"),
    ("dental",            "Servicio de Odontología"),
    ("odontol",           "Servicio de Odontología"),
]


def _build_author_dept_lookup(df: pd.DataFrame, aff_col: str) -> dict:
    """Estrategia 1: canon_key → depto más frecuente declarado explícitamente en el dataset."""
    rows = []
    for affil_str in df[aff_col].fillna("").astype(str):
        for seg in _chunk_authors_with_affils(affil_str):
            if not _is_cas_affil(seg, include_udd=True):
                continue
            dep = detect_department(seg)
            if dep == "Sin depto. especificado":
                continue
            m = _name_regex.match(seg)
            if not m:
                continue
            key = canon_author(f"{m.group(1).strip()}, {m.group(2).strip()}")
            if key:
                rows.append({"key": key, "dep": dep})

    if not rows:
        return {}
    return (
        pd.DataFrame(rows)
        .groupby(["key", "dep"]).size().reset_index(name="n")
        .sort_values("n", ascending=False)
        .drop_duplicates("key")
        .set_index("key")["dep"]
        .to_dict()
    )


def _infer_dept_from_coauthors(affil_str: str) -> str:
    """Estrategia 2: depto mayoritario de los co-autores CAS del mismo paper."""
    deps = []
    for seg in _chunk_authors_with_affils(affil_str):
        if not _is_cas_affil(seg, include_udd=True):
            continue
        dep = detect_department(seg)
        if dep != "Sin depto. especificado":
            deps.append(dep)
    if not deps:
        return "Sin depto. especificado"
    return max(set(deps), key=deps.count)


def _infer_dept_from_area(row: pd.Series, wos_col: Optional[str]) -> str:
    """Estrategia 3: mapeo área temática WoS/Scopus → departamento probable."""
    if not wos_col or wos_col not in row.index:
        return "Sin depto. especificado"
    text = _norm_text(str(row.get(wos_col, "") or ""))
    if not text:
        return "Sin depto. especificado"
    for kw, dep in _AREA_TO_DEPT:
        if kw in text:
            return dep
    return "Sin depto. especificado"


def _apply_dept_inference(
    df: pd.DataFrame,
    aff_col: str,
    author_dept_lookup: dict,
    wos_col: Optional[str],
) -> pd.DataFrame:
    """
    Segunda pasada sobre filas sin departamento declarado.
    Aplica las 3 estrategias en cascada y registra la fuente en 'Departamento_fuente'.
    """
    # Inicializar columna de fuente para TODAS las filas
    df["Departamento_fuente"] = "declarado"
    no_dept = df["Departamentos_lista"].apply(lambda x: x == ["Sin depto. especificado"])
    df.loc[~no_dept, "Departamento_fuente"] = "declarado"

    if not no_dept.any():
        return df

    def _resolve(row: pd.Series):
        affil_str = str(row.get(aff_col, "")) if pd.notna(row.get(aff_col)) else ""

        # ── Estrategia 1: mismo autor en otros papers ─────────────────────────
        for seg in _chunk_authors_with_affils(affil_str):
            if not _is_cas_affil(seg, include_udd=True):
                continue
            m = _name_regex.match(seg)
            if not m:
                continue
            key = canon_author(f"{m.group(1).strip()}, {m.group(2).strip()}")
            if key and key in author_dept_lookup:
                return [author_dept_lookup[key]], "inferido (historial autor)"

        # ── Estrategia 2: co-autores del mismo paper ──────────────────────────
        dep2 = _infer_dept_from_coauthors(affil_str)
        if dep2 != "Sin depto. especificado":
            return [dep2], "inferido (co-autores)"

        # ── Estrategia 3: área temática ───────────────────────────────────────
        dep3 = _infer_dept_from_area(row, wos_col)
        if dep3 != "Sin depto. especificado":
            return [dep3], "inferido (área temática)"

        return ["Sin depto. especificado"], "sin datos"

    results = df.loc[no_dept].apply(_resolve, axis=1)
    df.loc[no_dept, "Departamentos_lista"] = results.apply(lambda x: x[0])
    df.loc[no_dept, "Departamento_fuente"]  = results.apply(lambda x: x[1])

    # Actualizar columna de texto Departamento
    df["Departamento"] = df["Departamentos_lista"].apply(
        lambda lst: lst[0] if lst and lst != ["Sin depto. especificado"] else "Sin depto. especificado"
    )
    return df


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


def _resolve_quartile(df: pd.DataFrame, sjr_col, jif_q_col, jci_q_col) -> pd.Series:
    """Vectorizado — SJR tiene mayor prioridad sobre JIF, JIF sobre JCI."""
    def _norm_q_series(s: pd.Series) -> pd.Series:
        s = s.astype(str).str.upper().str.strip()
        result = pd.Series(None, index=s.index, dtype=object)
        q_mask = s.isin({"Q1", "Q2", "Q3", "Q4"})
        result[q_mask] = s[q_mask]
        n_mask = s.isin({"1", "2", "3", "4"})
        result[n_mask] = "Q" + s[n_mask]
        return result

    # Aplicar en orden de menor a mayor prioridad; la última escritura gana
    result = pd.Series(None, index=df.index, dtype=object)
    for col in [jci_q_col, jif_q_col, sjr_col]:
        if col and col in df.columns:
            mapped = _norm_q_series(df[col])
            result = mapped.where(mapped.notna(), result)
    return result.fillna("Sin cuartil")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["Year"] = _pick_best_year(df)

    oa_main = _first_col(df, ["OpenAccess_flag", "Open Access", "OA"])
    if oa_main:
        sr = df[oa_main].astype(str).str.lower().str.strip()
        df["OpenAccess_flag"] = sr.isin({"1", "true", "t", "yes", "y", "si", "sí"})
    else:
        df["OpenAccess_flag"] = False

    jif_col = _first_col(df, ["Journal Impact Factor", "Impact Factor", "JIF", "JIF_2023", "JCR_IF"])
    df["Journal Impact Factor"] = pd.to_numeric(df[jif_col], errors="coerce").fillna(0) if jif_col else 0

    sjr_col   = _first_col(df, ["SJR Best Quartile", "Best Quartile"])
    jif_q_col = _first_col(df, ["JIF Quartile", "JCR Quartile"])
    jci_q_col = _first_col(df, ["JCI Quartile"])
    df["Quartile"] = _resolve_quartile(df, sjr_col, jif_q_col, jci_q_col)

    aff_col = _first_col(df, [
        "Authors with affiliations", "Affiliations", "Author Affiliations",
        "Affiliation(s)", "Affiliation", "Author Affiliation",
        "Correspondence Address", "Address", "Reprint Address",
    ])
    wos_col = _first_col(df, ["WoS Categories", "Research Areas", "Categories"])

    if aff_col:
        # Pase 1: detección explícita desde afiliación declarada
        df["Departamentos_lista"] = df[aff_col].apply(
            lambda x: get_cas_departments(str(x) if pd.notna(x) else "", include_udd=True)
        )
        df["Departamento"] = df["Departamentos_lista"].apply(
            lambda lst: lst[0] if lst and lst != ["Sin depto. especificado"] else "Sin depto. especificado"
        )
        df["Colab_externa"] = df[aff_col].fillna("").apply(
            lambda x: _has_external_collab(x, include_udd=True)
        )
        df["Colab_internacional"] = df[aff_col].fillna("").apply(_has_international_collab)

        # Pase 2: inferencia para los que quedaron sin departamento
        author_dept_lookup = _build_author_dept_lookup(df, aff_col)
        df = _apply_dept_inference(df, aff_col, author_dept_lookup, wos_col)
    else:
        df["Departamentos_lista"] = [["Sin depto. especificado"]] * len(df)
        df["Departamento"] = "Sin depto. especificado"
        df["Departamento_fuente"] = "sin datos"
        df["Colab_externa"] = False
        df["Colab_internacional"] = False

    df["ClinicalTrial_flag"] = df.apply(detect_clinical_trial, axis=1)

    jbest = _pick_best_journal(df).fillna("").astype(str).str.strip()

    _JOURNAL_FIXED = {
        "revista medica de chile": "Revista Médica de Chile",
        "medica chile": "Revista Médica de Chile",
        "rev med chile": "Revista Médica de Chile",
        "plos one": "PLOS ONE",
        "bmj": "BMJ",
        "nejm": "NEJM",
        "the lancet": "The Lancet",
        "lancet": "The Lancet",
    }
    _LOWER_EXCEPTIONS = {"de", "del", "la", "las", "los", "y", "en", "of", "and", "the"}

    def fmt_journal(s: str) -> str:
        if not s or s.lower() in {"nan", "none"}:
            return ""
        base = unidecode.unidecode(s.strip().lower())
        if base in _JOURNAL_FIXED:
            return _JOURNAL_FIXED[base]
        words = re.sub(r"\s+", " ", s.strip()).split(" ")
        titled = " ".join(
            w.capitalize() if w.lower() not in _LOWER_EXCEPTIONS else w.lower()
            for w in words
        )
        titled = re.sub(r"\bBmj\b", "BMJ", titled)
        titled = re.sub(r"\bNejm\b", "NEJM", titled)
        titled = re.sub(r"\bPlos One\b", "PLOS ONE", titled)
        return titled

    df["Journal_display"] = jbest.map(fmt_journal)

    a_col = _first_col(df, ["AuthorNames_consolidated", "Author Full Names", "Author full names", "Authors", "Author Names", "Author", "Author(s)"])
    df["Authors_norm"] = df[a_col].fillna("").astype(str) if a_col else ""

    return df


# =========================
# Carga — fix: no st.stop() dentro de @st.cache_data
# =========================

@st.cache_data(show_spinner=False)
def load_data(uploaded=None) -> Optional[pd.DataFrame]:
    if uploaded is not None:
        return normalize_columns(pd.read_excel(uploaded, sheet_name=DEFAULT_SHEET_INDEX))
    if Path(DEFAULT_XLSX).exists():
        return normalize_columns(pd.read_excel(DEFAULT_XLSX, sheet_name=DEFAULT_SHEET_INDEX))
    return None


@st.cache_data(show_spinner=False)
def _cached_cas_ranking(
    dff: pd.DataFrame,
    include_udd: bool,
    fmt: str,
    top_n: int,
    aff_col: Optional[str],
    author_col: Optional[str],
) -> pd.DataFrame:
    return build_cas_ranking(dff, include_udd, fmt, top_n, aff_col, author_col)


# =========================
# Filtros
# =========================

def setup_filters(df: pd.DataFrame):
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
        quart_vals = [q for q in _Q_ORDER if q in df["Quartile"].unique().tolist()] or ["Sin cuartil"]
        quart_filter = st.multiselect("Cuartiles", quart_vals, default=quart_vals, key="quart_multiselect")

    with st.sidebar.expander("🏥 Departamentos", expanded=False):
        all_deps = sorted(set(
            dep for lst in df["Departamentos_lista"]
            for dep in lst if dep != "Sin depto. especificado"
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

    with st.sidebar.expander("🔍 Búsqueda en texto", expanded=False):
        search_term = st.text_input("Buscar en Título / Abstract / Keywords", key="search_input")

    return year_range, oa_filter, quart_filter, dept_filter, search_term, doc_filter


# =========================
# Exportación HTML
# =========================

def _prep_fig_for_export(fig: go.Figure) -> go.Figure:
    """Devuelve una copia de la figura con márgenes y ejes ajustados para HTML.

    Los márgenes compactos (l=10, b=10) que funcionan bien en Streamlit recortan
    los labels del eje X en el HTML exportado porque el layout no tiene espacio para
    los tick-labels completos. automargin=True + márgenes mínimos lo corrige.
    """
    fig = go.Figure(fig)  # copia sin mutar el original (que Streamlit sigue mostrando)

    # Detectar si el gráfico tiene barras/líneas horizontales — en ese caso el eje Y
    # ya tiene automargin desde el código, pero el eje X lleva las categorías.
    is_horizontal = any(
        getattr(t, "orientation", None) == "h"
        for t in fig.data
    )

    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)

    # Para gráficos con año en X (verticales) rotar labels si hay muchos ticks
    if not is_horizontal:
        # Leer el dtick actual; si es 1 (un tick por año) y hay muchos años → rotar
        xaxis = fig.layout.xaxis
        if getattr(xaxis, "dtick", None) == 1:
            fig.update_xaxes(tickangle=-45)

    # Garantizar márgenes mínimos suficientes para labels completos
    m = fig.layout.margin or {}
    fig.update_layout(
        margin=dict(
            l=max(int(getattr(m, "l", 0) or 0), 80),
            r=max(int(getattr(m, "r", 0) or 0), 30),
            t=max(int(getattr(m, "t", 0) or 0), 60),
            b=max(int(getattr(m, "b", 0) or 0), 90),  # espacio para labels rotados
        ),
        font=dict(size=12),  # fuente ligeramente mayor que en Streamlit (size=10)
    )
    return fig


def _generate_html_report(dff: pd.DataFrame, title: str, figs: List[go.Figure]) -> str:
    """Genera un informe HTML autónomo con todos los gráficos Plotly embebidos.

    Estrategia de carga de Plotly.js:
    - La primera figura usa include_plotlyjs='cdn', lo que inyecta un <script src=...>
      inline ANTES del div/script de ese gráfico — garantía de que Plotly está cargado.
    - Las figuras restantes usan include_plotlyjs=False (reusan el JS ya cargado).
    - NO ponemos el CDN en el <head> porque los scripts inline del body se parsean
      antes de que un <head> CDN sin 'defer' termine de ejecutarse en algunos browsers.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    valid_figs = [f for f in figs if f is not None]
    if not valid_figs:
        return "<html><body><p>No hay gráficos para exportar.</p></body></html>"

    charts_html_parts: List[str] = []
    for i, fig in enumerate(valid_figs):
        include_js = "cdn" if i == 0 else False
        try:
            div = _prep_fig_for_export(fig).to_html(
                full_html=False,
                include_plotlyjs=include_js,
                config={"responsive": True, "displayModeBar": True},
            )
        except Exception:
            continue
        charts_html_parts.append(f'<div class="chart">{div}</div>')

    charts_html = "\n".join(charts_html_parts)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 30px; background: #f8f9fa; color: #333; }}
  h1 {{ color: #1f77b4; text-align: center; }}
  p.meta {{ text-align: center; color: #666; font-size: 13px; margin-bottom: 30px; }}
  .chart {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 25px;
            box-shadow: 0 2px 6px rgba(0,0,0,.08); }}
</style>
</head>
<body>
<h1>📊 {title}</h1>
<p class="meta">Generado el {now} · {_n(len(dff))} publicaciones · {len(valid_figs)} gráficos</p>
{charts_html}
</body>
</html>"""


# =========================
# MAIN
# =========================

def main():
    up = st.sidebar.file_uploader("📂 Sube un XLSX", type=["xlsx"])

    with st.spinner("Cargando y normalizando dataset…"):
        df = load_data(up)

    if df is None:
        st.error(f"No se encontró `{DEFAULT_XLSX}`. Sube un XLSX en la barra lateral.")
        st.stop()

    # ── Info sidebar ──
    st.sidebar.header("📊 Información del Dataset")
    st.sidebar.write(f"📄 Total de publicaciones: {_n(len(df))}")
    if df["Year"].notna().any():
        st.sidebar.write(f"📅 Años: {int(df['Year'].min())} – {int(df['Year'].max())}")
    all_deps_unique = set(
        dep for lst in df["Departamentos_lista"]
        for dep in lst if dep != "Sin depto. especificado"
    )
    st.sidebar.write(f"🏥 Departamentos únicos: {len(all_deps_unique)}")

    year_range, oa_filter, quart_filter, dept_filter, search_term, doc_filter = setup_filters(df)

    # ── Guard: cuartil vacío ──
    if not quart_filter:
        st.sidebar.warning("⚠️ Selecciona al menos un cuartil.")
        st.info("No hay publicaciones que mostrar: ningún cuartil seleccionado.")
        st.stop()

    # ── Aplicar filtros ──
    mask = pd.Series(True, index=df.index)
    yr_ok = df["Year"].between(year_range[0], year_range[1], inclusive="both")
    mask &= df["Year"].isna() | yr_ok

    if oa_filter == "Solo OA":
        mask &= df["OpenAccess_flag"]
    elif oa_filter == "No OA":
        mask &= ~df["OpenAccess_flag"]

    mask &= df["Quartile"].isin(quart_filter)

    if dept_filter:
        mask &= df["Departamentos_lista"].apply(lambda lst: any(d in dept_filter for d in lst))

    if doc_filter:
        doc_col = _first_col(df, ["Document Type", "Publication Type", "DT", "Type", "Tipo"])
        if doc_col:
            mask &= df[doc_col].astype(str).isin(doc_filter)

    # Búsqueda en Título + Abstract + Keywords (antes solo buscaba en Title)
    if search_term.strip():
        search_cols = ["Title", "Abstract", "Author Keywords", "Keywords", "Index Keywords"]
        combined_text = pd.Series("", index=df.index)
        for sc in search_cols:
            if sc in df.columns:
                combined_text = combined_text + " " + df[sc].fillna("").astype(str)
        mask &= combined_text.str.contains(search_term, case=False, na=False, regex=False)

    dff = df.loc[mask].copy()
    # Year_int calculado una sola vez — los tabs reusan esta columna
    dff["Year_int"] = pd.to_numeric(dff["Year"], errors="coerce").astype("Int64")

    st.sidebar.write(f"🔍 Registros después de filtrar: {_n(len(dff))}")

    if dff.empty:
        st.warning("No hay publicaciones que cumplan los filtros actuales.")
        st.stop()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    st.header("📊 Métricas Principales")

    citas_col = _first_col(dff, ["Cited by", "Times Cited", "Citation Count", "Citas"])
    total_citas = pd.to_numeric(dff[citas_col], errors="coerce").fillna(0) if citas_col else pd.Series([0] * len(dff), index=dff.index)

    sorted_citas = total_citas.sort_values(ascending=False).reset_index(drop=True)
    h_index = int(sum(sorted_citas >= (np.arange(len(sorted_citas)) + 1)))

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("📚 Publicaciones", f"{_n(len(dff))} / {_n(len(df))}")
    with col2: st.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
    with col3: st.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
    with col4: st.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

    col5, col6, col7, col8 = st.columns(4)
    with col5: st.metric("📖 Total citas", _n(int(total_citas.sum())))
    with col6: st.metric("📖 Promedio citas", f"{total_citas.mean():.1f}")
    with col7: st.metric("🏆 % en Q1", f"{100 * (dff['Quartile'] == 'Q1').mean():.1f}%")
    with col8: st.metric("📊 h-index", h_index)

    if "Colab_externa" in dff.columns:
        col9, col10 = st.columns(2)
        with col9:  st.metric("🤝 % Colab. externa",         f"{100 * dff['Colab_externa'].mean():.1f}%")
        with col10: st.metric("🌍 % Colab. internacional",   f"{100 * dff['Colab_internacional'].mean():.1f}%")

    # Lista de figuras para exportar al informe HTML
    _report_figs: List[go.Figure] = []

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
        "🏥 Departamentos", "📑 Revistas", "👥 Autores",
        "🌍 Colaboración", "🔬 Áreas Temáticas",
        "📋 Listado", "☁️ Wordcloud", "📖 Citas",
    ])

    # ── Tab 0: Publicaciones ──────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("📅 Publicaciones por año")
        gg = (
            dff[dff["Year_int"].notna()]
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
            _report_figs.append(fig)
        else:
            st.info("No hay datos con año válido.")

        st.subheader("📈 Suma JIF por año")
        current_year = datetime.now().year
        j = dff[dff["Year_int"].notna() & (dff["Year_int"] <= current_year)]
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
            _report_figs.append(fig)

    # ── Tab 1: Cuartiles ──────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("📊 Distribución global por cuartiles")
        cts = dff["Quartile"].value_counts().reset_index()
        cts.columns = ["Quartile", "Publicaciones"]
        cts["_ord"] = cts["Quartile"].map({q: i for i, q in enumerate(_Q_ORDER)})
        cts = cts.sort_values("_ord").drop(columns="_ord")
        fig = px.pie(cts, names="Quartile", values="Publicaciones", hole=0.4,
                     color="Quartile",
                     color_discrete_map=_Q_COLORS,
                     category_orders={"Quartile": _Q_ORDER})
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)
        _report_figs.append(fig)

        st.subheader("📊 Cuartiles por año")
        q_year = dff[dff["Year_int"].notna() & (dff["Quartile"] != "Sin cuartil")]
        if not q_year.empty:
            pivot = q_year.groupby(["Year_int", "Quartile"]).size().reset_index(name="n")
            fig2 = px.bar(pivot, x="Year_int", y="n", color="Quartile",
                          title="Publicaciones por cuartil y año",
                          color_discrete_map=_Q_COLORS,
                          category_orders={"Quartile": _Q_ORDER})
            fig2.update_layout(barmode="stack", xaxis=dict(dtick=1, title="Año"),
                               yaxis=dict(title="Publicaciones"),
                               margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig2, use_container_width=True)
            _report_figs.append(fig2)
        else:
            st.info("Sin datos suficientes para cuartiles por año.")

    # ── Tab 2: Open Access ────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("🔓 Publicaciones Open Access")
        oa = dff["OpenAccess_flag"].map({True: "Open Access", False: "Closed"}).value_counts().reset_index()
        oa.columns = ["Estado", "Publicaciones"]
        fig = px.pie(oa, names="Estado", values="Publicaciones", hole=0.4,
                     color="Estado",
                     color_discrete_map={"Open Access": "#27ae60", "Closed": "#95a5a6"})
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)
        _report_figs.append(fig)

        st.subheader("📈 Evolución Open Access por año")
        oa_yr = dff[dff["Year_int"].notna()]
        if not oa_yr.empty:
            oa_agg = (
                oa_yr.groupby("Year_int")
                .agg(Total=("OpenAccess_flag", "count"), OA=("OpenAccess_flag", "sum"))
                .reset_index()
            )
            oa_agg["% OA"] = (oa_agg["OA"] / oa_agg["Total"] * 100).round(1)
            fig_oa = px.bar(oa_agg, x="Year_int", y="% OA",
                            title="Porcentaje Open Access por año", text="% OA",
                            labels={"Year_int": "Año", "% OA": "% Open Access"})
            fig_oa.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_oa.update_layout(xaxis=dict(dtick=1), yaxis=dict(range=[0, 110]),
                                 margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig_oa, use_container_width=True)
            _report_figs.append(fig_oa)

    # ── Tab 3: Departamentos ──────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("🏥 Publicaciones por Departamento CAS/UDD")
        st.caption("Cada publicación puede contarse en más de un departamento si tiene autores de distintas unidades.")

        # Resumen de cobertura de la inferencia
        if "Departamento_fuente" in dff.columns:
            fuente_counts = dff["Departamento_fuente"].value_counts()
            n_declarado   = int(fuente_counts.get("declarado", 0))
            n_hist        = int(fuente_counts.get("inferido (historial autor)", 0))
            n_coautor     = int(fuente_counts.get("inferido (co-autores)", 0))
            n_area        = int(fuente_counts.get("inferido (área temática)", 0))
            n_sin         = int(fuente_counts.get("sin datos", 0))
            n_total_dff   = len(dff)
            with st.expander("📊 Cobertura de asignación de departamento", expanded=False):
                cc1, cc2, cc3, cc4, cc5 = st.columns(5)
                cc1.metric("✅ Declarado",            f"{_n(n_declarado)} ({100*n_declarado/n_total_dff:.0f}%)")
                cc2.metric("🔁 Historial autor",      f"{_n(n_hist)} ({100*n_hist/n_total_dff:.0f}%)")
                cc3.metric("👥 Co-autores",           f"{_n(n_coautor)} ({100*n_coautor/n_total_dff:.0f}%)")
                cc4.metric("🔬 Área temática",        f"{_n(n_area)} ({100*n_area/n_total_dff:.0f}%)")
                cc5.metric("❓ Sin datos",             f"{_n(n_sin)} ({100*n_sin/n_total_dff:.0f}%)")
                st.caption(
                    "**Declarado**: el autor especificó su departamento en la afiliación. "
                    "**Historial autor**: inferido del mismo autor en otros papers. "
                    "**Co-autores**: inferido de los co-autores CAS del mismo paper. "
                    "**Área temática**: inferido de las categorías WoS/Scopus del journal."
                )

        dep_exploded = (
            dff[["Departamentos_lista", "Year_int"]].copy()
            .explode("Departamentos_lista")
            .rename(columns={"Departamentos_lista": "Departamento"})
        )
        dep_exploded = dep_exploded[dep_exploded["Departamento"] != "Sin depto. especificado"]

        dep = dep_exploded["Departamento"].value_counts().reset_index()
        dep.columns = ["Departamento", "Publicaciones"]

        if not dep.empty:
            dep["Depto_corto"] = dep["Departamento"].map(_short_dept)
            fig = px.bar(
                dep.sort_values("Publicaciones"),
                x="Publicaciones", y="Depto_corto", orientation="h",
                title="Publicaciones por Departamento", text="Publicaciones",
            )
            fig.update_traces(textposition="inside", insidetextanchor="start")
            fig.update_layout(
                yaxis=dict(categoryorder="total ascending", title=""),
                margin=dict(l=220, r=10, t=50, b=10),
                height=max(400, 40 * len(dep) + 100), font=dict(size=11),
            )
            st.plotly_chart(fig, use_container_width=True)
            _report_figs.append(fig)

            # % de papers con participación de cada depto
            st.subheader("📊 % de publicaciones con participación de cada departamento")
            st.caption(
                f"Sobre {_n(len(dff))} publicaciones únicas. "
                "Un paper con autores de 3 deptos. suma 1 en cada → los % pueden superar 100%."
            )
            total_papers = len(dff)
            dept_paper_counts = {
                d: int(dff["Departamentos_lista"].apply(lambda lst: d in lst).sum())
                for d in dep["Departamento"].tolist()
            }
            dep_pct = (
                pd.DataFrame(list(dept_paper_counts.items()), columns=["Departamento", "Papers"])
                .assign(Porcentaje=lambda d: (d["Papers"] / total_papers * 100).round(1))
                .sort_values("Porcentaje", ascending=True)
            )
            dep_pct["Depto_corto"] = dep_pct["Departamento"].map(_short_dept)
            fig_pct = px.bar(
                dep_pct, x="Porcentaje", y="Depto_corto", orientation="h",
                title="% de publicaciones con participación de cada departamento",
                text=dep_pct.apply(lambda r: f"{r['Porcentaje']}% ({r['Papers']})", axis=1),
                color="Porcentaje", color_continuous_scale="Blues",
            )
            fig_pct.update_traces(textposition="inside", insidetextanchor="start")
            fig_pct.update_layout(
                xaxis=dict(title="% del total de publicaciones", range=[0, 105]),
                yaxis=dict(categoryorder="total ascending", title=""),
                coloraxis_showscale=False,
                margin=dict(l=220, r=10, t=50, b=10),
                height=max(400, 40 * len(dep_pct) + 100), font=dict(size=11),
            )
            st.plotly_chart(fig_pct, use_container_width=True)
            _report_figs.append(fig_pct)

            # Evolución por depto y año
            st.subheader("📈 Evolución por departamento y año")
            dep_yr = dep_exploded[dep_exploded["Year_int"].notna()].copy()
            if not dep_yr.empty:
                top_deps = dep["Departamento"].head(8).tolist()
                dep_yr_top = dep_yr[dep_yr["Departamento"].isin(top_deps)].copy()
                dep_yr_top["Depto_corto"] = dep_yr_top["Departamento"].map(_short_dept)
                pivot_dep = dep_yr_top.groupby(["Year_int", "Depto_corto"]).size().reset_index(name="n")
                fig2 = px.line(pivot_dep, x="Year_int", y="n", color="Depto_corto",
                               markers=True, title="Top 8 departamentos por año")
                fig2.update_layout(xaxis=dict(dtick=1, title="Año"),
                                   yaxis=dict(title="Publicaciones"),
                                   legend=dict(title="Departamento"),
                                   margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig2, use_container_width=True)
                _report_figs.append(fig2)
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
        jr = journals[journals != ""].value_counts().head(20).reset_index()
        jr.columns = ["Revista", "Publicaciones"]

        if not jr.empty:
            fig = px.bar(
                jr.sort_values("Publicaciones"),
                x="Publicaciones", y="Revista", orientation="h",
                title="Top 20 Revistas", text="Publicaciones",
            )
            fig.update_layout(yaxis=dict(categoryorder="total ascending"),
                              margin=dict(l=260, r=10, t=50, b=10), height=560,
                              yaxis_tickfont=dict(size=12), font=dict(size=10))
            fig.update_traces(textposition="inside", insidetextanchor="start")
            st.plotly_chart(fig, use_container_width=True)
            _report_figs.append(fig)

        st.subheader("📋 Revistas con métricas (JIF / Cuartil)")
        jif_col_name = _first_col(dff, ["Journal Impact Factor"])
        if jif_col_name:
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
            st.download_button(
                "⬇️ Descargar tabla revistas (CSV)",
                data=rev_metrics.to_csv(index=False).encode("utf-8-sig"),
                file_name="revistas_metricas.csv", mime="text/csv",
            )

    # ── Tab 5: Autores CAS ────────────────────────────────────────────────────
    with tabs[5]:
        st.subheader("👥 Autores CAS (solo autores con afiliación a Clínica Alemana/UDD)")
        aff_col = _first_col(dff, [
            "Authors with affiliations", "Affiliations", "Author Affiliations",
            "Affiliation(s)", "Affiliation", "Author Affiliation",
        ])
        if not aff_col:
            st.warning("No se encontró la columna de afiliaciones.")
        else:
            colA, colB, colC = st.columns([1.2, 1.6, 1])
            with colA:
                fmt_choice = st.radio("Formato:", ["Apellido, Inicial", "Apellido, Nombre(s)"],
                                      horizontal=True, index=0, key="fmt_radio")
            with colB:
                include_udd = st.checkbox("Incluir UDD/ICIM/F. Medicina además de Clínica Alemana",
                                          value=True, key="include_udd_cb")
            with colC:
                top_n = st.slider("Top N", min_value=10, max_value=100, value=50, step=5, key="topn_slider")

            fmt_key = "initials" if fmt_choice == "Apellido, Inicial" else "full"
            author_col = _first_col(dff, ["AuthorNames_consolidated", "Author full names", "Author Full Names", "Authors"])

            with st.spinner("Calculando ranking de autores CAS…"):
                ranking = _cached_cas_ranking(dff, include_udd, fmt_key, top_n, aff_col, author_col)

            if ranking.empty:
                st.info("No se detectaron autores CAS en el subconjunto filtrado.")
            else:
                plot_df = ranking.sort_values("Publicaciones", ascending=True)
                max_label_len = int(plot_df["Autor"].astype(str).str.len().max())
                left_margin = min(520, 160 + max_label_len * 7)

                fig = px.bar(plot_df, x="Publicaciones", y="Autor", orientation="h",
                             title=f"Top {len(plot_df)} Autores CAS · {fmt_choice}",
                             text="Publicaciones")
                fig.update_layout(
                    yaxis=dict(categoryorder="total ascending", automargin=True, title="Autor"),
                    margin=dict(l=left_margin, r=20, t=60, b=40),
                    height=max(500, 20 * len(plot_df) + 160), font=dict(size=12),
                )
                fig.update_traces(textposition="inside", insidetextanchor="start")
                st.plotly_chart(fig, use_container_width=True)
                _report_figs.append(fig)

                # Evolución temporal del autor seleccionado
                st.subheader("📈 Evolución temporal de un autor")
                selected_author = st.selectbox(
                    "Selecciona un autor para ver su producción por año:",
                    ranking["Autor"].tolist(), key="autor_evo_select",
                )
                if selected_author:
                    evo_df = _author_yearly_evolution(dff, selected_author)
                    if not evo_df.empty:
                        fig_evo = px.bar(
                            evo_df, x="Año", y="Publicaciones",
                            title=f"Producción anual — {selected_author}",
                            text="Publicaciones",
                        )
                        fig_evo.update_traces(textposition="outside")
                        fig_evo.update_layout(
                            xaxis=dict(dtick=1, title="Año"), yaxis=dict(title="Publicaciones"),
                            margin=dict(l=10, r=10, t=50, b=10), font=dict(size=11),
                        )
                        st.plotly_chart(fig_evo, use_container_width=True)
                    else:
                        st.info("No se encontraron datos anuales para este autor.")

                st.subheader("📋 Ranking (tabla)")
                st.dataframe(ranking, use_container_width=True, height=400)
                st.download_button(
                    "⬇️ Descargar ranking CAS (CSV)",
                    data=ranking.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"ranking_autores_CAS_top{len(plot_df)}.csv",
                    mime="text/csv",
                )

    # ── Tab 6: Colaboración ───────────────────────────────────────────────────
    with tabs[6]:
        st.subheader("🌍 Análisis de Colaboración")

        if "Colab_externa" not in dff.columns:
            st.info("No hay datos de colaboración disponibles.")
        else:
            n_total  = len(dff)
            n_ext    = int(dff["Colab_externa"].sum())
            n_intl   = int(dff["Colab_internacional"].sum())
            n_int_only = n_total - n_ext

            c1, c2, c3 = st.columns(3)
            with c1:  st.metric("🏛️ Solo interna",           f"{_n(n_int_only)} ({100*n_int_only/n_total:.1f}%)")
            with c2:  st.metric("🤝 Con colab. externa",      f"{_n(n_ext)} ({100*n_ext/n_total:.1f}%)")
            with c3:  st.metric("🌍 Con colab. internacional", f"{_n(n_intl)} ({100*n_intl/n_total:.1f}%)")

            n_nacional = max(0, n_ext - n_intl)
            collab_counts = pd.DataFrame({
                "Tipo": ["Solo interna", "Colab. nacional", "Colab. internacional"],
                "Publicaciones": [n_int_only, n_nacional, n_intl],
            })
            collab_counts = collab_counts[collab_counts["Publicaciones"] > 0]
            fig_col = px.pie(
                collab_counts, names="Tipo", values="Publicaciones", hole=0.4,
                title="Distribución por tipo de colaboración",
                color="Tipo",
                color_discrete_map={
                    "Solo interna": "#3498db",
                    "Colab. nacional": "#2ecc71",
                    "Colab. internacional": "#e67e22",
                },
            )
            fig_col.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=11))
            st.plotly_chart(fig_col, use_container_width=True)
            _report_figs.append(fig_col)

            # Evolución de colaboración por año
            st.subheader("📈 Evolución de colaboración por año")
            cyr = dff[dff["Year_int"].notna()]
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
                cyr_agg["% Externa"]       = (cyr_agg["Externa"]       / cyr_agg["Total"] * 100).round(1)
                cyr_agg["% Internacional"] = (cyr_agg["Internacional"] / cyr_agg["Total"] * 100).round(1)
                fig_cyr = go.Figure()
                fig_cyr.add_trace(go.Scatter(
                    x=cyr_agg["Year_int"], y=cyr_agg["% Externa"],
                    mode="lines+markers", name="% Colab. externa", line=dict(color="#2ecc71"),
                ))
                fig_cyr.add_trace(go.Scatter(
                    x=cyr_agg["Year_int"], y=cyr_agg["% Internacional"],
                    mode="lines+markers", name="% Colab. internacional", line=dict(color="#e67e22"),
                ))
                fig_cyr.update_layout(
                    title="Evolución de colaboración (%)",
                    xaxis=dict(dtick=1, title="Año"), yaxis=dict(title="%", range=[0, 105]),
                    margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10),
                )
                st.plotly_chart(fig_cyr, use_container_width=True)
                _report_figs.append(fig_cyr)

            # Mapa de países colaboradores
            st.subheader("🗺️ Países colaboradores")
            aff_col_map = _first_col(dff, [
                "Authors with affiliations", "Affiliations", "Author Affiliations",
                "Affiliation(s)", "Affiliation",
            ])
            if aff_col_map:
                all_countries: List[str] = []
                for affil_str in dff[aff_col_map].fillna("").astype(str):
                    all_countries.extend(_extract_countries(affil_str))
                if all_countries:
                    country_counts = (
                        pd.Series(all_countries)
                        .value_counts()
                        .reset_index()
                        .rename(columns={"index": "País", 0: "Menciones", "count": "Menciones"})
                    )
                    country_counts.columns = ["País", "Menciones"]
                    fig_map = px.choropleth(
                        country_counts, locations="País",
                        locationmode="country names",
                        color="Menciones",
                        color_continuous_scale="Blues",
                        title="Países con autores colaboradores (frecuencia de aparición en afiliaciones)",
                    )
                    fig_map.update_layout(
                        margin=dict(l=0, r=0, t=50, b=0), font=dict(size=10),
                        geo=dict(showframe=False, showcoastlines=True),
                    )
                    st.plotly_chart(fig_map, use_container_width=True)
                    _report_figs.append(fig_map)

                    st.subheader("📋 Top 20 países")
                    st.dataframe(country_counts.head(20), use_container_width=True, height=300)
                else:
                    st.info("No se pudieron extraer países de las afiliaciones.")
            else:
                st.info("No se encontró columna de afiliaciones para el mapa.")

    # ── Tab 7: Áreas Temáticas ────────────────────────────────────────────────
    with tabs[7]:
        st.subheader("🔬 Áreas Temáticas")
        wos_cat_col = _first_col(dff, ["WoS Categories", "Research Areas", "Areas", "Categories"])
        if wos_cat_col:
            cats_raw = (
                dff[wos_cat_col].dropna().astype(str)
                .str.split(r";|,|\|").explode()
                .str.strip().str.title()
            )
            cats_raw = cats_raw[cats_raw.str.len() > 2]
            top_cats = cats_raw.value_counts().head(20).reset_index()
            top_cats.columns = ["Área", "Publicaciones"]
            if not top_cats.empty:
                fig_cat = px.bar(
                    top_cats.sort_values("Publicaciones"),
                    x="Publicaciones", y="Área", orientation="h",
                    title="Top 20 Áreas Temáticas", text="Publicaciones",
                )
                fig_cat.update_layout(
                    yaxis=dict(categoryorder="total ascending"),
                    margin=dict(l=280, r=10, t=50, b=10),
                    height=max(450, 35 * len(top_cats) + 100), font=dict(size=10),
                )
                fig_cat.update_traces(textposition="inside", insidetextanchor="start")
                st.plotly_chart(fig_cat, use_container_width=True)
                _report_figs.append(fig_cat)
                st.dataframe(top_cats, use_container_width=True, height=300)
        else:
            st.info("No se encontró columna de áreas temáticas (WoS Categories / Research Areas).")

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
                    title="Top 15 Áreas Scimago", text="Publicaciones",
                )
                fig_sjr.update_layout(
                    yaxis=dict(categoryorder="total ascending"),
                    margin=dict(l=260, r=10, t=50, b=10),
                    height=max(400, 35 * len(top_sjr) + 100), font=dict(size=10),
                )
                fig_sjr.update_traces(textposition="inside", insidetextanchor="start")
                st.plotly_chart(fig_sjr, use_container_width=True)

    # ── Tab 8: Listado ────────────────────────────────────────────────────────
    with tabs[8]:
        st.subheader("📋 Listado de publicaciones")
        basic_candidates = [
            "Title", "Journal_display", "Source title", "Year", "DOI",
            "Authors", "Quartile", "Journal Impact Factor", "Departamento",
            "Cited by", "Times Cited", "OpenAccess_flag",
        ]
        selected_cols = [c for c in basic_candidates if c in dff.columns]
        display_df = dff[selected_cols].copy() if selected_cols else dff.copy()

        if "OpenAccess_flag" in display_df.columns:
            display_df["OpenAccess_flag"] = display_df["OpenAccess_flag"].map(
                {True: "Open Access", False: "Closed"}
            ).fillna("Closed")

        rename_map = {
            "Title": "Título", "Journal_display": "Revista", "Source title": "Journal",
            "Year": "Año", "DOI": "DOI", "Authors": "Autores",
            "Quartile": "Cuartil", "Journal Impact Factor": "JIF",
            "Departamento": "Departamento", "Cited by": "Citas_scopus",
            "Times Cited": "Citas_wos", "OpenAccess_flag": "Open Access",
        }
        display_df = display_df.rename(columns={k: v for k, v in rename_map.items() if k in display_df.columns})

        preferred_display_cols = [
            "Título", "Revista", "Año", "DOI", "Autores",
            "Cuartil", "JIF", "Departamento", "Citas_scopus", "Open Access",
        ]
        final_cols = [c for c in preferred_display_cols if c in display_df.columns]
        if final_cols:
            display_df = display_df[final_cols].copy()

        display_df = display_df.reset_index(drop=True)
        display_df.index = display_df.index + 1
        st.caption(f"Mostrando {_n(len(display_df))} publicaciones del subconjunto filtrado.")
        st.dataframe(display_df, use_container_width=True, height=500)

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            display_df.to_excel(writer, index=False, sheet_name="Listado")

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button("⬇️ Descargar listado (CSV)",
                               data=display_df.to_csv(index=False).encode("utf-8-sig"),
                               file_name="listado_publicaciones.csv", mime="text/csv")
        with col_dl2:
            st.download_button("⬇️ Descargar listado (Excel)",
                               data=excel_buffer.getvalue(),
                               file_name="listado_publicaciones.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ── Tab 9: Wordcloud ──────────────────────────────────────────────────────
    with tabs[9]:
        st.subheader("☁️ Wordcloud")
        try:
            import importlib.util
            if importlib.util.find_spec("wordcloud") is None:
                st.info("Instala `wordcloud` para ver esta sección: `pip install wordcloud`")
            else:
                from wordcloud import WordCloud, STOPWORDS
                import matplotlib.pyplot as plt

                custom_stop = set(STOPWORDS)
                custom_stop.update([
                    "el","la","los","las","un","una","unos","unas","de","del","y","en",
                    "por","para","con","the","a","an","of","for","to","with","on","at",
                    "by","from","they","their","this","that","these","those",
                ])

                st.markdown("**Keywords**")
                kw_cols = ["Author Keywords", "Author keywords", "Keywords", "Index Keywords", "Keywords Plus"]
                kws = [dff[c].dropna().astype(str) for c in kw_cols if c in dff.columns]
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
                        fig_t, ax_t = plt.subplots(figsize=(10, 4))
                        ax_t.imshow(wc_title, interpolation="bilinear")
                        ax_t.axis("off")
                        st.pyplot(fig_t, use_container_width=True, clear_figure=True)
        except Exception as e:
            st.warning(f"Error en Wordcloud: {e}")

    # ── Tab 10: Citas ─────────────────────────────────────────────────────────
    with tabs[10]:
        st.subheader("📖 Citas por año")
        if citas_col and (total_citas > 0).any():
            dff_c = dff[["Year_int", citas_col]].copy()
            dff_c["Citas"] = pd.to_numeric(dff_c[citas_col], errors="coerce").fillna(0)
            citas_year = (
                dff_c[dff_c["Year_int"].notna()]
                .groupby("Year_int")["Citas"].sum()
                .reset_index().rename(columns={"Year_int": "Año"})
            )
            if not citas_year.empty:
                fig = px.bar(citas_year, x="Año", y="Citas", title="Citas por Año", text="Citas")
                fig.update_traces(textposition="outside")
                fig.update_layout(margin=dict(l=10, r=10, t=50, b=10),
                                  font=dict(size=10), xaxis=dict(dtick=1))
                st.plotly_chart(fig, use_container_width=True)
                _report_figs.append(fig)
        else:
            st.info("No hay datos de citas en este dataset.")

        # Top papers más citados
        st.subheader("🏆 Top 20 papers más citados")
        if citas_col:
            top_cited_cols = [c for c in ["Title", "Journal_display", "Year", citas_col, "Quartile"] if c in dff.columns]
            top_cited = (
                dff[top_cited_cols]
                .copy()
                .rename(columns={"Title": "Título", "Journal_display": "Revista",
                                 "Year": "Año", citas_col: "Citas", "Quartile": "Cuartil"})
                .sort_values("Citas", ascending=False)
                .head(20)
                .reset_index(drop=True)
            )
            top_cited.index = top_cited.index + 1
            st.dataframe(top_cited, use_container_width=True, height=400)
            st.download_button(
                "⬇️ Descargar top citados (CSV)",
                data=top_cited.to_csv(index=False).encode("utf-8-sig"),
                file_name="top_citados.csv", mime="text/csv",
            )
        else:
            st.info("No hay columna de citas disponible.")

    # ── Exportar informe HTML ─────────────────────────────────────────────────
    st.divider()
    st.subheader("📥 Exportar informe completo")
    st.caption(
        f"Genera un archivo HTML autónomo con los {len(_report_figs)} gráficos principales "
        "del subconjunto filtrado actual. Se abre directamente en cualquier navegador."
    )
    if st.button("Generar informe HTML", type="primary"):
        with st.spinner("Generando informe…"):
            html_content = _generate_html_report(
                dff,
                "Dashboard de Producción Científica — CAS/UDD",
                _report_figs,
            )
        st.download_button(
            "⬇️ Descargar informe HTML",
            data=html_content.encode("utf-8"),
            file_name=f"informe_CAS_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
            mime="text/html",
        )


if __name__ == "__main__":
    main()
