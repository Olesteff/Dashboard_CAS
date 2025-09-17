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
# Detectar dispositivo móvil
# =========================
def is_mobile():
    """Detecta si el usuario está en un dispositivo móvil"""
    try:
        user_agent = st.query_params.get('user_agent', '')
        mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'windows phone']
        return any(keyword in user_agent.lower() for keyword in mobile_keywords)
    except:
        return False

MOBILE_MODE = is_mobile()

# =========================
# CSS para móviles
# =========================
mobile_css = """
<style>
@media (max-width: 768px) {
    .main .block-container {
        padding: 1rem !important;
    }
    .stButton > button {
        width: 100% !important;
        margin: 5px 0 !important;
    }
    [data-testid="column"] {
        width: 100% !important;
        flex: unset !important;
        padding: 0.5rem !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
        flex-wrap: wrap !important;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 10px !important;
        font-size: 11px !important;
        height: auto !important;
        min-height: 28px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 14px !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 11px !important;
    }
    .stDataFrame {
        font-size: 11px !important;
    }
    .stPlotlyChart {
        margin: 0 !important;
        padding: 0 !important;
    }
    .element-container {
        margin-bottom: 0.5rem !important;
    }
}
</style>
"""

st.markdown(mobile_css, unsafe_allow_html=True)

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
        "universidad de chile": "Universidad de Chile",
        "university of chile": "Universidad de Chile",
        "uchile": "Universidad de Chile",
        "pontificia universidad catolica de chile": "Pontificia Universidad Católica de Chile",
        "pontifical catholic university of chile": "Pontificia Universidad Católica de Chile",
        "universidad catolica de chile": "Pontificia Universidad Católica de Chile",
        "uc chile": "Pontificia Universidad Católica de Chile",
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
        "hospital clinico universidad de chile": "Hospital Clínico Universidad de Chile",
        "hospital clinico universidad catolica": "Hospital Clínico Universidad Católica",
        "hospital clinico puc": "Hospital Clínico Universidad Católica",
        "hospital padre hurtado": "Hospital Padre Hurtado",
        "hospital militar de santiago": "Hospital Militar de Santiago",
        "hospital militar": "Hospital Militar de Santiago",
        "clinica las condes": "Clínica Las Condes",
        "clc": "Clínica Las Condes",
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
                .apply(lambda s: s.astype(str).str.lower().str.strip().isin({"1","true","t","yes","y","si","sí"}))
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
# Filtros optimizados
# =========================
def setup_filters(df):
    st.sidebar.header("🔎 Filtros")
    
    # Año
    if pd.api.types.is_numeric_dtype(df["Year"]) and df["Year"].notna().any():
        y_min, y_max = int(df["Year"].min()), int(df["Year"].max())
    else:
        y_min, y_max = 2010, 2024
    
    year_range = st.sidebar.slider("Años", y_min, y_max, (y_min, y_max))
    
    # Open Access
    oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo OA", "No OA"])
    
    # Cuartiles
    quart_vals = [q for q in ["Q1","Q2","Q3","Q4","Sin cuartil"] if q in df["Quartile"].unique().tolist()] or ["Sin cuartil"]
    quart_filter = st.sidebar.multiselect("Cuartiles", quart_vals, default=quart_vals)
    
    # Departamentos
    dept_filter = st.sidebar.multiselect("Departamentos", sorted(df["Departamento"].astype(str).unique()))
    
    # Búsqueda
    search_term = st.sidebar.text_input("Buscar en títulos")
    
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
    cols1 = st.columns(4 if not MOBILE_MODE else 2)
    with cols1[0]:
        st.metric("📚 Publicaciones", f"{len(dff):,}")
    with cols1[1]:
        st.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
    
    if not MOBILE_MODE:
        with cols1[2]:
            st.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
        with cols1[3]:
            st.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))
    else:
        cols2 = st.columns(2)
        with cols2[0]:
            st.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
        with cols2[1]:
            st.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

    # Citas y h-index
    if "Cited by" in dff.columns:
        total_citas = pd.to_numeric(dff["Cited by"], errors="coerce").fillna(0)
    elif "Times Cited" in dff.columns:
        total_citas = pd.to_numeric(dff["Times Cited"], errors="coerce").fillna(0)
    else:
        total_citas = pd.Series([0]*len(dff))

    h_index = int(sum(total_citas.sort_values(ascending=False).reset_index(drop=True) >= 
                      (np.arange(len(total_citas)) + 1)))

    cols3 = st.columns(4 if not MOBILE_MODE else 2)
    with cols3[0]:
        st.metric("📖 Total citas", int(total_citas.sum()))
    with cols3[1]:
        st.metric("📊 h-index", h_index)
    
    if not MOBILE_MODE:
        with cols3[2]:
            st.metric("📖 Promedio citas", f"{total_citas.mean():.1f}")
        with cols3[3]:
            st.metric("🏆 % en Q1", f"{100 * (dff['Quartile']=='Q1').mean():.1f}%")
    else:
        cols4 = st.columns(2)
        with cols4[0]:
            st.metric("📖 Promedio citas", f"{total_citas.mean():.1f}")
        with cols4[1]:
            st.metric("🏆 % en Q1", f"{100 * (dff['Quartile']=='Q1').mean():.1f}%")

    # =========================
    # Pestañas
    # =========================
    if MOBILE_MODE:
        # Modo móvil: selectbox en lugar de tabs
        tab_options = [
            "📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
            "🏥 Departamentos", "📑 Revistas", "👥 Autores", 
            "☁️ Wordcloud", "📖 Citas", "🌍 Colaboración"
        ]
        selected_tab = st.selectbox("Seleccionar sección:", tab_options)
        tab_index = tab_options.index(selected_tab)
    else:
        # Modo desktop: tabs normales
        tabs = st.tabs([
            "📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
            "🏥 Departamentos", "📑 Revistas", "👥 Autores", 
            "☁️ Wordcloud", "📖 Citas", "🌍 Colaboración"
        ])

    # Función para mostrar contenido según pestaña
    def show_tab_content(tab_index):
        if tab_index == 0:
            st.subheader("📅 Publicaciones por año")
            g = dff.dropna(subset=["Year"]).astype({"Year": int}).groupby("Year").size().reset_index(name="Publicaciones")
            fig = px.bar(g, x="Year", y="Publicaciones", title="")
            fig.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                font=dict(size=12),
                height=400 if MOBILE_MODE else 500
            )
            st.plotly_chart(fig, use_container_width=True)

        elif tab_index == 1:
            st.subheader("📊 Distribución por cuartiles")
            cts = dff["Quartile"].value_counts().reset_index()
            cts.columns = ["Quartile", "Publicaciones"]
            fig = px.pie(cts, names="Quartile", values="Publicaciones", hole=0.4)
            fig.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                font=dict(size=12),
                height=400 if MOBILE_MODE else 500
            )
            st.plotly_chart(fig, use_container_width=True)

        elif tab_index == 2:
            st.subheader("🔓 Publicaciones Open Access")
            oa = dff["OpenAccess_flag"].map({True: "Open Access", False: "Closed"}).value_counts().reset_index()
            oa.columns = ["Estado", "Publicaciones"]
            fig = px.pie(oa, names="Estado", values="Publicaciones", hole=0.4)
            fig.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                font=dict(size=12),
                height=400 if MOBILE_MODE else 500
            )
            st.plotly_chart(fig, use_container_width=True)

        elif tab_index == 3:
            st.subheader("🏥 Publicaciones por Departamento")
            dep = dff["Departamento"].fillna("Sin asignar").value_counts().reset_index()
            dep.columns = ["Departamento", "Publicaciones"]
            fig = px.bar(dep, x="Publicaciones", y="Departamento", orientation='h', title="")
            fig.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                font=dict(size=12),
                height=500 if MOBILE_MODE else 600,
                yaxis=dict(categoryorder='total ascending')
            )
            st.plotly_chart(fig, use_container_width=True)

        elif tab_index == 4:
            st.subheader("📑 Revistas más frecuentes")
            
            def format_journal_name(name: str) -> str:
                if not isinstance(name, str) or not name.strip():
                    return "—"
                formatted = re.sub(r"\s+", " ", name.strip())
                words = formatted.split()
                formatted = " ".join([w.capitalize() if len(w) > 2 else w.lower() for w in words])
                corrections = {
                    "De": "de", "La": "la", "El": "el", "Y": "y", "En": "en",
                    "Del": "del", "Los": "los", "Las": "las", "Journal": "Journal",
                    "Revista": "Revista", "Bmj": "BMJ", "Nejm": "NEJM", "Lancet": "The Lancet"
                }
                for wrong, right in corrections.items():
                    formatted = formatted.replace(f" {wrong} ", f" {right} ")
                return formatted
            
            dff["Journal_formatted"] = dff["Journal_norm"].apply(format_journal_name)
            journals = dff["Journal_formatted"].fillna("—").value_counts().head(15).reset_index()
            journals.columns = ["Revista", "Publicaciones"]
            
            fig = px.bar(journals.sort_values("Publicaciones"), x="Publicaciones", y="Revista", orientation='h', title="")
            fig.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                font=dict(size=12),
                height=600 if MOBILE_MODE else 700,
                yaxis=dict(categoryorder='total ascending')
            )
            st.plotly_chart(fig, use_container_width=True)

        elif tab_index == 5:
            st.subheader("👥 Autores de Clínica Alemana (CAS)")

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
                top_cas = cas_authors_formatted.value_counts().head(15).reset_index()
                top_cas.columns = ["Autor CAS", "Publicaciones"]
                top_cas_sorted = top_cas.sort_values("Publicaciones", ascending=True)

                fig = px.bar(top_cas_sorted, x="Publicaciones", y="Autor CAS", orientation='h', title="")
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    font=dict(size=12),
                    height=500 if MOBILE_MODE else 600,
                    yaxis=dict(categoryorder='total ascending')
                )
                st.plotly_chart(fig, use_container_width=True)
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
                    "the","a","an","of","for","to","with","on","at","by","from","they","their","this","that"
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
                fig = px.bar(citas_year, x="Year", y=total_citas.name, title="")
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    font=dict(size=12),
                    height=400 if MOBILE_MODE else 500
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de citas en este dataset.")

        elif tab_index == 8:
            st.subheader("🌍 Colaboración internacional")
            if "Affiliations" in dff.columns:
                affils = dff["Affiliations"].dropna().astype(str)
                institutions = affils.str.split(r";|,").explode().str.strip()
                institutions = institutions[institutions.str.contains(
                    r"(univ|universidad|hospital|clinic|institut|centre|centro)", case=False, na=False
                )]
                institutions = institutions[~institutions.str.contains(
                    r"(school|department|faculty|facultad|division|unidad)", case=False, na=False
                )]
                institutions = institutions.apply(normalize_institution)
                top_institutions = institutions.value_counts().head(12).reset_index()
                top_institutions.columns = ["Institución", "Publicaciones"]

                fig = px.bar(top_institutions.sort_values("Publicaciones"), x="Publicaciones", y="Institución", orientation='h', title="")
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=10),
                    font=dict(size=12),
                    height=500 if MOBILE_MODE else 600,
                    yaxis=dict(categoryorder='total ascending')
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No se encontraron instituciones en las afiliaciones.")

    # Mostrar contenido según el modo
    if MOBILE_MODE:
        show_tab_content(tab_index)
    else:
        for i, tab in enumerate(tabs):
            with tab:
                show_tab_content(i)

if __name__ == "__main__":
    main()