"""Tests for desktop launcher."""

import shutil

from yanhu.launcher import check_ffmpeg_availability, ensure_default_directories


class TestCheckFfmpegAvailability:
    """Test ffmpeg availability checking."""

    def test_both_available(self, monkeypatch):
        """Both ffmpeg and ffprobe available."""
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/" + x)
        is_available, error = check_ffmpeg_availability()
        assert is_available
        assert error is None

    def test_both_missing(self, monkeypatch):
        """Both ffmpeg and ffprobe missing."""
        monkeypatch.setattr(shutil, "which", lambda x: None)
        is_available, error = check_ffmpeg_availability()
        assert not is_available
        assert "ffmpeg and ffprobe not found" in error

    def test_ffmpeg_missing(self, monkeypatch):
        """Only ffmpeg missing."""

        def mock_which(cmd):
            return "/usr/bin/ffprobe" if cmd == "ffprobe" else None

        monkeypatch.setattr(shutil, "which", mock_which)
        is_available, error = check_ffmpeg_availability()
        assert not is_available
        assert "ffmpeg not found" in error
        assert "ffprobe is available" in error

    def test_ffprobe_missing(self, monkeypatch):
        """Only ffprobe missing."""

        def mock_which(cmd):
            return "/usr/bin/ffmpeg" if cmd == "ffmpeg" else None

        monkeypatch.setattr(shutil, "which", mock_which)
        is_available, error = check_ffmpeg_availability()
        assert not is_available
        assert "ffprobe not found" in error
        assert "ffmpeg is available" in error


class TestEnsureDefaultDirectories:
    """Test default directory creation."""

    def test_creates_directories(self, tmp_path, monkeypatch):
        """Should create sessions and raw directories."""
        # Use tmp_path as home
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        sessions_dir, raw_dir = ensure_default_directories()

        # Verify directories created
        assert sessions_dir.exists()
        assert raw_dir.exists()
        assert sessions_dir == fake_home / "yanhu-sessions" / "sessions"
        assert raw_dir == fake_home / "yanhu-sessions" / "raw"

    def test_idempotent(self, tmp_path, monkeypatch):
        """Should not fail if directories already exist."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)

        # Call twice
        sessions_dir1, raw_dir1 = ensure_default_directories()
        sessions_dir2, raw_dir2 = ensure_default_directories()

        # Should return same paths
        assert sessions_dir1 == sessions_dir2
        assert raw_dir1 == raw_dir2
        assert sessions_dir1.exists()
        assert raw_dir1.exists()
