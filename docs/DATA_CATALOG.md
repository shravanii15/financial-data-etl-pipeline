# Data Catalog & Lineage

This document is auto-generated from `src/schema.py` and `src/catalog.py` --
regenerate it any time the schema or transform logic changes by running
`python src/catalog.py`, so the docs never drift out of sync with the code.

Every table below traces back to a real, publicly available source (no
synthetic or fabricated data). The transformation notes describe every
judgment call the pipeline makes, not just the mechanical renames.

---

## `dim_company`

Reference table of S&P 500 constituent companies: identity, sector classification, and index-membership metadata.

**Primary key:** `symbol`

**Source:** data/raw/sp500_companies.csv

**Source description:** Wikipedia's list of current S&P 500 companies, maintained as a structured CSV by the open-source 'datasets' project on GitHub (github.com/datasets/s-and-p-500-companies).

### Columns

| Column | Type | Nullable | Description |
|---|---|---|---|
| `symbol` | string | no | Stock ticker symbol. Primary key. |
| `security_name` | string | no | Full company name. |
| `gics_sector` | string | no | GICS sector classification. |
| `gics_sub_industry` | string | no | GICS sub-industry classification. |
| `hq_location` | string | yes | Headquarters city/state as filed. |
| `date_added` | date | yes | Date the company joined the S&P 500 index. |
| `cik` | string | no | SEC Central Index Key -- the company's unique SEC filer ID. |
| `founded` | string | yes | Year founded (kept as string: source mixes plain years with 'YYYY (earlier-year)' formats). |

### Transformations applied (extract -> transform)

- Column names normalized to snake_case.
- `symbol` upper-cased and whitespace-stripped (join key across all three tables).
- `date_added` parsed from free-text into an ISO date; unparseable values become null rather than a pipeline failure.
- `cik` normalized to a 10-digit zero-padded string (SEC's own convention) -- keeping it numeric would silently drop leading zeros.
- Exact duplicate `symbol` rows collapsed, keeping the first occurrence.

## `fact_company_financials`

Point-in-time snapshot of core valuation and profitability metrics for each S&P 500 constituent.

**Primary key:** `symbol`

**Source:** data/raw/sp500_financials.csv

**Source description:** Company fundamentals snapshot maintained as a structured CSV by the open-source 'datasets' project on GitHub (github.com/datasets/s-and-p-500-companies-financials), sourced from public market data providers.

### Columns

| Column | Type | Nullable | Description |
|---|---|---|---|
| `symbol` | string | no | Stock ticker symbol. Foreign key -> dim_company.symbol. |
| `price` | float | yes | Latest share price at time of snapshot (USD). |
| `pe_ratio` | float | yes | Price-to-earnings ratio. |
| `dividend_yield` | float | yes | Trailing dividend yield (decimal, e.g. 0.02 = 2%). |
| `eps` | float | yes | Trailing earnings per share (USD). |
| `week52_low` | float | yes | 52-week low share price (USD). |
| `week52_high` | float | yes | 52-week high share price (USD). |
| `market_cap` | float | yes | Market capitalization (USD). |
| `ebitda` | float | yes | Trailing EBITDA (USD). |
| `price_to_sales` | float | yes | Price-to-sales ratio. |
| `price_to_book` | float | yes | Price-to-book ratio. |
| `sec_filings_url` | string | yes | Link to the company's SEC EDGAR filing history. |

### Transformations applied (extract -> transform)

- Column names normalized to snake_case (e.g. `Price/Earnings` -> `pe_ratio`).
- All ratio/dollar fields coerced to numeric; values that don't parse become null (logged, not dropped).
- Negative `pe_ratio` values set to null: a P/E ratio can't be meaningfully negative -- the source encodes 'earnings were negative, ratio undefined' this way, so we normalize it to an explicit null instead of a misleading negative number.
- Exact duplicate `symbol` rows collapsed, keeping the first occurrence.

## `fact_market_volatility`

Daily CBOE Volatility Index (VIX) levels -- a standard proxy for market-wide risk and stress, used here as macro context alongside company-level financials (private credit/equity valuations move with broad market volatility).

**Primary key:** `date`

**Source:** data/raw/vix_daily.csv

**Source description:** CBOE VIX daily OPEN/HIGH/LOW/CLOSE, maintained as a structured CSV by the open-source 'datasets' project on GitHub (github.com/datasets/finance-vix).

### Columns

| Column | Type | Nullable | Description |
|---|---|---|---|
| `date` | date | no | Trading date. Primary key. |
| `open` | float | no | VIX index level at open. |
| `high` | float | no | VIX index level, intraday high. |
| `low` | float | no | VIX index level, intraday low. |
| `close` | float | no | VIX index level at close. |

### Transformations applied (extract -> transform)

- Column names normalized to snake_case.
- `date` parsed to an ISO date; rows with an unparseable date are dropped (can't anchor a time series without a date).
- Duplicate dates collapsed, keeping the last occurrence (assumed to be the most recently corrected value).
- Sorted ascending by date so downstream rolling-window anomaly detection is well-defined.

---

## Lineage summary (source -> warehouse)

```
data/raw/sp500_companies.csv  --[transform_companies()]-->   dim_company
data/raw/sp500_financials.csv --[transform_financials()]-->  fact_company_financials
data/raw/vix_daily.csv        --[transform_volatility()]-->  fact_market_volatility

dim_company.symbol  <---(referential integrity check)---  fact_company_financials.symbol
```

All three cleaned tables are loaded into `data/processed/warehouse.duckdb`
by `src/load.py`. The same function signature (`load_to_bigquery()` in the
same file) loads them into a BigQuery dataset instead, once cloud
credentials are configured -- the transform/validate/anomaly logic upstream
is identical either way.
