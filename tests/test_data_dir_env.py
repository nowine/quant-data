"""Tests for DATA_DIR env override (ADR-004 + containerization support).

Background:
    - quant-data is now run inside a podman container for production isolation
      (commit 848b7f5 introduced the unified collector image on 2026-08-21).
    - Inside the container, the host path `/root/secureshare/files/ETF轮动分析框架/data`
      is NOT visible (rootless podman mount-namespace isolation — `/root` is
      only accessible to the host, not to the container's bind mounts).
    - docker-compose.yml mounts the host data dir to `/data` inside the
      container. So inside the container, DATA_DIR must resolve to `/data/data`
      (i.e. /data + the trailing "/data" subdir).
    - Dev / unit-test paths still expect the host absolute path.

Design (per 主人 Q17-Q20, 2026-08-23):
    - Env var: QUANT_DATA_DIR
    - Default: unchanged host absolute path (back-compat)
    - Empty string in env: treat as "not set", use default (no fail-fast on empty)
    - Invalid path in env: still use it — collector will fail at first write,
      which is the same UX as a wrong hardcode (no extra validation cost here).

This file is intentionally separate from tests/test_config.py because it
specifically tests containerization behavior; keeping it isolated makes it
easy to skip on hosts that don't have a `podman` runtime.
"""

import os
import importlib
import pytest


_HOST_DEFAULT = "/root/secureshare/files/ETF轮动分析框架/data"
_CONTAINER_PATH = "/data/data"


class TestDataDirEnv:
    """DATA_DIR env override behavior."""

    def setup_method(self):
        """Reset module state before each test so env changes take effect."""
        # Drop any cached env override so we re-read module-level constants.
        os.environ.pop("QUANT_DATA_DIR", None)
        import src.config as cfg
        importlib.reload(cfg)

    def teardown_method(self):
        """Restore env to a clean state after each test."""
        os.environ.pop("QUANT_DATA_DIR", None)
        import src.config as cfg
        importlib.reload(cfg)

    def test_default_is_host_absolute_path(self):
        """Without QUANT_DATA_DIR set, DATA_DIR = legacy host path."""
        from src.config import DATA_DIR
        assert DATA_DIR == _HOST_DEFAULT

    def test_env_override_changes_data_dir(self):
        """QUANT_DATA_DIR env var must override the default at module import time."""
        os.environ["QUANT_DATA_DIR"] = _CONTAINER_PATH
        import src.config as cfg
        importlib.reload(cfg)
        try:
            assert cfg.DATA_DIR == _CONTAINER_PATH
        finally:
            importlib.reload(cfg)

    def test_empty_env_falls_back_to_default(self):
        """Empty QUANT_DATA_DIR must not silently flip to ''; use default."""
        os.environ["QUANT_DATA_DIR"] = ""
        import src.config as cfg
        importlib.reload(cfg)
        try:
            assert cfg.DATA_DIR == _HOST_DEFAULT
        finally:
            importlib.reload(cfg)

    def test_relative_path_passes_through_unchanged(self):
        """QUANT_DATA_DIR=/tmp/qd → DATA_DIR='/tmp/qd' (no normalization).

        This documents current behavior — collector may fail at write time
        if the path doesn't exist, but config layer is permissive. If we ever
        need strict validation, do it in init_config() not here.
        """
        os.environ["QUANT_DATA_DIR"] = "/tmp/qd"
        import src.config as cfg
        importlib.reload(cfg)
        try:
            assert cfg.DATA_DIR == "/tmp/qd"
        finally:
            importlib.reload(cfg)
