"""Data validation utilities for the ETF data collection system."""

import time as _time
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from src.config import VALIDATION_RULES


class ValidationResult(BaseModel):
    """Result of a data validation check."""

    passed: bool
    warnings: list[str] = []
    errors: list[str] = []


def validate(
    df: pd.DataFrame,
    rules: dict,
    min_rows: int = 1,
    required_columns: list[str] | None = None,
) -> ValidationResult:
    """Run all five categories of validation checks against a DataFrame.

    Args:
        df: The DataFrame to validate.
        rules: Dict of column -> {min, max, nullable} rules. Only columns
            present in `df` are validated; VALIDATION_RULES from config
            is used as a fallback for columns not in `rules`.
        min_rows: Minimum number of rows required.
        required_columns: List of columns that must be present. If None,
            defaults to columns present in both `df.columns` and `rules`.

    Returns:
        ValidationResult with passed, warnings, and errors lists.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- 1. Empty DataFrame check ---
    if df.empty:
        errors.append("DataFrame is empty — no rows to validate")
        return ValidationResult(passed=False, errors=errors)

    # Build effective rules: user rules override config rules,
    # but only for columns that actually exist in the DataFrame.
    effective_rules: dict = {}
    for col in df.columns:
        base = dict(VALIDATION_RULES.get(col, {}))
        base.update(rules.get(col, {}))
        effective_rules[col] = base

    # --- 2. Required columns presence ---
    if required_columns is None:
        required_columns = list(effective_rules.keys())

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")

    # --- 3. Row count check ---
    if len(df) < min_rows:
        errors.append(f"Row count ({len(df)}) below minimum threshold ({min_rows})")

    # --- 4. Null check — critical columns must not be all-null ---
    for col in df.columns:
        if col in effective_rules and effective_rules[col].get("nullable", False):
            continue  # nullable=True columns are exempt
        if col in required_columns or col in effective_rules:
            if df[col].isna().all():
                errors.append(f"Column '{col}' is entirely null")

    # --- 5. Range check ---
    for col, rule in effective_rules.items():
        if col not in df.columns:
            continue
        col_data = df[col].dropna()
        if len(col_data) == 0:
            continue

        min_val = rule.get("min")
        max_val = rule.get("max")

        if min_val is not None:
            violations = col_data[col_data < min_val]
            if not violations.empty:
                errors.append(
                    f"Column '{col}' has {len(violations)} value(s) below minimum "
                    f"({min_val}): {violations.tolist()[:5]}"
                )
        if max_val is not None:
            violations = col_data[col_data > max_val]
            if not violations.empty:
                errors.append(
                    f"Column '{col}' has {len(violations)} value(s) above maximum "
                    f"({max_val}): {violations.tolist()[:5]}"
                )

    # --- 6. Staleness warning (checked separately via check_stale) ---

    passed = len(errors) == 0
    return ValidationResult(passed=passed, errors=errors, warnings=warnings)


def check_stale(filepath: str | Path, max_age_hours: float) -> bool:
    """Check whether a cache file is older than max_age_hours.

    Args:
        filepath: Path to the file.
        max_age_hours: Maximum age in hours before the file is considered stale.

    Returns:
        True if the file is stale (older than max_age_hours) or does not exist.
        False if the file is fresh.
    """
    path = Path(filepath)
    if not path.exists():
        return True  # Missing files are stale by convention

    mtime = path.stat().st_mtime
    age_seconds = _time.time() - mtime
    age_hours = age_seconds / 3600
    return age_hours > max_age_hours