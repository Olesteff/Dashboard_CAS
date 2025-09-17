# /app/app.py
# Dashboard Cienciométrico con Tabs + Merge/Dedup + PDF + WordCloud de títulos (lee 1ª hoja)

from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# -----------------------------
# Configuración general
# -----------------------------
st.set_page_config(
    page_title="Dashboard Cienciométrico",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = 0  # siempre la 1ª hoja

DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)

CAND = {
    "title": ["Title", "Document Title", "TI"],
    "year": ["Year", "Publication Year", "PY", "_Year", "Year_clean"],
    "doi": ["DOI", "Doi"],
    "link": ["Link", "URL", "Full Text URL"],
    "journal": ["Journal_norm", "Source title", "Source Title", "Publication Name", "Journal"],
    "dept": ["Departamento", "Dept_CAS_list", "Dept_FMUDD_list", "Department"],
    "authors": ["Author full names", "Author Full Names", "Authors"],
    "cited": ["Cited by", "Times Cited", "TimesCited"],
    "pmid": ["PubMed ID", "PMID"],
    "wos": ["Web of Science Record", "Unique WOS ID", "UT (Unique WOS ID)"],
    "eid": ["EID", "Scopus EID"],
    "oa_flags": ["OpenAccess_flag", "OA_Scopus", "OA_WoS", "OA_PubMed", "OA"],
}

# -----------------------------
# Utilidades básicas
# -----------------------------
def _first_col(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    for c in names:
        if c in df.columns:
            return c
    return None

def _extract_doi(val: object) -> Optional[str]:
    if pd.isna(val):
        return None
    m = DOI_REGEX.search(str(val))
    return m.group(0).lower() if m else None

def _norm_text(s: object) -> str:
    if pd.isna(s):
        return ""
    t = str(s).strip()
    t = re.sub(r"\s+", " ", t)
    return t

def _title_key(s: object) -> str:
    if pd.isna(s):
        return ""
    t = re.sub(r"[^A-Za-z0-9 ]", " ", str(s).lower())
    return re.sub(r"\s+", " ", t).strip()

def _bool_from_str_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(False, index=pd.RangeIndex(0))
    x = s.astype(str).str.lower().str.strip()
    true_vals = {"1", "true", "t", "yes", "y", "si", "sí"}
    false_vals = {"0", "false", "f", "no", "n", ""}
    out = pd.Series(index=x.index, dtype=bool)
    out.loc[x.isin(true_vals)] = True
    out.loc[x.isin(false_vals)] = False
    return out.fillna(False)

def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> Optional[bytes]:
    for engine in ("xlsxwriter", "openpyxl"):
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine=engine) as w:
                df.to_excel(w, index=False, sheet_name=sheet_name)
            buf.seek(0)
            return buf.getvalue()
        except Exception:
            continue
    return None

def _plotly_png(fig) -> Optional[bytes]:
    try:
        buf = BytesIO()
        fig.write_image(buf, format="png", scale=3)  # requiere kaleido
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

def _make_pdf_report(imgs: Dict[str, bytes], kpis: Dict[str, str]) -> Optional[bytes]:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from reportlab.lib.units import cm

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        W, H = A4

        c.setFont("Helvetica-Bold", 18)
        c.drawString(2*cm, H-2.5*cm, "Dashboard Cienciométrico — Resumen")
        c.setFont("Helvetica", 11)
        y = H-4*cm
        for k, v in kpis.items():
            c.drawString(2*cm, y, f"{k}: {v}")
            y -= 0.7*cm
        c.showPage()

        for title, png in imgs.items():
            c.setFont("Helvetica-Bold", 14)
            c.drawString(2*cm, H-2.2*cm, title)
            if png is not None:
                img = ImageReader(BytesIO(png))
                max_w, max_h = W-3*cm, H-5*cm
                c.drawImage(img, 1.5*cm, 3*cm, width=max_w, height=max_h, preserveAspectRatio=True, anchor='s')
            else:
                c.setFont("Helvetica", 12)
                c.drawString(2*cm, H-3.5*cm, "(Instala 'kaleido' para incluir imágenes)")
            c.showPage()

        c.save()
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

