"""Tests for the --extra-holdings wiring in collector_daily.

Seam under test: `_resolve_extra_holdings(raw_arg, existing_codes)`
    Pure function (given the mocked akshare enrichment). Takes the CLI
    string, parses + enriches + dedups against an existing code set.

Plus a small set of integration tests for run_close_mode/run_morning_mode
that verify extra-holdings triggers the right sub-tasks without breaking
the default path. These mock akshare and the snapshot/etf_history sources
so no network calls happen.

Public contract (per ADR-003 §CLI 契约):
- Default (no --extra-holdings flag): behavior identical to today.
- extra flag passed → parsed → enriched via akshare (mocked) →
  dedup'd against existing codes → run for the surviving codes.
- Dedup emits one warning log line per duplicate.
- Failures during extra-holdings collection land in `result["errors_extra"]`,
  not in `result["errors"]`.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

import src.collector_daily as cd


# ── helpers ────────────────────────────────────────────────────────────────────

def _akshare_enrichment(codes: list[str]) -> pd.DataFrame:
    """Mock enrichment: always returns the code with a name derived from it."""
    return pd.DataFrame(
        {
            "code": [str(c) for c in codes],
            "name": [f"MockETF-{c}" for c in codes],
            "sector": [None] * len(codes),
        }
    )


# ── _resolve_extra_holdings (the helper seam) ─────────────────────────────────

class TestResolveExtraHoldings:
    def test_empty_arg_returns_empty_list(self):
        result = cd._resolve_extra_holdings("", existing_codes={"159530"})
        assert result == []

    def test_whitespace_arg_returns_empty_list(self):
        result = cd._resolve_extra_holdings("   \n  ", existing_codes=set())
        assert result == []

    def test_single_new_code(self):
        with patch(
            "src.collector_daily.build_extra_holdings_set",
            return_value=_akshare_enrichment(["512480"]),
        ):
            result = cd._resolve_extra_holdings(
                '[{"code": "512480"}]', existing_codes={"159530"}
            )
        assert len(result) == 1
        assert result[0]["code"] == "512480"
        assert result[0]["name"] == "MockETF-512480"
        assert result[0]["sector"] is None

    def test_dedup_against_existing(self):
        """Codes already in existing_codes are filtered out, with a warn log."""
        with patch(
            "src.collector_daily.build_extra_holdings_set",
            return_value=_akshare_enrichment(["159530", "512480"]),
        ):
            result = cd._resolve_extra_holdings(
                '[{"code": "159530"}, {"code": "512480"}]',
                existing_codes={"159530", "588750"},
            )
        assert [r["code"] for r in result] == ["512480"]

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="extra-holdings"):
            cd._resolve_extra_holdings("not-json", existing_codes=set())

    def test_akshare_failure_returns_empty_list(self):
        """If akshare fails, _resolve_extra_holdings returns [] (best-effort)."""
        with patch(
            "src.collector_daily.build_extra_holdings_set",
            side_effect=RuntimeError("akshare down"),
        ):
            result = cd._resolve_extra_holdings(
                '[{"code": "512480"}]', existing_codes=set()
            )
        assert result == []

    def test_existing_codes_defaults_to_empty(self):
        """existing_codes defaults to set() when not provided."""
        with patch(
            "src.collector_daily.build_extra_holdings_set",
            return_value=_akshare_enrichment(["512480"]),
        ):
            result = cd._resolve_extra_holdings('[{"code": "512480"}]')
        assert len(result) == 1


# ── CLI integration: extra-holdings flows through to run_*_mode ───────────────

class TestRunCloseModeWithExtra:
    def test_default_run_unchanged_when_no_extra_flag(self, monkeypatch):
        """No extra-holdings → no extra NAV calls; same shape as today."""
        monkeypatch.setattr(cd, "_collect_csv", lambda *a, **kw: {"status": "success"})
        monkeypatch.setattr(cd, "_collect_json", lambda *a, **kw: {"status": "success"})

        with patch("src.collector_daily._resolve_extra_holdings") as mock_resolve:
            # _resolve_extra_holdings is always called; returns [] for None arg.
            mock_resolve.return_value = []
            result = cd.run_close_mode()

        # Called once with extra=None; dedup set comes from ETF_WATCH_LIST.
        mock_resolve.assert_called_once()
        call_args = mock_resolve.call_args
        assert call_args[0][0] is None  # the raw arg
        assert "errors_extra" in result
        assert result["errors_extra"] == []
        assert "errors" in result

    def test_extra_holdings_triggers_nav_only(self, monkeypatch):
        """close mode + extra → NAV tasks for the extra codes (per ADR Q7=A)."""
        monkeypatch.setattr(cd, "_collect_csv", lambda *a, **kw: {"status": "success"})
        monkeypatch.setattr(cd, "_collect_json", lambda *a, **kw: {"status": "success"})

        monkeypatch.setattr(
            cd,
            "_resolve_extra_holdings",
            lambda raw, existing_codes=set(): [
                {"code": "512480", "name": "半导体ETF", "sector": None}
            ],
        )

        captured_nav_paths = []
        real_collect = cd._collect_csv

        def capture_collect(name, fn, path, errors, **kw):
            if name.startswith("extra_nav_"):
                captured_nav_paths.append(name)
            return {"status": "success"}

        monkeypatch.setattr(cd, "_collect_csv", capture_collect)

        result = cd.run_close_mode(extra='[{"code": "512480"}]')

        assert any(n == "extra_nav_512480" for n in captured_nav_paths), (
            f"close mode should run NAV for extra 512480; got {captured_nav_paths}"
        )


class TestRunMorningModeWithExtra:
    def test_default_run_unchanged_when_no_extra_flag(self, monkeypatch):
        monkeypatch.setattr(cd, "_collect_csv", lambda *a, **kw: {"status": "success"})
        monkeypatch.setattr(cd, "_collect_json", lambda *a, **kw: {"status": "success"})

        with patch("src.collector_daily._resolve_extra_holdings") as mock_resolve:
            mock_resolve.return_value = []
            result = cd.run_morning_mode()

        mock_resolve.assert_called_once()
        assert result["errors_extra"] == []

    def test_extra_holdings_triggers_premium_and_tech(self, monkeypatch):
        """morning mode + extra → premium + tech for extra codes (per ADR Q8=A)."""
        monkeypatch.setattr(cd, "_collect_csv", lambda *a, **kw: {"status": "success"})
        monkeypatch.setattr(cd, "_collect_json", lambda *a, **kw: {"status": "success"})

        monkeypatch.setattr(
            cd,
            "_resolve_extra_holdings",
            lambda raw, existing_codes=set(): [
                {"code": "512480", "name": "半导体ETF", "sector": None}
            ],
        )

        captured_names = []
        def capture(name, fn, path, errors, **kw):
            captured_names.append(name)
            return {"status": "success"}

        monkeypatch.setattr(cd, "_collect_csv", capture)

        result = cd.run_morning_mode(extra='[{"code": "512480"}]')

        assert "extra_premium_512480" in captured_names, captured_names
        assert "extra_tech_512480" in captured_names, captured_names

    def test_extra_holdings_failure_lands_in_errors_extra(self, monkeypatch):
        """Failures during extra collection go to errors_extra, NOT errors."""
        def collect_with_fail(name, fn, path, errors, **kw):
            if name.startswith("extra_"):
                errors.append(f"FAILED: {name}")  # simulate _collect error path
                return {"status": "error", "message": f"{name} failed"}
            return {"status": "success"}

        monkeypatch.setattr(cd, "_collect_csv", collect_with_fail)
        monkeypatch.setattr(cd, "_collect_json", lambda *a, **kw: {"status": "success"})

        monkeypatch.setattr(
            cd,
            "_resolve_extra_holdings",
            lambda raw, existing_codes=set(): [
                {"code": "512480", "name": "半导体ETF", "sector": None}
            ],
        )

        result = cd.run_morning_mode(extra='[{"code": "512480"}]')

        # Main errors must be empty; extra errors must contain the failures.
        assert result["errors"] == []
        assert len(result["errors_extra"]) >= 1
        assert any("extra_premium_512480" in e for e in result["errors_extra"])


# ── argparse: --extra-holdings parsed and forwarded ───────────────────────────

class TestCLIExtraHoldings:
    def test_cli_parses_extra_holdings(self, monkeypatch):
        """main() with --extra-holdings forwards raw string to run_morning_mode."""
        captured = {}

        def mock_morning(extra=None):
            captured["extra"] = extra
            return {"errors": [], "errors_extra": []}

        monkeypatch.setattr(cd, "run_morning_mode", mock_morning)
        monkeypatch.setattr(cd, "is_trading_day", lambda: True)
        monkeypatch.setattr(
            "sys.argv",
            ["collector_daily.py", "--mode", "morning",
             "--extra-holdings", '[{"code": "512480"}]'],
        )

        cd.main()

        assert captured["extra"] == '[{"code": "512480"}]'

    def test_cli_default_extra_is_none(self, monkeypatch):
        """No --extra-holdings → run_morning_mode called with extra=None."""
        captured = {}

        def mock_morning(extra=None):
            captured["extra"] = extra
            return {"errors": [], "errors_extra": []}

        monkeypatch.setattr(cd, "run_morning_mode", mock_morning)
        monkeypatch.setattr(cd, "is_trading_day", lambda: True)
        monkeypatch.setattr(
            "sys.argv",
            ["collector_daily.py", "--mode", "morning"],
        )

        cd.main()

        assert captured["extra"] is None