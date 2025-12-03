# app_dashboard.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, List, Iterable

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
# Encabezado
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
# Responsive (móvil)
# =========================
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

# =========================
# 🔧 Autores CAS
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

def build_cas_ranking(dff: pd.DataFrame, include_udd: bool, fmt: str, top_n: int,
                      aff_col: Optional[str]) -> pd.DataFrame:
    if not aff_col or aff_col not in dff.columns:
        return pd.DataFrame()
    lists = dff[aff_col].apply(lambda s: extract_cas_authors_list(s, include_udd))
    if lists.map(len).sum() == 0:
        return pd.DataFrame()
    ser = lists.explode().dropna().astype(str).str.strip()
    if fmt == "initials":
        ser = ser.map(author_to_initials)
    else:
        ser = ser.map(author_to_full)
    counts = ser.value_counts().reset_index()
    counts.columns = ["Autor", "Publicaciones"]
    counts = counts.sort_values("Publicaciones", ascending=False).head(top_n)
    return counts

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
        df["OpenAccess_flag"] = sr.isin({"1","true","t","yes","y","si","sí"})
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
        mapping = {"1":"Q1","2":"Q2","3":"Q3","4":"Q4","Q-1":"Q1","Q-2":"Q2","Q-3":"Q3","Q-4":"Q4",
                   "QUARTIL 1":"Q1","QUARTIL 2":"Q2","QUARTIL 3":"Q3","QUARTIL 4":"Q4"}
        norm = raw.replace(mapping)
        norm = norm.str.extract(r"(Q[1-4])", expand=False).fillna(norm)
        df["Quartile"] = norm.where(norm.isin(["Q1","Q2","Q3","Q4"]), "Sin cuartil")
    else:
        df["Quartile"] = "Sin cuartil"

    # Departamento
    aff_col = _first_col(df, [
        "Authors with affiliations", "Affiliations", "Author Affiliations",
        "Affiliation(s)", "Affiliation", "Author Affiliation",
        "Correspondence Address", "Address", "Reprint Address"
    ])
    if aff_col:
        df["Departamento"] = df[aff_col].apply(detect_department)
    else:
        df["Departamento"] = "Sin asignar"

    # Ensayos clínicos
    df["ClinicalTrial_flag"] = df.apply(detect_clinical_trial, axis=1)

    # Revistas (respeta “Revista …” y normaliza suavemente)
    jbest = _pick_best_journal(df).fillna("").astype(str).str.strip()

    def fmt_journal(s: str) -> str:
        if not s or s.lower() in {"nan", "none"}:
            return ""
        base = unidecode.unidecode(s.strip().lower())

        # Mapeos explícitos más comunes
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

        # Si ya venía con “Revista …”, respeta la palabra “Revista”
        keep_revista = s.strip().lower().startswith("revista ")

        # Title Case suave (sin borrar conectores)
        words = re.sub(r"\s+", " ", s.strip()).split(" ")
        lower_exceptions = {"de","del","la","las","los","y","en","of","and","the"}
        titled = " ".join(w.capitalize() if w.lower() not in lower_exceptions else w.lower()
                          for w in words)

        # Asegurar siglas
        titled = re.sub(r"\bBmj\b", "BMJ", titled)
        titled = re.sub(r"\bNejm\b", "NEJM", titled)
        titled = re.sub(r"\bPlos One\b", "PLOS ONE", titled)

        if keep_revista and not titled.lower().startswith("revista "):
            titled = "Revista " + titled
        return titled

    df["Journal_display"] = jbest.map(fmt_journal)

    # Autores (cadena)
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
        quart_vals = [q for q in ["Q1","Q2","Q3","Q4","Sin cuartil"] if q in df["Quartile"].unique().tolist()] or ["Sin cuartil"]
        quart_filter = st.multiselect("Cuartiles", quart_vals, default=quart_vals, key="quart_multiselect")

    with st.sidebar.expander("🏥 Departamentos", expanded=False):
        depts = sorted(x for x in df["Departamento"].astype(str).unique() if x != "Sin asignar")
        dept_filter = st.multiselect("Departamentos", depts, default=None, key="dept_multiselect")

    with st.sidebar.expander("🔍 Búsqueda", expanded=False):
        search_term = st.text_input("Buscar en títulos", key="search_input")
    
    return year_range, oa_filter, quart_filter, dept_filter, search_term

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
    st.sidebar.write(f"🏥 Departamentos únicos: {df['Departamento'].nunique()}")

    # Filtros (incluye sin año por defecto)
    year_range, oa_filter, quart_filter, dept_filter, search_term = setup_filters(df)

    mask = pd.Series(True, index=df.index)
    yr_ok = df["Year"].between(year_range[0], year_range[1], inclusive="both")
    mask &= (df["Year"].isna() | yr_ok)

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

    if "Cited by" in dff.columns:
        total_citas = pd.to_numeric(dff["Cited by"], errors="coerce").fillna(0)
    elif "Times Cited" in dff.columns:
        total_citas = pd.to_numeric(dff["Times Cited"], errors="coerce").fillna(0)
    else:
        total_citas = pd.Series([0]*len(dff))
    h_index = int(sum(total_citas.sort_values(ascending=False).reset_index(drop=True) >= 
                      (np.arange(len(total_citas)) + 1)))
    col5, col6, col7, col8 = st.columns(4)
    with col5: st.metric("📖 Total citas", int(total_citas.sum()))
    with col6: st.metric("📖 Promedio citas", f"{total_citas.mean():.1f}")
    with col7: st.metric("🏆 % en Q1", f"{100 * (dff['Quartile']=='Q1').mean():.1f}%")
    with col8: st.metric("📊 h-index", h_index)

    # =========================
    # Pestañas
    # =========================
    tabs = st.tabs([
        "📅 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
        "🏥 Departamentos", "📑 Revistas", "👥 Autores",
        "☁️ Wordcloud", "📖 Citas"
    ])

    # --- Publicaciones
    with tabs[0]:
        st.subheader("📅 Publicaciones por año")
        g = dff.copy()
        g["Year_int"] = pd.to_numeric(g["Year"], errors="coerce").astype("Int64")
        gg = (
            g[g["Year_int"].notna()]
            .groupby("Year_int")
            .size()
            .reset_index(name="Publicaciones")
            .sort_values("Year_int")
        )
        fig = px.bar(gg, x="Year_int", y="Publicaciones", title="Publicaciones por Año", text="Publicaciones")
        fig.update_layout(
            margin=dict(l=10, r=10, t=50, b=10),
            font=dict(size=10),
            xaxis=dict(title="Año", dtick=1),
            yaxis=dict(title="Publicaciones"),
        )
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Suma JIF por año")
        j = dff.copy()
        j["Year_int"] = pd.to_numeric(j["Year"], errors="coerce").astype("Int64")
        j = j[j["Year_int"].notna() & (j["Year_int"] <= 2025)]
        if not j.empty:
            jj = (
                j.groupby("Year_int")["Journal Impact Factor"]
                 .sum(min_count=1)
                 .reset_index()
                 .rename(columns={"Year_int": "Year", "Journal Impact Factor": "Suma JIF"})
            )
            y_min = int(jj["Year"].min())
            full_years = pd.DataFrame({"Year": range(y_min, 2025 + 1)})
            jj = full_years.merge(jj, on="Year", how="left").fillna({"Suma JIF": 0})
            jj["Suma JIF"] = jj["Suma JIF"].round(1)

            fig = px.line(jj, x="Year", y="Suma JIF", markers=True, title="Suma JIF por Año", text="Suma JIF")
            fig.update_traces(textposition="top center")
            fig.update_layout(
                margin=dict(l=10, r=10, t=50, b=10),
                font=dict(size=10),
                xaxis=dict(title="Año", dtick=1),
                yaxis=dict(title="Suma JIF"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos con año válido (≤ 2025) para el gráfico de JIF.")

    # --- Cuartiles
    with tabs[1]:
        st.subheader("📊 Distribución por cuartiles")
        cts = dff["Quartile"].value_counts().reset_index()
        cts.columns = ["Quartile", "Publicaciones"]
        fig = px.pie(cts, names="Quartile", values="Publicaciones", hole=0.4)
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- Open Access
    with tabs[2]:
        st.subheader("🔓 Publicaciones Open Access")
        oa = dff["OpenAccess_flag"].map({True: "Open Access", False: "Closed"}).value_counts().reset_index()
        oa.columns = ["Estado", "Publicaciones"]
        fig = px.pie(oa, names="Estado", values="Publicaciones", hole=0.4)
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- Departamentos
    with tabs[3]:
        st.subheader("🏥 Publicaciones por Departamento (sin 'Sin asignar')")
        dep = (
            dff.loc[dff["Departamento"] != "Sin asignar", "Departamento"]
            .fillna("—")
            .value_counts()
            .reset_index()
        )
        dep.columns = ["Departamento", "Publicaciones"]
        fig = px.bar(dep, x="Departamento", y="Publicaciones", title="Top Departamentos", text="Publicaciones")
        fig.update_traces(textposition='outside')
        fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- Revistas
    with tabs[4]:
        st.subheader("📑 Revistas más frecuentes")
        journals = (
            dff["Journal_display"]
            .replace({"nan": "", "None": "", "—": ""})
            .astype(str).str.strip()
        )
        journals = journals[journals != ""]
        jr = journals.value_counts().head(20).reset_index()
        jr.columns = ["Revista", "Publicaciones"]

        fig = px.bar(
            jr.sort_values("Publicaciones"),
            x="Publicaciones", y="Revista",
            orientation="h",
            title="Top 20 Revistas",
            text="Publicaciones"
        )
        fig.update_layout(
            yaxis=dict(categoryorder='total ascending'),
            margin=dict(l=260, r=10, t=50, b=10),
            height=560,
            yaxis_tickfont=dict(size=12),
            font=dict(size=10)
        )
        fig.update_traces(textposition='inside', insidetextanchor='start')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(jr, use_container_width=True)

    # --- 👥 Autores (CAS)
    with tabs[5]:
        st.subheader("👥 Autores CAS (sólo publicaciones con afiliación a Clínica Alemana/UDD)")
        aff_col = _first_col(dff, [
            "Authors with affiliations", "Affiliations", "Author Affiliations",
            "Affiliation(s)", "Affiliation", "Author Affiliation"
        ])
        if not aff_col:
            st.warning("No se encontró la columna de afiliaciones (p. ej. 'Authors with affiliations').")
        else:
            colA, colB, colC = st.columns([1.2, 1.6, 1])
            with colA:
                fmt_choice = st.radio(
                    "Formato:",
                    ["Apellido, Inicial", "Apellido, Nombre(s)"],
                    horizontal=True, index=0
                )
            with colB:
                include_udd = st.checkbox(
                    "Incluir UDD/ICIM/F. Medicina además de Clínica Alemana",
                    value=True
                )
            with colC:
                top_n = st.slider("Top N", min_value=10, max_value=100, value=50, step=5)

            fmt_key = "initials" if fmt_choice == "Apellido, Inicial" else "full"
            ranking = build_cas_ranking(dff, include_udd, fmt_key, top_n, aff_col)

            if ranking.empty:
                st.info("No se detectaron autores CAS en el subconjunto filtrado.")
            else:
                plot_df = ranking.sort_values("Publicaciones", ascending=True)

                # Margen izquierdo dinámico para que SIEMPRE se vea el primer autor
                max_label_len = int(plot_df["Autor"].astype(str).str.len().max())
                left_margin = min(520, 160 + max_label_len * 7)

                fig = px.bar(
                    plot_df, x="Publicaciones", y="Autor",
                    orientation="h",
                    title=f"Top {len(plot_df)} Autores CAS · {fmt_choice}",
                    text="Publicaciones",
                )
                fig.update_layout(
                    yaxis=dict(categoryorder='total ascending', automargin=True, title="Autor"),
                    margin=dict(l=left_margin, r=20, t=60, b=40),
                    height=max(500, 20 * len(plot_df) + 160),
                    font=dict(size=12)
                )
                fig.update_traces(textposition='inside', insidetextanchor='start')
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📋 Ranking (tabla)")
                st.dataframe(ranking, use_container_width=True, height=400)

                csv_bytes = ranking.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "⬇️ Descargar ranking CAS (CSV)",
                    data=csv_bytes,
                    file_name=f"ranking_autores_CAS_top{len(plot_df)}.csv",
                    mime="text/csv"
                )

    # --- Wordcloud
    with tabs[6]:
        st.subheader("☁️ Wordcloud (Keywords)")
        try:
            from wordcloud import WordCloud, STOPWORDS
            import matplotlib.pyplot as plt

            kw_cols = [
                "Author Keywords", "Author keywords", "Author Keywords Plus",
                "Keywords", "Indexed Keywords", "Index Keywords",
                "AuthKeywords", "DE", "ID", "Keywords Plus"
            ]
            kws = []
            for c in kw_cols:
                if c in dff.columns:
                    kws.append(dff[c].dropna().astype(str))
            if kws:
                kw_text = " ; ".join(pd.concat(kws).tolist())
            else:
                kw_text = " ".join(dff["Title"].dropna().astype(str).tolist())

            if kw_text.strip():
                custom_stop = set(STOPWORDS)
                custom_stop.update([
                    "el","la","los","las","un","una","unos","unas","de","del","y","en",
                    "por","para","con","the","a","an","of","for","to","with","on","at",
                    "by","from","they","their","this","that","these","those"
                ])
                wc = WordCloud(width=1200, height=500, background_color="white",
                               stopwords=custom_stop).generate(kw_text)
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.imshow(wc, interpolation="bilinear")
                ax.axis("off")
                st.pyplot(fig, use_container_width=True, clear_figure=True)
            else:
                st.info("No hay palabras clave para construir la nube.")
        except Exception:
            st.info("Instala la librería `wordcloud` para ver esta sección:  `pip install wordcloud`")

    # --- Citas por año
    with tabs[7]:
        st.subheader("📖 Citas por año")
        if not total_citas.empty:
            dff_tmp = dff.copy()
            dff_tmp["Year_int"] = pd.to_numeric(dff_tmp["Year"], errors="coerce").astype("Int64")
            citas_year = (
                dff_tmp[dff_tmp["Year_int"].notna()]
                .groupby("Year_int")[total_citas.name]
                .sum()
                .reset_index()
                .rename(columns={"Year_int":"Year", total_citas.name:"Citas"})
            )
            fig = px.bar(citas_year, x="Year", y="Citas", title="Citas por Año", text="Citas")
            fig.update_traces(textposition='outside')
            fig.update_layout(
                autosize=True, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=10),
                xaxis=dict(dtick=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de citas en este dataset.")

if __name__ == "__main__":
    main()