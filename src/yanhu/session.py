"""Session management: ID generation, directory setup."""

import re
import shutil
from datetime import datetime
from pathlib import Path

# session_id format: YYYY-MM-DD_HH-MM-SS_<game>_<runTag>
SESSION_ID_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_[a-zA-Z0-9_-]+_[a-zA-Z0-9_-]+$"
)


def generate_session_id(game: str, tag: str, timestamp: datetime | None = None) -> str:
    """Generate a session ID from game name, tag, and timestamp.

    Args:
        game: Game name (e.g., "gnosia", "genshin")
        tag: Run tag (e.g., "run01", "session02")
        timestamp: Optional timestamp; defaults to now

    Returns:
        Session ID in format: YYYY-MM-DD_HH-MM-SS_<game>_<tag>
    """
    if timestamp is None:
        timestamp = datetime.now()
    ts_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
    return f"{ts_str}_{game}_{tag}"


def validate_session_id(session_id: str) -> bool:
    """Check if a session ID matches the expected format."""
    return SESSION_ID_PATTERN.match(session_id) is not None


def parse_session_id(session_id: str) -> dict[str, str] | None:
    """Parse session ID into components.

    Returns:
        Dict with keys: date, time, game, tag; or None if invalid
    """
    if not validate_session_id(session_id):
        return None
    parts = session_id.split("_")
    # Format: YYYY-MM-DD_HH-MM-SS_game_tag
    # Split gives: [YYYY-MM-DD, HH-MM-SS, game, tag]
    return {
        "date": parts[0],
        "time": parts[1],
        "game": parts[2],
        "tag": parts[3],
    }


def create_session_directory(
    session_id: str,
    output_dir: Path,
) -> Path:
    """Create session directory structure.

    Creates:
        <output_dir>/<session_id>/
            source/
            segments/

    Returns:
        Path to session directory
    """
    session_dir = output_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "source").mkdir(exist_ok=True)
    (session_dir / "segments").mkdir(exist_ok=True)
    return session_dir


def copy_source_video(
    source_path: Path,
    session_dir: Path,
) -> Path:
    """Copy source video to session's source/ directory.

    Returns:
        Path to the copied video (relative to session_dir)
    """
    dest_dir = session_dir / "source"
    dest_path = dest_dir / source_path.name
    shutil.copy2(source_path, dest_path)
    return Path("source") / source_path.name
