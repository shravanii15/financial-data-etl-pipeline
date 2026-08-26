import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anomaly import zscore_outliers, rolling_change_outliers


def test_zscore_outliers_flags_extreme_value():
    values = [10, 11, 9, 10, 12, 500]  # 500 is a clear outlier
    df = pd.DataFrame({"v": values})
    flagged = zscore_outliers(df, "v", threshold=2.0)
    assert 500 in flagged["v"].values


def test_zscore_outliers_empty_when_no_variance():
    df = pd.DataFrame({"v": [5, 5, 5, 5]})
    flagged = zscore_outliers(df, "v")
    assert len(flagged) == 0


def test_rolling_change_outliers_flags_spike():
    rng = np.random.default_rng(0)
    base = 15 + rng.normal(0, 0.3, 60)
    base[45] = base[44] * 3  # inject an obvious spike
    dates = pd.date_range("2024-01-01", periods=60)
    df = pd.DataFrame({"date": dates, "close": base})
    flagged = rolling_change_outliers(df, "close", "date", window=30, threshold=3.0)
    assert dates[45] in pd.to_datetime(flagged["date"]).values
