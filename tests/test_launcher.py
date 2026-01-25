"""Tests for desktop launcher."""

import shutil
import sys

from yanhu.launcher import check_ffmpeg_availability, ensure_default_directories, selfcheck_asr


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
        from pathlib import Path

        monkeypatch.setattr(shutil, "which", lambda x: None)
        # Mock Path.exists to prevent fallback paths from being found
        monkeypatch.setattr(Path, "exists", lambda self: False)
        is_available, error = check_ffmpeg_availability()
        assert not is_available
        assert "ffmpeg and ffprobe not found" in error

    def test_ffmpeg_missing(self, monkeypatch):
        """Only ffmpeg missing."""
        from pathlib import Path

        def mock_which(cmd):
            return "/usr/bin/ffprobe" if cmd == "ffprobe" else None

        monkeypatch.setattr(shutil, "which", mock_which)
        # Mock Path.exists to prevent fallback paths from being found
        monkeypatch.setattr(Path, "exists", lambda self: False)
        is_available, error = check_ffmpeg_availability()
        assert not is_available
        assert "ffmpeg not found" in error
        assert "ffprobe is available" in error

    def test_ffprobe_missing(self, monkeypatch):
        """Only ffprobe missing."""
        from pathlib import Path

        def mock_which(cmd):
            return "/usr/bin/ffmpeg" if cmd == "ffmpeg" else None

        monkeypatch.setattr(shutil, "which", mock_which)
        # Mock Path.exists to prevent fallback paths from being found
        monkeypatch.setattr(Path, "exists", lambda self: False)
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


class TestLauncherAppCreation:
    """Test that launcher can create app without crashes."""

    def test_create_app_with_launcher_kwargs(self, tmp_path):
        """create_app accepts jobs_dir parameter used by launcher."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # This is the exact call pattern from launcher.py
        app = create_app(
            sessions_dir=str(sessions_dir),
            raw_dir=str(raw_dir),
            jobs_dir=str(jobs_dir),
            worker_enabled=True,
            allow_any_path=False,
            preset="fast",
        )

        assert app is not None
        assert app.config["jobs_dir"] == jobs_dir
        assert app.config["sessions_dir"] == sessions_dir
        assert app.config["worker_enabled"] is True

    def test_run_app_accepts_debug_parameter(self, tmp_path, monkeypatch):
        """run_app accepts debug parameter for backward compatibility."""
        from yanhu.app import run_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Mock Flask app.run to prevent actual server startup
        run_called = []

        def mock_run(self, **kwargs):
            run_called.append(kwargs)

        # Patch Flask.run before importing/creating app
        from flask import Flask
        monkeypatch.setattr(Flask, "run", mock_run)

        # Call run_app with debug parameter (should not crash)
        run_app(
            sessions_dir=sessions_dir,
            host="127.0.0.1",
            port=8787,
            raw_dir=raw_dir,
            worker_enabled=False,
            allow_any_path=False,
            preset="fast",
            debug=True,
        )

        # Verify Flask.run was called with debug=True
        assert len(run_called) == 1
        assert run_called[0]["debug"] is True
        assert run_called[0]["host"] == "127.0.0.1"
        assert run_called[0]["port"] == 8787

    def test_run_app_defaults_debug_to_false(self, tmp_path, monkeypatch):
        """run_app defaults debug to False when not provided."""
        from yanhu.app import run_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Mock Flask app.run
        run_called = []

        def mock_run(self, **kwargs):
            run_called.append(kwargs)

        from flask import Flask
        monkeypatch.setattr(Flask, "run", mock_run)

        # Call run_app without debug parameter
        run_app(sessions_dir=sessions_dir, worker_enabled=False)

        # Verify Flask.run was called with debug=False
        assert len(run_called) == 1
        assert run_called[0]["debug"] is False


class TestKwargFiltering:
    """Test kwarg filtering for launcher compatibility."""

    def test_filter_kwargs_by_signature_keeps_valid_kwargs(self):
        """filter_kwargs_by_signature keeps valid kwargs."""
        from yanhu.launcher import filter_kwargs_by_signature

        def sample_func(a, b, c=3):
            pass

        kwargs = {"a": 1, "b": 2, "c": 4}
        filtered = filter_kwargs_by_signature(sample_func, kwargs)

        assert filtered == {"a": 1, "b": 2, "c": 4}

    def test_filter_kwargs_by_signature_drops_invalid_kwargs(self):
        """filter_kwargs_by_signature drops invalid kwargs."""
        from yanhu.launcher import filter_kwargs_by_signature

        def sample_func(a, b):
            pass

        kwargs = {"a": 1, "b": 2, "invalid": 3, "also_invalid": 4}
        filtered = filter_kwargs_by_signature(sample_func, kwargs)

        # Should only keep valid kwargs
        assert filtered == {"a": 1, "b": 2}
        # Invalid kwargs should be dropped
        assert "invalid" not in filtered
        assert "also_invalid" not in filtered

    def test_filter_kwargs_logs_warning_for_dropped_kwargs(self, caplog):
        """filter_kwargs_by_signature logs warning when dropping kwargs."""
        import logging

        from yanhu.launcher import filter_kwargs_by_signature

        def sample_func(a, b):
            pass

        kwargs = {"a": 1, "b": 2, "unexpected": 3}

        with caplog.at_level(logging.WARNING):
            filter_kwargs_by_signature(sample_func, kwargs)

        # Should log warning about dropped kwarg
        assert len(caplog.records) == 1
        assert "unexpected" in caplog.text
        assert "sample_func" in caplog.text

    def test_launcher_call_pattern_with_filtering(self, tmp_path):
        """Launcher call pattern with kwarg filtering doesn't crash."""
        from yanhu.app import create_app
        from yanhu.launcher import filter_kwargs_by_signature

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Simulate launcher pattern with extra/unknown kwargs
        create_app_kwargs = {
            "sessions_dir": str(sessions_dir),
            "raw_dir": str(raw_dir),
            "jobs_dir": str(sessions_dir.parent / "_queue" / "jobs"),
            "worker_enabled": True,
            "allow_any_path": False,
            "preset": "fast",
            "unknown_kwarg": "should_be_dropped",  # This would crash without filtering
        }

        # Filter before calling (defensive)
        filtered = filter_kwargs_by_signature(create_app, create_app_kwargs)

        # Should not include unknown_kwarg
        assert "unknown_kwarg" not in filtered

        # Should not crash when creating app
        app = create_app(**filtered)
        assert app is not None


