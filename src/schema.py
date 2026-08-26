"""
schema.py
---------
Defines the target (cleaned) schema for every table this pipeline produces.

Each entry describes: the column name, its expected data type, whether nulls
are allowed, and a short human-readable description. This single source of
truth is used in two places:
  1. transform.py   -> to cast/rename columns into this shape
  2. catalog.py      -> to auto-generate the data catalog doc from the same
                         definitions, so the docs can never drift out of sync
                         with the actual code.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ColumnSpec:
    name: str
    dtype: str  # "string" | "float" | "int" | "date"
    nullable: bool
    description: str


@dataclass
class TableSpec:
    name: str
    description: str
    primary_key: str
    source_file: str
    source_description: str
    columns: list = field(default_factory=list)


DIM_COMPANY = TableSpec(
    name="dim_company",
    description=(
        "Reference table of S&P 500 constituent companies: identity, sector "
        "classification, and index-membership metadata."
    ),
    primary_key="symbol",
    source_file="data/raw/sp500_companies.csv",
    source_description=(
        "Wikipedia's list of current S&P 500 companies, maintained as a "
        "structured CSV by the open-source 'datasets' project on GitHub "
        "(github.com/datasets/s-and-p-500-companies)."
    ),
    columns=[
        ColumnSpec("symbol", "string", False, "Stock ticker symbol. Primary key."),
        ColumnSpec("security_name", "string", False, "Full company name."),
        ColumnSpec("gics_sector", "string", False, "GICS sector classification."),
        ColumnSpec("gics_sub_industry", "string", False, "GICS sub-industry classification."),
        ColumnSpec("hq_location", "string", True, "Headquarters city/state as filed."),
        ColumnSpec("date_added", "date", True, "Date the company joined the S&P 500 index."),
        ColumnSpec("cik", "string", False, "SEC Central Index Key -- the company's unique SEC filer ID."),
        ColumnSpec("founded", "string", True, "Year founded (kept as string: source mixes plain years with 'YYYY (earlier-year)' formats)."),
    ],
)

FACT_COMPANY_FINANCIALS = TableSpec(
    name="fact_company_financials",
    description=(
        "Point-in-time snapshot of core valuation and profitability metrics "
        "for each S&P 500 constituent."
    ),
    primary_key="symbol",
    source_file="data/raw/sp500_financials.csv",
    source_description=(
        "Company fundamentals snapshot maintained as a structured CSV by the "
        "open-source 'datasets' project on GitHub "
        "(github.com/datasets/s-and-p-500-companies-financials), sourced "
        "from public market data providers."
    ),
    columns=[
        ColumnSpec("symbol", "string", False, "Stock ticker symbol. Foreign key -> dim_company.symbol."),
        ColumnSpec("price", "float", True, "Latest share price at time of snapshot (USD)."),
        ColumnSpec("pe_ratio", "float", True, "Price-to-earnings ratio."),
        ColumnSpec("dividend_yield", "float", True, "Trailing dividend yield (decimal, e.g. 0.02 = 2%)."),
        ColumnSpec("eps", "float", True, "Trailing earnings per share (USD)."),
        ColumnSpec("week52_low", "float", True, "52-week low share price (USD)."),
        ColumnSpec("week52_high", "float", True, "52-week high share price (USD)."),
        ColumnSpec("market_cap", "float", True, "Market capitalization (USD)."),
        ColumnSpec("ebitda", "float", True, "Trailing EBITDA (USD)."),
        ColumnSpec("price_to_sales", "float", True, "Price-to-sales ratio."),
        ColumnSpec("price_to_book", "float", True, "Price-to-book ratio."),
        ColumnSpec("sec_filings_url", "string", True, "Link to the company's SEC EDGAR filing history."),
    ],
)

FACT_MARKET_VOLATILITY = TableSpec(
    name="fact_market_volatility",
    description=(
        "Daily CBOE Volatility Index (VIX) levels -- a standard proxy for "
        "market-wide risk and stress, used here as macro context alongside "
        "company-level financials (private credit/equity valuations move "
        "with broad market volatility)."
    ),
    primary_key="date",
    source_file="data/raw/vix_daily.csv",
    source_description=(
        "CBOE VIX daily OPEN/HIGH/LOW/CLOSE, maintained as a structured CSV "
        "by the open-source 'datasets' project on GitHub "
        "(github.com/datasets/finance-vix)."
    ),
    columns=[
        ColumnSpec("date", "date", False, "Trading date. Primary key."),
        ColumnSpec("open", "float", False, "VIX index level at open."),
        ColumnSpec("high", "float", False, "VIX index level, intraday high."),
        ColumnSpec("low", "float", False, "VIX index level, intraday low."),
        ColumnSpec("close", "float", False, "VIX index level at close."),
    ],
)

ALL_TABLES = [DIM_COMPANY, FACT_COMPANY_FINANCIALS, FACT_MARKET_VOLATILITY]
