# app_final.py
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================
# Config
# =========================
st.set_page_config(
    page_title="Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"  # 1ª hoja
DEFAULT_SHEET_INDEX = 0  # usa la primera hoja


# =========================
# FUNCIONES AUXILIARES
# =========================
def detectar_departamento(row):
    text = str(row.get("Authors with affiliations", "")) + " " + str(row.get("Affiliations", ""))
    text = text.lower()

    if "neurolog" in text or "psiquiatr" in text:
        return "Neurología y Psiquiatría"
    if "oncolog" in text:
        return "Oncología"
    if "pediatr" in text:
        return "Pediatría"
    if "ginecolog" in text or "obstet" in text:
        return "Ginecología y Obstetricia"
    if "cirug" in text:
        return "Cirugía"
    if "trauma" in text or "ortop" in text:
        return "Traumatología y Ortopedia"
    if "medicina interna" in text:
        return "Medicina Interna"
    if "enfermer" in text:
        return "Enfermería"
    if "imágenes" in text or "radiolog" in text:
        return "Imágenes"
    return "Sin asignar"

def detectar_ensayo_clinico(row):
    text = str(row.get("Publication Type", "")) + " " + str(row.get("Article Title", ""))
    text = text.lower()
    if "clinical trial" in text or "ensayo clínico" in text:
        return True
    return False

@st.cache_data
def load_data(uploaded=None):
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=DEFAULT_SHEET)

    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=DEFAULT_SHEET)

    return pd.DataFrame()


# =========================
# Utils
# =========================
def _first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _coerce_bool(sr: pd.Series) -> pd.Series:
    if sr is None:
        return pd.Series([False]*0, dtype=bool)
    x = sr.astype(str).str.lower().str.strip()
    true_vals = {"1","true","t","yes","y","si","sí"}
    false_vals = {"0","false","f","no","n","nan",""}
    out = pd.Series(index=sr.index, dtype=bool)
    out.loc[x.isin(true_vals)] = True
    out.loc[x.isin(false_vals)] = False
    return out.fillna(False)

def _coerce_num(sr: pd.Series) -> pd.Series:
    try:
        return pd.to_numeric(sr, errors="coerce")
    except Exception:
        return pd.Series([np.nan]*len(sr), index=sr.index)

def _title_key(s: object) -> str:
    t = str(s or "").lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    for engine in ("xlsxwriter","openpyxl"):
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as w:
                df.to_excel(w, index=False, sheet_name=sheet_name)
            buf.seek(0)
            return buf.getvalue()
        except Exception:
            continue
    return None

# =========================
# Carga
# =========================
@st.cache_data(show_spinner=False)
def load_data(uploaded=None) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=0, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=DEFAULT_SHEET_INDEX, dtype=str)
    raise FileNotFoundError(f"No se encontró {DEFAULT_XLSX}. Sube un XLSX desde la barra lateral.")

