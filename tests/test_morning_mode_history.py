"""Tests for morning mode calling get_etf_history for USER_HOLDINGS (量比/ATR/MA data source).

需求：morning 模式新增对 USER_HOLDINGS 调用 get_etf_history() 获取历史行情，
作为量比/ATR/MA 的数据来源，替代原来通过 ttfund nav_history 的方式。
"""

import datetime
import pandas as pd
import pytest


def _reload(monkeypatch, tmp_path, extra_modules=None):
    """Reload collector_daily with patched DATA_DIR."""
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


class TestMorningModeUsesEtfHistory:
    """TDD: morning mode should call get_etf_history for each USER_HOLDINGS ETF."""

    def test_morning_mode_calls_get_etf_history_for_user_holdings(
        self, monkeypatch, tmp_path
    ):
        """run_morning_mode must call get_etf_history for each user holding ETF."""
        import importlib

        import akshare as ak
        import pandas as pd

        # Mock THS (for ETF snapshot if called)
        ak.fund_etf_category_ths = lambda: pd.DataFrame({
            "序号": [1], "基金代码": ["510300"], "基金名称": ["test"],
            "当前-单位净值": [3.8], "当前-累计净值": [3.8],
            "前一日-单位净值": [3.7], "前一日-累计净值": [3.7],
            "增长值": [0.1], "增长率": [2.7],
            "赎回状态": ["开放"], "申购状态": ["开放"],
            "最新-交易日": ["2026-05-20"], "最新-单位净值": [3.8],
            "最新-累计净值": [3.8], "基金类型": ["股票型"], "查询日期": ["2026-05-20"],
        })

        # Must reload collector_daily AFTER mocking akshare so function references
        # are captured from the mocked akshare_client
        from src import config, logger as logger_module
        importlib.reload(config)
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        importlib.reload(logger_module)

        from src import akshare_client as ak_module, akshare_fund_client as af_module
        importlib.reload(ak_module)
        importlib.reload(af_module)

        from src import collector_daily as cd_module
        # CRITICAL: get_etf_history is imported into collector_daily at import time.
        # Must patch on cd_module, not ak_module.
        calls = []
        def tracking_get_etf_history(code):
            calls.append(code)
            return pd.DataFrame({
                "date": ["2026-05-20"] * 60,
                "open": [3.8] * 60,
                "high": [4.0] * 60,
                "low": [3.6] * 60,
                "close": [3.8] * 60,
                "volume": [1e6] * 60,
                "amount": [3.8e6] * 60,
            })
        cd_module.get_etf_history = tracking_get_etf_history
        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, af_module])
        # Re-patch after reload since reload replaces the module object
        cd.get_etf_history = tracking_get_etf_history
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))

        af_module.get_gold_info = lambda scope: {"data": {}}
        af_module.get_index_info = lambda idx, scope: {"data": {}}

        result = cd.run_morning_mode()

        # Should have called get_etf_history for at least one user holding
        assert len(calls) >= 1, f"get_etf_history not called, calls={calls}"
        # At least one should be from USER_HOLDINGS
        from src.config import USER_HOLDINGS
        holding_codes = [h["code"] for h in USER_HOLDINGS]
        assert any(c in holding_codes for c in calls), \
            f"Expected call for one of {holding_codes}, got {calls}"

    def test_tech_indicators_use_etf_history_columns(
        self, monkeypatch, tmp_path
    ):
        """Technical indicators (MA/ATR/RSI/Bollinger/MACD) must be computed
        from get_etf_history output which has open/high/low/close/volume columns.

        The key difference from the old nav_history approach:
        - get_etf_history provides open/high/low/close/volume → full OHLCV
        - nav_history only provides DWJZ (close-like price) → no volume/ATR
        """
        import importlib

        import akshare as ak
        import pandas as pd

        ak.fund_etf_category_ths = lambda: pd.DataFrame({
            "序号": [1], "基金代码": ["510300"], "基金名称": ["test"],
            "当前-单位净值": [3.8], "当前-累计净值": [3.8],
            "前一日-单位净值": [3.7], "前一日-累计净值": [3.7],
            "增长值": [0.1], "增长率": [2.7],
            "赎回状态": ["开放"], "申购状态": ["开放"],
            "最新-交易日": ["2026-05-20"], "最新-单位净值": [3.8],
            "最新-累计净值": [3.8], "基金类型": ["股票型"], "查询日期": ["2026-05-20"],
        })

        # Provide 60 days of OHLCV data (enough for MA20, ATR14, etc.)
        ohlcv_data = {
            "date": pd.date_range("2026-03-01", periods=60, freq="D").strftime("%Y-%m-%d").tolist(),
            "open": [3.8] * 60,
            "high": [4.0] * 60,
            "low": [3.6] * 60,
            "close": [3.8] * 60,
            "volume": [1_000_000] * 60,
            "amount": [3_800_000] * 60,
        }

        from src import config, logger as logger_module
        importlib.reload(config)
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        importlib.reload(logger_module)

        from src import akshare_client as ak_module, akshare_fund_client as af_module
        importlib.reload(ak_module)
        importlib.reload(af_module)

        from src import collector_daily as cd_module
        cd_module.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, af_module])
        cd.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))

        # tech_indicators are saved via _collect_csv which returns a result dict.
        # Call _run_tech_indicators_for_user_holdings directly to verify indicators.
        tech_df = cd._run_tech_indicators_for_user_holdings()
        assert len(tech_df) >= 1, f"Expected at least 1 row in tech indicators, got {len(tech_df)}"
        assert "atr14" in tech_df.columns, f"Missing atr14 in {list(tech_df.columns)}"
        assert "volume_ratio" in tech_df.columns, f"Missing volume_ratio in {list(tech_df.columns)}"
        assert "ma20" in tech_df.columns
        assert "rsi14" in tech_df.columns

        # Values should be valid numbers (ATR should be >0 since we have high/low)
        last_row = tech_df.iloc[-1]
        assert not pd.isna(last_row["atr14"]), "atr14 should not be NaN with get_etf_history OHLCV"
        assert last_row["atr14"] > 0




