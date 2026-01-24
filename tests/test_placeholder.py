"""Placeholder tests for CI validation."""

import yanhu


def test_version_exists():
    """Verify package has a version string."""
    assert hasattr(yanhu, "__version__")
    assert isinstance(yanhu.__version__, str)


def test_version_format():
    """Verify version follows semver-like format."""
    version = yanhu.__version__
    parts = version.split(".")
    assert len(parts) >= 2, "Version should have at least major.minor"
