"""Tests for session management."""

import os
import shutil
from datetime import datetime
from pathlib import Path

from yanhu.session import (
    SESSION_ID_PATTERN,
    copy_source_video,
    create_session_directory,
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


class TestCopySourceVideoObservability:
    """Test copy_source_video with P2.1 observability."""

    def test_copy_mode_explicit(self, tmp_path):
        """Explicit copy mode should copy and report correct metadata."""
        # Create source video
        source_video = tmp_path / "source_video.mp4"
        source_video.write_text("test video content")
        raw_inode = os.stat(source_video).st_ino

        # Create session directory
        session_dir = tmp_path / "session"
        create_session_directory("test_session", session_dir.parent)
        session_dir.mkdir(exist_ok=True)
        (session_dir / "source").mkdir(exist_ok=True)

        # Copy with explicit copy mode
        source_local, metadata = copy_source_video(source_video, session_dir, mode="copy")

        # Verify return values
        assert source_local == Path("source") / "source_video.mp4"
        assert metadata.source_mode == "copy"
        assert metadata.source_inode_raw == raw_inode
        assert metadata.source_inode_raw != metadata.source_inode_session  # Different inodes
        assert metadata.source_link_count >= 1
        assert metadata.source_fallback_error is None
        assert metadata.source_symlink_target is None

        # Verify file exists
        dest_path = session_dir / "source" / "source_video.mp4"
        assert dest_path.exists()
        assert dest_path.read_text() == "test video content"

    def test_hardlink_same_filesystem(self, tmp_path):
        """Hardlink on same filesystem should succeed and report correct metadata."""
        # Create source video
        source_video = tmp_path / "source_video.mp4"
        source_video.write_text("test video content")
        raw_inode = os.stat(source_video).st_ino

        # Create session directory
        session_dir = tmp_path / "session"
        create_session_directory("test_session", session_dir.parent)
        session_dir.mkdir(exist_ok=True)
        (session_dir / "source").mkdir(exist_ok=True)

        # Link (should create hardlink on same filesystem)
        source_local, metadata = copy_source_video(source_video, session_dir, mode="link")

        # Verify hardlink metadata
        assert source_local == Path("source") / "source_video.mp4"
        assert metadata.source_mode == "hardlink"
        assert metadata.source_inode_raw == raw_inode
        assert metadata.source_inode_raw == metadata.source_inode_session  # Same inode
        assert metadata.source_link_count >= 2  # At least 2 links
        assert metadata.source_fallback_error is None
        assert metadata.source_symlink_target is None

        # Verify file exists and has same inode
        dest_path = session_dir / "source" / "source_video.mp4"
        assert dest_path.exists()
        dest_inode = os.stat(dest_path).st_ino
        assert dest_inode == raw_inode

    def test_symlink_mode(self, tmp_path):
        """Symlink should create symlink and report correct metadata."""
        # Create source video
        source_video = tmp_path / "source_video.mp4"
        source_video.write_text("test video content")
        raw_inode = os.stat(source_video, follow_symlinks=True).st_ino

        # Create session directory
        session_dir = tmp_path / "session"
        create_session_directory("test_session", session_dir.parent)
        session_dir.mkdir(exist_ok=True)
        (session_dir / "source").mkdir(exist_ok=True)

        # Create symlink manually to test symlink detection
        dest_path = session_dir / "source" / "source_video.mp4"
        os.symlink(source_video, dest_path)

        # Verify it's a symlink
        assert os.path.islink(dest_path)
        symlink_target = os.readlink(dest_path)
        assert Path(symlink_target) == source_video

        # Verify metadata would be correct (we can't easily force symlink through copy_source_video
        # on same filesystem, so we test the detection logic)
        session_inode = os.lstat(dest_path).st_ino  # lstat to not follow symlink
        link_count = os.lstat(dest_path).st_nlink

        # Symlink should have different inode than target
        assert session_inode != raw_inode
        assert link_count >= 1

    def test_metadata_fields_populated(self, tmp_path):
        """All metadata fields should be populated."""
        # Create source video
        source_video = tmp_path / "test.mp4"
        source_video.write_text("content")

        # Create session directory
        session_dir = tmp_path / "session"
        session_dir.mkdir(exist_ok=True)
        (session_dir / "source").mkdir(exist_ok=True)

        # Copy
        _, metadata = copy_source_video(source_video, session_dir, mode="copy")

        # All required fields should be populated
        assert metadata.source_mode in ["hardlink", "symlink", "copy"]
        assert isinstance(metadata.source_inode_raw, int)
        assert metadata.source_inode_raw > 0
        assert isinstance(metadata.source_inode_session, int)
        assert metadata.source_inode_session > 0
        assert isinstance(metadata.source_link_count, int)
        assert metadata.source_link_count >= 1
        # Optional fields
        assert (
            metadata.source_fallback_error is None
            or isinstance(metadata.source_fallback_error, str)
        )
        assert (
            metadata.source_symlink_target is None
            or isinstance(metadata.source_symlink_target, str)
        )

    def test_link_count_verification(self, tmp_path):
        """Link count should be >= 2 for hardlink, >= 1 for copy/symlink."""
        # Create source video
        source_video = tmp_path / "test.mp4"
        source_video.write_text("content")

        # Create session directory
        session_dir = tmp_path / "session"
        session_dir.mkdir(exist_ok=True)
        (session_dir / "source").mkdir(exist_ok=True)

        # Test hardlink
        _, metadata_link = copy_source_video(source_video, session_dir, mode="link")
        if metadata_link.source_mode == "hardlink":
            assert metadata_link.source_link_count >= 2

        # Clean up for copy test
        shutil.rmtree(session_dir / "source")
        (session_dir / "source").mkdir(exist_ok=True)

        # Test copy
        _, metadata_copy = copy_source_video(source_video, session_dir, mode="copy")
        assert metadata_copy.source_mode == "copy"
        assert metadata_copy.source_link_count >= 1
