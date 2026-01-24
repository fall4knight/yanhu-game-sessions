"""Desktop launcher for Yanhu Sessions.

Provides a double-click entrypoint for non-programmers.
"""

from __future__ import annotations

import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

from yanhu.app import create_app, run_app


def check_ffmpeg_availability() -> tuple[bool, str | None]:
    """Check if ffmpeg and ffprobe are available.

    Returns:
        Tuple of (is_available, error_message).
        If available, error_message is None.
    """
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None

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
    """
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

    # Create app
    host = "127.0.0.1"
    port = 8787
    app = create_app(
        sessions_dir=str(sessions_dir),
        raw_dir=str(raw_dir),
        jobs_dir=str(sessions_dir.parent / "_queue" / "jobs"),
        worker_enabled=True,
        allow_any_path=False,
        preset="fast",
    )

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

    # Start Flask app (blocking)
    try:
        run_app(app, host=host, port=port, debug=False)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)


if __name__ == "__main__":
    run_launcher()
