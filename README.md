# Bibliometric Pipeline & Dashboard — CAS-UDD

A reproducible, open-source bibliometric pipeline for research institutions without access to commercial APIs. Integrates **Scopus**, **Web of Science**, **PubMed**, and **OpenAlex** into a unified dataset with automatic departmental attribution and an interactive Streamlit dashboard.

**Case study:** Facultad de Medicina Clínica Alemana – Universidad del Desarrollo (CAS-UDD), Santiago, Chile.

---

## Why this project

Most university hospitals in Latin America lack access to Scopus or Web of Science APIs (SciVal, InCites). This pipeline demonstrates that a fully functional institutional bibliometric system can be built using:

- Manual exports from Scopus and WoS (standard institutional subscriptions)
- **OpenAlex** as a free, open API source (no subscription required)
- Open-source Python tools only

The result is a dataset of **7,977 unique publications** with metrics including FWCI, JIF, quartile, open access status, and departmental attribution — at zero additional infrastructure cost.

---

## Features

- **Multi-source integration**: Scopus → WoS → OpenAlex → PubMed (priority-based deduplication)
- **Incremental WoS loading**: base file + glob pattern for quarterly updates
- **OpenAlex API harvesting**: cursor pagination, local JSONL cache, `type=article` filter
- **FWCI propagation**: Field-Weighted Citation Impact from OpenAlex cross-joined to all sources by DOI
- **Departmental attribution**: 6-layer inference (declared → author history → Scopus ID → co-authors → WoS addresses → MMCAS roster)
- **JCR/Scimago enrichment**: journal impact factor and quartile via InCites and Scimago exports
- **Interactive dashboard**: 10 analytical modules (publications, quartiles, open access, departments, journals, authors, collaboration, topics, word cloud, citations)
- **HTML report export**: standalone file with all charts, no server needed

---

## Dataset composition (CAS-UDD case)

| Source | Papers | Role |
|--------|--------|------|
| Scopus | 5,252 | Primary source |
| OpenAlex | 1,584 | Additional (pre-2005 Chilean journals not in Scopus) |
| WoS | 1,085 | Complementary |
| PubMed | 55 | Complementary |
| **Total unique** | **7,977** | After DOI-based deduplication |

---

## Repository structure

```
├── pipeline_CAS_v2-2.ipynb     # Main pipeline notebook
├── app-2.py                    # Streamlit dashboard
├── requirements.txt            # Python dependencies
├── data/
│   └── (input files — not included, see Data section below)
└── README.md
```

---

## Input files required

| File | Source | Format |
|------|--------|--------|
| `scopus.xlsx` | Scopus export | Excel |
| `wos.xlsx` | Web of Science export | Excel |
| `pubmed.xlsx` | PubMed export | Excel |
| `Incites.xlsx` | Clarivate InCites | Excel |
| `Incites_Medicina.xlsx` | Clarivate InCites | Excel |
| `scimago.xlsx` | Scimago Journal Rank | Excel |
| `MMCAS.xlsx` | Institutional staff roster | Excel |

OpenAlex data is harvested automatically via API using the institution's **ROR ID** (CAS-UDD: `028ynny55`). Results are cached locally in `openalex.jsonl`.

---

## Quickstart

```bash
git clone https://github.com/Olesteff/Dashboard_CAS
cd cas-udd-bibliometrics
pip install -r requirements.txt
```

1. Place your input files in the project directory
2. Open `pipeline_CAS_v2-2.ipynb` in Jupyter and run all cells
3. Launch the dashboard:

```bash
streamlit run app-2.py
```

To use with a different institution, change the ROR ID in the pipeline config cell:

```python
OPENALEX_ROR = 'YOUR_ROR_ID'   # find yours at https://ror.org
```

---

## Adapting to your institution

This pipeline is designed to be transferable. The only institution-specific components are:

- The ROR ID (OpenAlex filter)
- The staff roster file (MMCAS.xlsx) for departmental attribution
- The keyword lists for department name normalization

Everything else works with standard Scopus/WoS exports.

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

> [Author(s)]. (2025). *A reproducible multi-source bibliometric pipeline for research institutions using OpenAlex*. [Journal TBD].

---

## License

MIT License — free to use, modify, and distribute with attribution.

---

## Contact

Olen Cepeda — olen.cepeda@gmail.com
