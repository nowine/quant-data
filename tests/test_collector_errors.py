"""Tests for structured error propagation in all collectors.

Tests the _record_error / _collect_csv / _collect_json error registry pattern
across collector_daily, collector_weekly, and collector_monthly.

Key scenarios tested:
  - Exception during fetch → status=error, error appended to result["errors"]
  - Empty DataFrame returned → status=degraded, error appended to result["errors"]
  - Success / cache_hit → errors list not touched
  - result["errors"] always present in run_xxx() output
  - Error format: "{task}: {detail}; suggestion: {action}"
"""

import datetime
import pandas as pd
import pytest

# ── collector_daily tests ──────────────────────────────────────────────────────

def _reload(monkeypatch, tmp_path, extra_modules=None):
    """Reload collector_daily with patched DATA_DIR.

    Args:
        monkeypatch: pytest monkeypatch fixture
        tmp_path: pytest tmp_path fixture
        extra_modules: list of modules to reload before collector_daily
    """
    import importlib
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)

    if extra_modules:
        for mod in extra_modules:
            importlib.reload(mod)

    from src import collector_daily
    importlib.reload(collector_daily)
    return collector_daily


class TestRecordError:
    def test_record_error_appends_structured_message(self, monkeypatch, tmp_path):
        """_record_error should append formatted '{name}: {detail}; suggestion: {suggestion}'."""
        cd = _reload(monkeypatch, tmp_path)
        errors = []
        cd._record_error(errors, "us_stock_index", "RemoteDisconnected", "use LLM search")
        assert len(errors) == 1
        assert errors[0] == "us_stock_index: RemoteDisconnected; suggestion: use LLM search"

    def test_record_error_accumulates_multiple(self, monkeypatch, tmp_path):
        """Multiple _record_error calls should accumulate all entries."""
        cd = _reload(monkeypatch, tmp_path)
        errors = []
        cd._record_error(errors, "task_a", "detail a", "suggest a")
        cd._record_error(errors, "task_b", "detail b", "suggest b")
        assert len(errors) == 2
        assert errors[0].startswith("task_a:")
        assert errors[1].startswith("task_b:")


class TestCollectCsvErrorPropagation:
    def test_collect_csv_on_empty_df_returns_degraded_and_append_error(self, monkeypatch, tmp_path):
        """_collect_csv with empty DataFrame should return status=degraded and append error."""
        cd = _reload(monkeypatch, tmp_path)
        errors = []
        filepath = tmp_path / "daily" / "empty.csv"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        result = cd._collect_csv(
            name="us_stock_index",
            fetch_fn=lambda: pd.DataFrame(),
            filepath=filepath,
            errors=errors,
            suggestion="use LLM to search current US stock index data",
        )

        assert result["status"] == "degraded"
        assert len(errors) == 1
        assert "us_stock_index" in errors[0]
        assert "returned empty data" in errors[0]
        assert "suggestion: use LLM" in errors[0]

    def test_collect_csv_on_exception_returns_error_and_append_error(self, monkeypatch, tmp_path):
        """_collect_csv when fetch_fn raises should return status=error and append error."""
        cd = _reload(monkeypatch, tmp_path)
        errors = []
        filepath = tmp_path / "daily" / "exception.csv"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        def failing_fetch():
            raise ConnectionError("connection refused")

        result = cd._collect_csv(
            name="nav_510300",
            fetch_fn=failing_fetch,
            filepath=filepath,
            errors=errors,
            suggestion="check ttfund NAV interface or use LLM",
        )

        assert result["status"] == "error"
        assert "connection refused" in result["error"]
        assert len(errors) == 1
        assert "nav_510300" in errors[0]
        assert "connection refused" in errors[0]
        assert "suggestion: check ttfund NAV interface" in errors[0]

    def test_collect_csv_on_success_does_not_clear_errors(self, monkeypatch, tmp_path):
        """_collect_csv with valid non-empty DataFrame should not modify the errors list."""
        cd = _reload(monkeypatch, tmp_path)
        errors = ["previous_error"]
        filepath = tmp_path / "daily" / "success.csv"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        result = cd._collect_csv(
            name="etf_snapshot",
            fetch_fn=lambda: pd.DataFrame({"代码": ["510300"], "最新价": [3.8]}),
            filepath=filepath,
            errors=errors,
            suggestion="use LLM",
        )

        assert result["status"] == "success"
        assert len(errors) == 1  # original error preserved, no false positive added

    def test_collect_csv_on_cache_hit_does_not_append_error(self, monkeypatch, tmp_path):
        """_collect_csv with exists_today True should return skipped without touching errors."""
        cd = _reload(monkeypatch, tmp_path)
        errors = []
        filepath = tmp_path / "daily" / "cached.csv"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text("already cached")  # make exists_today return True

        result = cd._collect_csv(
            name="cached_task",
            fetch_fn=lambda: (_ for _ in ()).throw(RuntimeError("should not be called")),
            filepath=filepath,
            errors=errors,
            suggestion="use LLM",
        )

        assert result["status"] == "skipped"
        assert len(errors) == 0