class TestSectorAggregationWithoutVolumeCol:
    """TDD: _run_sector_aggregation should NOT pass volume_col to aggregate_by_sector.

    THS source (get_etf_snapshot) has no 成交额 field.
    Sector ranking only needs 涨跌幅, not volume.
    """

    def test_sector_aggregation_called_without_volume_col(self, monkeypatch, tmp_path):
        """_run_sector_aggregation must not reference 成交额 or volume_col."""
        from src import config
        from src import akshare_client as ak_module, akshare_fund_client as af_module
        import importlib

        import akshare as ak

        # THS mock must cover ALL codes in SECTOR_MAPPING so sector_agg finds data.
        # Use real config to get all codes so test is robust.
        all_codes = sorted(set(c for codes in config.SECTOR_MAPPING.values() for c in codes))
        ths_mock = pd.DataFrame({
            "序号": list(range(1, len(all_codes) + 1)),
            "基金代码": all_codes,
            "基金名称": [f"ETF{c}" for c in all_codes],
            "当前-单位净值": [3.8] * len(all_codes),
            "当前-累计净值": [3.8] * len(all_codes),
            "前一日-单位净值": [3.7] * len(all_codes),
            "前一日-累计净值": [3.7] * len(all_codes),
            "增长值": [0.1] * len(all_codes),
            "增长率": [2.7] * len(all_codes),
            "赎回状态": ["开放"] * len(all_codes),
            "申购状态": ["开放"] * len(all_codes),
            "最新-交易日": ["2026-05-20"] * len(all_codes),
            "最新-单位净值": [3.8] * len(all_codes),
            "最新-累计净值": [3.8] * len(all_codes),
            "基金类型": ["股票型"] * len(all_codes),
            "查询日期": ["2026-05-20"] * len(all_codes),
        })
        ak.fund_etf_category_ths = lambda: ths_mock

        importlib.reload(ak_module)
        importlib.reload(af_module)

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, af_module])
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))

        ak.macro_china_market_margin_sh = lambda: pd.DataFrame({"date": ["2026-05-20"], "balance": [1e9]})
        ak.stock_hsgt_hist_em = lambda *a, **kw: pd.DataFrame({"date": ["2026-05-20"], "flow": [100]})
        ak.stock_us_spot_em = lambda: pd.DataFrame({"名称": ["标普500指数"], "最新价": [5000]})
        af_module.get_nav_history = lambda code, rng: {"data": {"nav_history": {"items": []}}}

        result = cd.run_close_mode()

        # sector_rank is stored via _collect_csv which returns a result dict (not the DataFrame)
        assert "sector_rank" in result, f"sector_rank missing from {list(result.keys())}"
        sector_result = result["sector_rank"]
        assert isinstance(sector_result, dict), f"Expected dict, got {type(sector_result)}"
        assert sector_result["status"] == "success", \
            f"sector_rank status should be success, got {sector_result}"
        assert sector_result["rows"] >= 1, \
            f"sector_rank should have >= 1 row, got {sector_result['rows']}"

        # The DataFrame is saved to CSV — verify it exists and has expected columns
        sector_csv_path = cd._sector_rank_path()
        assert sector_csv_path.exists(), f"sector_rank CSV not saved at {sector_csv_path}"
        sector_df = pd.read_csv(sector_csv_path)
        assert len(sector_df) >= 1, "sector_rank CSV should have >= 1 row"
        # Should NOT have 成交额 column (no such field in THS data)
        assert "成交额" not in sector_df.columns, \
            f"成交额 should not be in sector_rank columns: {list(sector_df.columns)}"
        # Should have avg_change_pct and rank
        assert "avg_change_pct" in sector_df.columns, \
            f"avg_change_pct missing from {list(sector_df.columns)}"
        assert "rank" in sector_df.columns, \
            f"rank missing from {list(sector_df.columns)}"


