"""Desktop launcher for Yanhu Sessions.

Provides a double-click entrypoint for non-programmers.
"""

from __future__ import annotations

import argparse
import inspect
import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path

from yanhu.app import create_app, run_app

logger = logging.getLogger(__name__)


def filter_kwargs_by_signature(func, kwargs: dict) -> dict:
    """Filter kwargs to only include parameters accepted by func's signature.

    Logs a warning when dropping unexpected kwargs.

    Args:
        func: The function to inspect
        kwargs: Dictionary of keyword arguments

    Returns:
        Filtered dictionary with only valid parameters
    """
    sig = inspect.signature(func)
    valid_params = set(sig.parameters.keys())
    filtered = {}
    for key, value in kwargs.items():
        if key in valid_params:
            filtered[key] = value
        else:
            logger.warning(f"Dropping unexpected kwarg '{key}' when calling {func.__name__}")
    return filtered


def check_ffmpeg_availability() -> tuple[bool, str | None]:
    """Check if ffmpeg and ffprobe are available.

    Returns:
        Tuple of (is_available, error_message).
        If available, error_message is None.
    """
    from yanhu.ffmpeg_utils import find_ffmpeg, find_ffprobe

    ffmpeg_ok = find_ffmpeg() is not None
    ffprobe_ok = find_ffprobe() is not None

    if not ffmpeg_ok and not ffprobe_ok:
        return False, "ffmpeg and ffprobe not found"
    elif not ffmpeg_ok:
        return False, "ffmpeg not found (ffprobe is available)"
    elif not ffprobe_ok:
        return False, "ffprobe not found (ffmpeg is available)"

    return True, None


def ensure_default_directories() -> tuple[Path, Path]:
    """Ensure default sessions and raw directories exist.

    Returns:
        Tuple of (sessions_dir, raw_dir).
    """
    # Use ~/yanhu-sessions as default
    base_dir = Path.home() / "yanhu-sessions"
    sessions_dir = base_dir / "sessions"
    raw_dir = base_dir / "raw"

    # Create directories
    sessions_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    return sessions_dir, raw_dir


