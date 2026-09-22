"""Tests for src/extra_holdings.build_extra_holdings_set — akshare enrichment seam.

Seam: `build_extra_holdings_set(codes: list[str]) -> pd.DataFrame`.

Contract (per ADR-003, 2026-08-20):
- Input: list of 6-digit code strings.
- Output: DataFrame with columns [code, name, sector], one row per input code.
- name comes from akshare.fund_name_em() (cached at ~/.cache/quant-data/fund_name.csv, 24h TTL).
- sector is always None (akshare has no industry sector API; documented in ADR).
- Codes missing from the akshare table get name="" (empty string), sector=None —
  they DO appear in the output (callers shouldn't have to filter).
- The function NEVER raises on akshare errors; it falls back to an empty
  result (all rows have name="", sector=None). Callers detect data quality
  via the empty name column, not via exceptions. This matches the "extra
  holdings are best-effort, don't break the run" semantics.
- This seam is mocked at the akshare boundary in these tests; a separate
  manual verification (commit 3 pre-merge) hits the real API.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.extra_holdings import (
    CACHE_FILENAME,
    CACHE_TTL_HOURS,
    build_extra_holdings_set,
    _cache_path,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _akshare_df() -> pd.DataFrame:
    """Sample fund_name_em() output (subset)."""
    return pd.DataFrame(
        {
            "基金代码": ["159530", "512480", "512690", "510300"],
            "基金简称": [
                "机器人ETF易方达",
                "半导体ETF国联安",
                "白酒ETF鹏华",
                "沪深300ETF华泰柏瑞",
            ],
            "基金类型": [
                "指数型-股票",
                "指数型-股票",
                "指数型-股票",
                "指数型-股票",
            ],
        }
    )


# ── path / constants ──────────────────────────────────────────────────────────

class TestCachePath:
    def test_cache_filename_is_stable(self):
        assert CACHE_FILENAME == "fund_name.csv"

    def test_cache_ttl_is_24_hours(self):
        assert CACHE_TTL_HOURS == 24

    def test_cache_path_lives_in_user_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        path = _cache_path()
        assert path == Path(tmp_path) / ".cache" / "quant-data" / "fund_name.csv"


# ── cache hit (no akshare call) ────────────────────────────────────────────────

class TestCacheHit:
    def test_fresh_cache_skips_akshare(self, tmp_path, monkeypatch):
        """If cache file exists and is fresh, akshare is NOT called."""
        monkeypatch.setenv("HOME", str(tmp_path))
        cache_path = _cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Write a fresh cache file
        cached = _akshare_df()
        cached.to_csv(cache_path, index=False)

        with patch("src.extra_holdings._fetch_fund_name_from_akshare") as mock_fetch:
            df = build_extra_holdings_set(["159530", "512480"])

        mock_fetch.assert_not_called()
        assert sorted(df["code"].tolist()) == ["159530", "512480"]
        assert df.set_index("code").loc["159530", "name"] == "机器人ETF易方达"
        assert df.set_index("code").loc["512480", "name"] == "半导体ETF国联安"


# ── cache miss / stale → fetch from akshare ───────────────────────────────────

class TestCacheMiss:
    def test_no_cache_file_fetches_and_writes(self, tmp_path, monkeypatch):
        """First run: no cache, must fetch from akshare and write cache."""
        monkeypatch.setenv("HOME", str(tmp_path))
        cache_path = _cache_path()

        with patch(
            "src.extra_holdings._fetch_fund_name_from_akshare",
            return_value=_akshare_df(),
        ) as mock_fetch:
            df = build_extra_holdings_set(["159530"])

        mock_fetch.assert_called_once()
        assert cache_path.exists(), "cache file should be written after fetch"
        # Verify cache content (re-read)
        cached = pd.read_csv(cache_path, dtype={"基金代码": str})
        assert "159530" in cached["基金代码"].tolist()
        assert df.iloc[0]["name"] == "机器人ETF易方达"

    def test_stale_cache_triggers_refresh(self, tmp_path, monkeypatch):
        """Cache file older than TTL → fetch again, overwrite cache."""
        monkeypatch.setenv("HOME", str(tmp_path))
        cache_path = _cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Write a cache file and backdate its mtime past TTL
        stale = _akshare_df().iloc[:1]  # only 159530
        stale.to_csv(cache_path, index=False)
        import time
        old_time = time.time() - (CACHE_TTL_HOURS * 3600 + 60)
        import os
        os.utime(cache_path, (old_time, old_time))

        # akshare now returns a *different* 159530 name → confirms refresh happened
        refreshed = _akshare_df()
        refreshed.loc[
            refreshed["基金代码"] == "159530", "基金简称"
        ] = "机器人ETF易方达-RENAMED"

        with patch(
            "src.extra_holdings._fetch_fund_name_from_akshare",
            return_value=refreshed,
        ):
            df = build_extra_holdings_set(["159530"])

        assert df.iloc[0]["name"] == "机器人ETF易方达-RENAMED"


# ── partial / missing codes ──────────────────────────────────────────────────

class TestPartialMatch:
    def test_unknown_code_yields_empty_name(self, tmp_path, monkeypatch):
        """Codes missing from akshare must still appear in output with name=''."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "src.extra_holdings._fetch_fund_name_from_akshare",
            return_value=_akshare_df(),
        ):
            df = build_extra_holdings_set(["159530", "999999"])

        assert len(df) == 2
        assert df.set_index("code").loc["159530", "name"] == "机器人ETF易方达"
        assert df.set_index("code").loc["999999", "name"] == ""

    def test_empty_input_returns_empty_dataframe(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch("src.extra_holdings._fetch_fund_name_from_akshare") as mock_fetch:
            df = build_extra_holdings_set([])
        mock_fetch.assert_not_called()
        assert df.empty
        assert list(df.columns) == ["code", "name", "sector"]


# ── akshare failure fallback ─────────────────────────────────────────────────

class TestAkshareFailure:
    def test_akshare_exception_yields_empty_names(self, tmp_path, monkeypatch):
        """Akshare fails → all rows present, name='', akshare NOT cached."""
        monkeypatch.setenv("HOME", str(tmp_path))
        cache_path = _cache_path()

        def boom():
            raise RuntimeError("akshare source down")

        with patch("src.extra_holdings._fetch_fund_name_from_akshare", side_effect=boom):
            df = build_extra_holdings_set(["159530", "512480"])

        assert len(df) == 2
        assert (df["name"] == "").all()
        assert (df["sector"].isna()).all()
        assert not cache_path.exists(), "failed fetch must not pollute cache"


# ── output shape stability ───────────────────────────────────────────────────

class TestOutputShape:
    def test_columns_are_stable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch(
            "src.extra_holdings._fetch_fund_name_from_akshare",
            return_value=_akshare_df(),
        ):
            df = build_extra_holdings_set(["159530"])
        assert list(df.columns) == ["code", "name", "sector"]

    def test_dtype_code_is_string(self, tmp_path, monkeypatch):
        """Leading-zero codes must round-trip as strings, not ints."""
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch(
            "src.extra_holdings._fetch_fund_name_from_akshare",
            return_value=_akshare_df(),
        ):
            df = build_extra_holdings_set(["159530"])
        assert df["code"].dtype.kind == "O", "code must be object/string dtype"
        assert df["code"].iloc[0] == "159530"