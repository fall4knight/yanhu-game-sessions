"""Tests for ffprobe discovery in packaged apps."""

from pathlib import Path

from yanhu.ffmpeg_utils import find_ffmpeg, find_ffprobe


class TestFfprobeDiscovery:
    """Test ffprobe path discovery for packaged apps."""

    def test_find_ffprobe_uses_which_first(self, monkeypatch):
        """Test find_ffprobe() tries shutil.which() first."""

        def mock_which(cmd):
            if cmd == "ffprobe":
                return "/usr/bin/ffprobe"
            return None

        monkeypatch.setattr("shutil.which", mock_which)

        result = find_ffprobe()
        assert result == "/usr/bin/ffprobe"

    def test_find_ffprobe_falls_back_to_homebrew_paths(self, monkeypatch):
        """Test find_ffprobe() tries common absolute paths when which() fails."""

        def mock_which(cmd):
            return None  # Simulate PATH not containing ffprobe

        monkeypatch.setattr("shutil.which", mock_which)

        # Mock Path methods to simulate Homebrew path existing
        original_exists = Path.exists
        original_is_file = Path.is_file

        def mock_exists(self):
            if str(self) == "/opt/homebrew/bin/ffprobe":
                return True
            return original_exists(self)

        def mock_is_file(self):
            if str(self) == "/opt/homebrew/bin/ffprobe":
                return True
            return original_is_file(self)

        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "is_file", mock_is_file)

        result = find_ffprobe()
        assert result == "/opt/homebrew/bin/ffprobe"

    def test_find_ffprobe_returns_none_when_not_found(self, monkeypatch):
        """Test find_ffprobe() returns None when ffprobe not found anywhere."""

        def mock_which(cmd):
            return None

        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        result = find_ffprobe()
        assert result is None

    def test_find_ffmpeg_uses_which_first(self, monkeypatch):
        """Test find_ffmpeg() tries shutil.which() first."""

        def mock_which(cmd):
            if cmd == "ffmpeg":
                return "/usr/bin/ffmpeg"
            return None

        monkeypatch.setattr("shutil.which", mock_which)

        result = find_ffmpeg()
        assert result == "/usr/bin/ffmpeg"

    def test_find_ffmpeg_returns_none_when_not_found(self, monkeypatch):
        """Test find_ffmpeg() returns None when ffmpeg not found anywhere."""

        def mock_which(cmd):
            return None

        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        result = find_ffmpeg()
        assert result is None
