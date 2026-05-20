import pandas as pd

def test_save_and_load_csv(tmp_path):
    df = pd.DataFrame({"date": ["2026-05-19"], "close": [100.5]})
    filepath = tmp_path / "test.csv"
    from src.storage import save_csv, load_csv
    save_csv(df, str(filepath))
    loaded = load_csv(str(filepath))
    assert loaded["close"][0] == 100.5
    assert loaded.columns.tolist() == ["date", "close"]

def test_save_csv_no_bom(tmp_path):
    filepath = tmp_path / "nobom.csv"
    from src.storage import save_csv
    save_csv(pd.DataFrame({"a": [1]}), str(filepath))
    with open(filepath, "rb") as f:
        header = f.read(3)
    assert header != b'\xef\xbb\xbf', "BOM found - should be UTF-8 no BOM"

def test_load_csv_nonexistent():
    from src.storage import load_csv
    try:
        load_csv("/nonexistent/path.csv")
        assert False, "Should raise FileNotFoundError"
    except FileNotFoundError:
        pass

def test_save_csv_creates_directory(tmp_path):
    filepath = tmp_path / "subdir" / "nested" / "test.csv"
    from src.storage import save_csv
    save_csv(pd.DataFrame({"a": [1]}), str(filepath))
    assert filepath.exists()
