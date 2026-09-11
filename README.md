# Nifty 100 Financial Intelligence Platform

Production-grade financial analytics platform covering 92 Nifty 100 companies:
ETL pipeline, 50+ KPI ratio engine, investment screener, peer comparison,
Streamlit dashboard, valuation module, NLP intelligence, automated PDF
reporting, KMeans clustering and a 16-endpoint REST API.

Built over 45 days / 6 sprints per the Data Analytics Division execution plan
(DAD-PROJ-001 v1.0).

## Highlights

- 12 source datasets (7 core + 5 supplementary) loaded into a 10-table SQLite warehouse
- 16 data-quality rules enforced at load time (CRITICAL halts, WARNING flags)
- 50+ computed KPIs with documented edge-case handling (negative equity, debt-free ICR, CAGR turnarounds, bank carve-outs)
- 6 preset screeners + 15 configurable filters via `config/screener_config.yaml`
- Peer percentile rankings for 11 peer groups across 10 metrics
- 8-screen interactive Streamlit dashboard
- 92 company tearsheets, 10 sector reports, 1 portfolio summary (ReportLab)
- Rule-based NLP pros/cons for all 92 companies with confidence scores
- Cash-flow intelligence: CFO quality, CapEx intensity, distress and deleveraging flags
- KMeans (k=5) company archetypes with elbow validation
- FastAPI REST service with OpenAPI export

## Tech Stack

| Layer | Technology |
| --- | --- |
| Data | pandas, NumPy, openpyxl |
| Storage | SQLite 3.x |
| Analytics | scipy, scikit-learn |
| Visualisation | matplotlib, Plotly, squarify, seaborn |
| Dashboard | Streamlit |
| API | FastAPI, Uvicorn |
| Reports | ReportLab |
| Testing | pytest, pytest-cov, pytest-html |
| Quality | black, ruff |

## Quick Start

Requirements: Python 3.12+, `uv` and `pip`.

```bash
uv venv
uv sync

make load
make ratios
make test
```

## Makefile Targets

| Target | Purpose |
| --- | --- |
| `make load` | Idempotent full ETL load of all 12 source files |
| `make ratios` | Recompute all KPIs into `financial_ratios` |
| `make test` | Run pytest suite, emit `reports/pytest_report.html` |
| `make report` | Generate tearsheets, sector and portfolio PDFs |
| `make dashboard` | Start Streamlit on port 8501 |
| `make api` | Start FastAPI/Uvicorn on port 5000 |
| `make clean` | Remove caches and test artifacts (keeps the database) |

## Running the Dashboard

```bash
streamlit run src/dashboard/app.py --server.port 8501
```

Screens: Home, Company Profile, Financial Screener, Peer Comparison,
Trend Analysis, Sector Analysis, Capital Allocation Map, Annual Reports.
All database access is cached with `@st.cache_data(ttl=600)`.

## Running the API

```bash
uvicorn src.api.main:app --host 127.0.0.1 --port 5000
```

Interactive OpenAPI docs: `http://localhost:5000/docs`
Exported spec: `docs/openapi.json`

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/health` | Status, per-table row counts, uptime |
| `GET /api/v1/companies` | List companies (sector / search filters) |
| `GET /api/v1/companies/{ticker}` | Full profile + latest KPIs (404 if unknown) |
| `GET /api/v1/companies/{ticker}/pl` | P&L history with year filters |
| `GET /api/v1/companies/{ticker}/bs` | Balance sheet history |
| `GET /api/v1/companies/{ticker}/cashflow` | Cash flow history |
| `GET /api/v1/companies/{ticker}/ratios` | All computed KPIs per year |
| `GET /api/v1/companies/{ticker}/tearsheet` | Binary PDF download |
| `GET /api/v1/screener` | Threshold screening (400 on bad params) |
| `GET /api/v1/sectors` | Sector list with median KPIs |
| `GET /api/v1/sectors/{sector}/companies` | Companies in a sector |
| `GET /api/v1/peers/{group_name}` | Peer percentile ranks |
| `GET /api/v1/companies/{ticker}/peers/compare` | Radar comparison data |
| `GET /api/v1/market-cap/{ticker}` | Historical valuation multiples |
| `GET /api/v1/portfolio/stats` | P10-P90 distribution table |
| `GET /api/v1/companies/{ticker}/documents` | Annual report links |

## Generating Reports

```bash
python -m src.reports.tearsheet
python -m src.reports.sector_report
python -m src.reports.portfolio_report
python -m src.reports.radar
```

## Intelligence Modules

```bash
python -m src.nlp.parser
python -m src.nlp.pros_cons_generator
python -m src.analytics.cashflow_intelligence
python -m src.analytics.capital_allocation_report
python -m src.analytics.clustering
python -m src.analytics.cluster_profiling
python -m src.analytics.valuation
```

## Testing & Quality Gates

```bash
pytest tests/ -q --html=reports/pytest_report.html --self-contained-html
black src/ tests/
ruff check src/ tests/
```

- 184 tests, 0 failures (ETL, KPI, DQ, NLP, reports, screener, API, dashboard)
- Suite runtime under 15 s; HTML report archived in `reports/`
- Formatting: black (line length 88); linting: ruff with a per-file ignore for
  the Streamlit page-naming convention (`N999`)

## Repository Layout

| Path | Contents |
| --- | --- |
| `data/raw/`, `data/supporting/` | Source Excel files (read-only) |
| `data/nifty100.db` | SQLite warehouse (10 tables) |
| `src/etl/` | loader, normaliser, validator |
| `src/analytics/` | ratios, cagr, cashflow, peer, valuation, clustering |
| `src/screener/` | filter engine, composite score, Excel export |
| `src/nlp/` | analysis parser, pros/cons generator |
| `src/reports/` | tearsheet, sector, portfolio, radar generators |
| `src/dashboard/` | Streamlit app (8 screens) |
| `src/api/` | FastAPI app + routers |
| `tests/` | pytest suite mirroring `src/` |
| `config/` | screener_config.yaml, ratio_config.yaml |
| `output/` | CSV/Excel deliverables + final archive |
| `reports/` | PDFs, radar PNGs, heatmap, elbow plot, pytest HTML |
| `docs/` | analyst guide, acceptance checklist, retros, openapi.json |

## Known Data Notes

- `sectors.xlsx` delivers 10 broad sectors; the plan table lists 11
  (Conglomerates folded into other sectors). All sector outputs are
  data-driven: 10 sector PDFs.
- Tearsheets: 91 generated; JIOFIN skipped (fewer than 3 years of history)
  and logged in `output/skipped_tearsheets.csv` per the Day-34 rule.
- Financials carve-out: D/E warnings and ICR thresholds treat banks and NBFCs
  separately; debt-free companies display ICR as "Debt Free".
- `stock_prices` and `market_cap` are simulated datasets and are labelled as
  such in the dashboard.

## Final Deliverables Archive

`output/final_deliverables/` contains all 23 signed-off deliverables
(219 files): database, audits, Excel workbooks, CSVs, 91 tearsheets,
sector and portfolio PDFs, radar charts, OpenAPI spec, analyst guide,
acceptance checklist and pytest report.


