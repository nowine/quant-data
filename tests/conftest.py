"""Project-level pytest configuration.

Registers custom markers used across the test suite.
"""

# pytest markers — keep this list in sync with @pytest.mark.X usages.
pytestmark = [
    # No-op top-level marker — real registration happens via the dict below
]


def pytest_configure(config):
    """Register custom markers so pytest doesn't warn about them."""
    config.addinivalue_line(
        "markers",
        "phase2: Tests reserved for Phase 2 backlog items "
        "(see docs/phase-2-followup.md). Currently skip; flip when implemented.",
    )