# =========================
# Detección/normalización en el dashboard (no borra columnas)
# =========================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str)

    # Año
    year_col = _first_col(df, ["_Year", "Year", "Publication Year", "PY"])
    if year_col:
        df["_Year"] = pd.to_numeric(df[year_col], errors="coerce").astype("Int64")
    else:
        df["_Year"] = pd.NA

    # Título
    title_col = _first_col(df, ["Title", "Document Title", "TI"])
    if title_col and "Title" not in df.columns:
        df["Title"] = df[title_col].astype(str)
    df["_title_key"] = df.get("Title", pd.Series("", index=df.index)).map(_title_key)

    # Open Access (True/False)
    oa_col = _first_col(df, ["OpenAccess_flag", "Open Access", "OA"])
    df["OpenAccess_flag"] = _coerce_bool(df[oa_col]) if oa_col else False

    # Clinical trials (si falta, lo detectamos)
    ct_col = _first_col(df, ["ClinicalTrial_flag", "Clinical Trial", "Ensayo_clinico"])
    if ct_col:
        df["ClinicalTrial_flag"] = _coerce_bool(df[ct_col])
    else:
        # detección naive
        text = (
            df.get("Title","").astype(str) + " " +
            df.get("Abstract","").astype(str) + " " +
            df.get("Publication Type","").astype(str) + " " +
            df.get("Keywords","").astype(str)
        ).str.lower()
        ct_regex = r"(ensayo\\s*clinico|clinical\\s*trial|randomi[sz]ed|phase\\s*[i1v]+|double\\s*blind|placebo\\-controlled)"
        df["ClinicalTrial_flag"] = text.str.contains(ct_regex, regex=True, na=False)

    # Sponsor (si falta, detectamos por texto)
    sp_col = _first_col(df, ["Has_Sponsor", "Sponsor_flag", "Funding sponsor", "Funding Sponsor"])
    if sp_col and sp_col in df.columns and df[sp_col].notna().any():
        df["Has_Sponsor"] = _coerce_bool(df[sp_col]) if df[sp_col].dropna().astype(str).str.lower().isin({"true","false","1","0","si","sí","no"}).any() \
                             else df[sp_col].astype(str).str.strip().ne("")
    else:
        # construir texto de funding si hay columnas relevantes
        fund_cols = [c for c in df.columns if re.search(r"(fund|grant|sponsor|financ|anid|conicyt|nih|erc|wellcome|fapesp)", c, flags=re.I)]
        fund_text = df[fund_cols].astype(str).agg(" ".join, axis=1) if fund_cols else ""
        df["Has_Sponsor"] = fund_text.astype(str).str.strip().ne("")

    # JIF (usar "Journal Impact Factor" exactamente o variantes)
    jif_col = _first_col(df, [
        "Journal Impact Factor", "Journal impact factor", "JOURNAL IMPACT FACTOR",
        "JIF","JIF_2023","Impact Factor","JCR_IF"
    ])
    df["_JIF_num"] = _coerce_num(df[jif_col]).fillna(0.0) if jif_col else 0.0

    # Cuartiles (usar JCR Quartile si existe; estandarizar)
    q_col = _first_col(df, [
        "JCR Quartile", "JCR_Quartile", "Quartile", "quartile_std",
        "SJR Quartile", "SJR_Quartile","Quartile_JCR","JIF Quartile"
    ])
    if q_col:
        q = df[q_col].astype(str).str.upper().str.extract(r"(Q[1-4])", expand=False)
        df["quartile_std"] = q.fillna("Sin cuartil")
    else:
        df["quartile_std"] = "Sin cuartil"

    # Departamento (si falta o vacío, inferimos desde afiliaciones)
    if "Departamento" not in df.columns or df["Departamento"].isna().all() or (df["Departamento"].astype(str).str.strip()=="").all():
        aff_col = _first_col(df, ["Authors with affiliations","Author Affiliations","Affiliations","C1","Author Information"])
        def detect_department(aff: str) -> str:
            a = str(aff or "").lower()
            rules = [
                ("oncolog", "Oncología"),
                ("pediatr", "Pediatría"),
                ("neurolog", "Neurología y Psiquiatría"),
                ("psiquiatr", "Neurología y Psiquiatría"),
                ("radiolog", "Imágenes"),
                ("imagen", "Imágenes"),
                ("ginecol", "Ginecología y Obstetricia"),
                ("obstet", "Ginecología y Obstetricia"),
                ("traumatolog", "Traumatología y Ortopedia"),
                ("ortoped", "Traumatología y Ortopedia"),
                ("dermatolog", "Dermatología"),
                ("medicina interna", "Medicina Interna"),
                ("internal medicine", "Medicina Interna"),
                ("urgenc", "Urgencias"),
                ("intensiv", "Cuidados Intensivos"),
                ("anestesi", "Anestesiología"),
                ("cardiol", "Cardiología"),
                ("endocrin", "Endocrinología"),
                ("nefrol", "Nefrología"),
                ("neumol", "Neumología"),
                ("rehabilit", "Rehabilitación"),
                ("odont", "Odontología"),
                ("alemana", "Clínica Alemana (General)"),
                ("universidad del desarrollo", "Clínica Alemana (General)"),
                ("udd", "Clínica Alemana (General)"),
            ]
            for kw, dep in rules:
                if kw in a:
                    return dep
            return "Sin asignar"
        df["Departamento"] = df.get(aff_col, pd.Series("", index=df.index)).map(detect_department)
    else:
        df["Departamento"] = df["Departamento"].fillna("Sin asignar").astype(str)

    # IDs mínimas (para merge por capas)
    for name in ["DOI","DOI_norm","PMID","PMID_norm","EID"]:
        if name not in df.columns:
            df[name] = pd.NA

    return df

