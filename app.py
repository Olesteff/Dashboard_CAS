# app.py — FIX loader XLSX (lee siempre 1ª hoja). Incluye panel de estado de carga.
# Reemplaza tu función load_dataframe por esta versión + helpers y usa el bloque "Estado de carga" tras leer df.

from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st

DEFAULT_XLSX = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
DEFAULT_SHEET = 0  # siempre 1ª hoja

# ---------- NUEVO: resolver ruta por múltiples candidatos ----------
def resolve_default_xlsx(file_name: str = DEFAULT_XLSX) -> Path | None:
    """Busca el XLSX en varias rutas típicas. Devuelve Path existente o None."""
    here = Path(__file__).resolve().parent
    candidates = [
        Path(file_name),                     # ruta relativa (repo root)
        here / file_name,                    # junto a app.py
        Path.cwd() / file_name,              # directorio de trabajo
        Path("data") / file_name,            # ./data/
        Path("datasets") / file_name,        # ./datasets/
        Path("/mnt/data") / file_name,       # entorno de contenedor
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

# ---------- NUEVO: loader robusto (1ª hoja) + estado ----------
@st.cache_data(show_spinner=False)
def load_dataframe(uploaded_file, sheet_index: int = DEFAULT_SHEET):
    """
    Lee el XLSX desde el uploader (prioridad) o desde el disco buscando la 1ª hoja.
    Retorna (df, meta) donde meta={'source','sheet','path'}.
    """
    meta = {"source": "", "sheet": "", "path": ""}
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_index, dtype=str)
        # nombre de la 1ª hoja (por si suben un libro con varias hojas)
        try:
            xls = pd.ExcelFile(uploaded_file)
            sheet_name = xls.sheet_names[sheet_index]
        except Exception:
            sheet_name = f"Sheet[{sheet_index}]"
        meta.update({"source": "upload", "sheet": sheet_name, "path": getattr(uploaded_file, "name", "")})
        return df, meta

    p = resolve_default_xlsx()
    if p is None:
        tried = [
            str(Path(DEFAULT_XLSX)),
            str(Path(__file__).resolve().parent / DEFAULT_XLSX),
            str(Path.cwd() / DEFAULT_XLSX),
            "data/" + DEFAULT_XLSX,
            "datasets/" + DEFAULT_XLSX,
            "/mnt/data/" + DEFAULT_XLSX,
        ]
        raise FileNotFoundError(
            "No se encontró el XLSX por defecto. Probé estas rutas:\n- " + "\n- ".join(tried) +
            "\nSube el archivo desde la barra lateral o colócalo junto a app.py."
        )

    # Lee siempre la 1ª hoja del archivo encontrado en disco
    df = pd.read_excel(p, sheet_name=sheet_index, dtype=str)
    try:
        xls = pd.ExcelFile(p)
        sheet_name = xls.sheet_names[sheet_index]
    except Exception:
        sheet_name = f"Sheet[{sheet_index}]"
    meta.update({"source": "disk", "sheet": sheet_name, "path": str(p)})
    return df, meta

# --------------------- EJEMPLO DE USO EN TU APP ---------------------
# En tu sidebar ya tienes:
uploaded = st.sidebar.file_uploader("Sube el XLSX (usa la 1ª hoja)", type=["xlsx"])

# Sustituye tu llamada anterior por ésta:
try:
    df, meta = load_dataframe(uploaded, sheet_index=0)  # 0 = primera hoja SIEMPRE
except Exception as e:
    st.error(str(e))
    st.stop()

# Estado de carga (mostrar arriba para confirmar)
st.caption(f"Fuente: **{meta['source']}** · Hoja: **{meta['sheet']}** · Ruta: `{meta['path']}` · "
           f"Filas: **{len(df):,}** · Columnas: **{df.shape[1]}**")

# ... A partir de aquí sigue tu pipeline normal (normalize/filters/tabs/figuras)
# df contiene ya los datos de la 1ª hoja. Ejemplo de primera vista:
st.dataframe(df.head(10), use_container_width=True)