class TestCollectJsonErrorPropagation:
    def test_collect_json_on_empty_data_returns_degraded_and_append_error(self, monkeypatch, tmp_path):
        """_collect_json with empty/falsy data should return status=degraded and append error."""
        cd = _reload(monkeypatch, tmp_path)
        errors = []
        filepath = tmp_path / "daily" / "empty.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        result = cd._collect_json(
            name="index_valuation",
            fetch_fn=lambda: {},
            filepath=filepath,
            errors=errors,
            suggestion="check ttfund index valuation or use LLM",
        )

        assert result["status"] == "degraded"
        assert len(errors) == 1
        assert "index_valuation" in errors[0]
        assert "returned empty data" in errors[0]

    def test_collect_json_on_exception_returns_error_and_append_error(self, monkeypatch, tmp_path):
        """_collect_json when fetch_fn raises should return status=error and append error."""
        cd = _reload(monkeypatch, tmp_path)
        errors = []
        filepath = tmp_path / "daily" / "bad.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)

        result = cd._collect_json(
            name="gold_macro",
            fetch_fn=lambda: (_ for _ in ()).throw(ValueError("invalid response")),
            filepath=filepath,
            errors=errors,
            suggestion="check ttfund gold/macro interface or use LLM",
        )

        assert result["status"] == "error"
        assert len(errors) == 1
        assert "gold_macro" in errors[0]
        assert "suggestion: check ttfund gold/macro" in errors[0]


