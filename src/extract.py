"""
extract.py
----------
Extract step: reads the raw source CSVs exactly as downloaded, with zero
cleaning. The point of keeping this step separate from transform.py is that
extract should be dumb and traceable -- if a downstream number ever looks
wrong, you should be able to point at the exact raw row it came from.

Sources (all real, public data -- see docs/DATA_CATALOG.md for full lineage):
  - S&P 500 constituent list       (github.com/datasets/s-and-p-500-companies)
  - S&P 500 fundamentals snapshot  (github.com/datasets/s-and-p-500-companies-financials)
  - CBOE VIX daily history         (github.com/datasets/finance-vix)
"""

import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def extract_companies() -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / "sp500_companies.csv")


def extract_financials() -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / "sp500_financials.csv")


def extract_volatility() -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / "vix_daily.csv")


def extract_all() -> dict:
    return {
        "companies": extract_companies(),
        "financials": extract_financials(),
        "volatility": extract_volatility(),
    }


if __name__ == "__main__":
    data = extract_all()
    for name, df in data.items():
        print(f"{name}: {len(df)} rows, {len(df.columns)} columns")
