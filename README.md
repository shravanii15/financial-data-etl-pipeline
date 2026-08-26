# Financial Data ETL & Governance Pipeline

A small end-to-end data pipeline: pull real public financial data, clean it
into a proper schema, validate it, flag anomalies, load it into a warehouse,
and document exactly where every field came from and what happened to it
along the way.

## Why I built this

I was applying to data roles at firms that manage private-company capital
(private equity and private credit), and wanted to actually understand how
a team like that evaluates and monitors the companies it invests in, rather
than just describe skills on a resume. Public company financials and market
data are messy in the same ways the private-company data those teams work
with is: inconsistent fields, snapshots that fall out of sync, values that
look fine individually but don't hold up under a second glance. So this
became a genuine exercise in finding and handling that mess, not a toy
dataset built to look impressive.

The most interesting part wasn't writing the ETL script. It was the data
quality pass. Running the validation checks turned up a real issue I didn't
expect: 40 of the 503 tickers in the company financials snapshot don't
appear in the constituent list snapshot at all. Both are legitimate,
actively maintained public S&P 500 datasets, but they were captured at
slightly different points in time, and the index's membership changed in
between (a company got added or dropped), so the two "reference" sources
drifted out of sync with each other. That's exactly the kind of silent data
governance problem a validation layer is supposed to catch before it
reaches anyone making a decision off the numbers, and it's a more honest
example of why data governance matters than anything I could have staged
on purpose.

## What this project actually does

1. **Extract**: pulls three real, public datasets (see Data Catalog below).
2. **Transform**: cleans and reshapes each into a proper schema: consistent
   column names, correct types, documented handling of nulls and bad values.
3. **Validate**: runs a small, reusable data quality framework (null checks,
   uniqueness, range checks, referential integrity between tables) and
   produces a pass/fail report.
4. **Detect anomalies**: flags statistical outliers in company valuation
   ratios and market volatility spikes, using a generic z-score / rolling
   z-score approach that isn't hardcoded to this dataset.
5. **Load**: writes the cleaned tables into a real embedded SQL warehouse
   (DuckDB) by default, so anyone can clone this and run it with zero setup.
   A BigQuery loader is included and just needs credentials; swap the last
   step and everything upstream stays identical.
6. **Document**: auto-generates a data catalog and lineage doc directly
   from the schema/transform code, so the docs can't silently drift out of
   sync with what the pipeline actually does.
7. **Report**: builds a single HTML dashboard summarizing the run: which
   checks passed, what got flagged, and why.

## Data sources (all real, all public)

| Dataset | What it is | Source |
|---|---|---|
| S&P 500 constituents | Company identity + sector classification | [github.com/datasets/s-and-p-500-companies](https://github.com/datasets/s-and-p-500-companies) |
| S&P 500 financials snapshot | Valuation/profitability metrics per company | [github.com/datasets/s-and-p-500-companies-financials](https://github.com/datasets/s-and-p-500-companies-financials) |
| CBOE VIX daily history | Market volatility index, 1990-present | [github.com/datasets/finance-vix](https://github.com/datasets/finance-vix) |

Full field-by-field lineage and every cleaning decision is documented in
[`docs/DATA_CATALOG.md`](docs/DATA_CATALOG.md), auto-generated from the
schema and transform code rather than hand-written separately.

## Project structure

```
src/
  schema.py       target schema definitions (single source of truth)
  extract.py      raw CSV extraction, no cleaning
  transform.py    cleaning + reshaping into the target schema
  validate.py     reusable data quality check framework
  anomaly.py      reusable anomaly detection (z-score, rolling z-score)
  load.py         loads into DuckDB (default) or BigQuery (optional)
  catalog.py       generates docs/DATA_CATALOG.md from schema.py
  pipeline.py       orchestrates the full run
dashboard/
  generate_report.py   builds data/processed/report.html
docs/
  DATA_CATALOG.md       auto-generated lineage + schema doc
tests/
  test_validate.py
  test_anomaly.py
data/
  raw/          source CSVs, committed so the repo runs standalone
  processed/    pipeline output (warehouse, cleaned CSVs, report); gitignored
```

## Running it

```bash
pip install -r requirements.txt

python src/pipeline.py              # runs the full pipeline
python dashboard/generate_report.py # builds data/processed/report.html
python -m pytest tests/ -q          # 8 tests covering validate.py + anomaly.py
```

Open `data/processed/report.html` in a browser to see the run summary.
Query the warehouse directly with:

```python
from src.load import query
query("SELECT * FROM fact_company_financials WHERE pe_ratio > 100")
```

### Optional: load into BigQuery instead of DuckDB

```bash
pip install google-cloud-bigquery
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export BIGQUERY_PROJECT=your-gcp-project-id
python -c "from src.load import load_to_bigquery; from src.pipeline import *; \
  raw = extract_all(); t = transform_all(raw); \
  load_to_bigquery({'dim_company': t['companies'], 'fact_company_financials': t['financials'], 'fact_market_volatility': t['volatility']})"
```

## What a real run found

From an actual run of this pipeline (see `data/processed/run_report.json`
after running it yourself):

- **13 validation checks, 11 passed, 2 failed.** Both failures are real
  data issues, not test artifacts: 2 rows with an out-of-range P/E ratio,
  and the 40-ticker referential integrity mismatch described above.
- **6 P/E ratio outliers and 3 price-to-book outliers** flagged by the
  anomaly detector: statistically unusual valuation multiples worth a
  second look before relying on them.
- **22 VIX volatility spikes** flagged across 35+ years of daily data:
  days where market volatility moved far more than recent history would
  predict.

## Notes on scope

This was built over a couple of days as a focused project, not a production
system. There's plenty that would change for a real deployment: incremental
loads instead of full-refresh, a real orchestrator instead of a single
script, alerting on validation failures, and so on. The parts I did
prioritize getting right are the parts that seemed to matter most: a schema
that's actually documented, validation that catches real problems, and
lineage that explains *why*, not just *what*.
