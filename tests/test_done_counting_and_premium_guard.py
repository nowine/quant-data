"""Tests for Done-counting semantics and the premium date-alignment guard.

Background (2026-09-29):
- "Done: X/Y" counted only status=="success" leaf tasks but included the
  errors/errors_extra keys in the denominator and collapsed the 27-fund nav
  dict into one task → a fully cache-hit run reported "0/8".
- THS snapshot source lag (最新-交易日 stuck at 9/24 while NAV reached 9/28)
  produced mixed-date premium artifacts (e.g. 510300 +2.25%).
"""

import datetime

import pandas as pd
import pytest

from src import config
import src.collector_daily as cd
from src.storage import save_csv


class TestSummarizeResult:
    def test_counts_leaf_tasks_and_ignores_error_lists(self):
        result = {
            "etf_snapshot": {"status": "skipped", "elapsed_sec": 0},
            "margin_sh": {"status": "success", "rows": 5},
            "nav": {
                "510300": {"status": "success", "rows": 100},
                "510500": {"status": "error", "error": "x"},
            },
            "errors": ["boom"],
            "errors_extra": ["extra boom"],
        }
        done, total, counts = cd._summarize_result(result)
        assert total == 4, "nav dict must expand into leaf tasks; errors lists excluded"
        assert done == 3, "skipped (cache_hit) must count as done"
        assert counts == {"skipped": 1, "success": 2, "error": 1}

    def test_empty_result(self):
        done, total, counts = cd._summarize_result({"errors": [], "errors_extra": []})
        assert done == 0
        assert total == 0
        assert counts == {}

    def test_deep_nesting(self):
        result = {
            "extra_nav": {"512480": {"status": "success", "rows": 1}},
            "premium_510300": {"status": "degraded", "rows": 0},
        }
        done, total, counts = cd._summarize_result(result)
        assert (done, total) == (1, 2)
        assert counts == {"success": 1, "degraded": 1}


class TestPremiumDateGuard:
    def _write_snapshot(self, tmp_path, trade_date):
        d = tmp_path / "daily"
        d.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(
            {
                "代码": ["510300"],
                "名称": ["沪深300ETF"],
                "最新价": [4.5127],
                "最新-交易日": [trade_date],
            }
        )
        save_csv(df, str(d / "etf_snapshot_2026-05-20.csv"))

    def _nav(self, fsrq):
        return {"data": {"nav_history": {"items": [{"FSRQ": fsrq, "DWJZ": "4.4133"}]}}}

    def _holders(self):
        return [{"code": "510300", "name": "沪深300ETF", "sector": None}]

    def test_date_mismatch_skips_row(self, monkeypatch, tmp_path):
        """THS lag case: snapshot 9/24-style date vs NAV 9/28 → no row, no artifact."""
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 21))
        self._write_snapshot(tmp_path, "2026-05-18")
        monkeypatch.setattr(cd, "get_nav_history", lambda code, rng: self._nav("2026-05-20"))

        df = cd._run_premium_rate_for_holdings(self._holders())
        assert df.empty, "mixed-date premium must not be computed"

    def test_date_match_computes_premium(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 21))
        self._write_snapshot(tmp_path, "2026-05-20")
        monkeypatch.setattr(cd, "get_nav_history", lambda code, rng: self._nav("2026-05-20"))

        df = cd._run_premium_rate_for_holdings(self._holders())
        assert len(df) == 1
        assert df.iloc[0]["premium_pct"] == pytest.approx((4.5127 / 4.4133 - 1) * 100, abs=1e-3)

    def test_missing_dates_keep_legacy_behavior(self, monkeypatch, tmp_path):
        """Rows without a trade-date (THS junk rows) still compute — no silent kill."""
        monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
        monkeypatch.setattr(cd, "today", lambda: datetime.date(2026, 5, 21))
        self._write_snapshot(tmp_path, "")
        monkeypatch.setattr(cd, "get_nav_history", lambda code, rng: self._nav("2026-05-20"))

        df = cd._run_premium_rate_for_holdings(self._holders())
        assert len(df) == 1
