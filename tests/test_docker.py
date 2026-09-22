"""TDD: Docker configuration validation.

Unified-image contract (2026-08-21, per ADR-004 + 主人 unification decision):
- One image, four collectors dispatched via --script at runtime.
- Public ENTRYPOINT = scripts/entrypoint.sh.
- Pin akshare==1.18.60 (host version) to avoid silent API drift.
"""

import re
import yaml
from pathlib import Path


COMPOSE_PATH = Path(__file__).parent.parent / "docker-compose.yml"
DOCKERFILE_PATH = Path(__file__).parent.parent / "Dockerfile"


def test_docker_compose_valid():
    """Verify docker-compose.yml is valid and uses the entrypoint routing contract."""
    assert COMPOSE_PATH.exists(), "docker-compose.yml must exist"
    with open(COMPOSE_PATH) as f:
        data = yaml.safe_load(f)
    service = data["services"]["collector"]
    assert service["build"] == "."
    # New contract: command must invoke the entrypoint with --script
    cmd = service.get("command", "")
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    assert "--script" in cmd_str, (
        f"command must include --script per unified-image contract, got: {cmd!r}"
    )
    assert cmd_str  # non-empty


def test_dockerfile_has_multi_stage():
    """Verify Dockerfile uses multi-stage build with non-root user."""
    assert DOCKERFILE_PATH.exists(), "Dockerfile must exist"
    content = DOCKERFILE_PATH.read_text()
    assert "AS builder" in content, "Dockerfile must have builder stage"
    assert "AS runner" in content, "Dockerfile must have runner stage"
    assert "USER appuser" in content, "Dockerfile must run as non-root"


def test_dockerfile_pins_akshare():
    """akshare must be pinned to avoid silent API drift (MEMORY #11 lesson)."""
    content = DOCKERFILE_PATH.read_text()
    assert "akshare==" in content, (
        "akshare must be pinned to exact version (e.g. akshare==1.18.60), "
        "not floating (e.g. akshare>=1.0.0)."
    )
    # Extract the version
    match = re.search(r"akshare==([\d.]+)", content)
    assert match, "akshare==X.Y.Z pattern required"
    assert match.group(1) == "1.18.60", (
        f"akshare must pin to 1.18.60 (host version), got {match.group(1)}"
    )


def test_dockerfile_exposes_entrypoint():
    """ENTRYPOINT must point at scripts/entrypoint.sh (unified dispatch)."""
    content = DOCKERFILE_PATH.read_text()
    assert 'ENTRYPOINT ["bash", "/app/scripts/entrypoint.sh"]' in content, (
        "Dockerfile ENTRYPOINT must dispatch via scripts/entrypoint.sh"
    )


def test_dockerfile_mounts_data_volume():
    """docker-compose must bind-mount the data directory to /data inside container."""
    content = COMPOSE_PATH.read_text()
    assert "/data" in content, "compose must expose /data inside container"
    assert "/root/secureshare/files" in content, (
        "compose must bind-mount /root/secureshare/files to /data"
    )