# =========================
# Merge/Dedup con match por capas (DOI>PMID>EID>TY)
# =========================
def build_match_key(df: pd.DataFrame) -> pd.Series:
    doi = (df["DOI_norm"] if "DOI_norm" in df.columns else df.get("DOI","")).fillna("").astype(str)
    pmid = (df["PMID_norm"] if "PMID_norm" in df.columns else df.get("PMID","")).fillna("").astype(str)
    eid = df.get("EID","").fillna("").astype(str)
    y = df.get("_Year", pd.Series([-1]*len(df), index=df.index)).fillna(-1).astype("Int64").astype(str)
    t = df.get("_title_key", pd.Series([""]*len(df), index=df.index)).fillna("").astype(str)
    ty = "TY:" + y + "|" + t

    key = doi.where(doi != "", "PMID:" + pmid)
    key = key.where(key != "PMID:", "EID:" + eid)
    key = key.where(~key.isin(["","PMID:","EID:"]), ty)
    return key

def merge_preview(old_df: pd.DataFrame, new_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str,int]]:
    old = old_df.copy(); new = new_df.copy()
    old["_mk"] = build_match_key(old); new["_mk"] = build_match_key(new)
    old_set = set(k for k in old["_mk"] if isinstance(k,str) and k)
    new["_is_new"] = ~new["_mk"].isin(old_set)

    def layer(k: str) -> str:
        if k.startswith("10."): return "DOI"
        if k.startswith("PMID:") and len(k)>5: return "PMID"
        if k.startswith("EID:") and len(k)>4: return "EID"
        if k.startswith("TY:"): return "TY"
        return "VACIO"

    counts = new.loc[~new["_is_new"], "_mk"].map(layer).value_counts().to_dict()
    return new, counts

def merge_apply(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    a = old_df.copy(); b = new_df.copy()
    a["_mk"] = build_match_key(a); b["_mk"] = build_match_key(b)
    z = pd.concat([a, b], ignore_index=True, sort=False)
    z["_title_key"] = z.get("_title_key","")
    z["_dedup"] = z["_mk"].fillna("") + "|" + z["_title_key"].fillna("")
    z = z.drop_duplicates(subset="_dedup", keep="first").drop(columns=["_dedup"], errors="ignore")
    return z

# =========================
# Sidebar – datos base + merge
# =========================
with st.sidebar:
    st.header("Datos base")
    up = st.file_uploader("Sube un XLSX", type=["xlsx"])
    st.caption(f"Por defecto: `{DEFAULT_XLSX}` (1ª hoja)")

df_base = load_data(up)
df = normalize_columns(df_base)

with st.sidebar:
    st.markdown("---")
    st.header("Actualizar dataset (merge por capas)")
    new_files = st.file_uploader("Nuevos CSV/XLSX", type=["csv","xlsx"], accept_multiple_files=True)
    btn_prev = st.button("👀 Previsualizar unión")
    btn_apply = st.button("✅ Aplicar actualización", type="primary")
    save_over = st.checkbox("Sobrescribir archivo base al aplicar", value=False)

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
    prev, lc = merge_preview(df, new_df)
    n_new = int(prev["_is_new"].sum())
    n_dup = int(len(prev) - n_new)
    st.sidebar.success(f"Vista previa: {n_new} nuevos · {n_dup} duplicados.")
    st.sidebar.write("Coincidencias por capa:", lc)

if not new_df.empty and btn_apply:
    merged = merge_apply(df, new_df)
    st.sidebar.success(f"Unión aplicada. Registros ahora: {len(merged):,}")
    if save_over and Path(DEFAULT_XLSX).exists():
        try:
            merged.to_excel(DEFAULT_XLSX, index=False)
            st.sidebar.success(f"Sobrescrito `{DEFAULT_XLSX}`.")
        except Exception as e:
            st.sidebar.error(f"No se pudo sobrescribir: {e}")
    df = merged  # usar merged en la app

# =========================
# Filtros
# =========================
with st.sidebar:
    st.header("Filtros")

    # Año
    if df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int)
        lo, hi = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Año", lo, hi, (lo, hi))
    else:
        y1, y2 = (0, 9999)

    # OA
    oa_choice = st.radio("Open Access", ["Todos","Solo Open Access","Solo Closed Access"], index=0)

    # Cuartil
    qs = ["Q1","Q2","Q3","Q4","Sin cuartil"]
    sel_q = st.multiselect("Cuartil JCR/SJR", qs, default=qs)

    # Departamento
    dep_pool = (
        df["Departamento"].fillna("Sin asignar").astype(str)
        .str.split(r"\s*;\s*").explode().dropna().unique().tolist()
    )
    dep_pool = sorted([d for d in dep_pool if d])
    sel_dep = st.multiselect("Departamento", dep_pool, default=[])

    # Búsqueda por título
    qtxt = st.text_input("Buscar en título", "")