# -----------------------------
# Utilidades de texto / WordCloud
# -----------------------------
def _strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")

def build_stopwords(extra_csv: str = "") -> set:
    # Por qué: cubrir artículos, conectores y muy comunes EN/ES (incluye 'are' como pidió)
    en = {
        "a","an","the","and","or","but","if","then","else","for","to","of","in","on","at","by","with","from","as",
        "is","are","was","were","be","been","being","it","its","this","that","these","those","we","you","they","i",
        "he","she","them","his","her","their","our","us","my","your","not","no","yes","do","does","did","done",
        "can","could","may","might","must","should","would","will","there","here","than","also","et","al"
    }
    es = {
        "el","la","los","las","un","una","unos","unas","y","o","u","pero","si","entonces","sino","como","de","del",
        "en","con","por","para","a","al","que","se","su","sus","es","son","fue","fueron","ser","ha","han","hay",
        "este","esta","estos","estas","eso","esa","esos","esas","lo"
    }
    extras = {w.strip().lower() for w in extra_csv.split(",") if w.strip()}
    # palabras 1-2 letras casi siempre ruido
    short = set([chr(c) for c in range(ord('a'), ord('z')+1)]) | set(list("de el la los las y o u en al si no".split()))
    return en | es | extras | short

def tokenize_titles(series: pd.Series, min_len: int, stop: set, bigrams: bool = False) -> Counter:
    cnt: Counter = Counter()
    for raw in series.dropna().astype(str):
        t = _strip_accents(raw.lower())
        t = re.sub(r"[^a-z0-9 ]+", " ", t)
        words = [w for w in t.split() if len(w) >= min_len and w not in stop]
        if not words:
            continue
        cnt.update(words)
        if bigrams and len(words) >= 2:
            # por qué: bigrams ayudan a captar temas compuestos
            cnt.update([f"{words[i]} {words[i+1]}" for i in range(len(words)-1)])
    return cnt

def _wordcloud_png_from_freq(freq: Dict[str, int], width: int = 1600, height: int = 900) -> Optional[bytes]:
    try:
        from wordcloud import WordCloud  # type: ignore
        wc = WordCloud(
            width=width,
            height=height,
            background_color="white",
            collocations=False,   # por qué: evitamos auto-bigrams que distorsionan
            normalize_plurals=False,
            prefer_horizontal=0.9,
            random_state=42
        ).generate_from_frequencies(freq)
        img = wc.to_image()
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None

# -----------------------------
# Carga (cache) — primera hoja
# -----------------------------
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded, sheet_name=DEFAULT_SHEET) -> pd.DataFrame:
    if uploaded is not None:
        return pd.read_excel(uploaded, sheet_name=sheet_name, dtype=str)
    if Path(DEFAULT_XLSX).exists():
        return pd.read_excel(DEFAULT_XLSX, sheet_name=sheet_name, dtype=str)
    raise FileNotFoundError(f"No se encontró {DEFAULT_XLSX}. Sube el XLSX desde la barra lateral.")

