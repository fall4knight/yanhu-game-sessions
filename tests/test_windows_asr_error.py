"""Tests for Windows ASR error handling (WinError 1314 symlink privilege)."""

import json
import sys


class TestIsWindowsSymlinkError:
    """Test _is_windows_symlink_error helper function."""

    def test_returns_false_on_non_windows(self, monkeypatch):
        """Should return False on non-Windows platforms."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "linux")
        exc = OSError("Some error")
        assert _is_windows_symlink_error(exc) is False

    def test_detects_winerror_1314(self, monkeypatch):
        """Should detect OSError with winerror=1314."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "win32")

        # Create OSError with winerror attribute
        exc = OSError("A required privilege is not held by the client")
        exc.winerror = 1314

        assert _is_windows_symlink_error(exc) is True

    def test_detects_1314_in_message(self, monkeypatch):
        """Should detect '1314' in error message."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "win32")

        exc = OSError("[WinError 1314] A required privilege is not held")
        assert _is_windows_symlink_error(exc) is True

    def test_detects_privilege_in_message(self, monkeypatch):
        """Should detect 'privilege' keyword in error message."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "win32")

        exc = OSError("Required privilege not held by client")
        assert _is_windows_symlink_error(exc) is True

    def test_detects_nested_exception(self, monkeypatch):
        """Should detect WinError 1314 in nested exception cause."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "win32")

        inner_exc = OSError("Privilege error")
        inner_exc.winerror = 1314

        outer_exc = RuntimeError("Model loading failed")
        outer_exc.__cause__ = inner_exc

        assert _is_windows_symlink_error(outer_exc) is True

    def test_returns_false_for_other_oserror(self, monkeypatch):
        """Should return False for non-symlink OSErrors."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "win32")

        exc = OSError("File not found")
        assert _is_windows_symlink_error(exc) is False

    def test_returns_false_for_other_exceptions(self, monkeypatch):
        """Should return False for non-OSError exceptions."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "win32")

        exc = ValueError("Invalid value")
        assert _is_windows_symlink_error(exc) is False


class TestAggregateAsrErrorsSymlink:
    """Test aggregate_asr_errors detection of Windows symlink errors."""

    def test_detects_symlink_error_in_transcript(self, tmp_path):
        """Should detect Windows symlink error and set dependency_error."""
        from yanhu.watcher import aggregate_asr_errors

        # Create mock transcript with symlink error
        asr_dir = tmp_path / "outputs" / "asr" / "whisper_local"
        asr_dir.mkdir(parents=True)
        transcript_path = asr_dir / "transcript.json"

        transcript_data = [
            {
                "segment_id": "part_0001",
                "asr_backend": "whisper_local",
                "asr_error": "Windows symlink privilege error (WinError 1314): "
                "The HuggingFace cache requires symlink support.",
            }
        ]
        transcript_path.write_text(json.dumps(transcript_data))

        result = aggregate_asr_errors(tmp_path, ["whisper_local"])

        assert result is not None
        assert result.failed_segments == 1
        assert result.dependency_error is not None
        assert "1314" in result.dependency_error or "symlink" in result.dependency_error.lower()
        assert "Developer Mode" in result.dependency_error

    def test_detects_winerror_1314_pattern(self, tmp_path):
        """Should detect 'WinError1314' pattern in error message."""
        from yanhu.watcher import aggregate_asr_errors

        asr_dir = tmp_path / "outputs" / "asr" / "whisper_local"
        asr_dir.mkdir(parents=True)
        transcript_path = asr_dir / "transcript.json"

        transcript_data = [
            {
                "segment_id": "part_0001",
                "asr_backend": "whisper_local",
                "asr_error": "backend=faster-whisper | exception=WinError1314 | "
                "message=privilege not held",
            }
        ]
        transcript_path.write_text(json.dumps(transcript_data))

        result = aggregate_asr_errors(tmp_path, ["whisper_local"])

        assert result is not None
        assert result.dependency_error is not None
        assert "symlink" in result.dependency_error.lower()

    def test_partial_symlink_errors_get_hint(self, tmp_path):
        """Should set partial_symlink_hint if only some segments have symlink error."""
        from yanhu.watcher import aggregate_asr_errors

        asr_dir = tmp_path / "outputs" / "asr" / "whisper_local"
        asr_dir.mkdir(parents=True)
        transcript_path = asr_dir / "transcript.json"

        transcript_data = [
            {
                "segment_id": "part_0001",
                "asr_backend": "whisper_local",
                "asr_error": "WinError 1314 symlink privilege error",
            },
            {
                "segment_id": "part_0002",
                "asr_backend": "whisper_local",
                "asr_items": [{"text": "Hello", "t_start": 0.0, "t_end": 1.0}],
            },
        ]
        transcript_path.write_text(json.dumps(transcript_data))

        result = aggregate_asr_errors(tmp_path, ["whisper_local"])

        assert result is not None
        assert result.failed_segments == 1
        # dependency_error should NOT be set (partial failure doesn't block job)
        assert result.dependency_error is None
        # BUT partial_symlink_hint SHOULD be set to inform user
        assert result.partial_symlink_hint is not None
        assert "1/2" in result.partial_symlink_hint
        assert "Developer Mode" in result.partial_symlink_hint

    def test_ffmpeg_error_takes_priority(self, tmp_path):
        """ffmpeg error should take priority over symlink error if all segments fail with ffmpeg."""
        from yanhu.watcher import aggregate_asr_errors

        asr_dir = tmp_path / "outputs" / "asr" / "whisper_local"
        asr_dir.mkdir(parents=True)
        transcript_path = asr_dir / "transcript.json"

        transcript_data = [
            {
                "segment_id": "part_0001",
                "asr_backend": "whisper_local",
                "asr_error": "ffmpeg not found",
            }
        ]
        transcript_path.write_text(json.dumps(transcript_data))

        result = aggregate_asr_errors(tmp_path, ["whisper_local"])

        assert result is not None
        assert result.dependency_error is not None
        assert "ffmpeg" in result.dependency_error.lower()


class TestHfHubDisableSymlinks:
    """Test that HF_HUB_DISABLE_SYMLINKS is set correctly on retry."""

    def test_symlink_error_detection_on_windows(self, monkeypatch):
        """Should correctly detect WinError 1314 for retry logic."""
        from yanhu.transcriber import _is_windows_symlink_error

        monkeypatch.setattr(sys, "platform", "win32")

        # Create a WinError 1314-style exception
        exc = OSError("[WinError 1314] A required privilege is not held")
        exc.winerror = 1314

        # Verify detection works
        assert _is_windows_symlink_error(exc) is True

        # Verify non-1314 errors are not detected
        other_exc = OSError("Some other error")
        assert _is_windows_symlink_error(other_exc) is False

    def test_env_var_names_are_correct(self):
        """Verify the HF hub environment variable names we use are correct."""
        # HF_HUB_DISABLE_SYMLINKS_WARNING is the only documented symlink-related env var
        # https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables
        # Note: HF_HUB_DISABLE_SYMLINKS is NOT a supported env var
        expected_var = "HF_HUB_DISABLE_SYMLINKS_WARNING"

        # Verify the variable is referenced in the code
        import inspect

        import yanhu.transcriber as transcriber_module

        source = inspect.getsource(transcriber_module)
        assert expected_var in source, f"Expected {expected_var} to be used in transcriber.py"

        # Verify we don't use the non-existent HF_HUB_DISABLE_SYMLINKS
        # (only HF_HUB_DISABLE_SYMLINKS_WARNING is valid)
        lines = source.split("\n")
        for line in lines:
            if "HF_HUB_DISABLE_SYMLINKS" in line and "WARNING" not in line:
                # Allow comments that explain why we don't use it
                if line.strip().startswith("#"):
                    continue
                # Fail if we're setting the non-existent env var
                if "os.environ" in line:
                    raise AssertionError(
                        f"Found non-existent env var HF_HUB_DISABLE_SYMLINKS in: {line}"
                    )
