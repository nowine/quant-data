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


class TestLoadCsvCodeColumn:
    """Regression tests for premium-rate bug (2026-08-20):

    akshare_client.get_etf_snapshot writes the '代码' column as str to avoid
    leading-zero / type-mismatch issues, but load_csv() used default type inference
    which silently coerced "159530" back to int 159530. This broke
    ``df["代码"] == "159530"`` matching downstream and made premium_* tasks fail.

    Fix: load_csv should preserve the '代码' column as str when present.
    """

    def test_load_csv_preserves_code_as_str(self, tmp_path):
        """A CSV with leading-zero / 6-digit ETF codes should keep 代码 as str."""
        filepath = tmp_path / "snapshot.csv"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("代码,名称,最新价\n")
            f.write('159530,易方达国证机器人产业ETF,1.34\n')
            f.write('588750,汇添富上证科创板芯片ETF,2.36\n')
            f.write('159934,易方达黄金ETF,9.40\n')
        from src.storage import load_csv
        df = load_csv(str(filepath))
        # Check via kind — any non-numeric kind (O for object/string) is acceptable.
        # Numeric kinds (i/u/f) would indicate the regression we're guarding against.
        assert df["代码"].dtype.kind == "O", (
            f"代码 column should be non-numeric (kind O), got kind={df['代码'].dtype.kind} dtype={df['代码'].dtype}"
        )
        # String membership must work — this is what premium_rate relies on
        assert "159530" in df["代码"].values
        assert df[df["代码"] == "159530"].iloc[0]["名称"] == "易方达国证机器人产业ETF"

    def test_load_csv_no_code_column_unchanged(self, tmp_path):
        """CSV without a '代码' column should behave as before (no regression)."""
        filepath = tmp_path / "other.csv"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("date,close\n")
            f.write("2026-08-19,100.5\n")
        from src.storage import load_csv
        df = load_csv(str(filepath))
        assert df["close"][0] == 100.5
