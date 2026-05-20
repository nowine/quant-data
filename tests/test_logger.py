import os
import tempfile
from datetime import date


def test_log_collect_writes_csv(tmp_path, monkeypatch):
    # Patch DATA_DIR on the config module directly (env var doesn't work because
    # src.config is already loaded with the real path at import time)
    import importlib
    from src import config, logger as logger_module
    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    logger_module.run_id = "test_run_123"
    logger_module.log_collect("test_task", "akshare", "success", 100, 1.5, "")

    today = date.today().strftime("%Y%m%d")
    log_file = tmp_path / f"logs/collect_{today}.csv"
    assert log_file.exists(), f"Log file not created: {log_file}"
    content = log_file.read_text()
    assert "test_task" in content
    assert "akshare" in content
    assert "success" in content


def test_run_id_is_unique():
    from src.logger import get_run_id
    rid1 = get_run_id()
    rid2 = get_run_id()
    assert rid1 != rid2
    assert len(rid1) > 20


def test_run_id_format():
    from src.logger import get_run_id
    rid = get_run_id()
    assert len(rid) > 20
    assert rid.isalnum() or "-" in rid