class TestRunCloseModeErrors:
    def test_run_close_mode_always_has_errors_key(self, monkeypatch, tmp_path):
        """run_close_mode result should always contain 'errors' key, even if all succeed."""
        import importlib
        from src import akshare_client as ak_module, ttfund_client as tt_module

        importlib.reload(ak_module)
        importlib.reload(tt_module)

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, tt_module])
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))
        # Mock akshare internals so no real network calls
        import akshare as ak
        ak.fund_etf_category_ths = lambda: pd.DataFrame({"序号":[1],"基金代码":["510300"],"基金名称":["test"],"当前-单位净值":[3.8],"当前-累计净值":[3.8],"前一日-单位净值":[3.7],"前一日-累计净值":[3.7],"增长值":[0.1],"增长率":[2.7],"赎回状态":["开放"],"申购状态":["开放"],"最新-交易日":["2026-05-20"],"最新-单位净值":[3.8],"最新-累计净值":[3.8],"基金类型":["股票型"],"查询日期":["2026-05-20"]})
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame({"date": ["2026-05-20"], "balance": [1e9]})
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]})
        ak.stock_us_spot_em = lambda: pd.DataFrame({"名称": ["标普500指数"], "最新价": [5000]})
        tt_module.get_nav_history = lambda code, rng: {"data": {"nav_history": {"items": [{"JZRQ": "2026-05-20", "DWJZ": "3.8"}]}}}

        result = cd.run_close_mode()

        assert "errors" in result
        assert isinstance(result["errors"], list)

    def test_run_close_mode_empty_df_propagates_degraded_error(self, monkeypatch, tmp_path):
        """run_close_mode with empty akshare response should record degraded error."""
        import importlib
        from src import akshare_client as ak_module, ttfund_client as tt_module
        import akshare as ak

        ths_mock_df = pd.DataFrame({
            "序号":[1],"基金代码":["510300"],"基金名称":["test"],
            "当前-单位净值":[3.8],"当前-累计净值":[3.8],
            "前一日-单位净值":[3.7],"前一日-累计净值":[3.7],
            "增长值":[0.1],"增长率":[2.7],
            "赎回状态":["开放"],"申购状态":["开放"],
            "最新-交易日":["2026-05-20"],"最新-单位净值":[3.8],
            "最新-累计净值":[3.8],"基金类型":["股票型"],"查询日期":["2026-05-20"],
        })
        # Set mocks BEFORE reload
        ak.fund_etf_category_ths = lambda: ths_mock_df
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame()  # empty → degraded
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]})
        ak.stock_us_spot_em = lambda: pd.DataFrame({"名称": ["标普500指数"], "最新价": [5000]})

        importlib.reload(ak_module)
        importlib.reload(tt_module)

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, tt_module])
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))
        tt_module.get_nav_history = lambda code, rng: {"data": {"nav_history": {"items": []}}}

        result = cd.run_close_mode()

        assert "errors" in result
        assert len(result["errors"]) >= 1
        assert any("margin_sh" in e and "degraded" in e or "returned empty" in e for e in result["errors"])

    def test_run_close_mode_exception_propagates_to_errors(self, monkeypatch, tmp_path):
        """run_close_mode when an API raises should record error in result['errors'] with suggestion."""
        import importlib
        from src import akshare_client as ak_module, ttfund_client as tt_module
        import akshare as ak

        ths_mock_df = pd.DataFrame({
            "序号":[1],"基金代码":["510300"],"基金名称":["test"],
            "当前-单位净值":[3.8],"当前-累计净值":[3.8],
            "前一日-单位净值":[3.7],"前一日-累计净值":[3.7],
            "增长值":[0.1],"增长率":[2.7],
            "赎回状态":["开放"],"申购状态":["开放"],
            "最新-交易日":["2026-05-20"],"最新-单位净值":[3.8],
            "最新-累计净值":[3.8],"基金类型":["股票型"],"查询日期":["2026-05-20"],
        })
        # Set ALL akshare mocks BEFORE reload
        ak.fund_etf_category_ths = lambda: ths_mock_df
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame({"date": ["2026-05-20"], "balance": [1e9]})
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]})
        ak.stock_us_spot_em = lambda: (_ for _ in ()).throw(
            ConnectionError("RemoteDisconnected('Remote end closed connection')")
        )

        importlib.reload(ak_module)
        importlib.reload(tt_module)

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, tt_module])
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))
        tt_module.get_nav_history = lambda code, rng: {"data": {"nav_history": {"items": []}}}

        result = cd.run_close_mode()

        assert "errors" in result
        usd_errors = [e for e in result["errors"] if "us_stock_index" in e]
        assert len(usd_errors) == 1, f"Expected 1 us_stock_index error, got {usd_errors}"
        assert "RemoteDisconnected" in usd_errors[0] or "ConnectionError" in usd_errors[0]
        assert "suggestion:" in usd_errors[0]

    def test_run_close_mode_error_format_is_structured(self, monkeypatch, tmp_path):
        """Each error entry should follow '{task}: {detail}; suggestion: {action}' format."""
        import importlib
        from src import akshare_client as ak_module, ttfund_client as tt_module
        import akshare as ak

        # Set mocks BEFORE reload so akshare_client captures them at import time
        ak.fund_etf_category_ths = lambda: pd.DataFrame()
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame()
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame()
        ak.stock_us_spot_em = lambda: pd.DataFrame()  # empty → degraded

        importlib.reload(ak_module)
        importlib.reload(tt_module)

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, tt_module])
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))
        tt_module.get_nav_history = lambda code, rng: {}

        result = cd.run_close_mode()

        for err in result.get("errors", []):
            parts = err.split("; suggestion: ")
            assert len(parts) == 2, f"Error format must be 'task: detail; suggestion: action', got: {err}"


