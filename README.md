# Dashboard Cienciométrico — CAS-UDD

Este repositorio desarrolla un **dashboard bibliométrico** para analizar la producción científica de la Facultad de Medicina Clínica Alemana – Universidad del Desarrollo (CAS–UDD).

## 🚀 Cómo ejecutarlo localmente

Clonar el repositorio y ejecutar:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📊 Funcionalidades principales
- Carga de dataset consolidado enriquecido (Excel).
- Visualización de publicaciones por año, departamento y cuartil.
- Gráficos interactivos (Plotly, Matplotlib).
- Descarga de tablas y figuras.

## 🌐 Despliegue online
Este proyecto puede desplegarse fácilmente en **Streamlit Community Cloud**:

1. Subir el repositorio a GitHub.
2. En [Streamlit Cloud](https://share.streamlit.io), seleccionar este repositorio.
3. Indicar como archivo principal: `app.py`.
4. ¡Listo! Obtendrás un enlace público con el dashboard.