mask = pd.Series(True, index=df.index)

mask &= df["_Year"].fillna(-1).astype(int).between(y1, y2)

if oa_choice == "Solo Open Access":
    mask &= df["OpenAccess_flag"]
elif oa_choice == "Solo Closed Access":
    mask &= ~df["OpenAccess_flag"]

if sel_q:
    mask &= df["quartile_std"].isin(sel_q)

if sel_dep:
    patt = "|".join(re.escape(x) for x in sel_dep)
    mask &= df["Departamento"].fillna("").str.contains(patt)

if qtxt and "Title" in df.columns:
    mask &= df["Title"].fillna("").str.contains(qtxt, case=False, na=False)

dff = df.loc[mask].copy()
dff = dff.loc[:, ~pd.Index(dff.columns).duplicated(keep="last")]

st.title("Dashboard de Producción Científica Clínica Alemana- Universidad del Desarrollo")
st.caption("Dataset activo: " + (up.name if up is not None else DEFAULT_XLSX))

# =========================
# KPIs
# =========================
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total publicaciones", f"{len(dff):,}")

pct_oa = (dff["OpenAccess_flag"].mean() * 100) if len(dff) else 0.0
c2.metric("% Open Access", f"{pct_oa:.1f}%")

sum_jif = float(dff["_JIF_num"].sum()) if "_JIF_num" in dff.columns else 0.0
c3.metric("⭐ Suma total JIF", f"{sum_jif:,.1f}")

n_ct = int(dff["ClinicalTrial_flag"].sum()) if "ClinicalTrial_flag" in dff.columns else 0
c4.metric("🧪 Ensayos clínicos", f"{n_ct:,}")

n_sp = int(dff["Has_Sponsor"].sum()) if "Has_Sponsor" in dff.columns else 0
c5.metric("🤝 Con sponsor", f"{n_sp:,}")

# =========================
# Tabs
# =========================
tabs = st.tabs([
    "📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access", "🏥 Departamentos",
    "📚 Revistas", "👤 Autores", "☁️ Wordcloud"
])

# 1) Publicaciones
with tabs[0]:
    st.subheader("Publicaciones por año")
    if dff["_Year"].notna().any():
        g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
        fig = px.bar(x=g.index, y=g.values, labels={"x":"Año","y":"Publicaciones"}, title="Conteo por año")
        st.plotly_chart(fig, use_container_width=True, key="pubs_year")
    st.dataframe(dff.head(1000), use_container_width=True, height=430)
    # Descargas
    csv_bytes = dff.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ CSV filtrado", csv_bytes, "resultados_filtrados.csv", "text/csv", key="dl_csv")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ XLSX filtrado", xlsx_bytes, "resultados_filtrados.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_xlsx")

# 2) Cuartiles
with tabs[1]:
    st.subheader("Distribución por cuartil (JCR/SJR)")
    cts = dff["quartile_std"].value_counts()
    if not cts.empty:
        fig = px.pie(names=cts.index, values=cts.values, hole=0.5, title="Cuartiles")
        st.plotly_chart(fig, use_container_width=True, key="quart_pie")
        st.dataframe(cts.rename_axis("Cuartil").reset_index(name="Publicaciones"), use_container_width=True, height=360)
    else:
        st.info("Sin datos de cuartil.")

