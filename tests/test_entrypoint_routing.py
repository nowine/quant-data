"""Tests for scripts/entrypoint.sh — the unified cron-invocation seam.

Per ADR-004 + the unified-image decision (2026-08-21):
- All 4 collectors are dispatched through one entrypoint script.
- Public contract: `--script {daily|weekly|monthly|quarterly}` + forwarded args.
- Wrong / missing script → non-zero exit (cron alert fires).

Hermetic since 2026-09-29: routing tests previously executed the REAL
collector via subprocess on trading days — a full-suite run then fetched
live akshare data and wrote 91 *_<today>.csv files into the repo's
production data/ tree (incident: 00:18 writes cached-hit by the 07:00
report). Now a `python3` shim replaces the interpreter: we assert only the
routing (which script + args entrypoint dispatches), never run collection.
QUANT_DATA_DIR is still pointed at a quarantine dir as belt-and-suspenders
for any future test that runs real python.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = PROJECT_ROOT / "scripts" / "entrypoint.sh"
EXAMPLE_CONFIG = PROJECT_ROOT / "examples" / "etf_config.example.json"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"

pytestmark = pytest.mark.skipif(
    not VENV_PYTHON.exists(),
    reason="repo .venv not available; entrypoint.sh needs a python3 with pandas",
)


def _make_python_shim(shim_dir: Path) -> None:
    """A fake python3 that echoes its argv so routing is assertable."""
    shim = shim_dir / "python3"
    shim.write_text('#!/bin/bash\necho "SHIM_PY $@"\nexit 0\n')
    shim.chmod(0o755)


@pytest.fixture(scope="module")
def shim_env(tmp_path_factory):
    """(shim_dir, quarantine_dir) shared by routing tests in this module."""
    shim_dir = tmp_path_factory.mktemp("shim-bin")
    _make_python_shim(shim_dir)
    quarantine = tmp_path_factory.mktemp("quarantine")
    return shim_dir, quarantine


def _run(
    args,
    *,
    expect_exit: int = 0,
    timeout: int = 60,
    shim_dir: Path | None = None,
    quarantine: Path | None = None,
) -> subprocess.CompletedProcess:
    # Prepend the repo venv so entrypoint.sh's `python3` resolves predictably;
    # when shim_dir is given it wins, so no real collection ever runs.
    path_parts = []
    if shim_dir is not None:
        path_parts.append(str(shim_dir))
    path_parts.append(str(PROJECT_ROOT / ".venv" / "bin"))
    path_parts.append(os.environ["PATH"])
    env = {
        **os.environ,
        "PYTHONPATH": ".",
        "PATH": os.pathsep.join(path_parts),
    }
    if quarantine is not None:
        # Never let a child collector write into the repo's data/ tree.
        env["QUANT_DATA_DIR"] = str(quarantine)
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
    def test_daily_routes_with_mode_morning(self, shim_env):
        """--script daily --mode morning dispatches to collector_daily."""
        shim_dir, quarantine = shim_env
        result = _run(
            ["--script", "daily", "--mode", "morning", "--config", str(EXAMPLE_CONFIG)],
            timeout=60,
            shim_dir=shim_dir,
            quarantine=quarantine,
        )
        assert result.returncode == 0
        assert "src/collector_daily.py" in result.stdout
        assert "--mode morning" in result.stdout

    def test_daily_routes_with_mode_close(self, shim_env):
        """--script daily --mode close dispatches to collector_daily."""
        shim_dir, quarantine = shim_env
        result = _run(
            ["--script", "daily", "--mode", "close", "--config", str(EXAMPLE_CONFIG)],
            timeout=60,
            shim_dir=shim_dir,
            quarantine=quarantine,
        )
        assert result.returncode == 0
        assert "src/collector_daily.py" in result.stdout
        assert "--mode close" in result.stdout

    def test_weekly_routes(self, shim_env):
        """--script weekly → collector_weekly."""
        shim_dir, quarantine = shim_env
        result = _run(
            ["--script", "weekly", "--config", str(EXAMPLE_CONFIG)],
            timeout=60,
            shim_dir=shim_dir,
            quarantine=quarantine,
        )
        assert result.returncode == 0
        assert "src/collector_weekly.py" in result.stdout

    def test_monthly_routes(self, shim_env):
        """--script monthly → collector_monthly."""
        shim_dir, quarantine = shim_env
        result = _run(
            ["--script", "monthly", "--config", str(EXAMPLE_CONFIG)],
            timeout=60,
            shim_dir=shim_dir,
            quarantine=quarantine,
        )
        assert result.returncode == 0
        assert "src/collector_monthly.py" in result.stdout

    def test_quarterly_routes(self, shim_env):
        """--script quarterly → collector_quarterly."""
        shim_dir, quarantine = shim_env
        result = _run(
            ["--script", "quarterly", "--config", str(EXAMPLE_CONFIG)],
            timeout=60,
            shim_dir=shim_dir,
            quarantine=quarantine,
        )
        assert result.returncode == 0
        assert "src/collector_quarterly.py" in result.stdout


# ── Arg forwarding ────────────────────────────────────────────────────────────


class TestArgForwarding:
    def test_extra_holdings_forwarded(self, shim_env):
        """--extra-holdings JSON must pass through to collector_daily."""
        shim_dir, quarantine = shim_env
        result = _run(
            [
                "--script",
                "daily",
                "--mode",
                "morning",
                "--config",
                str(EXAMPLE_CONFIG),
                "--extra-holdings",
                '[{"code": "512480"}]',
            ],
            timeout=60,
            shim_dir=shim_dir,
            quarantine=quarantine,
        )
        assert result.returncode == 0
        assert "--extra-holdings" in result.stdout
        assert "512480" in result.stdout
