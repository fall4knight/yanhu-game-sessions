"""Tests for session management."""

from datetime import datetime

from yanhu.session import (
    SESSION_ID_PATTERN,
    generate_session_id,
    parse_session_id,
    validate_session_id,
)


class TestSessionIdFormat:
    """Test session ID format validation."""

    def test_valid_session_id_format(self):
        """Valid session IDs should match the pattern."""
        valid_ids = [
            "2026-01-19_21-45-00_gnosia_run01",
            "2024-12-31_23-59-59_genshin_session02",
            "2025-06-15_00-00-00_star-rail_test",
            "2026-01-01_12-30-45_game_tag123",
        ]
        for session_id in valid_ids:
            assert validate_session_id(session_id), f"Should be valid: {session_id}"

    def test_invalid_session_id_format(self):
        """Invalid session IDs should not match."""
        invalid_ids = [
            "2026-01-19_21-45_gnosia_run01",  # missing seconds
            "2026-1-19_21-45-00_gnosia_run01",  # single digit month
            "gnosia_run01",  # missing timestamp
            "2026-01-19_21-45-00_gnosia",  # missing tag
            "2026-01-19_21-45-00__run01",  # empty game
            "",  # empty string
        ]
        for session_id in invalid_ids:
            assert not validate_session_id(session_id), f"Should be invalid: {session_id}"

    def test_regex_pattern_matches_spec(self):
        """Pattern should match the README spec format."""
        # README format: YYYY-MM-DD_HH-MM-SS_<game>_<runTag>
        pattern_str = SESSION_ID_PATTERN.pattern
        assert "\\d{4}-\\d{2}-\\d{2}" in pattern_str  # date
        assert "\\d{2}-\\d{2}-\\d{2}" in pattern_str  # time


class TestSessionIdGeneration:
    """Test session ID generation."""

    def test_generate_session_id_format(self):
        """Generated ID should match expected format."""
        ts = datetime(2026, 1, 19, 21, 45, 0)
        session_id = generate_session_id("gnosia", "run01", timestamp=ts)
        assert session_id == "2026-01-19_21-45-00_gnosia_run01"

    def test_generate_session_id_validates(self):
        """Generated ID should pass validation."""
        session_id = generate_session_id("genshin", "session02")
        assert validate_session_id(session_id)

    def test_generate_session_id_with_hyphenated_names(self):
        """Should handle hyphenated game names and tags."""
        ts = datetime(2026, 1, 1, 0, 0, 0)
        session_id = generate_session_id("star-rail", "run-01", timestamp=ts)
        assert session_id == "2026-01-01_00-00-00_star-rail_run-01"
        assert validate_session_id(session_id)


class TestSessionIdParsing:
    """Test session ID parsing."""

    def test_parse_valid_session_id(self):
        """Should parse valid session ID into components."""
        result = parse_session_id("2026-01-19_21-45-00_gnosia_run01")
        assert result is not None
        assert result["date"] == "2026-01-19"
        assert result["time"] == "21-45-00"
        assert result["game"] == "gnosia"
        assert result["tag"] == "run01"

    def test_parse_invalid_session_id(self):
        """Should return None for invalid session ID."""
        assert parse_session_id("invalid") is None
        assert parse_session_id("") is None
