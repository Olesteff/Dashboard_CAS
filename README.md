# Bibliometric Pipeline & Dashboard — CAS-UDD

A reproducible, open-source bibliometric pipeline for research institutions without access to commercial APIs. Integrates **Scopus**, **Web of Science**, and **PubMed** into a unified dataset with automatic departmental attribution and an interactive Streamlit dashboard.

**Case study:** Facultad de Medicina Clínica Alemana – Universidad del Desarrollo (CAS-UDD), Santiago, Chile.

---

## Why this project

Most university hospitals in Latin America lack access to Scopus or Web of Science APIs (SciVal, InCites). This pipeline demonstrates that a fully functional institutional bibliometric system can be built using:

- Manual exports from Scopus and WoS (standard institutional subscriptions)
- PubMed as a free complementary source
- Open-source Python tools only

The result is a dataset of **6,526 unique publications** with metrics including JIF, quartile (JCR/Scimago), open access status, and departmental attribution — at zero additional infrastructure cost.

---

## Features

- **Multi-source integration**: Scopus → WoS → PubMed (priority-based deduplication)
- **Three-pass deduplication**: by DOI/PMID/EID/UT, normalized title+year, and WoS no-DOI pairs
- **Departmental attribution**: 6-layer inference (declared → author history → Scopus ID → co-authors → WoS addresses → MMCAS roster)
- **JCR/Scimago enrichment**: journal impact factor and quartile via InCites and Scimago exports
- **Interactive dashboard**: analytical modules covering publications, quartiles, open access, departments, journals, authors, collaboration, topics, word cloud, and citations
- **HTML report export**: standalone file with all charts, no server needed

---

## Dataset composition (CAS-UDD case)

| Source | Papers | Role |
|--------|--------|------|
| Scopus | 5,324 | Primary source |
| WoS | 1,093 | Complementary |
| PubMed | 109 | Complementary |
| **Total unique** | **6,526** | After three-pass deduplication |

---

## Repository structure

```
├── pipeline_cas_udd_v4_4.ipynb   # Main pipeline notebook
├── app.py                         # Streamlit dashboard
├── requirements.txt               # Python dependencies
├── MMCAS.xlsx                     # Institutional staff roster
├── data/
│   └── (input files — not included, see Data section below)
└── README.md
```

---

## Input files required

| File | Source | Format |
|------|--------|--------|
| `scopus.xlsx` | Scopus export | Excel |
| `wos*.xlsx` | Web of Science export(s) | Excel |
| `pubmed.xlsx` | PubMed export | Excel |
| `Incites.xlsx` | Clarivate InCites | Excel |
| `scimago.xlsx` | Scimago Journal Rank | Excel |
| `MMCAS.xlsx` | Institutional staff roster | Excel |

---

## Quickstart

```bash
git clone https://github.com/Olesteff/Dashboard_CAS
cd Dashboard_CAS
pip install -r requirements.txt
```

1. Place your input files in the project directory
2. Open `pipeline_cas_udd_v4_4.ipynb` in Jupyter and run all cells
3. Launch the dashboard:

```bash
streamlit run app.py
```

---

## Adapting to your institution

This pipeline is designed to be transferable. The only institution-specific components are:

- The staff roster file (MMCAS.xlsx) for departmental attribution
- The keyword lists for department name normalization

Everything else works with standard Scopus/WoS/PubMed exports.

---

## Requirements

```
pandas
numpy
openpyxl
requests
streamlit
plotly
unidecode
wordcloud
matplotlib
```

---

## Citation

If you use this pipeline in your research, please cite:

> [Author(s)]. (2025). *A reproducible multi-source bibliometric pipeline for research institutions*. [Journal TBD].

---

## License

MIT License — free to use, modify, and distribute with attribution.

---

## Contact

Olen Cepeda — olen.cepeda@gmail.com
