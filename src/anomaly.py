"""
anomaly.py
----------
Generic anomaly detection, independent of what the numbers mean. Two
detectors are provided:

  - zscore_outliers(): flags values in a static column that sit far outside
    the column's own distribution (e.g. a company's P/E ratio that's wildly
    higher than its peers').
  - rolling_change_outliers(): flags days where a time series moves far more
    than its own recent history would predict (e.g. a VIX spike). This is
    the same statistical idea used for outbreak/spike detection in any
    monitoring context -- the method doesn't care whether the series is
    market volatility, disease case counts, or server error rates.

Both return the anomalous rows plus the z-score that triggered the flag, so
a human can judge severity rather than just getting a yes/no.
"""

import pandas as pd
import numpy as np


def zscore_outliers(df: pd.DataFrame, column: str, threshold: float = 3.0) -> pd.DataFrame:
    series = df[column]
    mean, std = series.mean(), series.std()
    if std == 0 or pd.isna(std):
        return df.iloc[0:0].copy()
    z = (series - mean) / std
    flagged = df.loc[z.abs() >= threshold].copy()
    flagged["zscore"] = z.loc[flagged.index]
    return flagged.sort_values("zscore", key=lambda s: s.abs(), ascending=False)


def rolling_change_outliers(
    df: pd.DataFrame, value_col: str, date_col: str, window: int = 30, threshold: float = 3.0
) -> pd.DataFrame:
    d = df.sort_values(date_col).copy()
    d["pct_change"] = d[value_col].pct_change()
    rolling_mean = d["pct_change"].rolling(window, min_periods=window // 2).mean()
    rolling_std = d["pct_change"].rolling(window, min_periods=window // 2).std()
    d["change_zscore"] = (d["pct_change"] - rolling_mean) / rolling_std
    flagged = d.loc[d["change_zscore"].abs() >= threshold].copy()
    return flagged.sort_values(date_col)