class TestRunMorningModeErrors:
    def test_run_morning_mode_always_has_errors_key(self, monkeypatch, tmp_path):
        """run_morning_mode result should always contain 'errors' key, even if empty."""
        from src import ttfund_client as tt_module

        import importlib
        importlib.reload(tt_module)

        cd = _reload(monkeypatch, tmp_path, extra_modules=[tt_module])
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))
        tt_module.get_gold_info = lambda scope: {"data": {}}
        tt_module.get_index_info = lambda idx, scope: {"data": {}}

        result = cd.run_morning_mode()

        assert "errors" in result
        assert isinstance(result["errors"], list)

    def test_run_morning_mode_error_format_is_structured(self, monkeypatch, tmp_path):
        """Each morning-mode error entry should follow '{task}: {detail}; suggestion: {action}'."""
        from src import ttfund_client as tt_module

        import importlib
        importlib.reload(tt_module)

        cd = _reload(monkeypatch, tmp_path, extra_modules=[tt_module])
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))
        # Empty data → degraded
        tt_module.get_gold_info = lambda scope: None
        tt_module.get_index_info = lambda idx, scope: None

        result = cd.run_morning_mode()

        for err in result.get("errors", []):
            parts = err.split("; suggestion: ")
            assert len(parts) == 2, f"Morning error format must be 'task: detail; suggestion: action', got: {err}"


# ── collector_weekly tests ──────────────────────────────────────────────────────

def _reload_weekly(monkeypatch, tmp_path):
    """Reload collector_weekly with patched DATA_DIR."""
    import importlib
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)
    from src import collector_weekly
    importlib.reload(collector_weekly)
    return collector_weekly


class TestWeeklyErrorPropagation:
    def test_run_weekly_always_has_errors_key(self, monkeypatch, tmp_path):
        """run_weekly result should always contain 'errors' key."""
        cw = _reload_weekly(monkeypatch, tmp_path)
        monkeypatch.setattr(cw, "today", lambda: datetime.date(2026, 5, 18))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.fund_etf_scale_sse = lambda: pd.DataFrame()
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame()
        ak.fund_portfolio_industry_allocation_em = lambda year: pd.DataFrame()

        result = cw.run_weekly()

        assert "errors" in result
        assert isinstance(result["errors"], list)

    def test_run_weekly_empty_data_propagates_degraded_errors(self, monkeypatch, tmp_path):
        """run_weekly with empty fetch results should append degraded errors to result['errors']."""
        cw = _reload_weekly(monkeypatch, tmp_path)
        monkeypatch.setattr(cw, "today", lambda: datetime.date(2026, 5, 18))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.fund_etf_scale_sse = lambda: pd.DataFrame()  # empty → degraded
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame()
        ak.fund_portfolio_industry_allocation_em = lambda year: pd.DataFrame()

        result = cw.run_weekly()

        assert "errors" in result
        assert len(result["errors"]) >= 1
        assert any("etf_scale" in e for e in result["errors"])

    def test_run_weekly_exception_propagates_to_errors(self, monkeypatch, tmp_path):
        """run_weekly when get_industry_alloc raises should record error in result['errors']."""
        cw = _reload_weekly(monkeypatch, tmp_path)
        monkeypatch.setattr(cw, "today", lambda: datetime.date(2026, 5, 18))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.fund_etf_scale_sse = lambda: pd.DataFrame()
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame()
        ak.fund_portfolio_industry_allocation_em = lambda year: (_ for _ in ()).throw(
            ConnectionError("connection reset")
        )

        result = cw.run_weekly()

        assert "errors" in result
        alloc_errors = [e for e in result["errors"] if "industry_alloc" in e]
        assert len(alloc_errors) == 1
        assert "connection reset" in alloc_errors[0]
        assert "suggestion:" in alloc_errors[0]

    def test_run_weekly_error_format_is_structured(self, monkeypatch, tmp_path):
        """Each weekly error entry should follow '{task}: {detail}; suggestion: {action}'."""
        cw = _reload_weekly(monkeypatch, tmp_path)
        monkeypatch.setattr(cw, "today", lambda: datetime.date(2026, 5, 18))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.fund_etf_scale_sse = lambda: pd.DataFrame()
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame()
        ak.fund_portfolio_industry_allocation_em = lambda year: pd.DataFrame()

        result = cw.run_weekly()

        for err in result.get("errors", []):
            parts = err.split("; suggestion: ")
            assert len(parts) == 2, f"Weekly error format must be 'task: detail; suggestion: action', got: {err}"


# ── collector_monthly tests ────────────────────────────────────────────────────

