"""
pipeline.py
-----------
Orchestrates the full run: extract -> transform -> validate -> detect
anomalies -> load -> write a run report. This is the file to run end-to-end:

    python src/pipeline.py

Every step's output is deliberately kept as plain DataFrames passed between
functions -- easy to unit test each stage in isolation (see tests/), and
easy to swap the load target without touching anything upstream.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from extract import extract_all
from transform import transform_all
from validate import (
    check_not_null, check_unique, check_in_range,
    check_referential_integrity, check_row_count_min, summarize,
)
from anomaly import zscore_outliers, rolling_change_outliers
from load import load_to_duckdb

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def run_validation(tables: dict) -> list:
    companies, financials, volatility = tables["companies"], tables["financials"], tables["volatility"]

    results = [
        # dim_company
        check_not_null(companies, "dim_company", "symbol"),
        check_unique(companies, "dim_company", "symbol"),
        check_not_null(companies, "dim_company", "cik"),
        check_row_count_min(companies, "dim_company", 400),

        # fact_company_financials
        check_not_null(financials, "fact_company_financials", "symbol"),
        check_unique(financials, "fact_company_financials", "symbol"),
        check_in_range(financials, "fact_company_financials", "pe_ratio", min_v=0, max_v=500),
        check_in_range(financials, "fact_company_financials", "dividend_yield", min_v=0, max_v=0.25),
        check_referential_integrity(
            financials, "symbol", companies, "symbol", "fact_company_financials",
        ),

        # fact_market_volatility
        check_not_null(volatility, "fact_market_volatility", "date"),
        check_unique(volatility, "fact_market_volatility", "date"),
        check_in_range(volatility, "fact_market_volatility", "close", min_v=0, max_v=200),
        check_row_count_min(volatility, "fact_market_volatility", 1000),
    ]
    return results


def run_anomaly_detection(tables: dict) -> dict:
    financials, volatility = tables["financials"], tables["volatility"]

    pe_outliers = zscore_outliers(financials.dropna(subset=["pe_ratio"]), "pe_ratio", threshold=3.0)
    pb_outliers = zscore_outliers(financials.dropna(subset=["price_to_book"]), "price_to_book", threshold=3.0)
    vix_spikes = rolling_change_outliers(volatility, "close", "date", window=30, threshold=4.0)

    return {
        "pe_ratio_outliers": pe_outliers[["symbol", "pe_ratio", "zscore"]],
        "price_to_book_outliers": pb_outliers[["symbol", "price_to_book", "zscore"]],
        "vix_volatility_spikes": vix_spikes[["date", "close", "pct_change", "change_zscore"]],
    }


def write_run_report(validation_results: list, anomalies: dict) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = summarize(validation_results)
    summary_df.to_csv(PROCESSED_DIR / "validation_report.csv", index=False)

    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "total_checks": len(validation_results),
            "passed": int(sum(r.passed for r in validation_results)),
            "failed": int(sum(not r.passed for r in validation_results)),
        },
        "anomalies": {name: int(len(df)) for name, df in anomalies.items()},
    }
    with open(PROCESSED_DIR / "run_report.json", "w") as f:
        json.dump(report, f, indent=2)

    for name, df in anomalies.items():
        df.to_csv(PROCESSED_DIR / f"anomalies_{name}.csv", index=False)

    return report


def main():
    print("1/5  Extracting raw data...")
    raw = extract_all()

    print("2/5  Transforming into target schema...")
    tables = transform_all(raw)

    print("3/5  Running data quality checks...")
    validation_results = run_validation(tables)
    for r in validation_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"     [{status}] {r.table}.{r.column or '-'}: {r.detail}")

    print("4/5  Running anomaly detection...")
    anomalies = run_anomaly_detection(tables)
    for name, df in anomalies.items():
        print(f"     {name}: {len(df)} flagged rows")

    print("5/5  Loading cleaned tables into the warehouse (DuckDB)...")
    warehouse_tables = {
        "dim_company": tables["companies"],
        "fact_company_financials": tables["financials"],
        "fact_market_volatility": tables["volatility"],
    }
    load_to_duckdb(warehouse_tables)

    report = write_run_report(validation_results, anomalies)
    print("\nRun report:")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
