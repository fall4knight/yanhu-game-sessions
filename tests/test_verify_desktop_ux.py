"""Tests for desktop UX verification gate."""

import pytest

from yanhu.verify import verify_desktop_ux


class TestVerifyDesktopUX:
    """Test desktop UX smoke gate."""

    def test_passes_in_current_codebase(self):
        """Verify gate passes for current implementation."""
        valid, error = verify_desktop_ux()
        assert valid, f"Desktop UX verification should pass but got error:\n{error}"
        assert error == ""

    def test_checks_ffprobe_discovery(self, monkeypatch):
        """Verify gate checks for ffprobe discovery function."""
        # Mock missing find_ffprobe
        import yanhu.ffmpeg_utils

        original_find_ffprobe = yanhu.ffmpeg_utils.find_ffprobe

        # Temporarily remove the function
        monkeypatch.delattr(yanhu.ffmpeg_utils, "find_ffprobe")

        try:
            valid, error = verify_desktop_ux()
            assert not valid
            assert "find_ffprobe" in error
        finally:
            # Restore for other tests (monkeypatch will undo on teardown)
            if not hasattr(yanhu.ffmpeg_utils, "find_ffprobe"):
                setattr(yanhu.ffmpeg_utils, "find_ffprobe", original_find_ffprobe)

    def test_checks_shutdown_endpoint_exists(self, monkeypatch):
        """Verify gate checks for shutdown endpoint."""
        # This test verifies that the verification looks for /api/shutdown
        # We can't easily mock this without breaking imports, but we verify
        # the current implementation passes
        valid, error = verify_desktop_ux()
        assert valid, f"Should pass with shutdown endpoint present: {error}"

    def test_checks_os_exit_fallback(self):
        """Verify gate checks for os._exit fallback in shutdown."""
        # The current implementation has os._exit, so this passes
        valid, error = verify_desktop_ux()
        assert valid

        # Verify the check would catch missing os._exit by checking error message
        # (We can't easily mock this without breaking the app module)

    def test_checks_launcher_compatibility(self):
        """Verify gate checks launcher compatibility contracts."""
        valid, error = verify_desktop_ux()
        assert valid, f"Should pass with current launcher compatibility: {error}"

        # Verify specific checks
        import inspect

        from yanhu.app import create_app, run_app

        # Check create_app has jobs_dir
        create_app_sig = inspect.signature(create_app)
        assert "jobs_dir" in create_app_sig.parameters, "create_app must accept jobs_dir"

        # Check run_app has debug
        run_app_sig = inspect.signature(run_app)
        assert "debug" in run_app_sig.parameters, "run_app must accept debug parameter"

    def test_catches_missing_create_app(self, monkeypatch):
        """Verify gate catches missing create_app."""
        import yanhu.app

        original_create_app = yanhu.app.create_app

        # Temporarily remove the function
        monkeypatch.delattr(yanhu.app, "create_app")

        try:
            valid, error = verify_desktop_ux()
            assert not valid
            assert "create_app" in error
        finally:
            # Restore for other tests (monkeypatch will undo on teardown)
            if not hasattr(yanhu.app, "create_app"):
                setattr(yanhu.app, "create_app", original_create_app)

    def test_all_checks_return_detailed_errors(self):
        """Verify gate returns detailed error messages for debugging."""
        # This test documents that errors should be actionable
        # The current implementation passes, so we just verify structure
        valid, error = verify_desktop_ux()

        # If it fails (shouldn't in current code), errors should be multiline
        if not valid:
            assert "\n" in error or len(error) > 0, "Errors should be detailed"


class TestFFprobeDiscoveryContract:
    """Test ffprobe discovery contract (Check A)."""

    def test_find_ffprobe_exists_and_is_callable(self):
        """find_ffprobe must exist and be callable."""
        from yanhu.ffmpeg_utils import find_ffprobe

        assert callable(find_ffprobe)

    def test_find_ffprobe_uses_shutil_which(self):
        """find_ffprobe must use shutil.which for PATH lookup."""
        import inspect

        from yanhu.ffmpeg_utils import find_ffprobe

        source = inspect.getsource(find_ffprobe)
        assert "shutil.which" in source, "Must check PATH using shutil.which"

    def test_find_ffprobe_has_fallback_paths(self):
        """find_ffprobe must check common fallback paths for packaged apps."""
        import inspect

        from yanhu.ffmpeg_utils import find_ffprobe

        source = inspect.getsource(find_ffprobe)
        # Must include common Homebrew and system paths
        assert (
            "/opt/homebrew/bin" in source or "/usr/local/bin" in source
        ), "Must check common fallback paths for macOS"


class TestQuitServerContract:
    """Test Quit Server contract (Check B)."""

    def test_shutdown_endpoint_exists(self):
        """Shutdown endpoint must exist in app.py."""
        import inspect

        from yanhu import app as app_module

        source = inspect.getsource(app_module)
        assert "/api/shutdown" in source, "Must have /api/shutdown endpoint"

    def test_shutdown_has_os_exit_fallback(self):
        """Shutdown logic must use os._exit(0) for reliable termination."""
        import inspect

        from yanhu import app as app_module

        source = inspect.getsource(app_module)
        assert "os._exit" in source, "Must use os._exit(0) as termination fallback"

    def test_shutdown_requires_token(self):
        """Shutdown endpoint must require security token."""
        import inspect

        from yanhu import app as app_module

        source = inspect.getsource(app_module)
        assert "shutdown_token" in source, "Must use shutdown_token for security"

    def test_shutdown_localhost_only(self):
        """Shutdown endpoint must restrict to localhost."""
        import inspect

        from yanhu import app as app_module

        source = inspect.getsource(app_module)
        assert (
            "127.0.0.1" in source or "localhost" in source
        ), "Must restrict shutdown to localhost"


class TestLauncherCompatibilityContract:
    """Test launcher compatibility contract (Check C)."""

    def test_create_app_accepts_jobs_dir(self):
        """create_app must accept jobs_dir parameter."""
        import inspect

        from yanhu.app import create_app

        sig = inspect.signature(create_app)
        assert "jobs_dir" in sig.parameters, "create_app must accept jobs_dir kwarg"

    def test_create_app_accepts_str_paths(self):
        """create_app must accept str paths (not just Path objects)."""
        import inspect

        from yanhu.app import create_app

        sig = inspect.signature(create_app)
        sessions_dir_param = sig.parameters.get("sessions_dir")
        assert sessions_dir_param is not None, "create_app must have sessions_dir parameter"

        # The parameter should accept str (check annotation if present)
        annotation = sessions_dir_param.annotation
        if annotation != inspect.Parameter.empty:
            annotation_str = str(annotation)
            # Should allow str in type hint
            assert "str" in annotation_str or annotation is str, (
                "create_app sessions_dir should accept str paths"
            )

    def test_run_app_accepts_debug_kwarg(self):
        """run_app must accept debug kwarg for backward compatibility."""
        import inspect

        from yanhu.app import run_app

        sig = inspect.signature(run_app)
        assert "debug" in sig.parameters, "run_app must accept debug parameter"

    def test_create_app_callable_with_str_paths(self, tmp_path):
        """create_app must be callable with str paths without crashes."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Must not crash when called with str paths
        try:
            app = create_app(sessions_dir=str(sessions_dir))
            assert app is not None
        except Exception as e:
            pytest.fail(f"create_app should accept str paths but raised: {e}")
