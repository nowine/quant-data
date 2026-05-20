"""CSV and JSON storage utilities."""

import json
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


def save_json(data: list | dict, filepath: str) -> None:
    """Save dict or list to a JSON file.

    Args:
        data: Data to serialize (dict or list).
        filepath: Path to the JSON file.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath: str) -> list | dict:
    """Load a JSON file.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Data loaded from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {filepath}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
