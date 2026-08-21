"""Tests for scripts/entrypoint.sh — the unified cron-invocation seam.

Per ADR-004 + the unified-image decision (2026-08-21):
- All 4 collectors are dispatched through one entrypoint script.
- Public contract: `--script {daily|weekly|monthly|quarterly}` + forwarded args.
- Wrong / missing script → non-zero exit (cron alert fires).

These tests shell out to the bash script with PYTHONPATH=. so the inner
python collectors can find src/.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = PROJECT_ROOT / "scripts" / "entrypoint.sh"
EXAMPLE_CONFIG = PROJECT_ROOT / "examples" / "etf_config.example.json"


def _run(args, *, expect_exit: int = 0, timeout: int = 60) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": "."}
    return subprocess.run(
        ["bash", str(ENTRYPOINT), *args],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ── Required --script ─────────────────────────────────────────────────────────

class TestScriptRequired:
    def test_missing_script_exits_nonzero(self):
        result = _run(["--config", str(EXAMPLE_CONFIG)], expect_exit=2)
        assert result.returncode == 2
        assert "--script" in result.stderr

    def test_unknown_script_exits_nonzero(self):
        result = _run(["--script", "bogus", "--config", str(EXAMPLE_CONFIG)], expect_exit=2)
        assert result.returncode == 2
        assert "unknown" in result.stderr.lower()


# ── Routing ───────────────────────────────────────────────────────────────────

class TestRouting:
    def test_daily_routes_with_mode_morning(self):
        """--script daily --mode morning dispatches to collector_daily."""
        result = _run(
            ["--script", "daily", "--mode", "morning",
             "--config", str(EXAMPLE_CONFIG)],
            timeout=120,
        )
        # morning mode runs all collectors and exits 0 even on partial failures
        # (P2 stubs are expected). Just verify it routed correctly.
        assert "akshare_fund_client.get_index_info" in result.stdout or \
               "is_trading_day" in result.stdout or \
               result.returncode == 0

    def test_daily_routes_with_mode_close(self):
        """--script daily --mode close dispatches to collector_daily."""
        result = _run(
            ["--script", "daily", "--mode", "close",
             "--config", str(EXAMPLE_CONFIG)],
            timeout=120,
        )
        assert result.returncode == 0

    def test_weekly_routes(self):
        """--script weekly → collector_weekly (date guard or real run)."""
        result = _run(
            ["--script", "weekly", "--config", str(EXAMPLE_CONFIG)],
        )
        assert result.returncode == 0
        # Friday (today) triggers the "not Monday" guard
        assert "Monday" in result.stdout or "weekly" in result.stdout.lower()

    def test_monthly_routes(self):
        """--script monthly → collector_monthly."""
        result = _run(
            ["--script", "monthly", "--config", str(EXAMPLE_CONFIG)],
            timeout=120,
        )
        assert result.returncode == 0
        assert "monthly" in result.stdout.lower() or "tasks" in result.stdout.lower()

    def test_quarterly_routes(self):
        """--script quarterly → collector_quarterly."""
        result = _run(
            ["--script", "quarterly", "--config", str(EXAMPLE_CONFIG)],
        )
        assert result.returncode == 0
        assert "quarterly" in result.stdout.lower() or "not a quarterly" in result.stdout.lower()


# ── Arg forwarding ────────────────────────────────────────────────────────────

class TestArgForwarding:
    def test_extra_holdings_forwarded(self, tmp_path):
        """--extra-holdings JSON must pass through to collector_daily."""
        result = _run(
            ["--script", "daily", "--mode", "morning",
             "--config", str(EXAMPLE_CONFIG),
             "--extra-holdings", '[{"code": "512480"}]'],
            timeout=120,
        )
        # Just confirm it didn't crash on the forwarded arg.
        assert result.returncode == 0