# ── TDD: morning mode must iterate ETF_WATCH_LIST too ────────────────────────
#
# 设计变更（2026-08-26 主人决定）:
#   USER_HOLDINGS 和 ETF_WATCH_LIST 需要的数据是一样的
#   （premium rate + tech indicator），报告侧按"持仓 vs 观察"分章节。
#   之前 morning mode 只跑 USER_HOLDINGS（5 只）→ 22 只纯 watch 没有 csv，
#   报告看不到观察标的的技术指标。
#
# 测试 seams:
#   - run_morning_mode() 返回的 result 必须包含 USER_HOLDINGS � ETF_WATCH_LIST
#     中每个 code 的 premium_<code> 和 tech_indicator_<code> key
#   - 不重复遍历（去重）— holdings ∩ watch 共用一份

class TestMorningModeCoversWatchList:
    """Morning mode must iterate USER_HOLDINGS + ETF_WATCH_LIST (deduped)."""

    def test_morning_mode_result_keys_cover_all_monitored_codes(self, monkeypatch, tmp_path):
        """result 必须有每个被监控标的的 premium_<code> 和 tech_indicator_<code> key。"""
        import importlib

        import akshare as ak
        from src import config, logger as logger_module

        # THS mock 覆盖所有 code（morning mode 不直接用，但 reload 安全网）
        all_codes = sorted(
            set(h["code"] for h in config.USER_HOLDINGS)
            | set(e["code"] for e in config.ETF_WATCH_LIST)
        )
        ths_mock = pd.DataFrame({
            "序号": list(range(1, len(all_codes) + 1)),
            "基金代码": all_codes,
            "基金名称": [f"ETF{c}" for c in all_codes],
            "当前-单位净值": [3.8] * len(all_codes),
            "当前-累计净值": [3.8] * len(all_codes),
            "前一日-单位净值": [3.7] * len(all_codes),
            "前一日-累计净值": [3.7] * len(all_codes),
            "增长值": [0.1] * len(all_codes),
            "增长率": [2.7] * len(all_codes),
            "赎回状态": ["开放"] * len(all_codes),
            "申购状态": ["开放"] * len(all_codes),
            "最新-交易日": ["2026-05-20"] * len(all_codes),
            "最新-单位净值": [3.8] * len(all_codes),
            "最新-累计净值": [3.8] * len(all_codes),
            "基金类型": ["股票型"] * len(all_codes),
            "查询日期": ["2026-05-20"] * len(all_codes),
        })
        ak.fund_etf_category_ths = lambda: ths_mock

        importlib.reload(config)
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        importlib.reload(logger_module)

        from src import akshare_client as ak_module, akshare_fund_client as af_module
        importlib.reload(ak_module)
        importlib.reload(af_module)

        # get_etf_history 返回有效 OHLCV（避免 _run_tech_indicators_for_holdings 跳过）
        ohlcv_data = {
            "date": pd.date_range("2026-03-01", periods=60, freq="D").strftime("%Y-%m-%d").tolist(),
            "open": [3.8] * 60,
            "high": [4.0] * 60,
            "low": [3.6] * 60,
            "close": [3.8] * 60,
            "volume": [1_000_000] * 60,
            "amount": [3_800_000] * 60,
        }
        ak_module.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        af_module.get_gold_info = lambda scope: {"data": {}}
        af_module.get_index_info = lambda idx, scope: {"data": {}}

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, af_module])
        cd.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))

        result = cd.run_morning_mode()

        # 被监控标的 = USER_HOLDINGS ∪ ETF_WATCH_LIST（去重）
        monitored = sorted(
            set(h["code"] for h in config.USER_HOLDINGS)
            | set(e["code"] for e in config.ETF_WATCH_LIST)
        )

        missing_premium = [c for c in monitored if f"premium_{c}" not in result]
        missing_tech = [c for c in monitored if f"tech_indicator_{c}" not in result]

        assert missing_premium == [], (
            f"morning mode missed premium_<code> for: {missing_premium}"
        )
        assert missing_tech == [], (
            f"morning mode missed tech_indicator_<code> for: {missing_tech}"
        )

    def test_morning_mode_includes_watch_only_codes(self, monkeypatch, tmp_path):
        """纯 watch 标的（如 159611）必须出现在 result 中。"""
        import importlib

        from src import config, logger as logger_module

        watch_only = sorted(
            set(e["code"] for e in config.ETF_WATCH_LIST)
            - set(h["code"] for h in config.USER_HOLDINGS)
        )
        assert watch_only, "测试前提:必须存在纯 watch 标的（不在 holdings）"

        importlib.reload(config)
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        importlib.reload(logger_module)

        from src import akshare_client as ak_module, akshare_fund_client as af_module
        importlib.reload(ak_module)
        importlib.reload(af_module)

        ohlcv_data = pd.DataFrame({
            "date": pd.date_range("2026-03-01", periods=60, freq="D").strftime("%Y-%m-%d").tolist(),
            "open": [3.8] * 60, "high": [4.0] * 60, "low": [3.6] * 60,
            "close": [3.8] * 60, "volume": [1_000_000] * 60, "amount": [3_800_000] * 60,
        })
        ak_module.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        af_module.get_gold_info = lambda scope: {"data": {}}
        af_module.get_index_info = lambda idx, scope: {"data": {}}

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, af_module])
        cd.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))

        result = cd.run_morning_mode()

        # 至少 1 个纯 watch 标的要有 premium 和 tech_indicator 结果 key
        for c in watch_only:
            assert f"premium_{c}" in result, (
                f"纯 watch 标的 {c} 缺少 premium_{c}; result keys 含 {sorted(result.keys())[:5]}..."
            )
            assert f"tech_indicator_{c}" in result, (
                f"纯 watch 标的 {c} 缺少 tech_indicator_{c}"
            )

    def test_morning_mode_calls_tech_for_all_monitored_codes(self, monkeypatch, tmp_path):
        """底层 _run_tech_indicators_for_holdings 必须收到完整的（去重）监控列表。"""
        import importlib

        from src import config, logger as logger_module

        importlib.reload(config)
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        importlib.reload(logger_module)

        from src import akshare_client as ak_module, akshare_fund_client as af_module
        importlib.reload(ak_module)
        importlib.reload(af_module)

        ohlcv_data = pd.DataFrame({
            "date": pd.date_range("2026-03-01", periods=60, freq="D").strftime("%Y-%m-%d").tolist(),
            "open": [3.8] * 60, "high": [4.0] * 60, "low": [3.6] * 60,
            "close": [3.8] * 60, "volume": [1_000_000] * 60, "amount": [3_800_000] * 60,
        })
        ak_module.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        af_module.get_gold_info = lambda scope: {"data": {}}
        af_module.get_index_info = lambda idx, scope: {"data": {}}

        cd = _reload(monkeypatch, tmp_path, extra_modules=[ak_module, af_module])
        cd.get_etf_history = lambda code: pd.DataFrame(ohlcv_data)
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 20))

        # 拦截底层 fetch 函数，记录传入的 holders 列表
        tech_calls = []
        premium_calls = []

        original_tech = cd._run_tech_indicators_for_holdings
        original_premium = cd._run_premium_rate_for_holdings

        def spy_tech(holders):
            tech_calls.append([h["code"] for h in holders])
            return original_tech(holders)

        def spy_premium(holders):
            premium_calls.append([h["code"] for h in holders])
            return original_premium(holders)

        monkeypatch.setattr(cd, "_run_tech_indicators_for_holdings", spy_tech)
        monkeypatch.setattr(cd, "_run_premium_rate_for_holdings", spy_premium)

        cd.run_morning_mode()

        # 监控标的 = 去重并集
        expected = sorted(
            set(h["code"] for h in config.USER_HOLDINGS)
            | set(e["code"] for e in config.ETF_WATCH_LIST)
        )

        # tech 至少一次调用传入完整列表（顺序：USER_HOLDINGS 先，WATCH 后）
        expected_set = set(expected)
        assert any(set(call) == expected_set for call in tech_calls), (
            f"Expected _run_tech_indicators_for_holdings called with {expected} (set), "
            f"got distinct call sets={[set(c) for c in tech_calls]}"
        )
        assert any(set(call) == expected_set for call in premium_calls), (
            f"Expected _run_premium_rate_for_holdings called with {expected} (set), "
            f"got distinct call sets={[set(c) for c in premium_calls]}"
        )