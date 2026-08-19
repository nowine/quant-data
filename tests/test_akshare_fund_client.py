"""Tests for src/akshare_fund_client.py — drop-in replacement for ttfund_client.

Coverage:
- Public API signatures match ttfund_client (param names + types).
- get_nav_history wraps akshare df in ttfund's `data.nav_history.items[].DWJZ` shape.
- Stub functions return ttfund-shaped empty bodies without raising.
- get_fund_info degrades gracefully when akshare returns empty / errors.
- `call(skill_id, params)` shim raises (no longer meaningful).

Phase 2 markers (`@pytest.mark.phase2`) are reserved for the stub-backed
features in docs/phase-2-followup.md — they'll be flipped on real-data tests
once P2-1/P2-2/P2-3 land.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src import akshare_fund_client as af


# ── Signature parity ──────────────────────────────────────────────────────────

class TestSignatureParity:
    """All ttfund_client public names must exist with matching signatures."""

    @pytest.mark.parametrize("name", [
        "get_nav_history",
        "get_gold_info",
        "get_index_info",
        "get_holdings",
        "search_funds",
        "get_manager_info",
        "get_strategy",
        "get_fund_info",
    ])
    def test_public_api_exists(self, name):
        assert hasattr(af, name), f"missing public function: {name}"
        assert callable(getattr(af, name)), f"{name} must be callable"

    def test_call_shim_exists(self):
        """`call(skill_id, params)` kept for compat — should raise on unknown."""
        assert hasattr(af, "call")
        with pytest.raises(af.AkshareFundDataError):
            af.call("UNKNOWN_SKILL", {})


# ── get_nav_history: real wrap shape ─────────────────────────────────────────

class TestGetNavHistory:

    def _mock_ak(self, df: pd.DataFrame):
        """Return a MagicMock that exposes akshare as `af._get_ak()`."""
        mock_ak = MagicMock()
        mock_ak.fund_open_fund_info_em.return_value = df
        return mock_ak

    def test_wraps_akshare_df_into_ttfund_shape(self):
        """akshare columns (净值日期/单位净值/日增长率) → DWJZ/FSRQ/JZZZL/LJJZ."""
        # akshare returns OLDEST-first; shim reverses to newest-first.
        df = pd.DataFrame({
            "净值日期": ["2026-08-18", "2026-08-19"],
            "单位净值": ["1.230", "1.234"],
            "日增长率": ["-0.15", "0.32"],
        })
        with patch.object(af, "_get_ak", return_value=self._mock_ak(df)):
            result = af.get_nav_history("510300", "y")

        # Top-level shape matches ttfund body
        assert "data" in result
        assert "nav_history" in result["data"]
        items = result["data"]["nav_history"]["items"]
        assert len(items) == 2

        # items[0] is the LATEST entry (reversed by shim)
        first = items[0]
        assert first["FSRQ"] == "2026-08-19"
        assert first["DWJZ"] == "1.234"
        assert first["JZZZL"] == "0.32"
        # LJJZ falls back to DWJZ when akshare doesn't provide it
        assert first["LJJZ"] == "1.234"
        assert first["NAVTYPE"] == "1"

    def test_newest_first_enforced(self):
        """akshare returns oldest-first; wrapper must reverse to newest-first
        so callers' items[0] is the latest NAV (matches ttfund contract)."""
        df = pd.DataFrame({
            "净值日期": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "单位净值": ["1.00", "1.05", "1.10"],
            "日增长率": ["0.0", "5.0", "4.76"],
        })
        with patch.object(af, "_get_ak", return_value=self._mock_ak(df)):
            items = af.get_nav_history("510300", "y")["data"]["nav_history"]["items"]
        assert [it["FSRQ"] for it in items] == ["2024-01-03", "2024-01-02", "2024-01-01"]
        # items[0] is the most recent — this is the contract callers depend on
        assert items[0]["DWJZ"] == "1.10"

    def test_empty_dataframe(self):
        """akshare returns empty → wrapped as `data.nav_history.items = []`."""
        df = pd.DataFrame(columns=["净值日期", "单位净值", "日增长率"])
        with patch.object(af, "_get_ak", return_value=self._mock_ak(df)):
            result = af.get_nav_history("000000", "y")
        assert result == {"data": {"nav_history": {"items": []}}}

    def test_akshare_raises_translated(self):
        """akshare timeout / network failure → AkshareFundTimeoutError."""
        mock_ak = MagicMock()
        mock_ak.fund_open_fund_info_em.side_effect = TimeoutError("eastmoney down")
        with patch.object(af, "_get_ak", return_value=mock_ak):
            with pytest.raises(af.AkshareFundTimeoutError):
                af.get_nav_history("510300", "y")

    def test_range_parameter_mapped(self):
        """Unknown range values fall back to '1年' (akshare default)."""
        df = pd.DataFrame(columns=["净值日期", "单位净值", "日增长率"])
        mock_ak = MagicMock()
        mock_ak.fund_open_fund_info_em.return_value = df
        with patch.object(af, "_get_ak", return_value=mock_ak):
            af.get_nav_history("510300", "y")
            af.get_nav_history("510300", "3y")
            af.get_nav_history("510300", "ln")
            af.get_nav_history("510300", "bogus_value")

        # Last call should have used default period ("1年")
        args, kwargs = mock_ak.fund_open_fund_info_em.call_args
        assert kwargs["period"] == "1年"

        # Verify specific known mappings
        mock_ak.reset_mock()
        with patch.object(af, "_get_ak", return_value=mock_ak):
            af.get_nav_history("510300", "ln")
        _, kwargs = mock_ak.fund_open_fund_info_em.call_args
        assert kwargs["period"] == "成立以来"


