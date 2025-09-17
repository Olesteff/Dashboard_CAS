# app_dashboard.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================
# Config
# =========================
st.set_page_config(
    page_title="📊 Dashboard de Producción Científica",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
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
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def detect_department(affiliation: str) -> str:
    ...
    return "Clínica Alemana"

def detect_clinical_trial(row: pd.Series) -> bool:
    ...
    return bool(re.search(ct_regex, text))

def extract_authors_cas(affiliations: str) -> str:
    ...
    return "; ".join(cas_authors)

import unidecode

def normalize_institution(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = unidecode.unidecode(name.lower())
    name = re.sub(r"[-,_]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    replacements = {
        "universidad de chile": "Universidad de Chile",
        "university of chile": "Universidad de Chile",
        "uchile": "Universidad de Chile",
        "pontificia universidad catolica de chile": "Pontificia Universidad Católica de Chile",
        "pontifical catholic university of chile": "Pontificia Universidad Católica de Chile",
        "universidad catolica de chile": "Pontificia Universidad Católica de Chile",
        "clinica alemana universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "clinica alemana": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "alemana clinic": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "School Of Medicine": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "university of development": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
        "hospital clinico universidad de chile": "Hospital Clínico Universidad de Chile",
        "hospital clinico universidad catolica": "Hospital Clínico Universidad Católica",
        "hospital clinico puc": "Hospital Clínico Universidad Católica",
        "hospital clinico": "Hospital Clínico Universidad de Chile",
        "clinica las condes": "Clínica Las Condes",
        "clc": "Clínica Las Condes",
        "clínica las condes": "Clínica Las Condes",
        "hospital militar": "Hospital Militar de Santiago",
        "hospital militar de santiago": "Hospital Militar de Santiago",
        "red de salud uc christus": "Red de Salud UC Christus",
        "uc christus": "Red de Salud UC Christus",
        "red de salud uc": "Red de Salud UC Christus",
        "red de salud catolica": "Red de Salud UC Christus",
        "red de salud católica": "Red de Salud UC Christus",
        "red de salud catolica puc": "Red de Salud UC Christus",
        "red de salud católica puc": "Red de Salud UC Christus",
        "red de salud catolica chile": "Red de Salud UC Christus",
    }

    for k, v in replacements.items():
        if k in name:
            return v
    return name.title()

def normalize_author(name: str) -> str:
    
    if not isinstance(name, str) or not name.strip():
        return ""
    
    name = name.replace(".", "").strip()
    
    # Caso "Apellido, Nombre"
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
        # Si son iniciales -> las dejamos separadas
        if re.fullmatch(r"[A-Z ]+", first, flags=re.I):
            first = " ".join(list(first.replace(" ", "")))
        return f"{first} {last}".title().strip()
    
    # Caso "Nombre Apellido" (ya ordenado)
    parts = name.split()
    parts = [p.strip() for p in parts if p.strip()]
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

up = st.sidebar.file_uploader("📂 Sube un XLSX", type=["xlsx"])
df = load_data(up)

# =========================
# Filtros
# =========================
st.sidebar.header("🔎 Filtros")
if pd.api.types.is_numeric_dtype(df["Year"]) and df["Year"].notna().any():
    y_min, y_max = int(df["Year"].min()), int(df["Year"].max())
else:
    y_min, y_max = 1900, 2100

year_range = st.sidebar.slider("Años", y_min, y_max, (y_min, y_max))
oa_filter = st.sidebar.radio("Open Access", ["Todos", "Solo OA", "No OA"])
quart_vals = [q for q in ["Q1","Q2","Q3","Q4","Sin cuartil"] if q in df["Quartile"].unique().tolist()] or ["Sin cuartil"]
quart_filter = st.sidebar.multiselect("Cuartiles", quart_vals, default=quart_vals)
dept_filter = st.sidebar.multiselect("Departamentos", sorted(df["Departamento"].astype(str).unique()), default=None)
search_term = st.sidebar.text_input("Buscar en títulos")

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
c1, c2, c3, c4 = st.columns(4)
c1.metric("📚 Publicaciones", f"{len(dff)} / {len(df)}")
c2.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
c3.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
c4.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

# =========================
# KPIs adicionales
# =========================
if "Cited by" in dff.columns:
    total_citas = pd.to_numeric(dff["Cited by"], errors="coerce").fillna(0)
elif "Times Cited" in dff.columns:
    total_citas = pd.to_numeric(dff["Times Cited"], errors="coerce").fillna(0)
else:
    total_citas = pd.Series([0]*len(dff))

h_index = int(sum(total_citas.sort_values(ascending=False).reset_index(drop=True) >= 
                  (np.arange(len(total_citas)) + 1)))

c5, c6, c7, c8 = st.columns(4)
c5.metric("📖 Total citas", int(total_citas.sum()))
c6.metric("📖 Promedio citas", f"{total_citas.mean():.1f}")
c7.metric("🏆 % en Q1", f"{100 * (dff['Quartile']=='Q1').mean():.1f}%")
c8.metric("📊 h-index", h_index)

# =========================
# Pestañas
# =========================
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
    st.plotly_chart(px.bar(g, x="Year", y="Publicaciones", title="Publicaciones por Año"), use_container_width=True)

    st.subheader("📈 Suma JIF por año")
    j = dff.dropna(subset=["Year"]).astype({"Year": int}).groupby("Year")["Journal Impact Factor"].sum().reset_index()
    st.plotly_chart(px.line(j, x="Year", y="Journal Impact Factor", markers=True, title="Suma JIF por Año"), use_container_width=True)

with tabs[1]:
    st.subheader("📊 Distribución por cuartiles")
    cts = dff["Quartile"].value_counts().reset_index()
    cts.columns = ["Quartile", "Publicaciones"]
    st.plotly_chart(px.pie(cts, names="Quartile", values="Publicaciones", hole=0.4), use_container_width=True)

with tabs[2]:
    st.subheader("🔓 Publicaciones Open Access")
    oa = dff["OpenAccess_flag"].map({True: "Open Access", False: "Closed"}).value_counts().reset_index()
    oa.columns = ["Estado", "Publicaciones"]
    st.plotly_chart(px.pie(oa, names="Estado", values="Publicaciones", hole=0.4), use_container_width=True)

with tabs[3]:
    st.subheader("🏥 Publicaciones por Departamento")
    dep = dff["Departamento"].fillna("Sin asignar").value_counts().reset_index()
    dep.columns = ["Departamento", "Publicaciones"]
    st.plotly_chart(px.bar(dep, x="Departamento", y="Publicaciones", title="Top Departamentos"), use_container_width=True)

with tabs[4]:
    st.subheader("📑 Revistas más frecuentes")
    
    # Función para formatear nombres de revistas
    def format_journal_name(name):
        if not isinstance(name, str):
            return "—"
        # Convertir a formato título (primera letra de cada palabra en mayúscula)
        formatted = name.title()
        # Corregir conectores comunes
        corrections = {
            "De": "de",
            "La": "la",
            "El": "el",
            "Y": "y",
            "En": "en",
            "Del": "del",
            "Los": "los",
            "Las": "las"
        }
        for wrong, right in corrections.items():
            formatted = formatted.replace(f" {wrong} ", f" {right} ")
        return formatted
    
    # Aplicar formato a los nombres de revistas
    dff["Journal_formatted"] = dff["Journal_norm"].apply(format_journal_name)
    
    journals = dff["Journal_formatted"].fillna("—").value_counts().head(20).reset_index()
    journals.columns = ["Revista", "Publicaciones"]
    
    # Crear gráfico con margen izquierdo suficiente
    fig = px.bar(journals.sort_values("Publicaciones"), 
                 x="Publicaciones", 
                 y="Revista", 
                 orientation="h", 
                 title="Top 20 Revistas")
    
    # Ajustar layout para que los nombres sean visibles
    fig.update_layout(
        yaxis=dict(categoryorder='total ascending'),
        margin=dict(l=300),  # Margen izquierdo más grande
        height=600,  # Altura suficiente para mostrar todos los nombres
        yaxis_tickfont=dict(size=12)  # Tamaño de fuente adecuado
    )
    
    # Mostrar valores dentro de las barras
    fig.update_traces(
        text=journals.sort_values("Publicaciones")["Publicaciones"],
        textposition='inside',
        insidetextanchor='start'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(journals)


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
            margin=dict(l=300, r=50, t=80, b=50),
            height=600,
            yaxis_tickfont=dict(size=12),
            title_font=dict(size=16)
        )

        fig.update_traces(
            textposition='inside',
            insidetextanchor='start',
            textfont=dict(size=11, color='white'),
            marker_color='#1f77b4'
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            top_cas.sort_values("Publicaciones", ascending=False).reset_index(drop=True)
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
        st.plotly_chart(
            px.bar(citas_year, x="Year", y=total_citas.name, title="Citas por Año"),
            use_container_width=True
        )
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

        institutions = institutions[~institutions.str.contains(
            r"(school|department|faculty|facultad|division|unidad)", 
            case=False, na=False
        )]

        # Diccionario de normalización
    normalization_map = {
    "university of chile": "Universidad de Chile",
    "universidad de chile": "Universidad de Chile",
    "pontificia universidad catolica de chile": "Pontificia Universidad Católica de Chile",
    "pontifical catholic university of chile": "Pontificia Universidad Católica de Chile",
    "clinica alemana - universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    "facultad de medicina clínica alemana - universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    "clinica alemana": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    "alemana clinic": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    "universidad del desarrollo": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    "university of development": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    "Instituto de Ciencias e Innovación en Medicina": "Facultad de Medicina Clínica Alemana - Universidad del Desarrollo",
    "clinica las condes": "Clínica Las Condes",
    "clínica las condes": "Clínica Las Condes",
    "clc": "Clínica Las Condes",
    "hospital militar de santiago": "Hospital Militar de Santiago",
    "hospital militar": "Hospital Militar de Santiago",
    "red de salud uc christus": "Red de Salud UC Christus",
    "uc christus": "Red de Salud UC Christus",
    "red de salud uc": "Red de Salud UC Christus",
    "red de salud catolica": "Red de Salud UC Christus",
    "red de salud católica": "Red de Salud UC Christus",
    "red de salud catolica puc": "Red de Salud UC Christus",
    "red de salud católica puc": "Red de Salud UC Christus",
    "red de salud catolica chile": "Red de Salud UC Christus",
    "hospital clinico universidad de chile": "Hospital Clínico Universidad de Chile",
    "hospital del salvador": "Hospital del Salvador",
    "harvard medical school": "Harvard University",
    "university of california": "University of California",
    "university of toronto": "University of Toronto"
}

        # Normalizar nombres
        def normalize_institution(name: str) -> str:
            key = re.sub(r"[^a-z ]", "", name.lower())  # quitar tildes y símbolos
            return normalization_map.get(key, name.strip())

        institutions = institutions.apply(normalize_institution)

        # Contar las top instituciones
        top_institutions = institutions.value_counts().head(15).reset_index()
        top_institutions.columns = ["Institución", "Publicaciones"]

        st.plotly_chart(
            px.bar(top_institutions.sort_values("Publicaciones"),
                   x="Publicaciones", y="Institución", orientation="h",
                   title="Top Instituciones en Afiliaciones"),
            use_container_width=True
        )
        st.dataframe(top_institutions)
    else:
        st.info("No se encontraron instituciones en las afiliaciones.")

with tabs[9]:
    st.subheader("🌱 Publicaciones por ODS")
    if "SDG" in dff.columns:
        sdg = dff["SDG"].dropna().astype(str).str.split(";").explode().str.strip()
        sdg_counts = sdg.value_counts().reset_index()
        sdg_counts.columns = ["ODS", "Publicaciones"]
        st.plotly_chart(
            px.bar(
                sdg_counts.sort_values("Publicaciones"),
                x="Publicaciones", y="ODS", orientation="h",
                title="Distribución por ODS"
            ),
            use_container_width=True
        )
        st.dataframe(sdg_counts)
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