def selfcheck_asr() -> int:
    """Run ASR import selfcheck for packaged builds.

    Verifies that all required ASR runtime modules can be imported.
    This is used by CI to validate that PyInstaller bundled ASR dependencies correctly.

    Returns:
        Exit code: 0 if all imports succeed, 1 otherwise
    """
    # Attempt to set UTF-8 encoding for Windows compatibility
    # (but we still use ASCII symbols for maximum robustness)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass  # Silently continue with default encoding

    print("=" * 60)
    print("Yanhu Desktop - ASR Import Selfcheck")
    print("=" * 60)
    print()

    # List of required ASR runtime modules
    required_modules = [
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

    successful = []
    failed = []

    for module_name in required_modules:
        try:
            __import__(module_name)
            successful.append(module_name)
            print(f"  [OK] {module_name}")
        except ImportError as e:
            failed.append(f"{module_name}: {e}")
            print(f"  [FAIL] {module_name} - {e}")

    print()
    print(f"Successful: {len(successful)}/{len(required_modules)}")
    print(f"Failed: {len(failed)}")
    print()

    # Check for faster_whisper assets (VAD model)
    asset_check_passed = True
    print("Checking faster_whisper assets:")
    try:
        # Try to locate the VAD asset file
        import faster_whisper

        # Check if this is a real module (has __file__ attribute)
        if not hasattr(faster_whisper, "__file__") or faster_whisper.__file__ is None:
            # This is a mock module, skip asset check
            print("  [SKIP] faster_whisper module is mocked (no __file__)")
        else:
            # Real module, try to find assets
            try:
                import importlib.resources as importlib_resources

                # Python 3.9+
                if hasattr(importlib_resources, "files"):
                    assets_path = importlib_resources.files("faster_whisper") / "assets"
                    vad_asset = assets_path / "silero_vad.onnx"
                    if not vad_asset.is_file():
                        # Try alternative name
                        vad_asset = assets_path / "silero_vad_v6.onnx"

                    if vad_asset.is_file():
                        print(f"  [OK] VAD asset found: {vad_asset.name}")
                    else:
                        print("  [FAIL] VAD asset (silero_vad*.onnx) not found")
                        asset_check_passed = False
                else:
                    # Fallback: try direct path lookup
                    fw_path = Path(faster_whisper.__file__).parent / "assets"
                    if fw_path.exists():
                        vad_files = list(fw_path.glob("silero_vad*.onnx"))
                        if vad_files:
                            print(f"  [OK] VAD asset found: {vad_files[0].name}")
                        else:
                            print("  [FAIL] VAD asset (silero_vad*.onnx) not found")
                            asset_check_passed = False
                    else:
                        print(f"  [FAIL] Assets directory not found: {fw_path}")
                        asset_check_passed = False
            except Exception as e:
                print(f"  [FAIL] Asset check error: {e}")
                asset_check_passed = False
    except ImportError:
        # faster_whisper not available, already reported in module check above
        print("  [SKIP] faster_whisper not available for asset check")

    print()

    if failed or not asset_check_passed:
        print("=" * 60)
        print("ASR SELFCHECK FAILED")
        print("=" * 60)
        print()
        if failed:
            print("Missing ASR dependencies - packaging error.")
        if not asset_check_passed:
            print("Missing faster_whisper assets - packaging error.")
        return 1

    print("=" * 60)
    print("ASR SELFCHECK PASSED")
    print("=" * 60)
    return 0


def open_browser(url: str, delay: float = 1.5):
    """Open browser after a delay.

    Args:
        url: URL to open
        delay: Delay in seconds before opening
    """
    time.sleep(delay)
    webbrowser.open(url)


def run_launcher():
    """Run the desktop launcher.

    This is the main entrypoint for the packaged desktop app.
    Supports --selfcheck-asr flag for CI verification.
    """
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Yanhu Sessions Desktop Launcher", add_help=False
    )
    parser.add_argument(
        "--selfcheck-asr",
        action="store_true",
        help="Run ASR import selfcheck and exit (for CI verification)",
    )
    args, _ = parser.parse_known_args()

    # Handle selfcheck mode
    if args.selfcheck_asr:
        sys.exit(selfcheck_asr())

    print("=" * 60)
    print("Yanhu Game Sessions - Desktop Launcher")
    print("=" * 60)

    # Check ffmpeg availability
    ffmpeg_ok, ffmpeg_error = check_ffmpeg_availability()
    if not ffmpeg_ok:
        print(f"\nWARNING: {ffmpeg_error}")
        print("\nThe app will start, but video processing will fail.")
        print("Please install ffmpeg to use all features.")
        print("\nInstall instructions:")
        print("  macOS:   brew install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        print("  Linux:   sudo apt-get install ffmpeg (Debian/Ubuntu)")
        print("           sudo yum install ffmpeg (RHEL/CentOS)")
        print("\n" + "=" * 60)

    # Ensure directories exist
    sessions_dir, raw_dir = ensure_default_directories()
    print(f"\nSessions directory: {sessions_dir}")
    print(f"Raw videos directory: {raw_dir}")

    # Create app with defensive kwarg filtering
    host = "127.0.0.1"
    port = 8787

    create_app_kwargs = {
        "sessions_dir": str(sessions_dir),
        "raw_dir": str(raw_dir),
        "jobs_dir": str(sessions_dir.parent / "_queue" / "jobs"),
        "worker_enabled": True,
        "allow_any_path": False,
        "preset": "fast",
    }
    create_app_kwargs = filter_kwargs_by_signature(create_app, create_app_kwargs)
    app = create_app(**create_app_kwargs)

    # Set ffmpeg check flag for app to display warning
    app.config["ffmpeg_available"] = ffmpeg_ok
    app.config["ffmpeg_error"] = ffmpeg_error

    url = f"http://{host}:{port}"
    print(f"\nStarting web server at {url}")
    print("\nOpening browser...")
    print("\nPress Ctrl+C to stop the server and exit.")
    print("=" * 60 + "\n")

    # Open browser in background thread
    browser_thread = threading.Thread(target=open_browser, args=(url,), daemon=True)
    browser_thread.start()

    # Start Flask app (blocking) with defensive kwarg filtering
    try:
        run_app_kwargs = {
            "sessions_dir": sessions_dir,
            "host": host,
            "port": port,
            "raw_dir": raw_dir,
            "worker_enabled": True,
            "allow_any_path": False,
            "preset": "fast",
            "debug": False,
        }
        run_app_kwargs = filter_kwargs_by_signature(run_app, run_app_kwargs)
        run_app(**run_app_kwargs)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)


if __name__ == "__main__":
    run_launcher()
