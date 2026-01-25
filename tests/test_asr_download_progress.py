"""Tests for ASR model download progress tracking."""

import json


class TestAsrDownloadProgress:
    """Test progress tracking during model download."""

    def test_download_model_stage_when_model_missing(self, tmp_path, monkeypatch):
        """When model missing, progress should show download_model stage with message."""
        import sys
        from types import ModuleType

        # Create mock faster_whisper module
        mock_faster_whisper = ModuleType("faster_whisper")

        class MockWhisperModel:
            def __init__(self, *args, **kwargs):
                pass

        mock_faster_whisper.WhisperModel = MockWhisperModel
        sys.modules["faster_whisper"] = mock_faster_whisper

        try:
            from yanhu.transcriber import WhisperLocalBackend

            session_dir = tmp_path / "session"
            session_dir.mkdir()
            (session_dir / "outputs").mkdir()

            # Mock _check_model_cached to return False (model not cached)
            def mock_check_cached(self):
                return False

            monkeypatch.setattr(
                "yanhu.transcriber.WhisperLocalBackend._check_model_cached",
                mock_check_cached,
            )

            backend = WhisperLocalBackend(model_size="base")
            error = backend._load_model(session_id="test_session", session_dir=session_dir)

            # Should succeed
            assert error is None

            # Check progress.json was created with download_model stage
            progress_file = session_dir / "outputs" / "progress.json"
            assert progress_file.exists()

            with open(progress_file, encoding="utf-8") as f:
                progress_data = json.load(f)

            # Should have download_model stage
            assert progress_data["stage"] == "download_model"
            # Should have message about model (either downloading or ready)
            assert "message" in progress_data
            assert "base" in progress_data["message"]
            # Message should mention either download or ready state
            assert ("Downloading" in progress_data["message"] or
                    "ready" in progress_data["message"] or
                    "Model" in progress_data["message"])
        finally:
            # Clean up mock
            if "faster_whisper" in sys.modules:
                del sys.modules["faster_whisper"]

    def test_no_progress_when_model_cached(self, tmp_path, monkeypatch):
        """When model cached, no download progress should be created."""
        import sys
        from types import ModuleType

        # Create mock faster_whisper module
        mock_faster_whisper = ModuleType("faster_whisper")

        class MockWhisperModel:
            def __init__(self, *args, **kwargs):
                pass

        mock_faster_whisper.WhisperModel = MockWhisperModel
        sys.modules["faster_whisper"] = mock_faster_whisper

        try:
            from yanhu.transcriber import WhisperLocalBackend

            session_dir = tmp_path / "session"
            session_dir.mkdir()
            (session_dir / "outputs").mkdir()

            # Mock _check_model_cached to return True (model cached)
            def mock_check_cached(self):
                return True

            monkeypatch.setattr(
                "yanhu.transcriber.WhisperLocalBackend._check_model_cached",
                mock_check_cached,
            )

            backend = WhisperLocalBackend(model_size="base")
            error = backend._load_model(session_id="test_session", session_dir=session_dir)

            # Should succeed
            assert error is None

            # Progress file should not be created (no download needed)
            progress_file = session_dir / "outputs" / "progress.json"
            assert not progress_file.exists()
        finally:
            # Clean up mock
            if "faster_whisper" in sys.modules:
                del sys.modules["faster_whisper"]

    def test_message_field_in_progress_snapshot(self, tmp_path):
        """ProgressSnapshot should include message field in to_dict."""
        from yanhu.progress import ProgressSnapshot

        snapshot = ProgressSnapshot(
            session_id="test",
            stage="download_model",
            done=0,
            total=1,
            elapsed_sec=5.5,
            eta_sec=None,
            updated_at="2026-01-25T00:00:00Z",
            message="Downloading model 'base' (~145 MB)",
        )

        data = snapshot.to_dict()

        assert "message" in data
        assert data["message"] == "Downloading model 'base' (~145 MB)"
        assert data["stage"] == "download_model"

    def test_message_field_optional(self, tmp_path):
        """ProgressSnapshot should work without message field."""
        from yanhu.progress import ProgressSnapshot

        snapshot = ProgressSnapshot(
            session_id="test",
            stage="transcribe",
            done=5,
            total=10,
            elapsed_sec=10.0,
            eta_sec=10.0,
            updated_at="2026-01-25T00:00:00Z",
        )

        data = snapshot.to_dict()

        # Message field should not be in dict if None
        assert "message" not in data
        assert data["stage"] == "transcribe"

    def test_progress_tracker_update_with_message(self, tmp_path):
        """ProgressTracker should accept message in update."""
        from yanhu.progress import ProgressTracker

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        tracker = ProgressTracker(
            session_id="test",
            session_dir=session_dir,
            stage="download_model",
            total=1,
            message="Starting download...",
        )

        # Update with new message
        tracker.update(done=0, message="Downloading... (10s elapsed)")

        # Read progress file
        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "message" in data
        assert "10s elapsed" in data["message"]
