"""Session management: ID generation, directory setup."""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from yanhu.manifest import SourceMetadata

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
    mode: str = "link",
) -> tuple[Path, SourceMetadata]:
    """Copy or link source video to session's source/ directory.

    Args:
        source_path: Path to source video file
        session_dir: Session directory
        mode: "link" (default, try hardlink/symlink) or "copy" (force copy)

    Returns:
        Tuple of (relative_path, source_metadata).
        relative_path is always relative to session_dir (e.g., "source/video.mp4")
        source_metadata contains observability fields for link/copy behavior
    """
    dest_dir = session_dir / "source"
    dest_path = dest_dir / source_path.name
    fallback_error: str | None = None
    actual_mode: str

    # Get inode of original file
    raw_stat = os.stat(source_path, follow_symlinks=True)
    raw_inode = raw_stat.st_ino

    if mode == "copy":
        # Explicit copy mode
        shutil.copy2(source_path, dest_path)
        actual_mode = "copy"
    elif mode == "link":
        # Try hardlink first (same filesystem), then symlink, then copy
        try:
            # Try hardlink (works if same filesystem)
            os.link(source_path, dest_path)
            actual_mode = "hardlink"
        except (OSError, NotImplementedError) as e:
            # Hardlink failed (cross-filesystem or unsupported), try symlink
            # Capture errno for observability
            errno_name = getattr(e, "errno", None)
            error_desc = f"{type(e).__name__}"
            if errno_name == 18:  # EXDEV
                error_desc = "EXDEV (cross-device link)"
            elif errno_name == 1:  # EPERM
                error_desc = "EPERM (operation not permitted)"
            elif errno_name == 13:  # EACCES
                error_desc = "EACCES (permission denied)"
            elif errno_name:
                error_desc = f"errno {errno_name}"

            try:
                os.symlink(source_path, dest_path)
                actual_mode = "symlink"
                fallback_error = f"Hardlink failed ({error_desc}), used symlink"
            except (OSError, NotImplementedError) as e2:
                # Symlink failed (Windows without admin?), fallback to copy
                errno_name2 = getattr(e2, "errno", None)
                error_desc2 = f"{type(e2).__name__}"
                if errno_name2:
                    error_desc2 = f"errno {errno_name2}"
                shutil.copy2(source_path, dest_path)
                actual_mode = "copy"
                fallback_error = (
                    f"Hardlink failed ({error_desc}), symlink failed ({error_desc2}), "
                    f"used copy (disk usage doubled)"
                )
    else:
        raise ValueError(f"Invalid source mode: {mode}. Must be 'link' or 'copy'.")

    # Verify actual result using stat
    session_stat = os.lstat(dest_path)  # lstat to not follow symlinks
    session_inode = session_stat.st_ino
    link_count = session_stat.st_nlink
    symlink_target: str | None = None

    # Verify mode matches expectations
    if os.path.islink(dest_path):
        # It's a symlink
        if actual_mode != "symlink":
            # This shouldn't happen, but capture it
            fallback_error = (
                f"{fallback_error or ''}; WARN: expected {actual_mode} but got symlink"
            )
            actual_mode = "symlink"
        symlink_target = str(os.readlink(dest_path))
    elif session_inode == raw_inode:
        # Same inode = hardlink
        if actual_mode != "hardlink":
            fallback_error = (
                f"{fallback_error or ''}; WARN: expected {actual_mode} but got hardlink"
            )
            actual_mode = "hardlink"
        if link_count < 2:
            fallback_error = (
                f"{fallback_error or ''}; WARN: hardlink but link_count={link_count}<2"
            )
    else:
        # Different inode = copy
        if actual_mode != "copy":
            fallback_error = (
                f"{fallback_error or ''}; WARN: expected {actual_mode} but got copy"
            )
            actual_mode = "copy"

    metadata = SourceMetadata(
        source_mode=actual_mode,
        source_inode_raw=raw_inode,
        source_inode_session=session_inode,
        source_link_count=link_count,
        source_fallback_error=fallback_error,
        source_symlink_target=symlink_target,
    )

    return Path("source") / source_path.name, metadata
