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


def exists_today(filepath: str) -> bool:
    """Check if a file exists and is non-empty.

    Args:
        filepath: Path to the file.

    Returns:
        True if file exists and has non-zero size, False otherwise.
    """
    path = Path(filepath)
    return path.exists() and path.stat().st_size > 0


def collect_if_missing(
    filepath: str,
    fetch_fn: callable,
    *args,
    **kwargs,
) -> pd.DataFrame:
    """Fetch data and save to cache if today's file is missing.

    Args:
        filepath: Path to the cache file.
        fetch_fn: Callable that returns a DataFrame (no args).
        *args: Positional args passed to fetch_fn.
        **kwargs: Keyword args passed to fetch_fn.

    Returns:
        DataFrame from cache or freshly fetched.
    """
    from src.logger import log_collect
    import time

    start = time.time()
    filename = Path(filepath).name

    if exists_today(filepath):
        # Cache hit — read and log
        elapsed = time.time() - start
        log_collect(
            task="partial_rerun",
            source=filename,
            status="cache_hit",
            rows=0,
            elapsed_sec=elapsed,
            message=f"Read from cache: {filepath}",
        )
        return load_csv(filepath)

    # Miss — fetch, save, log
    df = fetch_fn(*args, **kwargs)
    save_csv(df, filepath)
    elapsed = time.time() - start
    log_collect(
        task="partial_rerun",
        source=filename,
        status="success",
        rows=len(df),
        elapsed_sec=elapsed,
        message=f"Fetched and saved: {filepath}",
    )
    return df


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
