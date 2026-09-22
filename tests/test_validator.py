"""Tests for src.validator module."""

import os
import pandas as pd

from src.validator import ValidationResult, validate, check_stale


def test_validation_result_model():
    r = ValidationResult(passed=True, warnings=[], errors=[])
    assert r.passed is True
    assert len(r.warnings) == 0


def test_validation_result_defaults():
    r = ValidationResult(passed=True)
    assert r.warnings == []
    assert r.errors == []


def test_validate_range_error():
    df = pd.DataFrame({"pct": [150.0]})
    rules = {"pct": {"min": 0, "max": 100}}
    result = validate(df, rules)
    assert not result.passed
    assert any("above maximum" in e.lower() for e in result.errors)


def test_validate_empty_df():
    df = pd.DataFrame()
    result = validate(df, {})
    assert not result.passed
    assert len(result.errors) > 0


def test_validate_passes():
    df = pd.DataFrame({"value": [50.0]})
    rules = {"value": {"min": 0, "max": 100}}
    result = validate(df, rules)
    assert result.passed


def test_validate_empty_columns():
    """All key columns are empty/nan."""
    df = pd.DataFrame({"NAV": [pd.NA, pd.NA], "ETL_SCALE": [pd.NA, pd.NA]})
    result = validate(df, {})
    assert not result.passed


def test_validate_row_count_below_threshold():
    """Row count below minimum threshold."""
    df = pd.DataFrame({"value": [1.0]})
    result = validate(df, {}, min_rows=5)
    assert not result.passed
    assert any("row" in e.lower() or "count" in e.lower() for e in result.errors)


def test_check_stale_fresh(tmp_path):
    from src.storage import save_csv
    save_csv(pd.DataFrame({"a": [1]}), str(tmp_path / "fresh.csv"))
    assert not check_stale(str(tmp_path / "fresh.csv"), max_age_hours=24)


def test_check_stale_old(tmp_path):
    from src.storage import save_csv
    save_csv(pd.DataFrame({"a": [1]}), str(tmp_path / "old.csv"))
    # Manually set mtime to 2 days ago
    two_days_ago = os.path.getmtime(str(tmp_path / "old.csv")) - 2 * 86400
    os.utime(str(tmp_path / "old.csv"), (two_days_ago, two_days_ago))
    assert check_stale(str(tmp_path / "old.csv"), max_age_hours=24)