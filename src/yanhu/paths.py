"""Cross-platform paths for Yanhu Sessions.

Uses platformdirs to choose OS-appropriate locations:
- Windows: %LOCALAPPDATA%/yanhu-sessions (e.g., C:/Users/<user>/AppData/Local/yanhu-sessions)
- macOS: ~/Library/Application Support/yanhu-sessions
- Linux: ~/.local/share/yanhu-sessions (data), ~/.config/yanhu-sessions (config)

Provides one-time migration from legacy ~/yanhu-sessions path.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import platformdirs

logger = logging.getLogger(__name__)

# Application name for platformdirs
APP_NAME = "yanhu-sessions"

# Legacy path (pre-platformdirs)
LEGACY_BASE_DIR = Path.home() / "yanhu-sessions"


def get_data_dir() -> Path:
    """Get OS-appropriate directory for session data (videos, outputs).

    Returns:
        Path to data directory (created if needed)
    """
    return Path(platformdirs.user_data_dir(APP_NAME))


def get_config_dir() -> Path:
    """Get OS-appropriate directory for configuration files (.env, settings).

    Returns:
        Path to config directory (created if needed)
    """
    return Path(platformdirs.user_config_dir(APP_NAME))


def get_env_file_path() -> Path:
    """Get path to .env file for API keys.

    Returns:
        Path to .env file in config directory
    """
    return get_config_dir() / ".env"


def get_sessions_dir() -> Path:
    """Get path to sessions output directory.

    Returns:
        Path to sessions directory in data directory
    """
    return get_data_dir() / "sessions"


def get_raw_dir() -> Path:
    """Get path to raw videos input directory.

    Returns:
        Path to raw directory in data directory
    """
    return get_data_dir() / "raw"


def migrate_from_legacy_path() -> bool:
    """Migrate .env file from legacy ~/yanhu-sessions/.env if it exists.

    One-time migration: copies .env from legacy location to new config dir,
    then renames the legacy file to .env.migrated to prevent re-migration.

    Returns:
        True if migration occurred, False if no migration needed
    """
    legacy_env = LEGACY_BASE_DIR / ".env"
    new_env = get_env_file_path()

    # Skip if legacy .env doesn't exist
    if not legacy_env.exists():
        return False

    # Skip if already migrated (marker file exists)
    legacy_migrated = LEGACY_BASE_DIR / ".env.migrated"
    if legacy_migrated.exists():
        return False

    # Skip if new .env already has content (don't overwrite)
    if new_env.exists() and new_env.stat().st_size > 0:
        logger.info(
            f"Legacy .env exists at {legacy_env} but new .env already has content. "
            "Skipping migration. You may want to manually merge the files."
        )
        return False

    try:
        # Ensure config directory exists
        new_env.parent.mkdir(parents=True, exist_ok=True)

        # Copy legacy .env to new location
        shutil.copy2(legacy_env, new_env)

        # Mark as migrated (rename to .env.migrated)
        legacy_env.rename(legacy_migrated)

        logger.info(f"Migrated API keys from {legacy_env} to {new_env}")
        return True

    except OSError as e:
        logger.warning(f"Failed to migrate .env from legacy path: {e}")
        return False


def ensure_directories() -> tuple[Path, Path]:
    """Ensure sessions and raw directories exist.

    Also triggers migration from legacy path if needed.

    Returns:
        Tuple of (sessions_dir, raw_dir)
    """
    # Try migration first
    migrate_from_legacy_path()

    # Create directories
    sessions_dir = get_sessions_dir()
    raw_dir = get_raw_dir()

    sessions_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    return sessions_dir, raw_dir


def get_display_path(path: Path) -> str:
    """Get user-friendly display path, using ~ for home directory.

    Args:
        path: Path to format

    Returns:
        String with ~ substituted for home directory where applicable
    """
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)