# ── Stubs (Phase 2 backlog) ──────────────────────────────────────────────────

class TestStubs:

    def test_get_gold_info_returns_empty(self, caplog):
        with caplog.at_level("WARNING"):
            result = af.get_gold_info("all")
        assert result == {}
        # Stub log should have fired
        assert any("get_gold_info" in r.message for r in caplog.records)

    @pytest.mark.phase2
    def test_get_gold_info_real_data(self):
        """Placeholder — flip when P2-1 ships."""
        pytest.skip("Phase 2 P2-1: see docs/phase-2-followup.md")

    def test_get_holdings_returns_empty_datas(self):
        result = af.get_holdings("000001", "all")
        assert result == {"datas": []}

    @pytest.mark.phase2
    def test_get_holdings_real_data(self):
        """Placeholder — flip when P2-2 ships."""
        pytest.skip("Phase 2 P2-2: see docs/phase-2-followup.md")

    def test_get_index_info_partial_stub(self):
        """Returns dict with PE/PB fields explicitly None (Phase 2 P2-3)."""
        result = af.get_index_info("沪深300", "all")
        assert result["index_id"] == "沪深300"
        assert result["scope"] == "all"
        assert result["pe_percentile"] is None
        assert result["pb"] is None
        assert result["source"] == "akshare-partial-stub"

    @pytest.mark.phase2
    def test_get_index_info_full_valuation(self):
        """Placeholder — flip when P2-3 ships."""
        pytest.skip("Phase 2 P2-3: see docs/phase-2-followup.md")

    def test_get_strategy_returns_empty(self):
        assert af.get_strategy("司南双月宝组合") == {}

    def test_search_funds_preserves_pagination(self):
        """Not used by collectors — verify contract only."""
        result = af.search_funds(page=2, page_num=10, order="asc")
        assert result["page"] == 2
        assert result["pageNum"] == 10
        assert result["order"] == "asc"
        assert result["datas"] == []

    def test_get_manager_info_preserves_name(self):
        result = af.get_manager_info("张坤")
        assert result["manager_name"] == "张坤"


# ── get_fund_info ────────────────────────────────────────────────────────────

class TestGetFundInfo:

    def test_parses_xq_basic_info_dataframe(self):
        """akshare returns 2-col df (item / value); wrapper pivots to dict."""
        df = pd.DataFrame([
            ["基金全称", "华夏成长混合"],
            ["基金代码", "000001"],
            ["基金类型", "混合型"],
        ])
        mock_ak = MagicMock()
        mock_ak.fund_individual_basic_info_xq.return_value = df
        with patch.object(af, "_get_ak", return_value=mock_ak):
            result = af.get_fund_info("000001")
        assert result["fcode"] == "000001"
        assert result["基金全称"] == "华夏成长混合"
        assert result["基金代码"] == "000001"

    def test_akshare_failure_returns_fcode_only(self):
        mock_ak = MagicMock()
        mock_ak.fund_individual_basic_info_xq.side_effect = RuntimeError("xq down")
        with patch.object(af, "_get_ak", return_value=mock_ak):
            result = af.get_fund_info("999999")
        assert result["fcode"] == "999999"
        assert "error" in result

    def test_empty_dataframe(self):
        mock_ak = MagicMock()
        mock_ak.fund_individual_basic_info_xq.return_value = pd.DataFrame()
        with patch.object(af, "_get_ak", return_value=mock_ak):
            result = af.get_fund_info("000001")
        assert result == {"fcode": "000001"}


# ── Module-level: lazy akshare loader ────────────────────────────────────────

class TestLazyAkshareLoader:

    def test_akshare_missing_raises_runtime_error(self):
        """If akshare not installed, calling any data func raises clearly."""
        with patch.dict("sys.modules", {"akshare": None}):
            # Simulate akshare import failing
            import importlib
            with patch.object(af, "_ak", None):
                with patch("builtins.__import__", side_effect=ImportError("no akshare")):
                    with pytest.raises(RuntimeError, match="akshare is required"):
                        af._get_ak()