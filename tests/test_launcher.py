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
