# app_dashboard.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, List
import numpy as np
import pandas as pd
import plotly.express as px
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
# TÍTULO VISIBLE EN EL DASHBOARD
# =========================
st.markdown("""
    <div style="background-color:#f0f2f6;padding:25px;border-radius:10px;margin-bottom:25px;border-left:5px solid #1f77b4">
        <h1 style="color:#1f77b4;text-align:center;margin:0;">📊 Dashboard de Producción Científica</h1>
        <p style="text-align:center;color:#555;margin:10px 0 0 0;font-size:16px;">
            Análisis bibliométrico - Clínica Alemana Universidad del Desarrollo
        </p>
    </div>
""", unsafe_allow_html=True)

# =========================
# Configuración para móviles
# =========================
st.markdown(
    """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem;
        }
        .stButton > button {
            width: 100%;
            margin: 5px 0;
        }
        .stDataFrame {
            font-size: 12px;
        }
        .css-1d391kg {
            padding: 0.5rem;
        }
        /* Ajustar columnas para móviles */
        [data-testid="column"] {
            width: 100% !important;
            flex: unset !important;
        }
        /* Ajustar tabs para móviles */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            flex-wrap: wrap;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px;
            font-size: 12px;
            height: auto;
            min-height: 32px;
        }
        /* Ajustar métricas para móviles */
        [data-testid="stMetricValue"] {
            font-size: 14px;
        }
        [data-testid="stMetricLabel"] {
            font-size: 12px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET_INDEX = 0

# =========================
# Utils
# =========================
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def detect_department(affiliation: str) -> str:
    if not isinstance(affiliation, str):
        return "Sin asignar"
    aff = affiliation.lower()
    rules = [
        ("neurolog", "Neurología y Psiquiatría"),
        ("psiquiatr", "Neurología y Psiquiatría"),
        ("oncolog", "Oncología"),
        ("pediatr", "Pediatría"),
        ("ginecol", "Ginecología y Obstetricia"),
        ("obstetr", "Ginecología y Obstetricia"),
        ("medicina interna", "Medicina Interna"),
        ("internal medicine", "Medicina Interna"),
        ("trauma", "Traumatología y Ortopedia"),
        ("ortoped", "Traumatología y Ortopedia"),
        ("enfermer", "Enfermería"),
        ("imagen", "Imágenes"),
        ("radiolog", "Imágenes"),
        ("urgenc", "Urgencias"),
        ("cirug", "Cirugía"),
        ("anestesi", "Anestesiología"),
        ("cardiol", "Cardiología"),
    ]
    for kw, dep in rules:
        if kw in aff:
            return dep
    return "Clínica Alemana"

def detect_clinical_trial(row: pd.Series) -> bool:
    text = ""
    for col in ["Title", "Abstract", "Publication Type", "Keywords"]:
        if col in row and pd.notna(row[col]):
            text += " " + str(row[col])
    text = text.lower()
    ct_regex = r"(ensayo\s*cl[ií]nico|clinical\s*trial|randomi[sz]ed|phase\s*[i1v]+|double\s*blind|placebo\-controlled)"
    return bool(re.search(ct_regex, text))

def extract_authors_cas(affiliations: str) -> str:
    """Extrae autores con afiliación Clínica Alemana (CAS, Clinica Alemana)."""
    if not isinstance(affiliations, str):
        return ""
    parts = re.split(r";|\|", affiliations)
    cas_authors = []
    for part in parts:
        if re.search(r"(CAS|CL[IÍ]NICA\s+ALEMANA)", part, flags=re.I):
            name = part.split(",")[0].strip()
            if name:
                cas_authors.append(name)
    return "; ".join(cas_authors)

# =========================
# Utils
# =========================
import unidecode

def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Devuelve la primera columna encontrada en df que esté en la lista de candidatos."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def detect_department(affiliation: str) -> str:
    """Clasifica departamentos según palabras clave en las afiliaciones."""
    if not isinstance(affiliation, str):
        return "Sin asignar"
    aff = affiliation.lower()
    rules = [
        ("neurolog", "Neurología y Psiquiatría"),
        ("psiquiatr", "Neurología y Psiquiatría"),
        ("oncolog", "Oncología"),
        ("pediatr", "Pediatría"),
        ("ginecol", "Ginecología y Obstetricia"),
        ("obstetr", "Ginecología y Obstetricia"),
        ("medicina interna", "Medicina Interna"),
        ("internal medicine", "Medicina Interna"),
        ("trauma", "Traumatología y Ortopedia"),
        ("ortoped", "Traumatología y Ortopedia"),
        ("enfermer", "Enfermería"),
        ("imagen", "Imágenes"),
        ("radiolog", "Imágenes"),
        ("urgenc", "Urgencias"),
        ("cirug", "Cirugía"),
        ("anestesi", "Anestesiología"),
        ("cardiol", "Cardiología"),
    ]
    for kw, dep in rules:
        if kw in aff:
            return dep
    return "Clínica Alemana"


def detect_clinical_trial(row: pd.Series) -> bool:
    """Detecta si una publicación es un ensayo clínico a partir de título, abstract o keywords."""
    text = ""
    for col in ["Title", "Abstract", "Publication Type", "Keywords"]:
        if col in row and pd.notna(row[col]):
            text += " " + str(row[col])
    text = text.lower()
    ct_regex = r"(ensayo\s*cl[ií]nico|clinical\s*trial|randomi[sz]ed|phase\s*[i1v]+|double\s*blind|placebo\-controlled)"
    return bool(re.search(ct_regex, text))


def extract_authors_cas(affiliations: str) -> str:
    """Extrae autores con afiliación Clínica Alemana (CAS, Clinica Alemana)."""
    if not isinstance(affiliations, str):
        return ""
    parts = re.split(r";|\|", affiliations)
    cas_authors = []
    for part in parts:
        if re.search(r"(CAS|CL[IÍ]NICA\s+ALEMANA)", part, flags=re.I):
            name = part.split(",")[0].strip()
            if name:
                cas_authors.append(name)
    return "; ".join(cas_authors)


def normalize_institution(name: str) -> str:
    if not isinstance(name, str):
        return ""

    # Normalización básica
    key = unidecode.unidecode(name.lower().strip())

    # Reemplazar guiones raros (– — −) por espacio
    key = re.sub(r"[-–—−]", " ", key)

    # Quitar caracteres especiales (mantener solo letras, números y espacios)
    key = re.sub(r"[^a-z0-9 ]", " ", key)

    # Colapsar espacios múltiples
    key = re.sub(r"\s+", " ", key).strip()

    normalization_map = {
        # =====================
        # Chile
        # =====================
        "universidad de chile": "Universidad de Chile",
        "university of chile": "Universidad de Chile",
        "uchile": "Universidad de Chile",

        "pontificia universidad catolica de chile": "Pontificia Universidad Católica de Chile",
        "pontifical catholic university of chile": "Pontificia Universidad Católica de Chile",
        "universidad catolica de chile": "Pontificia Universidad Católica de Chile",
        "uc chile": "Pontificia Universidad Católica de Chile",

        # =====================
        # Clínica Alemana - UDD
        # =====================
        "clinica alemana universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana universidad de desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana universidad deldesarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana universidad d desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana universidad": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana universidad udd": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana de santiago": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "alemana clinic": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "udd": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "university of development": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "facultad de medicina clinica alemana universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "instituto de ciencias e innovacion en medicina": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "icim": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "centro de genetica y genomica": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "cegen": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",

        # =====================
        # Hospitales y clínicas
        # =====================
        "hospital clinico universidad de chile": "Hospital Clínico Universidad de Chile",
        "hospital clinico universidad catolica": "Hospital Clínico Universidad Católica",
        "hospital clinico puc": "Hospital Clínico Universidad Católica",
        "hospital padre hurtado": "Hospital Padre Hurtado",
        "hospital militar de santiago": "Hospital Militar de Santiago",
        "hospital militar": "Hospital Militar de Santiago",
        "clinica las condes": "Clínica Las Condes",
        "clc": "Clínica Las Condes",

        # =====================
        # Internacionales comunes
        # =====================
        "harvard medical school": "Harvard University",
        "harvard univ": "Harvard University",
        "university of california": "University of California",
        "uc berkeley": "University of California",
        "ucsf": "University of California",
        "university of toronto": "University of Toronto",
        "university of sydney": "University of Sydney",
    }

    return normalization_map.get(key, name.title())


def normalize_author(name: str) -> str:
    """Normaliza autores: 'Lavados, P.M.' -> 'Lavados, P.' o 'P. Lavados' según convención."""
    if not isinstance(name, str) or not name.strip():
        return ""

    name = name.replace(".", "").strip()

    # Caso "Apellido, Nombre"
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
        if re.fullmatch(r"[A-Z ]+", first, flags=re.I):
            first = " ".join(list(first.replace(" ", "")))
        return f"{last}, {first}".title().strip()

    # Caso "Nombre Apellido"
    parts = name.split()
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) > 1:
        last = parts[-1].title()
        initials = " ".join([p[0].upper() + "." for p in parts[:-1]])
        return f"{last}, {initials}"
    return " ".join(parts).title()

# =========================
# Normalización de columnas
# =========================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Year
    year_col = _first_col(df, ["_Year", "Year", "Publication Year", "PY", "Year_clean"])
    df["Year"] = pd.to_numeric(df[year_col], errors="coerce") if year_col else pd.NA

    # Open Access
    oa_main = _first_col(df, ["OpenAccess_flag", "Open Access", "OA"])
    if oa_main:
        sr = df[oa_main].astype(str).str.lower().str.strip()
        df["OpenAccess_flag"] = sr.isin({"1","true","t","yes","y","si","sí"})
    else:
        oa_cols = [c for c in ["OA_Scopus", "OA_WoS", "OA_PubMed"] if c in df.columns]
        if oa_cols:
            tmp = (
                df[oa_cols]
                .apply(lambda s: s.ast(str).str.lower().str.strip().isin({"1","true","t","yes","y","si","sí"}))
                .any(axis=1)
            )
            df["OpenAccess_flag"] = tmp.fillna(False)
        else:
            df["OpenAccess_flag"] = False

    # JIF
    jif_col = _first_col(df, ["Journal Impact Factor", "Impact Factor", "JIF", "JIF_2023", "JCR_IF"])
    df["Journal Impact Factor"] = pd.to_numeric(df[jif_col], errors="coerce").fillna(0) if jif_col else 0

    # Quartile
    q_col = _first_col(df, [
        "JIF Quartile", "JCR Quartile", "JCR_Quartile",
        "JCI Quartile", "SJR Quartile", "SJR_Quartile",
        "Quartile_JCR", "quartile_std", "Quartile",
    ])
    if q_col:
        raw = df[q_col].astype(str).str.upper().str.strip()
        mapping = {
            "1": "Q1", "Q-1": "Q1", "QUARTIL 1": "Q1",
            "2": "Q2", "Q-2": "Q2", "QUARTIL 2": "Q2",
            "3": "Q3", "Q-3": "Q3", "QUARTIL 3": "Q3",
            "4": "Q4", "Q-4": "Q4", "QUARTIL 4": "Q4",
        }
        norm = raw.replace(mapping)
        norm = norm.str.extract(r"(Q[1-4])", expand=False).fillna(norm)
        df["Quartile"] = norm.where(norm.isin(["Q1","Q2","Q3","Q4"]), "Sin cuartil")
    else:
        df["Quartile"] = "Sin cuartil"

    # Departamento
    aff_col = _first_col(df, ["Authors with affiliations", "Affiliations", "Author Affiliations"])
    df["Departamento"] = df[aff_col].apply(detect_department) if aff_col else "Sin asignar"

    # Ensayos clínicos
    df["ClinicalTrial_flag"] = df.apply(detect_clinical_trial, axis=1)

    # Revistas
    jr_col = _first_col(df, ["Journal_norm", "Journal", "Source Title", "Publication Name", "Source title"])
    df["Journal_norm"] = df[jr_col].fillna("").astype(str).replace({"": "—"}) if jr_col else "—"

    # Autores (normales)
    a_col = _first_col(df, ["Author Full Names", "Author full names", "Authors"])
    df["Authors_norm"] = df[a_col].fillna("").astype(str) if a_col else ""

    # Autores CAS (desde affiliations)
    if aff_col:
        df["Authors_CAS"] = df[aff_col].apply(extract_authors_cas)
    else:
        df["Authors_CAS"] = ""

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
# Filtros (optimizados para móviles)
# =========================
def setup_filters(df):
    st.sidebar.header("🔎 Filtros")

    # Usar expansores para organizar los filtros
    with st.sidebar.expander("📅 Rango de años", expanded=False):
        if pd.api.types.is_numeric_dtype(df["Year"]) and df["Year"].notna().any():
            y_min, y_max = int(df["Year"].min()), int(df["Year"].max())
        else:
            y_min, y_max = 1900, 2100
        year_range = st.slider("Años", y_min, y_max, (y_min, y_max), key="year_slider")

    with st.sidebar.expander("🔓 Open Access", expanded=False):
        oa_filter = st.radio("Open Access", ["Todos", "Solo OA", "No OA"], key="oa_radio")

    with st.sidebar.expander("📊 Cuartiles", expanded=False):
        quart_vals = [q for q in ["Q1","Q2","Q3","Q4","Sin cuartil"] if q in df["Quartile"].unique().tolist()] or ["Sin cuartil"]
        quart_filter = st.multiselect("Cuartiles", quart_vals, default=quart_vals, key="quart_multiselect")

    with st.sidebar.expander("🏥 Departamentos", expanded=False):
        dept_filter = st.multiselect("Departamentos", sorted(df["Departamento"].astype(str).unique()), default=None, key="dept_multiselect")

    with st.sidebar.expander("🔍 Búsqueda", expanded=False):
        search_term = st.text_input("Buscar en títulos", key="search_input")
    
    return year_range, oa_filter, quart_filter, dept_filter, search_term

# =========================
# MAIN APP
# =========================
def main():
    # Cargar datos
    up = st.sidebar.file_uploader("📂 Sube un XLSX", type=["xlsx"])
    df = load_data(up)
    
    # Configurar filtros
    year_range, oa_filter, quart_filter, dept_filter, search_term = setup_filters(df)
    
    # Aplicar filtros
    mask = pd.Series(True, index=df.index)
    mask &= df["Year"].fillna(-1).astype(int).between(year_range[0], year_range[1])
    if oa_filter == "Solo OA":
        mask &= df["OpenAccess_flag"]
    elif oa_filter == "No OA":
        mask &= ~df["OpenAccess_flag"]
    mask &= df["Quartile"].isin(quart_filter)
    if dept_filter:
        mask &= df["Departamento"].isin(dept_filter)
    if search_term.strip():
        mask &= df["Title"].fillna("").str.contains(search_term, case=False, na=False)

    dff = df.loc[mask].copy()

    # =========================
    # KPIs
    # =========================
    st.header("📊 Métricas Principales")
    
    # Primera fila de KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 Publicaciones", f"{len(dff)} / {len(df)}")
    with col2:
        st.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
    with col3:
        st.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
    with col4:
        st.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

    # Segunda fila de KPIs
    if "Cited by" in dff.columns:
        total_citas = pd.to_numeric(dff["Cited by"], errors="coerce").fillna(0)
    elif "Times Cited" in dff.columns:
        total_citas = pd.to_numeric(dff["Times Cited"], errors="coerce").fillna(0)
    else:
        total_citas = pd.Series([0]*len(dff))

    h_index = int(sum(total_citas.sort_values(ascending=False).reset_index(drop=True) >= 
                      (np.arange(len(total_citas)) + 1)))

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("📖 Total citas", int(total_citas.sum()))
    with col6:
        st.metric("📖 Promedio citas", f"{total_citas.mean():.1f}")
    with col7:
        st.metric("🏆 % en Q1", f"{100 * (dff['Quartile']=='Q1').mean():.1f}%")
    with col8:
        st.metric("📊 h-index", h_index)

    # =========================
    # Pestañas (versión móvil-friendly)
    # =========================
    # Para móviles, mostramos un selectbox en lugar de tabs horizontales
    if st.checkbox("📱 Modo móvil", help="Activar para mejor visualización en dispositivos pequeños"):
        tab_options = [
            "📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
            "🏥 Departamentos", "📑 Revistas", "👥 Autores", 
            "☁️ Wordcloud", "📖 Citas", "🌍 Colaboración", "🌱 ODS"
        ]
        selected_tab = st.selectbox("Seleccionar sección:", tab_options)
        tab_index = tab_options.index(selected_tab)
        
        # Crear un contenedor para la pestaña seleccionada
        with st.container():
            if tab_index == 0:
                st.subheader("📅 Publicaciones por año")
                g = dff.dropna(subset=["Year"]).astype({"Year": int}).groupby("Year").size().reset_index(name="Publicaciones")
                fig = px.bar(g, x="Year", y="Publicaciones", title="Publicaciones por Año")
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
                
                st.subheader("📈 Suma JIF por año")
                j = dff.dropna(subset=["Year"]).astype({"Year": int}).groupby("Year")["Journal Impact Factor"].sum().reset_index()
                fig = px.line(j, x="Year", y="Journal Impact Factor", markers=True, title="Suma JIF por Año")
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            
            elif tab_index == 1:
                st.subheader("📊 Distribución por cuartiles")
                cts = dff["Quartile"].value_counts().reset_index()
                cts.columns = ["Quartile", "Publicaciones"]
                fig = px.pie(cts, names="Quartile", values="Publicaciones", hole=0.4)
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            
            elif tab_index == 2:
                st.subheader("🔓 Publicaciones Open Access")
                oa = dff["OpenAccess_flag"].map({True: "Open Access", False: "Closed"}).value_counts().reset_index()
                oa.columns = ["Estado", "Publicaciones"]
                fig = px.pie(oa, names="Estado", values="Publicaciones", hole=0.4)
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            
            elif tab_index == 3:
                st.subheader("🏥 Publicaciones por Departamento")
                dep = dff["Departamento"].fillna("Sin asignar").value_counts().reset_index()
                dep.columns = ["Departamento", "Publicaciones"]
                fig = px.bar(dep, x="Departamento", y="Publicaciones", title="Top Departamentos")
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            
            elif tab_index == 4:
                st.subheader("📑 Revistas más frecuentes")
                
                def format_journal_name(name: str) -> str:
                    if not isinstance(name, str) or not name.strip():
                        return "—"

                    # Eliminar espacios extras
                    formatted = re.sub(r"\s+", " ", name.strip())

                    # Normalizar mayúsculas: capitalizar cada palabra
                    words = formatted.split()
                    formatted = " ".join([w.capitalize() if len(w) > 2 else w.lower() for w in words])

                    # Correcciones para mantener palabras clave intactas
                    corrections = {
                        "De": "de",
                        "La": "la",
                        "El": "el",
                        "Y": "y",
                        "En": "en",
                        "Del": "del",
                        "Los": "los",
                        "Las": "las",
                        "Journal": "Journal",   # Mantener Journal
                        "Revista": "Revista",   # Mantener Revista
                        "Bmj": "BMJ",           # Corrección siglas
                        "Nejm": "NEJM",
                        "Lancet": "The Lancet"
                    }
                    for wrong, right in corrections.items():
                        formatted = formatted.replace(f" {wrong} ", f" {right} ")

                    # Diccionario de normalización manual (revistas chilenas)
                    normalization_map = {
                        "Medica Chile": "Revista Médica de Chile",
                        "Chilena Pediatria": "Revista Chilena de Pediatría",
                        "Chilena Radiologia": "Revista Chilena de Radiología",
                        "Chilena Infectologia": "Revista Chilena de Infectología",
                        "Chilena Obstetricia Y Ginecologia": "Revista Chilena de Obstetricia y Ginecología",
                        "Andes Pediatrica": "Revista Andes Pediátrica",
                        "Chilena Cirugia": "Revista Chilena de Cirugía",
                        "Chilena Anestesia": "Revista Chilena de Anestesia",
                        "Chilena Enfermedades Respiratorias": "Revista Chilena de Enfermedades Respiratorias",
                        "Medica Clinica Las Condes": "Revista Médica Clínica Las Condes",
                    }

                    return normalization_map.get(formatted, formatted)
                
                # Aplicar formato a los nombres de revistas
                dff["Journal_formatted"] = dff["Journal_norm"].apply(format_journal_name)
                
                journals = dff["Journal_formatted"].fillna("—").value_counts().head(20).reset_index()
                journals.columns = ["Revista", "Publicaciones"]
                
                # Crear gráfico con margen izquierdo suficiente
                fig = px.bar(
                    journals.sort_values("Publicaciones"), 
                    x="Publicaciones", 
                    y="Revista", 
                    orientation="h", 
                    title="Top 20 Revistas"
                )
                
                # Ajustar layout
                fig.update_layout(
                    yaxis=dict(categoryorder='total ascending'),
                    margin=dict(l=10, r=10, t=50, b=10),
                    height=500,
                    yaxis_tickfont=dict(size=10),
                    font=dict(size=10)
                )
                
                # Mostrar valores dentro de las barras
                fig.update_traces(
                    text=journals.sort_values("Publicaciones")["Publicaciones"],
                    textposition='inside',
                    insidetextanchor='start'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(journals, use_container_width=True)
            
            elif tab_index == 5:
                st.subheader("🏥 Autores de Clínica Alemana (CAS)")

                # Procesar autores CAS
                cas_authors = (
                    dff["Authors_CAS"].fillna("")
                    .astype(str)
                    .str.split(r";")
                    .explode()
                    .str.strip()
                    .replace("", np.nan)
                    .dropna()
                )

                def format_to_lastname_initials(name: str) -> str:
                    """
                    Convierte 'Lavados Pm' -> 'Lavados, P.'
                    """
                    if not isinstance(name, str) or not name.strip():
                        return ""
                    parts = name.split()
                    if len(parts) == 1:
                        return parts[0].title()
                    last = parts[0].title()
                    initials = "".join([p[0].upper() + "." for p in parts[1:]])
                    return f"{last}, {initials}"

                if not cas_authors.empty:
                    cas_authors_formatted = cas_authors.apply(format_to_lastname_initials)

                    top_cas = cas_authors_formatted.value_counts().head(20).reset_index()
                    top_cas.columns = ["Autor CAS", "Publicaciones"]
                    top_cas_sorted = top_cas.sort_values("Publicaciones", ascending=True)

                    fig = px.bar(
                        top_cas_sorted,
                        x="Publicaciones",
                        y="Autor CAS",
                        orientation="h",
                        title="Top 20 Autores CAS",
                        text="Publicaciones"
                    )

                    fig.update_layout(
                        yaxis=dict(categoryorder='total ascending'),
                        margin=dict(l=10, r=10, t=50, b=10),
                        height=500,
                        yaxis_tickfont=dict(size=10),
                        title_font=dict(size=14),
                        font=dict(size=10)
                    )

                    fig.update_traces(
                        textposition='inside',
                        insidetextanchor='start',
                        textfont=dict(size=10, color='white'),
                        marker_color='#1f77b4'
                    )

                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(
                        top_cas.sort_values("Publicaciones", ascending=False).reset_index(drop=True),
                        use_container_width=True
                    )
                else:
                    st.info("No se detectaron autores CAS en las afiliaciones.")
            
            elif tab_index == 6:
                st.subheader("☁️ Wordcloud de títulos")
                try:
                    from wordcloud import WordCloud, STOPWORDS
                    import matplotlib.pyplot as plt
                    
                    custom_stopwords = set(STOPWORDS)
                    custom_stopwords.update([
                        "el","la","los","las","un","una","unos","unas","de","del","y","en","por","para","con",
                        "the","a","an","of","for","to","with","on","at","by","from","they","their","this","that","these","those"
                    ])

                    text = " ".join(dff["Title"].dropna().astype(str).tolist())
                    if text.strip():
                        wc = WordCloud(
                            width=800, height=400,
                            background_color="white",
                            stopwords=custom_stopwords
                        ).generate(text)
                        fig, ax = plt.subplots(figsize=(10, 5))
                        ax.imshow(wc, interpolation="bilinear")
                        ax.axis("off")
                        st.pyplot(fig, use_container_width=True, clear_figure=True)
                    else:
                        st.info("No hay títulos para construir la nube.")
                except ImportError:
                    st.error("Para usar wordcloud, instala: `pip install wordcloud`")
            
            elif tab_index == 7:
                st.subheader("📖 Citas por año")
                if not total_citas.empty:
                    citas_year = dff.groupby("Year")[total_citas.name].sum().reset_index()
                    fig = px.bar(citas_year, x="Year", y=total_citas.name, title="Citas por Año")
                    fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No hay datos de citas en este dataset.")
            
            elif tab_index == 8:
                st.subheader("🌍 Colaboración internacional (instituciones en afiliaciones)")
                if "Affiliations" in dff.columns:
                    # Normalizamos afiliaciones
                    affils = dff["Affiliations"].dropna().astype(str)

                    # Dividir por ; o , para separar instituciones
                    institutions = affils.str.split(r";|,").explode().str.strip()

                    # Filtrar instituciones relevantes (evitamos ruido)
                    institutions = institutions[institutions.str.contains(
                        r"(univ|universidad|hospital|clinic|institut|centre|centro)", 
                        case=False, na=False
                    )]

                    # Eliminar "school", "faculty", "department", etc.
                    institutions = institutions[~institutions.str.contains(
                        r"(school|department|faculty|facultad|division|unidad)", 
                        case=False, na=False
                    )]

                    # Normalizar nombres (usa la función definida en utils)
                    institutions = institutions.apply(normalize_institution)

                    # Contar las top instituciones
                    top_institutions = institutions.value_counts().head(15).reset_index()
                    top_institutions.columns = ["Institución", "Publicaciones"]

                    fig = px.bar(
                        top_institutions.sort_values("Publicaciones"),
                        x="Publicaciones", y="Institución", orientation="h",
                        title="Top Instituciones en Afiliaciones"
                    )
                    fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(top_institutions, use_container_width=True)
                else:
                    st.info("No se encontraron instituciones en las afiliaciones.")
            
            elif tab_index == 9:
                st.subheader("🌱 Publicaciones por ODS")
                if "SDG" in dff.columns:
                    sdg = dff["SDG"].dropna().astype(str).str.split(";").explode().str.strip()
                    sdg_counts = sdg.value_counts().reset_index()
                    sdg_counts.columns = ["ODS", "Publicaciones"]
                    fig = px.bar(
                        sdg_counts.sort_values("Publicaciones"),
                        x="Publicaciones", y="ODS", orientation="h",
                        title="Distribución por ODS"
                    )
                    fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(sdg_counts, use_container_width=True)
                else:
                    st.info("No hay información de ODS en este dataset.")
    
    else:
        # Versión original para desktop
        tabs = st.tabs([
            "📅 Publicaciones", 
            "📊 Cuartiles", 
            "🔓 Open Access",
            "🏥 Departamentos", 
            "📑 Revistas", 
            "👥 Autores", 
            "☁️ Wordcloud",
            "📖 Citas",
            "🌍 Colaboración",
            "🌱 ODS" 
        ])
        
        with tabs[0]:
            st.subheader("📅 Publicaciones por año")
            g = dff.dropna(subset=["Year"]).astype({"Year": int}).groupby("Year").size().reset_index(name="Publicaciones")
            fig = px.bar(g, x="Year", y="Publicaciones", title="Publicaciones por Año")
            fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📈 Suma JIF por año")
            j = dff.dropna(subset=["Year"]).astype({"Year": int}).groupby("Year")["Journal Impact Factor"].sum().reset_index()
            fig = px.line(j, x="Year", y="Journal Impact Factor", markers=True, title="Suma JIF por Año")
            fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)
        
        with tabs[1]:
            st.subheader("📊 Distribución por cuartiles")
            cts = dff["Quartile"].value_counts().reset_index()
            cts.columns = ["Quartile", "Publicaciones"]
            fig = px.pie(cts, names="Quartile", values="Publicaciones", hole=0.4)
            fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)
        
        with tabs[2]:
            st.subheader("🔓 Publicaciones Open Access")
            oa = dff["OpenAccess_flag"].map({True: "Open Access", False: "Closed"}).value_counts().reset_index()
            oa.columns = ["Estado", "Publicaciones"]
            fig = px.pie(oa, names="Estado", values="Publicaciones", hole=0.4)
            fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)
        
        with tabs[3]:
            st.subheader("🏥 Publicaciones por Departamento")
            dep = dff["Departamento"].fillna("Sin asignar").value_counts().reset_index()
            dep.columns = ["Departamento", "Publicaciones"]
            fig = px.bar(dep, x="Departamento", y="Publicaciones", title="Top Departamentos")
            fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)
        
        with tabs[4]:
            st.subheader("📑 Revistas más frecuentes")
            
            def format_journal_name(name: str) -> str:
                if not isinstance(name, str) or not name.strip():
                    return "—"

                # Eliminar espacios extras
                formatted = re.sub(r"\s+", " ", name.strip())

                # Normalizar mayúsculas: capitalizar cada palabra
                words = formatted.split()
                formatted = " ".join([w.capitalize() if len(w) > 2 else w.lower() for w in words])

                # Correcciones para mantener palabras clave intactas
                corrections = {
                    "De": "de",
                    "La": "la",
                    "El": "el",
                    "Y": "y",
                    "En": "en",
                    "Del": "del",
                    "Los": "los",
                    "Las": "las",
                    "Journal": "Journal",   # Mantener Journal
                    "Revista": "Revista",   # Mantener Revista
                    "Bmj": "BMJ",           # Corrección siglas
                    "Nejm": "NEJM",
                    "Lancet": "The Lancet"
                }
                for wrong, right in corrections.items():
                    formatted = formatted.replace(f" {wrong} ", f" {right} ")

                # Diccionario de normalización manual (revistas chilenas)
                normalization_map = {
                    "Medica Chile": "Revista Médica de Chile",
                    "Chilena Pediatria": "Revista Chilena de Pediatría",
                    "Chilena Radiologia": "Revista Chilena de Radiología",
                    "Chilena Infectologia": "Revista Chilena de Infectología",
                    "Chilena Obstetricia Y Ginecologia": "Revista Chilena de Obstetricia y Ginecología",
                    "Andes Pediatrica": "Revista Andes Pediátrica",
                    "Chilena Cirugia": "Revista Chilena de Cirugía",
                    "Chilena Anestesia": "Revista Chilena de Anestesia",
                    "Chilena Enfermedades Respiratorias": "Revista Chilena de Enfermedades Respiratorias",
                    "Medica Clinica Las Condes": "Revista Médica Clínica Las Condes",
                }

                return normalization_map.get(formatted, formatted)
            
            # Aplicar formato a los nombres de revistas
            dff["Journal_formatted"] = dff["Journal_norm"].apply(format_journal_name)
            
            journals = dff["Journal_formatted"].fillna("—").value_counts().head(20).reset_index()
            journals.columns = ["Revista", "Publicaciones"]
            
            # Crear gráfico con margen izquierdo suficiente
            fig = px.bar(
                journals.sort_values("Publicaciones"), 
                x="Publicaciones", 
                y="Revista", 
                orientation="h", 
                title="Top 20 Revistas"
            )
            
            # Ajustar layout
            fig.update_layout(
                yaxis=dict(categoryorder='total ascending'),
                margin=dict(l=300, r=10, t=50, b=10),
                height=600,
                yaxis_tickfont=dict(size=12),
                font=dict(size=10)
            )
            
            # Mostrar valores dentro de las barras
            fig.update_traces(
                text=journals.sort_values("Publicaciones")["Publicaciones"],
                textposition='inside',
                insidetextanchor='start'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(journals, use_container_width=True)
        
        with tabs[5]:
            st.subheader("🏥 Autores de Clínica Alemana (CAS)")

            # Procesar autores CAS
            cas_authors = (
                dff["Authors_CAS"].fillna("")
                .astype(str)
                .str.split(r";")
                .explode()
                .str.strip()
                .replace("", np.nan)
                .dropna()
            )

            def format_to_lastname_initials(name: str) -> str:
                """
                Convierte 'Lavados Pm' -> 'Lavados, P.'
                """
                if not isinstance(name, str) or not name.strip():
                    return ""
                parts = name.split()
                if len(parts) == 1:
                    return parts[0].title()
                last = parts[0].title()
                initials = "".join([p[0].upper() + "." for p in parts[1:]])
                return f"{last}, {initials}"

            if not cas_authors.empty:
                cas_authors_formatted = cas_authors.apply(format_to_lastname_initials)

                top_cas = cas_authors_formatted.value_counts().head(20).reset_index()
                top_cas.columns = ["Autor CAS", "Publicaciones"]
                top_cas_sorted = top_cas.sort_values("Publicaciones", ascending=True)

                fig = px.bar(
                    top_cas_sorted,
                    x="Publicaciones",
                    y="Autor CAS",
                    orientation="h",
                    title="Top 20 Autores CAS",
                    text="Publicaciones"
                )

                fig.update_layout(
                    yaxis=dict(categoryorder='total ascending'),
                    margin=dict(l=300, r=10, t=50, b=10),
                    height=600,
                    yaxis_tickfont=dict(size=12),
                    title_font=dict(size=16),
                    font=dict(size=10)
                )

                fig.update_traces(
                    textposition='inside',
                    insidetextanchor='start',
                    textfont=dict(size=11, color='white'),
                    marker_color='#1f77b4'
                )

                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(
                    top_cas.sort_values("Publicaciones", ascending=False).reset_index(drop=True),
                    use_container_width=True
                )
            else:
                st.info("No se detectaron autores CAS en las afiliaciones.")
        
        with tabs[6]:
            st.subheader("☁️ Wordcloud de títulos")
            try:
                from wordcloud import WordCloud, STOPWORDS
                import matplotlib.pyplot as plt
                
                custom_stopwords = set(STOPWORDS)
                custom_stopwords.update([
                    "el","la","los","las","un","una","unos","unas","de","del","y","en","por","para","con",
                    "the","a","an","of","for","to","with","on","at","by","from","they","their","this","that","these","those"
                ])

                text = " ".join(dff["Title"].dropna().astype(str).tolist())
                if text.strip():
                    wc = WordCloud(
                        width=1200, height=500,
                        background_color="white",
                        stopwords=custom_stopwords
                    ).generate(text)
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.imshow(wc, interpolation="bilinear")
                    ax.axis("off")
                    st.pyplot(fig, use_container_width=True, clear_figure=True)
                else:
                    st.info("No hay títulos para construir la nube.")
            except ImportError:
                st.error("Para usar wordcloud, instala: `pip install wordcloud`")
        
        with tabs[7]:
            st.subheader("📖 Citas por año")
            if not total_citas.empty:
                citas_year = dff.groupby("Year")[total_citas.name].sum().reset_index()
                fig = px.bar(citas_year, x="Year", y=total_citas.name, title="Citas por Año")
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de citas en este dataset.")
        
        with tabs[8]:
            st.subheader("🌍 Colaboración internacional (instituciones en afiliaciones)")
            if "Affiliations" in dff.columns:
                # Normalizamos afiliaciones
                affils = dff["Affiliations"].dropna().astype(str)

                # Dividir por ; o , para separar instituciones
                institutions = affils.str.split(r";|,").explode().str.strip()

                # Filtrar instituciones relevantes (evitamos ruido)
                institutions = institutions[institutions.str.contains(
                    r"(univ|universidad|hospital|clinic|institut|centre|centro)", 
                    case=False, na=False
                )]

                # Eliminar "school", "faculty", "department", etc.
                institutions = institutions[~institutions.str.contains(
                    r"(school|department|faculty|facultad|division|unidad)", 
                    case=False, na=False
                )]

                # Normalizar nombres (usa la función definida en utils)
                institutions = institutions.apply(normalize_institution)

                # Contar las top instituciones
                top_institutions = institutions.value_counts().head(15).reset_index()
                top_institutions.columns = ["Institución", "Publicaciones"]

                fig = px.bar(
                    top_institutions.sort_values("Publicaciones"),
                    x="Publicaciones", y="Institución", orientation="h",
                    title="Top Instituciones en Afiliaciones"
                )
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(top_institutions, use_container_width=True)
            else:
                st.info("No se encontraron instituciones en las afiliaciones.")
        
        with tabs[9]:
            st.subheader("🌱 Publicaciones por ODS")
            if "SDG" in dff.columns:
                sdg = dff["SDG"].dropna().astype(str).str.split(";").explode().str.strip()
                sdg_counts = sdg.value_counts().reset_index()
                sdg_counts.columns = ["ODS", "Publicaciones"]
                fig = px.bar(
                    sdg_counts.sort_values("Publicaciones"),
                    x="Publicaciones", y="ODS", orientation="h",
                    title="Distribución por ODS"
                )
                fig.update_layout(autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(sdg_counts, use_container_width=True)
            else:
                st.info("No hay información de ODS en este dataset.")

    # =========================
    # Módulo de carga y merge
    # =========================
    def build_match_key(df: pd.DataFrame) -> pd.Series:
        doi = df.get("DOI", pd.Series([""]*len(df), index=df.index)).fillna("").astype(str)
        pmid = df.get("PMID", pd.Series([""]*len(df), index=df.index)).fillna("").astype(str)
        eid = df.get("EID", pd.Series([""]*len(df), index=df.index)).fillna("").astype(str)
        y = df.get("Year", pd.Series(["-1"]*len(df), index=df.index)).astype(str)
        t = df.get("Title", pd.Series([""]*len(df), index=df.index)).astype(str).str.lower().str.strip()
        ty = "TY:" + y + "|" + t

        key = doi.where(doi != "", "PMID:" + pmid)
        key = key.where(~key.str.startswith("PMID:"), "EID:" + eid)
        key = key.where(~key.str.startswith("EID:"), ty)
        return key

    def merge_preview(old_df: pd.DataFrame, new_df: pd.DataFrame):
        old = old_df.copy(); new = new_df.copy()
        old["_mk"] = build_match_key(old); new["_mk"] = build_match_key(new)
        old_set = set(k for k in old["_mk"] if isinstance(k,str) and k)
        new["_is_new"] = ~new["_mk"].isin(old_set)
        return new

    def merge_apply(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        a = old_df.copy(); b = new_df.copy()
        a["_mk"] = build_match_key(a); b["_mk"] = build_match_key(b)
        z = pd.concat([a, b], ignore_index=True, sort=False)
        z["_dedup"] = z["_mk"].fillna("") + "|" + z["Title"].fillna("")
        z = z.drop_duplicates(subset="_dedup", keep="first").drop(columns=["_dedup"], errors="ignore")
        return z

    with st.sidebar:
        st.markdown("---")
        st.header("🔄 Actualizar dataset")
        new_files = st.file_uploader("Nuevos CSV/XLSX", type=["csv","xlsx"], accept_multiple_files=True)
        btn_prev  = st.button("👀 Previsualizar unión")
        btn_apply = st.button("✅ Aplicar actualización", type="primary")

    if new_files:
        tables = []
        for f in new_files:
            try:
                t = pd.read_csv(f, dtype=str) if f.name.lower().endswith(".csv") else pd.read_excel(f, dtype=str)
                tables.append(normalize_columns(t))
            except Exception:
                pass
        new_df = pd.concat(tables, ignore_index=True, sort=False) if tables else pd.DataFrame()
    else:
        new_df = pd.DataFrame()

    if not new_df.empty and btn_prev:
        prev = merge_preview(df, new_df)
        n_new = int(prev["_is_new"].sum())
        n_dup = int(len(prev) - n_new)
        st.sidebar.success(f"Vista previa: {n_new} nuevos · {n_dup} duplicados.")

    if not new_df.empty and btn_apply:
        df = merge_apply(df, new_df)
        st.sidebar.success(f"Unión aplicada. Registros ahora: {len(df):,}")

if __name__ == "__main__":
    main()