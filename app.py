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
c1.metric("📚 Publicaciones", len(dff))
c2.metric("🔓 % Open Access", f"{100 * dff['OpenAccess_flag'].mean():.1f}%")
c3.metric("📈 Suma JIF", f"{dff['Journal Impact Factor'].sum():.1f}")
c4.metric("🧪 Ensayos clínicos", int(dff["ClinicalTrial_flag"].sum()))

# =========================
# Tabs
# =========================
tabs = st.tabs([
    "📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
    "🏥 Departamentos", "📑 Revistas", "👥 Autores", "☁️ Wordcloud"
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
    journals = dff["Journal_norm"].fillna("—").value_counts().head(20).reset_index()
    journals.columns = ["Revista", "Publicaciones"]
    st.plotly_chart(px.bar(journals.sort_values("Publicaciones"), x="Publicaciones", y="Revista", orientation="h", title="Top 20 Revistas"), use_container_width=True)
    st.dataframe(journals)


with tabs[5]:
    st.subheader("🏥 Autores de Clínica Alemana (CAS)")
    cas_authors = (
        dff["Authors_CAS"].fillna("")
        .astype(str)
        .str.split(r";")
        .explode()
        .str.strip()
        .replace("", np.nan)
        .dropna()
    )
    if not cas_authors.empty:
        top_cas = cas_authors.value_counts().head(20).reset_index()
        top_cas.columns = ["Autor CAS", "Publicaciones"]

        fig = px.bar(
            top_cas,
            x="Publicaciones",
            y="Autor CAS",
            orientation="h",
            title="Top Autores CAS",
        )

        fig.update_layout(
            yaxis=dict(categoryorder="total ascending"),
            margin=dict(l=250),
            yaxis_tickfont=dict(size=11)
        )

        # 👇 Solo mostrar número dentro de la barra
        fig.update_traces(
            text=top_cas["Publicaciones"],
            textposition="inside",
            insidetextanchor="start"
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(top_cas)
    else:
        st.info("No se detectaron autores CAS en las afiliaciones.")

    st.subheader("🏥 Autores de Clínica Alemana (CAS)")
    cas_authors = (
        dff["Authors_CAS"].fillna("")
        .astype(str)
        .str.split(r";")
        .explode()
        .str.strip()
        .replace("", np.nan)
        .dropna()
    )
    if not cas_authors.empty:
        top_cas = cas_authors.value_counts().head(20).reset_index()
        top_cas.columns = ["Autor CAS", "Publicaciones"]
        st.plotly_chart(px.bar(top_cas.sort_values("Publicaciones"), x="Publicaciones", y="Autor CAS", orientation="h", title="Top Autores CAS"), use_container_width=True)
        st.dataframe(top_cas)
    else:
        st.info("No se detectaron autores CAS en las afiliaciones.")


with tabs[6]:
    st.subheader("☁️ Wordcloud de títulos")
    try:
        from wordcloud import WordCloud, STOPWORDS

custom_stopwords = set(STOPWORDS)
custom_stopwords.update([
    # Español
    "el","la","los","las","un","una","unos","unas","de","del","y","en","por","para","con",
    # Inglés
    "the","a","an","of","for","to","with","on","at","by","from","they","their","this","that","these","those"
])

st.subheader("☁️ Wordcloud de títulos")
text = " ".join(dff["Title"].dropna().astype(str).tolist())
if text.strip():
    wc = WordCloud(
        width=1200, height=500,
        background_color="white",
        stopwords=custom_stopwords
    ).generate(text)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    st.pyplot(fig, use_container_width=True, clear_figure=True)
else:
    st.info("No hay títulos para construir la nube.")