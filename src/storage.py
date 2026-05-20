"""CSV storage utilities for DataFrames."""

from pathlib import Path

import pandas as pd


def save_csv(df: pd.DataFrame, filepath: str, append: bool = False) -> None:
    """Save a DataFrame to a CSV file.

    Args:
        df: DataFrame to save.
        filepath: Path to the CSV file.
        append: If True, append to existing file; otherwise overwrite.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    if append:
        df.to_csv(path, mode='a', header=not path.exists(), index=False, encoding='utf-8')
    else:
        df.to_csv(path, mode='w', header=True, index=False, encoding='utf-8')


def load_csv(filepath: str) -> pd.DataFrame:
    """Load a CSV file into a DataFrame.

    Args:
        filepath: Path to the CSV file.

    Returns:
        DataFrame loaded from the CSV.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    return pd.read_csv(path, encoding='utf-8')