# 3) OA
with tabs[2]:
    st.subheader("Distribución Open Access")
    s = dff["OpenAccess_flag"].map({True:"Open Access", False:"Closed Access"}).value_counts()
    if not s.empty:
        fig = px.pie(names=s.index, values=s.values, hole=0.5, title="% OA vs Closed")
        st.plotly_chart(fig, use_container_width=True, key="oa_pie")
        st.dataframe(s.rename_axis("Estado").reset_index(name="Publicaciones"), use_container_width=True, height=360)
    else:
        st.info("No hay columna OpenAccess_flag.")

# 4) Departamentos
with tabs[3]:
    st.subheader("Distribución por departamento")
    s = dff["Departamento"].fillna("Sin asignar").astype(str).str.split(r"\s*;\s*").explode().value_counts()
    if not s.empty:
        fig = px.bar(s.sort_values(), orientation="h", title="Top departamentos")
        st.plotly_chart(fig, use_container_width=True, key="dep_bar")
        st.dataframe(s.rename_axis("Departamento").reset_index(name="Publicaciones"), use_container_width=True, height=420)
    else:
        st.info("No hay columna de Departamento.")

# 5) Revistas
with tabs[4]:
    st.subheader("Top revistas")
    jr_col = _first_col(dff, ["Journal_norm","Journal","Source Title","Publication Name","Source title"])
    if jr_col:
        s = dff[jr_col].fillna("—").value_counts().head(30)
        fig = px.bar(s.sort_values(), orientation="h", title="Top revistas (30)")
        st.plotly_chart(fig, use_container_width=True, key="jr_bar")
        st.dataframe(s.rename_axis("Revista").reset_index(name="Publicaciones"), use_container_width=True, height=420)
    else:
        st.info("No hay columna de revista.")

# 6) Autores
with tabs[5]:
    st.subheader("Top autores")
    a_col = _first_col(dff, ["Author Full Names","Author full names","Authors"])
    if a_col:
        s = dff[a_col].dropna().astype(str).str.split(";")
        authors = [a.strip() for sub in s for a in sub if a.strip()]
        if authors:
            vc = pd.Series(authors).value_counts().head(30)
            fig = px.bar(vc.sort_values(), orientation="h", title="Top autores (30)")
            st.plotly_chart(fig, use_container_width=True, key="auth_bar")
            st.dataframe(vc.rename_axis("Autor").reset_index(name="Publicaciones"), use_container_width=True, height=420)
        else:
            st.info("No hay autores parseables.")
    else:
        st.info("No hay columna de autores.")

# 7) Wordcloud (opcional)
with tabs[6]:
    st.subheader("Wordcloud (títulos)")
    try:
        from wordcloud import WordCloud
        import matplotlib.pyplot as plt
        text = " ".join(dff.get("Title", pd.Series(dtype=str)).dropna().astype(str).tolist())
        if text.strip():
            wc = WordCloud(width=1200, height=500, background_color="white").generate(text)
            fig, ax = plt.subplots(figsize=(10,4))
            ax.imshow(wc, interpolation="bilinear"); ax.axis("off")
            st.pyplot(fig, use_container_width=True, clear_figure=True)
        else:
            st.info("No hay títulos para construir la nube.")
    except Exception:
        st.info("Instala `wordcloud` para ver esta pestaña:  `pip install wordcloud`")

# =========================
# Suma JIF por año
# =========================
st.markdown("---")
st.subheader("Suma de JIF por año")
if "_JIF_num" in dff.columns and dff["_Year"].notna().any():
    j = (
        dff.dropna(subset=["_Year"])
           .assign(_Year=dff["_Year"].astype(int))
           .groupby("_Year")["_JIF_num"].sum()
           .sort_index()
    )
    fig = px.line(x=j.index, y=j.values, labels={"x":"Año","y":"Suma JIF"})
    st.plotly_chart(fig, use_container_width=True, key="jif_line")
else:
    st.info("No hay datos suficientes para calcular suma de JIF por año.")