class TestAsrSelfcheck:
    """Test ASR import selfcheck for packaged builds."""

    def test_selfcheck_asr_returns_zero_when_all_imports_succeed(self, monkeypatch, capsys):
        """selfcheck_asr returns 0 when all ASR modules import successfully."""
        import builtins

        # Mock __import__ to succeed for all modules
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            # Allow actual imports for non-ASR modules, mock ASR modules
            asr_modules = [
                "faster_whisper",
                "ctranslate2",
                "tokenizers",
                "huggingface_hub",
                "tiktoken",
                "regex",
                "safetensors",
                "av",
                "onnxruntime",
            ]
            if name in asr_modules:
                # Return a mock module
                from types import ModuleType

                return ModuleType(name)
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Run selfcheck
        exit_code = selfcheck_asr()

        # Should return 0 (success)
        assert exit_code == 0

        # Verify output contains success indicators
        captured = capsys.readouterr()
        assert "ASR SELFCHECK PASSED" in captured.out
        assert "Successful: 9/9" in captured.out

    def test_selfcheck_asr_returns_one_when_imports_fail(self, monkeypatch, capsys):
        """selfcheck_asr returns 1 when ASR modules fail to import."""
        import builtins

        # Mock __import__ to fail for ASR modules
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            asr_modules = [
                "faster_whisper",
                "ctranslate2",
                "tokenizers",
                "huggingface_hub",
                "tiktoken",
                "regex",
                "safetensors",
                "av",
                "onnxruntime",
            ]
            if name in asr_modules:
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Run selfcheck
        exit_code = selfcheck_asr()

        # Should return 1 (failure)
        assert exit_code == 1

        # Verify output contains failure indicators
        captured = capsys.readouterr()
        assert "ASR SELFCHECK FAILED" in captured.out
        assert "Failed: 9" in captured.out

    def test_launcher_with_selfcheck_asr_flag_exits_without_starting_server(
        self, monkeypatch, capsys
    ):
        """run_launcher with --selfcheck-asr flag runs selfcheck and exits."""
        import builtins

        # Mock sys.argv to include --selfcheck-asr
        monkeypatch.setattr(sys, "argv", ["yanhu-desktop", "--selfcheck-asr"])

        # Mock __import__ to succeed
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            asr_modules = [
                "faster_whisper",
                "ctranslate2",
                "tokenizers",
                "huggingface_hub",
                "tiktoken",
                "regex",
                "safetensors",
                "av",
                "onnxruntime",
            ]
            if name in asr_modules:
                from types import ModuleType

                return ModuleType(name)
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Mock sys.exit to capture exit code
        exit_code = []

        def mock_exit(code):
            exit_code.append(code)
            raise SystemExit(code)

        monkeypatch.setattr(sys, "exit", mock_exit)

        # Run launcher (should exit via selfcheck)
        from yanhu.launcher import run_launcher

        try:
            run_launcher()
        except SystemExit:
            pass

        # Verify it exited with code 0 (selfcheck passed)
        assert len(exit_code) == 1
        assert exit_code[0] == 0

        # Verify output contains selfcheck message (not launcher startup)
        captured = capsys.readouterr()
        assert "ASR Import Selfcheck" in captured.out
        assert "Desktop Launcher" not in captured.out  # Should NOT start launcher

    def test_selfcheck_asr_output_uses_ascii_symbols_no_unicode(self, monkeypatch, capsys):
        """selfcheck_asr output uses ASCII-safe symbols (no Unicode for Windows cp1252)."""
        import builtins

        # Mock __import__ to succeed for all modules
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            asr_modules = [
                "faster_whisper",
                "ctranslate2",
                "tokenizers",
                "huggingface_hub",
                "tiktoken",
                "regex",
                "safetensors",
                "av",
                "onnxruntime",
            ]
            if name in asr_modules:
                from types import ModuleType

                return ModuleType(name)
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Run selfcheck
        selfcheck_asr()

        # Verify output
        captured = capsys.readouterr()
        output = captured.out

        # Should NOT contain Unicode checkmarks (causes UnicodeEncodeError on Windows cp1252)
        assert "✓" not in output, "Should not use Unicode checkmark ✓ (Windows cp1252 incompatible)"
        assert "✗" not in output, "Should not use Unicode X-mark ✗ (Windows cp1252 incompatible)"

        # Should contain ASCII-safe alternatives
        assert "[OK]" in output, "Should use ASCII-safe [OK] token"
        assert "ASR SELFCHECK PASSED" in output