# -----------------------------
# Normalización
# -----------------------------
def normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~pd.Index(df.columns).duplicated(keep="last")]

    ycol = _first_col(df, CAND["year"])
    if ycol:
        df["_Year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")

    tcol = _first_col(df, CAND["title"])
    if tcol and tcol != "Title":
        df["Title"] = df[tcol].astype(str)

    dcol = _first_col(df, CAND["doi"])
    lcol = _first_col(df, CAND["link"])
    doi_base = df[dcol].astype(str).str.strip().str.lower() if dcol else pd.Series(np.nan, index=df.index)
    doi_from_link = df[lcol].astype(str).map(_extract_doi) if lcol else pd.Series(np.nan, index=df.index)
    df["DOI_norm"] = doi_base.where(doi_base.notna() & (doi_base != ""), doi_from_link)

    jcol = _first_col(df, CAND["journal"])
    if jcol:
        df["Journal_norm"] = df[jr_col] if (jr_col := jcol) else df.get("Journal_norm")
        df["Journal_norm"] = df["Journal_norm"].map(_norm_text)

    dpt = _first_col(df, CAND["dept"])
    if dpt:
        df["Departamento"] = df[dpt]

    acol = _first_col(df, CAND["authors"])
    if acol and acol != "Author Full Names":
        df["Author Full Names"] = df[acol]

    ccol = _first_col(df, CAND["cited"])
    if ccol and ccol != "Times Cited":
        df["Times Cited"] = pd.to_numeric(df[ccol], errors="coerce")

    pmid_col = _first_col(df, CAND["pmid"])
    if pmid_col and "PMID_norm" not in df.columns:
        df["PMID_norm"] = df[pmid_col].astype(str).str.replace(r"\D+", "", regex=True).replace("", np.nan)

    eid_col = _first_col(df, CAND["eid"])
    if eid_col and "EID" not in df.columns:
        df["EID"] = df[eid_col].astype(str)

    df["in_PubMed"] = df[pmid_col].notna() if pmid_col else False
    df["in_WoS"] = df[_first_col(df, CAND["wos"])].notna() if _first_col(df, CAND["wos"]) else False
    df["in_Scopus"] = False
    if "Times Cited" in df.columns:
        df["in_Scopus"] = df["Times Cited"].notna()
    if "OA_Scopus" in df.columns:
        df["in_Scopus"] = df["in_Scopus"] | df["OA_Scopus"].notna()

    oa_cols = [c for c in CAND["oa_flags"] if c in df.columns]
    if oa_cols:
        oa_any = pd.concat([_bool_from_str_series(df[c]) for c in oa_cols], axis=1).any(axis=1)
        df["Open Access"] = oa_any.map({True: "OA", False: "No OA"})
    else:
        df["Open Access"] = "Desconocido"

    return df

# -----------------------------
# Merge / Deduplicación
# -----------------------------
def _build_dedup_key(df_like: pd.DataFrame) -> pd.Series:
    parts: List[pd.Series] = []
    if "DOI_norm" in df_like.columns:
        parts.append(df_like["DOI_norm"].fillna(""))
    if "PMID_norm" in df_like.columns:
        parts.append("PMID:" + df_like["PMID_norm"].fillna(""))
    if "EID" in df_like.columns:
        parts.append("EID:" + df_like["EID"].astype(str).fillna(""))
    ycol = _first_col(df_like, CAND["year"])
    tcol = _first_col(df_like, CAND["title"])
    if ycol and tcol:
        y = pd.to_numeric(df_like[ycol], errors="coerce").fillna(-1).astype(int).astype(str)
        t = df_like[tcol].map(_title_key).fillna("")
        parts.append("TY:" + y + "|" + t)
    if not parts:
        return pd.Series("", index=df_like.index, dtype="object")
    key = parts[0].astype(str)
    for p in parts[1:]:
        key = key.where(key.astype(bool), p.astype(str))
    return key

def _read_any(file_obj) -> pd.DataFrame:
    name = (getattr(file_obj, "name", "") or "").lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(file_obj, dtype=str)
        return pd.read_excel(file_obj, dtype=str)
    except Exception:
        return pd.DataFrame()

# -----------------------------
# Sidebar – Carga y Filtros + Merge
# -----------------------------
with st.sidebar:
    st.subheader("Datos base")
    up = st.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])
    st.caption(f"Por defecto: `{DEFAULT_XLSX}` (se leerá la 1ª hoja)")
    st.markdown("---")
    st.subheader("Actualizar dataset (merge)")
    new_files = st.file_uploader("Nuevos CSV/XLSX", type=["csv", "xlsx"], accept_multiple_files=True)
    colA, colB = st.columns([1,1])
    with colA:
        btn_preview = st.button("👀 Previsualizar unión")
    with colB:
        btn_apply = st.button("✅ Aplicar actualización", type="primary")
    save_over = st.checkbox("Sobrescribir archivo base al aplicar (si existe)", value=False)
    st.markdown("---")
    st.subheader("Filtros")

# Carga y normalización inicial
try:
    base_df = load_dataframe(up, sheet_name=DEFAULT_SHEET)
except Exception as e:
    st.error(str(e))
    st.stop()

df = normalize_dataset(base_df)

