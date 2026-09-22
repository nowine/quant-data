import os
import pandas as pd


def test_exists_today_false_when_missing(tmp_path):
    from src.storage import exists_today

    assert not exists_today(str(tmp_path / "nonexist.csv"))


def test_exists_today_true_when_file_exists(tmp_path):
    from src.storage import save_csv, exists_today

    df = pd.DataFrame({"date": ["2026-05-20"], "value": [1]})
    save_csv(df, str(tmp_path / "test.csv"))
    assert exists_today(str(tmp_path / "test.csv"))


def test_exists_today_false_when_empty_file(tmp_path):
    from src.storage import exists_today

    # Create empty file
    tmp_path.joinpath("empty.csv").touch()
    assert not exists_today(str(tmp_path / "empty.csv"))


def test_collect_if_missing_cache_hit(tmp_path, monkeypatch):
    import importlib
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src.storage import save_csv, collect_if_missing

    df = pd.DataFrame({"date": ["2026-05-20"], "value": [1]})
    save_csv(df, str(tmp_path / "test.csv"))

    fetch_called = False

    def fake_fetch():
        nonlocal fetch_called
        fetch_called = True
        return pd.DataFrame({"date": ["2026-05-20"], "value": [2]})

    result = collect_if_missing(str(tmp_path / "test.csv"), fake_fetch)
    assert not fetch_called, "Should not call fetch when cache exists"
    assert result["value"][0] == 1  # cached value


def test_collect_if_missing_fetch_and_save(tmp_path, monkeypatch):
    import importlib
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    from src.storage import collect_if_missing

    def fake_fetch():
        return pd.DataFrame({"date": ["2026-05-20"], "value": [99]})

    result = collect_if_missing(str(tmp_path / "new.csv"), fake_fetch)
    assert result["value"][0] == 99
    assert os.path.exists(str(tmp_path / "new.csv"))