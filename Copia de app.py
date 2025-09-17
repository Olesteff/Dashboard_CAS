import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# =========================
# 📥 Funciones auxiliares
# =========================
@st.cache_data
def load_default_data():
    file_path = "dataset_unificado_enriquecido_jcr_PLUS.xlsx"
    return pd.read_excel(file_path)

def normalize_years(df):
    if "Year_clean" in df.columns:
        df["Año"] = pd.to_numeric(df["Year_clean"], errors="coerce").astype("Int64")
    elif "Year" in df.columns:
        df["Año"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["Año"])
    return df

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos_filtrados")
    return output.getvalue()

# =========================
# 📂 Importación de dataset
# =========================
st.sidebar.header("Carga de datos")
uploaded_file = st.sidebar.file_uploader("📂 Subir dataset (Excel o CSV)", type=["xlsx", "csv"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
else:
    st.sidebar.info("Usando dataset por defecto")
    df = load_default_data()

df = normalize_years(df)

# =========================
# 🎛️ Filtros en sidebar
# =========================
st.sidebar.header("Filtros")

# --- Filtro de años con slider ---
min_year = int(df["Año"].min())
max_year = int(df["Año"].max())
year_range = st.sidebar.slider(
    "Selecciona rango de años",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
    step=1
)
df = df[(df["Año"] >= year_range[0]) & (df["Año"] <= year_range[1])]

# --- Filtro Open Access ---
oa_filter = st.sidebar.radio("Open Access", ["Todos", "Open Access", "Closed Access"])
if oa_filter == "Open Access":
    df = df[df["OpenAccess_flag"] == True]
elif oa_filter == "Closed Access":
    df = df[df["OpenAccess_flag"] == False]

# --- Filtro de cuartil JCR ---
quartile_col = None
for cand in ["JCR_Quartile", "JIF Quartile", "Quartile", "Quartil", "Quartile JCR"]:
    if cand in df.columns:
        quartile_col = cand
        break

if quartile_col:
    quartiles = df[quartile_col].dropna().unique().tolist()
    selected_quartiles = st.sidebar.multiselect("Cuartil JCR", options=quartiles, default=quartiles)
    if selected_quartiles:
        df = df[df[quartile_col].isin(selected_quartiles)]

# =========================
# 💾 Descarga de datos
# =========================
st.sidebar.subheader("Descargar datos filtrados")
csv_data = df.to_csv(index=False).encode("utf-8")
excel_data = to_excel(df)

st.sidebar.download_button(
    label="⬇️ Descargar CSV",
    data=csv_data,
    file_name="dataset_filtrado.csv",
    mime="text/csv"
)

st.sidebar.download_button(
    label="⬇️ Descargar Excel",
    data=excel_data,
    file_name="dataset_filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# =========================
# 📊 Dashboard
# =========================
st.title("📊 Dashboard Producción Científica CAS-UDD")

tabs = ["📊 Producción", "📈 Impacto", "🔓 Open Access"]
dept_col = None
for cand in ["Departamento", "Department", "Dept", "Main Department"]:
    if cand in df.columns:
        dept_col = cand
        break
if dept_col:
    tabs.append("🏥 Departamentos")

tab1, tab2, tab3, *tab4 = st.tabs(tabs)

# --- Producción ---
with tab1:
    st.subheader("📊 Producción científica")
    pubs_per_year = df.groupby("Año").size().reset_index(name="N° Publicaciones")
    fig_pub_year = px.bar(
        pubs_per_year,
        x="Año",
        y="N° Publicaciones",
        title="📈 Publicaciones por año"
    )
    st.plotly_chart(fig_pub_year, use_container_width=True)

# --- Impacto ---
with tab2:
    st.subheader("📈 Impacto de las publicaciones")

    if "Journal Impact Factor" in df.columns:
        jif_year = df.groupby("Año")["Journal Impact Factor"].mean().reset_index()
        fig_jif = px.line(
            jif_year,
            x="Año",
            y="Journal Impact Factor",
            title="📈 Promedio JIF por año"
        )
        st.plotly_chart(fig_jif, use_container_width=True)

        if "Source title" in df.columns:
            jif_journals = df.groupby("Source title")["Journal Impact Factor"].mean().reset_index()
            top_jif = jif_journals.sort_values(by="Journal Impact Factor", ascending=False).head(10)
            fig_top_jif = px.bar(
                top_jif,
                x="Source title",
                y="Journal Impact Factor",
                title="🔝 Top 10 Revistas por JIF promedio",
                text="Journal Impact Factor"
            )
            fig_top_jif.update_traces(textposition="outside")
            st.plotly_chart(fig_top_jif, use_container_width=True)

# --- Open Access ---
with tab3:
    st.subheader("🔓 Open Access")

    if "OpenAccess_flag" in df.columns:
        oa_trend = df.groupby("Año")["OpenAccess_flag"].mean().reset_index()
        oa_trend["OpenAccess_flag"] *= 100
        fig_oa = px.line(
            oa_trend,
            x="Año",
            y="OpenAccess_flag",
            title="📈 Evolución de % OA por año"
        )
        fig_oa.update_traces(mode="lines+markers")
        st.plotly_chart(fig_oa, use_container_width=True)

    if "OpenAccess_flag" in df.columns and quartile_col:
        oa_quartile = df.groupby(quartile_col)["OpenAccess_flag"].mean().reset_index()
        oa_quartile["OpenAccess_flag"] *= 100
        fig_oa_q = px.bar(
            oa_quartile,
            x=quartile_col,
            y="OpenAccess_flag",
            title="📊 % OA por cuartil JCR",
            text="OpenAccess_flag"
        )
        fig_oa_q.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig_oa_q, use_container_width=True)

# --- Departamentos (si existe la columna) ---
if dept_col:
    with tab4[0]:
        st.subheader("🏥 Publicaciones por Departamento")
        dept_counts = df[dept_col].value_counts().reset_index()
        dept_counts.columns = ["Departamento", "N° Publicaciones"]
        fig_dept = px.bar(
            dept_counts.head(15),
            x="N° Publicaciones",
            y="Departamento",
            orientation="h",
            title="🏥 Top 15 Departamentos por publicaciones"
        )
        st.plotly_chart(fig_dept, use_container_width=True)
        st.dataframe(dept_counts)