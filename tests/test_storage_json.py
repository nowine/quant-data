"""Tests for JSON storage utilities."""

from src.storage import load_json, save_json


def test_save_and_load_json(tmp_path):
    data = {"fund_id": "001", "nav": 1.234}
    filepath = tmp_path / "test.json"
    save_json(data, str(filepath))
    loaded = load_json(str(filepath))
    assert loaded["fund_id"] == "001"
    assert loaded["nav"] == 1.234


def test_save_json_list(tmp_path):
    data = [{"code": "510300"}, {"code": "510500"}]
    filepath = tmp_path / "list.json"
    save_json(data, str(filepath))
    loaded = load_json(str(filepath))
    assert len(loaded) == 2


def test_load_json_nonexistent():
    try:
        load_json("/nonexistent/path.json")
        assert False, "Should raise"
    except FileNotFoundError:
        pass