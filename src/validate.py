"""
validate.py
-----------
A small, dependency-light data quality framework. It's written generic on
purpose: every check takes a DataFrame + column name(s) and returns a
structured result, so this module can be pointed at a different pipeline's
tables without modification -- only the *rules you call* are specific to
this project, not the checking machinery itself.

Each check returns a CheckResult. Running validate_table() against a table +
a list of checks produces a report you can inspect, log, or fail a pipeline
run on.
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class CheckResult:
    check_name: str
    table: str
    column: Optional[str]
    passed: bool
    n_failing_rows: int
    detail: str
    failing_index: list = field(default_factory=list)


def check_not_null(df: pd.DataFrame, table: str, column: str) -> CheckResult:
    mask = df[column].isna()
    n = int(mask.sum())
    return CheckResult(
        check_name="not_null", table=table, column=column, passed=(n == 0),
        n_failing_rows=n, detail=f"{n} of {len(df)} rows have a null {column}.",
        failing_index=df.index[mask].tolist(),
    )


def check_unique(df: pd.DataFrame, table: str, column: str) -> CheckResult:
    dupe_mask = df[column].duplicated(keep=False) & df[column].notna()
    n = int(dupe_mask.sum())
    return CheckResult(
        check_name="unique", table=table, column=column, passed=(n == 0),
        n_failing_rows=n, detail=f"{n} rows share a duplicated {column} value.",
        failing_index=df.index[dupe_mask].tolist(),
    )


def check_in_range(df: pd.DataFrame, table: str, column: str, min_v=None, max_v=None) -> CheckResult:
    series = df[column]
    mask = pd.Series(False, index=df.index)
    if min_v is not None:
        mask |= series < min_v
    if max_v is not None:
        mask |= series > max_v
    mask &= series.notna()
    n = int(mask.sum())
    return CheckResult(
        check_name="in_range", table=table, column=column, passed=(n == 0),
        n_failing_rows=n,
        detail=f"{n} rows have {column} outside expected range [{min_v}, {max_v}].",
        failing_index=df.index[mask].tolist(),
    )


def check_referential_integrity(
    child_df: pd.DataFrame, child_col: str, parent_df: pd.DataFrame, parent_col: str,
    table: str,
) -> CheckResult:
    parent_values = set(parent_df[parent_col].dropna())
    mask = ~child_df[child_col].isin(parent_values)
    n = int(mask.sum())
    return CheckResult(
        check_name="referential_integrity", table=table, column=child_col,
        passed=(n == 0), n_failing_rows=n,
        detail=f"{n} rows in {table}.{child_col} have no matching {parent_col} in the parent table.",
        failing_index=child_df.index[mask].tolist(),
    )


def check_row_count_min(df: pd.DataFrame, table: str, min_rows: int) -> CheckResult:
    n = len(df)
    passed = n >= min_rows
    return CheckResult(
        check_name="row_count_min", table=table, column=None, passed=passed,
        n_failing_rows=0 if passed else 1,
        detail=f"{table} has {n} rows (expected at least {min_rows}).",
    )


def run_checks(checks: list) -> list:
    """checks: a list of already-built CheckResult objects (call the check_*
    functions yourself so you control exactly which columns/rules apply per
    table -- see pipeline.py for the concrete rule set this project uses)."""
    return checks


def summarize(results: list) -> pd.DataFrame:
    rows = [
        {
            "table": r.table,
            "check": r.check_name,
            "column": r.column,
            "passed": r.passed,
            "n_failing_rows": r.n_failing_rows,
            "detail": r.detail,
        }
        for r in results
    ]
    return pd.DataFrame(rows)
