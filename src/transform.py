"""
transform.py
------------
Transform step: renames/casts raw columns into the target schema defined in
schema.py, and applies the specific cleaning decisions this pipeline makes.
Every cleaning decision is commented with WHY, because that reasoning is
exactly what gets pulled into docs/DATA_CATALOG.md (lineage should explain
judgment calls, not just list column names).
"""

import pandas as pd
import numpy as np


def transform_companies(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(
        columns={
            "Symbol": "symbol",
            "Security": "security_name",
            "GICS Sector": "gics_sector",
            "GICS Sub-Industry": "gics_sub_industry",
            "Headquarters Location": "hq_location",
            "Date added": "date_added",
            "CIK": "cik",
            "Founded": "founded",
        }
    ).copy()

    df["symbol"] = df["symbol"].str.strip().str.upper()
    df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce").dt.date
    # CIK is a SEC filer ID, not a number to do math on -- keep as a zero-padded
    # string (SEC's own convention is 10 digits) so leading zeros aren't lost.
    df["cik"] = df["cik"].astype(str).str.extract(r"(\d+)")[0].str.zfill(10)
    df["founded"] = df["founded"].astype(str).str.strip()

    df = df.drop_duplicates(subset="symbol", keep="first")
    return df[["symbol", "security_name", "gics_sector", "gics_sub_industry",
               "hq_location", "date_added", "cik", "founded"]]


def transform_financials(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(
        columns={
            "Symbol": "symbol",
            "Price": "price",
            "Price/Earnings": "pe_ratio",
            "Dividend Yield": "dividend_yield",
            "Earnings/Share": "eps",
            "52 Week Low": "week52_low",
            "52 Week High": "week52_high",
            "Market Cap": "market_cap",
            "EBITDA": "ebitda",
            "Price/Sales": "price_to_sales",
            "Price/Book": "price_to_book",
            "SEC Filings": "sec_filings_url",
        }
    ).copy()

    df["symbol"] = df["symbol"].str.strip().str.upper()

    numeric_cols = [
        "price", "pe_ratio", "dividend_yield", "eps", "week52_low",
        "week52_high", "market_cap", "ebitda", "price_to_sales", "price_to_book",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # A P/E ratio can't be negative in any meaningful sense (negative earnings
    # make the ratio undefined, not "negative") -- source data sometimes
    # encodes that case as a negative number instead of a null. Normalize it
    # to null and let validate.py flag how many rows this affected.
    df.loc[df["pe_ratio"] < 0, "pe_ratio"] = np.nan

    df = df.drop_duplicates(subset="symbol", keep="first")
    return df[["symbol", "price", "pe_ratio", "dividend_yield", "eps",
               "week52_low", "week52_high", "market_cap", "ebitda",
               "price_to_sales", "price_to_book", "sec_filings_url"]]


def transform_volatility(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(
        columns={"DATE": "date", "OPEN": "open", "HIGH": "high", "LOW": "low", "CLOSE": "close"}
    ).copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["date"]).drop_duplicates(subset="date", keep="last")
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "open", "high", "low", "close"]]


def transform_all(raw: dict) -> dict:
    return {
        "companies": transform_companies(raw["companies"]),
        "financials": transform_financials(raw["financials"]),
        "volatility": transform_volatility(raw["volatility"]),
    }
