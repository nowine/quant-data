"""Tests for requirements.txt"""


def test_requirements_file_exists():
    import os

    assert os.path.exists("requirements.txt"), "requirements.txt not found"


def test_requirements_has_core_deps():
    with open("requirements.txt") as f:
        content = f.read()
    core_deps = ["akshare", "pandas", "requests", "pydantic", "pytest", "ruff"]
    for dep in core_deps:
        assert dep in content, f"Missing dependency: {dep}"


def test_requirements_version_specified():
    with open("requirements.txt") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    for line in lines:
        assert ">=" in line or "==" in line, f"No version specifier: {line}"