# Si ya hay df actualizado en sesión, úsalo
if "__df_updated__" in st.session_state and isinstance(st.session_state["__df_updated__"], pd.DataFrame):
    df = st.session_state["__df_updated__"]

# Merge preview/apply
if new_files:
    news: List[pd.DataFrame] = []
    for f in new_files:
        t = _read_any(f)
        if not t.empty:
            news.append(normalize_dataset(t))
    new_df = pd.concat(news, ignore_index=True, sort=False) if news else pd.DataFrame()

    if not new_df.empty:
        pre_keys = _build_dedup_key(df)
        pre_set = set(k for k in pre_keys if isinstance(k, str) and k)
        cand_keys = _build_dedup_key(new_df)
        is_new = cand_keys.map(lambda k: (isinstance(k, str) and k not in pre_set and k != ""))

        if btn_preview:
            n_new = int(is_new.sum())
            n_dup = int(len(new_df) - n_new)
            st.info(f"Vista previa: {n_new} nuevos · {n_dup} duplicados/ignorados.")
            cols_preview = [c for c in ["Title", "_Year", "DOI_norm", "PMID_norm", "EID"] if c in new_df.columns]
            st.dataframe(new_df.loc[is_new, cols_preview].head(150), use_container_width=True, height=280)

        if btn_apply:
            merged = pd.concat([df, new_df], ignore_index=True, sort=False)
            merged["_dedup_key"] = _build_dedup_key(merged)
            merged["_title_key"] = merged["Title"].map(_title_key) if "Title" in merged.columns else ""
            merged["__tmp__"] = merged["_dedup_key"].fillna("") + "|" + merged["_title_key"].fillna("")
            merged = merged.drop_duplicates(subset="__tmp__", keep="first").drop(columns=["__tmp__"], errors="ignore")
            added = merged.shape[0] - df.shape[0]
            st.success(f"Actualización aplicada: +{max(0, added)} registros nuevos (total {len(merged):,}).")

            st.session_state["__df_updated__"] = merged
            df = merged

            xbytes = _df_to_xlsx_bytes(df)
            if xbytes:
                st.download_button("⬇️ Descargar dataset ACTUALIZADO (XLSX)", xbytes,
                                   file_name="dataset_actualizado.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="dl_updated_ds")

            if save_over and Path(DEFAULT_XLSX).exists():
                try:
                    df.to_excel(DEFAULT_XLSX, index=False)
                    st.success(f"Sobrescrito `{DEFAULT_XLSX}`.")
                except Exception as e:
                    st.error(f"No se pudo sobrescribir: {e}")

# -----------------------------
# Filtros (sidebar)
# -----------------------------
mask = pd.Series(True, index=df.index)

with st.sidebar:
    if "_Year" in df.columns and df["_Year"].notna().any():
        ys = df["_Year"].dropna().astype(int)
        y_min, y_max = int(ys.min()), int(ys.max())
        y1, y2 = st.slider("Año", y_min, y_max, (y_min, y_max))
        mask &= df["_Year"].astype(float).between(y1, y2)

    src_opts = [c for c in ["in_Scopus", "in_WoS", "in_PubMed"] if c in df.columns]
    sel_src = st.multiselect("Fuente", options=src_opts, default=src_opts)
    if sel_src:
        mask &= df[sel_src].fillna(False).any(axis=1)

    if "Open Access" in df.columns:
        oa_vals = ["OA", "No OA", "Desconocido"]
        sel_oa = st.multiselect("Open Access", oa_vals, default=oa_vals)
        mask &= df["Open Access"].isin(sel_oa)

    query = st.text_input("Buscar en título", "")
    if query and "Title" in df.columns:
        mask &= df["Title"].fillna("").str.contains(query, case=False, na=False)

    if "Departamento" in df.columns and df["Departamento"].notna().any():
        dep_pool = df["Departamento"].dropna().astype(str).str.split(r"\s*;\s*").explode().dropna()
        dep_pool = sorted(set([d for d in dep_pool if d]))
        sel_dep = st.multiselect("Departamento", dep_pool, default=[])
        if sel_dep:
            rgx = "|".join(map(re.escape, sel_dep))
            mask &= df["Departamento"].fillna("").str.contains(rgx)

dff = df[mask].copy()
dff = dff.loc[:, ~pd.Index(dff.columns).duplicated(keep="last")]

st.subheader(f"Resultados: {len(dff):,}")

# -----------------------------
# KPIs + figuras
# -----------------------------
def _kpis_summary(dff: pd.DataFrame) -> Dict[str, str]:
    kpis: Dict[str, str] = {}
    kpis["Nº publicaciones"] = f"{len(dff):,}"
    kpis["% con DOI"] = f"{(dff['DOI_norm'].notna().mean() * 100):.1f}%" if "DOI_norm" in dff.columns and len(dff) else "—"
    kpis["% OA"] = f"{(dff['Open Access'].eq('OA').mean() * 100):.1f}%" if "Open Access" in dff.columns and len(dff) else "—"
    kpis["Mediana citas"] = f"{pd.to_numeric(dff['Times Cited'], errors='coerce').median():.0f}" if "Times Cited" in dff.columns and len(dff) else "—"
    return kpis

def _fig_year_counts(dff: pd.DataFrame):
    g = dff["_Year"].dropna().astype(int).value_counts().sort_index()
    return px.bar(x=g.index, y=g.values, labels={"x": "Año", "y": "Nº publicaciones"}, title="Conteo por año")

def _fig_oa_pie(dff: pd.DataFrame):
    oa_counts = dff["Open Access"].fillna("Desconocido").value_counts()
    fig = px.pie(names=oa_counts.index, values=oa_counts.values, title="Proporción OA / No OA")
    fig.update_traces(textinfo="percent+label")
    return fig

# -----------------------------
# Tabs (añadimos 🔎 Títulos)
# -----------------------------
tabs = st.tabs(["📌 Resumen", "📄 Datos", "📚 Revistas", "🧑‍🔬 Autores", "🔎 Títulos", "🟢 OA", "⭐ Citas"])

# RESUMEN
with tabs[0]:
    k1, k2, k3, k4 = st.columns(4)
    KP = _kpis_summary(dff)
    k1.metric("Nº publicaciones", KP["Nº publicaciones"])
    k2.metric("% con DOI", KP["% con DOI"])
    k3.metric("% OA", KP["% OA"])
    k4.metric("Mediana citas", KP["Mediana citas"])

    imgs: Dict[str, Optional[bytes]] = {}

    st.subheader("📈 Publicaciones por año")
    if "_Year" in dff.columns and dff["_Year"].notna().any():
        fig_year = _fig_year_counts(dff)
        st.plotly_chart(fig_year, use_container_width=True)
        png = _plotly_png(fig_year); imgs["Publicaciones por año"] = png
        if png:
            st.download_button("⬇️ PNG — Publicaciones por año", png, "pubs_por_anio.png", "image/png")

    st.subheader("🟢 Open Access (resumen)")
    if "Open Access" in dff.columns and len(dff):
        fig_oa = _fig_oa_pie(dff)
        st.plotly_chart(fig_oa, use_container_width=True)
        png = _plotly_png(fig_oa); imgs["Open Access"] = png
        if png:
            st.download_button("⬇️ PNG — OA", png, "open_access.png", "image/png")

    pdf_bytes = _make_pdf_report({k: v for k, v in imgs.items() if v is not None}, KP)
    if pdf_bytes:
        st.download_button("⬇️ PDF — Reporte resumido", pdf_bytes, "reporte_dashboard.pdf", "application/pdf")
    else:
        st.caption("Para PDF con imágenes instala `reportlab` y `kaleido` (opcional).")

# DATOS
with tabs[1]:
    st.subheader("Resultados filtrados")
    st.dataframe(dff.head(1000), use_container_width=True, height=420)
    csv_bytes = dff.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ CSV — Resultados", csv_bytes, "resultados_filtrados.csv", "text/csv")
    xlsx_bytes = _df_to_xlsx_bytes(dff)
    if xlsx_bytes:
        st.download_button("⬇️ XLSX — Resultados", xlsx_bytes, "resultados_filtrados.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# REVISTAS
with tabs[2]:
    st.subheader("Top 20 Revistas")
    jr_col = "Journal_norm" if "Journal_norm" in dff.columns else _first_col(dff, CAND["journal"])
    if jr_col and dff[jr_col].notna().any():
        top_jr = dff[jr_col].fillna("—").value_counts().head(20).rename_axis("Journal").reset_index(name="N")
        fig_jr = px.bar(top_jr.sort_values("N"), x="N", y="Journal", orientation="h", title="Top 20 revistas")
        st.plotly_chart(fig_jr, use_container_width=True)
        st.dataframe(top_jr, use_container_width=True, height=420)
        png = _plotly_png(fig_jr)
        if png:
            st.download_button("⬇️ PNG — Top revistas", png, "top_revistas.png", "image/png")
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
        fig_auth = px.bar(top_auth.sort_values("N° Publicaciones"), x="N° Publicaciones", y="Autor",
                          orientation="h", title="Top 20 autores")
        st.plotly_chart(fig_auth, use_container_width=True)
        st.dataframe(top_auth, use_container_width=True, height=420)
        png = _plotly_png(fig_auth)
        if png:
            st.download_button("⬇️ PNG — Top autores", png, "top_autores.png", "image/png")
    else:
        st.info("No hay columna de autores.")

# 🔎 TÍTULOS — WordCloud
with tabs[4]:
    st.subheader("🔎 Tendencias en títulos (WordCloud)")
    if "Title" not in df.columns or df["Title"].dropna().empty:
        st.info("No hay columna de títulos.")
    else:
        c1, c2, c3, c4 = st.columns([1.1,1,1.2,2])
        with c1:
            scope = st.radio("Alcance", ["Filtrado", "Todo"], horizontal=True)
        with c2:
            min_len = st.slider("Mín. letras", 2, 6, 3)
        with c3:
            use_bigrams = st.checkbox("Incluir bigrams", value=False)
        with c4:
            stop_extra = st.text_input("Stopwords extra (coma separadas)", "study,analysis,clinical,trial,case,report,review,role,effect")
        ds = dff if scope == "Filtrado" else df

        stop = build_stopwords(stop_extra)
        freq = tokenize_titles(ds["Title"], min_len=min_len, stop=stop, bigrams=use_bigrams)

        if not freq:
            st.info("No hay términos después de filtrar stopwords.")
        else:
            # WordCloud (PNG)
            png_wc = _wordcloud_png_from_freq(dict(freq.most_common(300)))
            if png_wc:
                st.image(png_wc, caption="WordCloud de términos en títulos", use_container_width=True)
                st.download_button("⬇️ PNG — WordCloud", png_wc, "wordcloud_titulos.png", "image/png")
            else:
                st.warning("Instala el paquete `wordcloud` para renderizar la nube (pip install wordcloud).")

            # Top términos (tabla)
            top_n = st.slider("Top N términos", 10, 100, 30)
            top_df = pd.DataFrame(freq.most_common(top_n), columns=["Término", "Frecuencia"])
            st.dataframe(top_df, use_container_width=True, height=360)

# OA
with tabs[5]:
    st.subheader("Open Access")
    if "Open Access" in dff.columns and len(dff):
        fig_oa = _fig_oa_pie(dff)
        st.plotly_chart(fig_oa, use_container_width=True)
        png = _plotly_png(fig_oa)
        if png:
            st.download_button("⬇️ PNG — OA", png, "open_access.png", "image/png")
        cols = [c for c in ["Title", "_Year", "Open Access"] if c in dff.columns]
        st.dataframe(dff[cols].dropna(how="all"), use_container_width=True, height=420)
    else:
        st.info("No hay columna de OA.")

# CITAS
with tabs[6]:
    st.subheader("Más citadas")
    if "Times Cited" in dff.columns:
        tmp = dff.copy()
        tmp["Times Cited"] = pd.to_numeric(tmp["Times Cited"], errors="coerce")
        top_cited = tmp.sort_values("Times Cited", ascending=False).head(20)
        cols_show = [c for c in ["Title", "Author Full Names", "Times Cited", "_Year", "DOI_norm"] if c in top_cited.columns]
        st.dataframe(top_cited[cols_show], use_container_width=True, height=520)
    else:
        st.info("No hay columna de citas (‘Times Cited’/‘Cited by’).")
