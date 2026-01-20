"""FFmpeg utilities: availability check, command execution."""

import shutil
import subprocess
from pathlib import Path


class FFmpegNotFoundError(Exception):
    """Raised when ffmpeg is not available on the system."""

    pass


class FFmpegError(Exception):
    """Raised when ffmpeg command fails."""

    pass


def check_ffmpeg_available() -> str:
    """Check if ffmpeg is available and return its path.

    Returns:
        Path to ffmpeg executable

    Raises:
        FFmpegNotFoundError: If ffmpeg is not found
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise FFmpegNotFoundError(
            "ffmpeg not found. Please install ffmpeg:\n"
            "  macOS:   brew install ffmpeg\n"
            "  Ubuntu:  sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )
    return ffmpeg_path


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Duration in seconds

    Raises:
        FFmpegError: If ffprobe fails
    """
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path is None:
        raise FFmpegNotFoundError("ffprobe not found (usually installed with ffmpeg)")

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed: {result.stderr}")

    try:
        return float(result.stdout.strip())
    except ValueError as e:
        raise FFmpegError(f"Failed to parse duration: {result.stdout}") from e


def run_ffmpeg(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given arguments.

    Args:
        args: Arguments to pass to ffmpeg (excluding 'ffmpeg' itself)
        check: If True, raise on non-zero exit code

    Returns:
        CompletedProcess instance

    Raises:
        FFmpegNotFoundError: If ffmpeg is not found
        FFmpegError: If ffmpeg fails and check=True
    """
    ffmpeg_path = check_ffmpeg_available()
    cmd = [ffmpeg_path] + args

    result = subprocess.run(cmd, capture_output=True, text=True)

    if check and result.returncode != 0:
        raise FFmpegError(f"ffmpeg failed: {result.stderr}")

    return result
