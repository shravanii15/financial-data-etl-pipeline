"""
catalog.py
----------
Generates docs/DATA_CATALOG.md directly from schema.py, so the documentation
of "what is each field, where did it come from, what did we do to it" can
never silently drift out of sync with the actual pipeline code -- if a
column is renamed in schema.py, the catalog regenerates with the new name
the next time this script runs.

Run: python src/catalog.py
"""

from pathlib import Path
from schema import ALL_TABLES

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"

TRANSFORM_NOTES = {
    "dim_company": [
        "Column names normalized to snake_case.",
        "`symbol` upper-cased and whitespace-stripped (join key across all three tables).",
        "`date_added` parsed from free-text into an ISO date; unparseable values become null rather than a pipeline failure.",
        "`cik` normalized to a 10-digit zero-padded string (SEC's own convention) -- keeping it numeric would silently drop leading zeros.",
        "Exact duplicate `symbol` rows collapsed, keeping the first occurrence.",
    ],
    "fact_company_financials": [
        "Column names normalized to snake_case (e.g. `Price/Earnings` -> `pe_ratio`).",
        "All ratio/dollar fields coerced to numeric; values that don't parse become null (logged, not dropped).",
        "Negative `pe_ratio` values set to null: a P/E ratio can't be meaningfully negative -- the source encodes 'earnings were negative, ratio undefined' this way, so we normalize it to an explicit null instead of a misleading negative number.",
        "Exact duplicate `symbol` rows collapsed, keeping the first occurrence.",
    ],
    "fact_market_volatility": [
        "Column names normalized to snake_case.",
        "`date` parsed to an ISO date; rows with an unparseable date are dropped (can't anchor a time series without a date).",
        "Duplicate dates collapsed, keeping the last occurrence (assumed to be the most recently corrected value).",
        "Sorted ascending by date so downstream rolling-window anomaly detection is well-defined.",
    ],
}


def render_table_section(table) -> str:
    lines = [f"## `{table.name}`", "", table.description, "",
             f"**Primary key:** `{table.primary_key}`", "",
             f"**Source:** {table.source_file}", "",
             f"**Source description:** {table.source_description}", "", "### Columns", "",
             "| Column | Type | Nullable | Description |",
             "|---|---|---|---|"]
    for col in table.columns:
        lines.append(f"| `{col.name}` | {col.dtype} | {'yes' if col.nullable else 'no'} | {col.description} |")

    lines += ["", "### Transformations applied (extract -> transform)", ""]
    for note in TRANSFORM_NOTES.get(table.name, []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def generate() -> str:
    header = """# Data Catalog & Lineage

This document is auto-generated from `src/schema.py` and `src/catalog.py` --
regenerate it any time the schema or transform logic changes by running
`python src/catalog.py`, so the docs never drift out of sync with the code.

Every table below traces back to a real, publicly available source (no
synthetic or fabricated data). The transformation notes describe every
judgment call the pipeline makes, not just the mechanical renames.

---

"""
    sections = [render_table_section(t) for t in ALL_TABLES]
    lineage = """
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
"""
    return header + "\n".join(sections) + lineage


if __name__ == "__main__":
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    content = generate()
    out_path = DOCS_DIR / "DATA_CATALOG.md"
    out_path.write_text(content)
    print(f"Wrote {out_path}")
