

from pathlib import Path


class TestFindFfmpegPackagedApp:
    """Test find_ffmpeg() for packaged app support (Step 23)."""

    def test_find_ffmpeg_fallback_path(self, monkeypatch):
        """find_ffmpeg should find fallback path when PATH is empty."""
        from yanhu.ffmpeg_utils import find_ffmpeg

        # Mock shutil.which to return None (no PATH)
        monkeypatch.setattr("shutil.which", lambda _: None)

        # Mock Path.exists()/is_file() to return True for specific path
        original_exists = Path.exists
        original_is_file = Path.is_file

        def mock_exists(self):
            if str(self) == "/opt/homebrew/bin/ffmpeg":
                return True
            return original_exists(self)

        def mock_is_file(self):
            if str(self) == "/opt/homebrew/bin/ffmpeg":
                return True
            return original_is_file(self)

        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "is_file", mock_is_file)

        result = find_ffmpeg()
        assert result == "/opt/homebrew/bin/ffmpeg"

    def test_find_ffmpeg_not_found(self, monkeypatch):
        """find_ffmpeg should return None when ffmpeg is not found."""
        from yanhu.ffmpeg_utils import find_ffmpeg

        # Mock shutil.which to return None
        monkeypatch.setattr("shutil.which", lambda _: None)

        # Mock Path.exists() to always return False
        monkeypatch.setattr(Path, "exists", lambda _: False)

        result = find_ffmpeg()
        assert result is None
