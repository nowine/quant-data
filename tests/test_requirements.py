"""Tests for requirements.txt"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO_ROOT / "requirements.txt"


def test_requirements_file_exists():
    assert REQUIREMENTS.exists(), "requirements.txt not found"


def test_requirements_has_core_deps():
    content = REQUIREMENTS.read_text()
    core_deps = ["akshare", "pandas", "requests", "pydantic", "pytest", "ruff"]
    for dep in core_deps:
        assert dep in content, f"Missing dependency: {dep}"


def test_requirements_version_specified():
    lines = [
        line.strip()
        for line in REQUIREMENTS.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for line in lines:
        assert ">=" in line or "==" in line, f"No version specifier: {line}"
