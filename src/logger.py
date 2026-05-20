"""Logger for data collection runs.

Writes CSV logs to `data/logs/collect_YYYYMMDD.csv`.
"""

import csv
import os
import random
import string
from datetime import date, datetime


def get_run_id() -> str:
    """Generate a unique run ID: timestamp + random string, length > 20."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    rand = "".join(random.choices(string.ascii_letters + string.digits, k=12))
    return f"{ts}-{rand}"


# Global run_id shared across this process
run_id = get_run_id()


def log_collect(
    task: str,
    source: str,
    status: str,
    rows: int,
    elapsed_sec: float,
    message: str = "",
) -> None:
    """Append a row to the daily collection CSV log.

    File: data/logs/collect_YYYYMMDD.csv
    Fields: timestamp, task, source, status, rows, elapsed_sec, message, run_id
    """
    # Import here so monkeypatch of src.config.DATA_DIR takes effect
    from src.config import DATA_DIR

    today = date.today().strftime("%Y%m%d")
    log_dir = os.path.join(DATA_DIR, "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"collect_{today}.csv")

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task": task,
        "source": source,
        "status": status,
        "rows": rows,
        "elapsed_sec": round(elapsed_sec, 3),
        "message": message,
        "run_id": run_id,
    }

    file_exists = os.path.isfile(log_file)
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
