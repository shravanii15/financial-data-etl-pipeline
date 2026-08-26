import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from validate import check_not_null, check_unique, check_in_range, check_referential_integrity


def test_check_not_null_detects_nulls():
    df = pd.DataFrame({"a": [1, None, 3]})
    result = check_not_null(df, "t", "a")
    assert result.passed is False
    assert result.n_failing_rows == 1


def test_check_not_null_passes_clean_column():
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = check_not_null(df, "t", "a")
    assert result.passed is True


def test_check_unique_detects_duplicates():
    df = pd.DataFrame({"a": ["x", "x", "y"]})
    result = check_unique(df, "t", "a")
    assert result.passed is False
    assert result.n_failing_rows == 2


def test_check_in_range():
    df = pd.DataFrame({"a": [-1, 5, 600]})
    result = check_in_range(df, "t", "a", min_v=0, max_v=500)
    assert result.passed is False
    assert result.n_failing_rows == 2


def test_referential_integrity_flags_orphans():
    parent = pd.DataFrame({"id": ["A", "B"]})
    child = pd.DataFrame({"id": ["A", "C"]})
    result = check_referential_integrity(child, "id", parent, "id", "child")
    assert result.passed is False
    assert result.n_failing_rows == 1
