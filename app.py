import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# =========================
# Funciones de utilidad
# =========================
def load_data(file):
    df = pd.read_excel(file) if file.name.endswith("xlsx") else pd.read_csv(file)
    return df

def detect_department(aff: str) -> str:
    """Detecta el departamento a partir de texto en Affiliations/Authors with affiliations"""
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

# =========================
# Interfaz
# =========================
st.set_page_config(page_title="Dashboard CAS-UDD", layout="wide")
st.title("📊 Dashboard de Producción Científica Clínica Alemana – Universidad del Desarrollo")

uploaded_file = st.sidebar.file_uploader("Sube un XLSX", type=["xlsx", "csv"])
if uploaded_file:
    df = load_data(uploaded_file)

    # Normalización de columnas
    if "Year" not in df.columns:
        df["Year"] = pd.to_datetime(df["Date"], errors="coerce").dt.year

    if "OpenAccess_flag" not in df.columns:
        df["OpenAccess_flag"] = False

    if "Journal Impact Factor" not in df.columns:
        df["Journal Impact Factor"] = np.nan

    if "JCR_Quartile" not in df.columns:
        df["JCR_Quartile"] = "Sin cuartil"

    if "Clinical Trial" not in df.columns:
        df["Clinical Trial"] = False

    # Detectar departamento dinámicamente
    aff_col = None
    for cand in ["Authors with affiliations","Author Affiliations","Affiliations"]:
        if cand in df.columns:
            aff_col = cand
            break
    if aff_col:
        df["Departamento_detectado"] = df[aff_col].map(detect_department)
    else:
        df["Departamento_detectado"] = "Sin asignar"

    # =========================
    # KPIs
    # =========================
    total_pubs = len(df)
    open_pubs = df["OpenAccess_flag"].sum()
    pct_open = (open_pubs / total_pubs * 100) if total_pubs > 0 else 0
    suma_jif = df["Journal Impact Factor"].fillna(0).sum()
    ensayos = df["Clinical Trial"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total publicaciones", total_pubs)
    c2.metric("% Open Access", f"{pct_open:.1f}%")
    c3.metric("⭐ Suma total JIF", f"{suma_jif:,.1f}")
    c4.metric("🧪 Ensayos clínicos", ensayos)

    # =========================
    # Tabs
    # =========================
    tabs = st.tabs(["📈 Publicaciones", "📊 Cuartiles", "🔓 Open Access",
                    "🏥 Departamentos", "📚 Revistas"])

    # --- Publicaciones
    with tabs[0]:
        pubs_per_year = df.groupby("Year").size().reset_index(name="Publicaciones")
        fig = px.bar(pubs_per_year, x="Year", y="Publicaciones", title="Publicaciones por año")
        st.plotly_chart(fig, use_container_width=True)

    # --- Cuartiles
    with tabs[1]:
        qdist = df["JCR_Quartile"].value_counts().reset_index()
        qdist.columns = ["Cuartil","Publicaciones"]
        fig = px.pie(qdist, names="Cuartil", values="Publicaciones", hole=0.4,
                     title="Distribución por cuartil")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(qdist)

    # --- Open Access
    with tabs[2]:
        oa_dist = df["OpenAccess_flag"].value_counts().rename({True:"Open Access",False:"Closed Access"}).reset_index()
        oa_dist.columns = ["Tipo","Publicaciones"]
        fig = px.pie(oa_dist, names="Tipo", values="Publicaciones", hole=0.4,
                     title="Distribución Open Access")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(oa_dist)

    # --- Departamentos
    with tabs[3]:
        dep_dist = df["Departamento_detectado"].value_counts().reset_index()
        dep_dist.columns = ["Departamento","Publicaciones"]
        fig = px.bar(dep_dist, x="Departamento", y="Publicaciones", title="Distribución por departamento")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dep_dist)

    # --- Revistas
    with tabs[4]:
        if "Source title" in df.columns:
            rev_dist = df["Source title"].value_counts().head(20).reset_index()
            rev_dist.columns = ["Revista","Publicaciones"]
            fig = px.bar(rev_dist, x="Revista", y="Publicaciones", title="Top 20 Revistas")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(rev_dist)
        else:
            st.info("No se encontró la columna 'Source title'.")