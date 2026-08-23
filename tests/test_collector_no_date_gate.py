"""Tests for removing date-based early-exit from weekly / quarterly collectors.

Background (皮皮 collected issue list, 2026-08-23):
    - collector_weekly.py had `if today().weekday() != 0: sys.exit(0)` which
      blocked ALL weekly collection when the cron (Sunday 11:00) actually fired.
      The cron job / collector / SKILL.md were three-way inconsistent.
    - collector_quarterly.py had `if not is_quarterly_run_day(): sys.exit(0)`
      with the same problem.

Design (主人 Q26, Q27, Q29-B, 2026-08-23):
    - weekly / quarterly: NEVER early-exit on date. Collectors accept any day;
      akshare calls return empty/degraded on weekends (real network behavior),
      and the collector surfaces that as `status + reason` for the caller.
    - daily: KEEP the weekday check. Owner said "日报需要做交易日检查,因为日报
      关注的是交易日数据" (preserved scope-wise).
    - All collectors: on akshare/network failure, return structured
      `status="error"` with `reason` (human-readable) + `exception_type` (machine)
      fields. Caller (皮皮) decides how to follow up (use cache, mark degraded, skip).

This file lives next to test_collector_weekly.py etc. so the file-level test
cohesion is preserved. It tests the `_main()` CLI entry point boundary only
(date-gate removal), not the inner akshare call paths (those already have
mock coverage in test_collector_*.py).
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path
from datetime import date
from unittest.mock import patch


class TestDateGateRemoval:
    """Date-based early-exit removed from weekly + quarterly; daily preserved."""

    def setup_method(self, method):
        """Reload src.config so each test can call init_config() fresh.

        Without this, the 2nd test in this class hits the 'init_config called
        twice' RuntimeError from src/config.py (intentional guard, not a bug).
        """
        import src.config as cfg
        importlib.reload(cfg)

    def test_weekly_runs_on_non_monday(self, tmp_path):
        """Weekly collector must NOT early-exit on non-Monday (issue 1, L310-311).

        We patch `today()` inside the collector module to simulate a Sunday
        (2026-08-23 was a Sunday) and verify the collector runs instead of
        sys.exit(0) with the old "not Monday" message.
        """
        from src import collector_weekly
        from datetime import date as _date

        # 2026-08-23 is a Sunday
        sunday = _date(2026, 8, 23)
        with patch.object(collector_weekly, "today", return_value=sunday):
            # _main reads sys.argv — feed minimal args to hit the gate
            with patch.object(sys, "argv", [
                "collector_weekly.py",
                "--config", "/root/secureshare/files/ETF轮动分析框架/config/etf_config.json",
            ]):
                # Should NOT print "not Monday — weekly collector should run..."
                # Should call run_weekly() instead. We mock run_weekly to avoid
                # hitting akshare and to detect call.
                with patch.object(
                    collector_weekly, "run_weekly",
                    return_value={"etf_scale": {"status": "success", "rows": 5}},
                ) as mock_rw:
                    with patch("builtins.print"):  # suppress stdout noise
                        try:
                            collector_weekly.main()
                        except SystemExit as e:
                            # Old behavior: SystemExit(0) on non-Monday.
                            # New behavior: should reach run_weekly() call.
                            # If we get a SystemExit(0) here, gate is still in place.
                            if e.code == 0 and not mock_rw.called:
                                raise AssertionError(
                                    "Weekly collector still early-exits on non-Monday"
                                )
                    assert mock_rw.called, (
                        "Weekly collector should call run_weekly() on non-Monday"
                    )

    def test_quarterly_runs_on_non_quarter_day(self):
        """Quarterly collector must NOT early-exit on non-quarter day (issue 2, L185).

        2026-08-23 is August — definitely not a quarterly run day.
        """
        from src import collector_quarterly
        from datetime import date as _date

        non_quarter = _date(2026, 8, 23)
        with patch.object(collector_quarterly, "today", return_value=non_quarter):
            with patch.object(sys, "argv", [
                "collector_quarterly.py",
                "--config", "/root/secureshare/files/ETF轮动分析框架/config/etf_config.json",
            ]):
                with patch.object(
                    collector_quarterly, "run_quarterly",
                    return_value={"fund_holdings": {"status": "success", "rows": 3}},
                ) as mock_rq:
                    with patch("builtins.print"):
                        try:
                            collector_quarterly.main()
                        except SystemExit as e:
                            if e.code == 0 and not mock_rq.called:
                                raise AssertionError(
                                    "Quarterly collector still early-exits on non-quarter day"
                                )
                    assert mock_rq.called, (
                        "Quarterly collector should call run_quarterly() on non-quarter day"
                    )

    def test_daily_still_skips_on_weekend(self):
        """Daily collector MUST still early-exit on weekend (Q26 preserved).

        2026-08-23 is a Sunday — daily should print 'not a trading day' and exit 0.
        This locks the current behavior so we don't accidentally drift into the
        'collectors never early-exit' interpretation on daily.
        """
        from src import collector_daily
        from datetime import date as _date

        sunday = _date(2026, 8, 23)
        with patch.object(collector_daily, "today", return_value=sunday):
            with patch.object(sys, "argv", [
                "collector_daily.py",
                "--config", "/root/secureshare/files/ETF轮动分析框架/config/etf_config.json",
                "--mode", "morning",
            ]):
                # We expect SystemExit(0) BEFORE any run_*_mode() call.
                with patch.object(
                    collector_daily, "run_morning_mode",
                    return_value={"task_a": {"status": "success"}},
                ) as mock_rmm:
                    with patch.object(
                        collector_daily, "run_close_mode",
                        return_value={"task_b": {"status": "success"}},
                    ) as mock_rcm:
                        with patch("builtins.print"):
                            with pytest.raises(SystemExit) as exc_info:
                                collector_daily.main()
                            assert exc_info.value.code == 0, (
                                f"Daily weekend exit should be 0, got {exc_info.value.code}"
                            )
                            assert not mock_rmm.called, (
                                "Daily weekend should NOT call run_morning_mode"
                            )
                            assert not mock_rcm.called, (
                                "Daily weekend should NOT call run_close_mode"
                            )


class TestReasonOnError:
    """akshare failures should return status='error' with reason + exception_type (Q27)."""

    def test_collect_csv_returns_reason_on_chunked_encoding_error(self, tmp_path):
        """_collect_csv must catch ChunkedEncodingError (akshare Sunday fail) and
        return dict with status='error', reason=human-readable, exception_type='ChunkedEncodingError'.
        """
        from src import collector_weekly
        from requests.exceptions import ChunkedEncodingError

        # Build a mock filepath that doesn't exist yet (so cache-hit branch skipped)
        filepath = tmp_path / "etf_scale_test.csv"
        assert not filepath.exists()

        def fake_fetch():
            raise ChunkedEncodingError("IncompleteRead(0 bytes read)")

        errors = []
        result = collector_weekly._collect_csv(
            name="etf_scale",
            fetch_fn=fake_fetch,
            filepath=filepath,
            errors=errors,
            suggestion="check data source",
        )

        assert result["status"] == "error", f"Expected 'error', got {result['status']}"
        assert "reason" in result, "Missing 'reason' field"
        assert result.get("exception_type") == "ChunkedEncodingError", (
            f"exception_type should be 'ChunkedEncodingError', got: {result.get('exception_type')}"
        )
        # Reason is a human-readable hint (Chinese) — it should mention the source
        # / weekend angle but NOT necessarily the raw exception class name.
        # The class name lives in the separate `exception_type` field.
        assert any(
            keyword in result["reason"]
            for keyword in ("数据源", "周日", "节假日", "连接中断", "不完整")
        ), f"reason should hint at source/weekend, got: {result['reason']}"


# Need pytest for raises — import at top for the daily test
import pytest