def _reload_monthly(monkeypatch, tmp_path):
    """Reload collector_monthly with patched DATA_DIR."""
    import importlib
    from src import config, logger as logger_module

    importlib.reload(config)
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    importlib.reload(logger_module)
    from src import collector_monthly
    importlib.reload(collector_monthly)
    return collector_monthly


class TestMonthlyErrorPropagation:
    def test_run_monthly_always_has_errors_key(self, monkeypatch, tmp_path):
        """run_monthly result should always contain 'errors' key."""
        cm = _reload_monthly(monkeypatch, tmp_path)
        monkeypatch.setattr(cm, "today", lambda: datetime.date(2026, 5, 1))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame()
        ak.macro_china_cpi_yearly = lambda: pd.DataFrame()
        ak.macro_china_ppi_yearly = lambda: pd.DataFrame()
        ak.macro_china_pmi = lambda: pd.DataFrame()
        ak.macro_china_gdp = lambda: pd.DataFrame()
        ak.macro_china_m2 = lambda: pd.DataFrame()
        ak.macro_china_lpr = lambda: pd.DataFrame()

        result = cm.run_monthly()

        assert "errors" in result
        assert isinstance(result["errors"], list)

    def test_run_monthly_empty_data_propagates_degraded_errors(self, monkeypatch, tmp_path):
        """run_monthly with empty results should record degraded errors for each macro task."""
        cm = _reload_monthly(monkeypatch, tmp_path)
        monkeypatch.setattr(cm, "today", lambda: datetime.date(2026, 5, 1))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame()
        ak.macro_china_cpi_yearly = lambda: pd.DataFrame()
        ak.macro_china_ppi_yearly = lambda: pd.DataFrame()
        ak.macro_china_pmi = lambda: pd.DataFrame()
        ak.macro_china_gdp = lambda: pd.DataFrame()
        ak.macro_china_m2 = lambda: pd.DataFrame()
        ak.macro_china_lpr = lambda: pd.DataFrame()

        result = cm.run_monthly()

        assert "errors" in result
        assert len(result["errors"]) >= 1

    def test_run_monthly_exception_propagates_to_errors(self, monkeypatch, tmp_path):
        """run_monthly when get_cpi raises should record error in result['errors']."""
        cm = _reload_monthly(monkeypatch, tmp_path)
        monkeypatch.setattr(cm, "today", lambda: datetime.date(2026, 5, 1))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame()
        ak.macro_china_cpi_yearly = lambda: (_ for _ in ()).throw(
            ConnectionError("CPI API unavailable")
        )
        ak.macro_china_ppi_yearly = lambda: pd.DataFrame()
        ak.macro_china_pmi = lambda: pd.DataFrame()
        ak.macro_china_gdp = lambda: pd.DataFrame()
        ak.macro_china_m2 = lambda: pd.DataFrame()
        ak.macro_china_lpr = lambda: pd.DataFrame()

        result = cm.run_monthly()

        assert "errors" in result
        cpi_errors = [e for e in result["errors"] if "cpi" in e]
        assert len(cpi_errors) == 1
        assert "CPI API unavailable" in cpi_errors[0]
        assert "suggestion:" in cpi_errors[0]

    def test_run_monthly_error_format_is_structured(self, monkeypatch, tmp_path):
        """Each monthly error entry should follow '{task}: {detail}; suggestion: {action}'."""
        cm = _reload_monthly(monkeypatch, tmp_path)
        monkeypatch.setattr(cm, "today", lambda: datetime.date(2026, 5, 1))

        from src import akshare_client as ak_module
        import importlib
        importlib.reload(ak_module)
        import akshare as ak
        ak.macro_china_market_margin_sh = lambda: pd.DataFrame()
        ak.macro_china_cpi_yearly = lambda: pd.DataFrame()
        ak.macro_china_ppi_yearly = lambda: pd.DataFrame()
        ak.macro_china_pmi = lambda: pd.DataFrame()
        ak.macro_china_gdp = lambda: pd.DataFrame()
        ak.macro_china_m2 = lambda: pd.DataFrame()
        ak.macro_china_lpr = lambda: pd.DataFrame()

        result = cm.run_monthly()

        for err in result.get("errors", []):
            parts = err.split("; suggestion: ")
            assert len(parts) == 2, f"Monthly error format must be 'task: detail; suggestion: action', got: {err}"