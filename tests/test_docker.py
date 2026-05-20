"""TDD: Docker configuration validation."""
import yaml
from pathlib import Path


def test_docker_compose_valid():
    """Verify docker-compose.yml is valid and has correct structure."""
    compose_path = Path(__file__).parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist"
    with open(compose_path) as f:
        data = yaml.safe_load(f)
    assert data["services"]["collector"]["build"] == "."
    assert data["services"]["collector"]["command"] == "python src/collector_daily.py --mode=close"


def test_dockerfile_has_multi_stage():
    """Verify Dockerfile uses multi-stage build."""
    dockerfile_path = Path(__file__).parent.parent / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist"
    content = dockerfile_path.read_text()
    assert "AS builder" in content
    assert "AS runner" in content
    assert "USER appuser" in content
