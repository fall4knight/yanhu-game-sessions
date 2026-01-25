"""Key storage and management for API keys.

Provides secure storage for API keys with two backends:
1. KeychainKeyStore: Uses OS keychain via keyring library (preferred)
2. EnvFileKeyStore: Fallback to ~/.yanhu-sessions/.env file with chmod 600

Security:
- Keys are never exposed in full after saving (only masked)
- Keychain storage is OS-managed and encrypted
- Env file fallback uses restrictive file permissions (chmod 600)
- Settings endpoints require local-only access + token
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Protocol


def mask_key(key: str | None) -> str:
    """Mask API key for display.

    Format: first 6 chars + "…" + last 4 chars
    Examples:
        - "sk-ant-1234567890abcdef" -> "sk-ant…cdef"
        - "short" -> "short" (no masking if < 12 chars)
        - None -> ""

    Args:
        key: API key to mask

    Returns:
        Masked key string
    """
    if not key:
        return ""
    if len(key) < 12:
        return key  # Don't mask short keys
    return f"{key[:6]}…{key[-4:]}"


def get_key_status(key: str | None) -> dict[str, str | bool]:
    """Get status of an API key.

    Args:
        key: API key value or None

    Returns:
        Dict with 'set' (bool), 'masked' (str), 'present' (bool)
    """
    return {
        "set": bool(key),
        "masked": mask_key(key) if key else "",
        "present": bool(key),
    }


class KeyStore(Protocol):
    """Protocol for API key storage backends."""

    def get_key(self, key_name: str) -> str | None:
        """Get API key by name.

        Args:
            key_name: Name of the key (e.g., "ANTHROPIC_API_KEY")

        Returns:
            Key value or None if not set
        """
        ...

    def set_key(self, key_name: str, key_value: str) -> None:
        """Set API key.

        Args:
            key_name: Name of the key
            key_value: Key value to store
        """
        ...

    def delete_key(self, key_name: str) -> None:
        """Delete API key.

        Args:
            key_name: Name of the key to delete
        """
        ...

    def get_backend_name(self) -> str:
        """Get name of storage backend.

        Returns:
            Backend name (e.g., "keychain", "envfile")
        """
        ...


class KeychainKeyStore:
    """Store API keys in OS keychain using keyring library."""

    SERVICE_NAME = "yanhu-game-sessions"

    def __init__(self):
        """Initialize keychain key store."""
        try:
            import keyring

            self.keyring = keyring
            # Test keychain access
            self.keyring.get_password(self.SERVICE_NAME, "test")
            self._available = True
        except Exception:
            self._available = False
            self.keyring = None

    def is_available(self) -> bool:
        """Check if keychain is available.

        Returns:
            True if keychain can be used
        """
        return self._available

    def get_key(self, key_name: str) -> str | None:
        """Get API key from keychain."""
        if not self._available:
            return None
        try:
            return self.keyring.get_password(self.SERVICE_NAME, key_name)
        except Exception:
            return None

    def set_key(self, key_name: str, key_value: str) -> None:
        """Set API key in keychain."""
        if not self._available:
            raise RuntimeError("Keychain not available")
        self.keyring.set_password(self.SERVICE_NAME, key_name, key_value)

    def delete_key(self, key_name: str) -> None:
        """Delete API key from keychain."""
        if not self._available:
            return
        try:
            self.keyring.delete_password(self.SERVICE_NAME, key_name)
        except Exception:
            pass  # Key may not exist

    def get_backend_name(self) -> str:
        """Get backend name."""
        return "keychain"


class EnvFileKeyStore:
    """Store API keys in ~/.yanhu-sessions/.env file (fallback)."""

    def __init__(self, env_file: Path | None = None):
        """Initialize env file key store.

        Args:
            env_file: Path to .env file (default: ~/yanhu-sessions/.env)
        """
        if env_file is None:
            env_file = Path.home() / "yanhu-sessions" / ".env"
        self.env_file = env_file

    def _ensure_file_exists(self) -> None:
        """Ensure .env file exists with secure permissions."""
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.env_file.exists():
            self.env_file.touch()
        # Set restrictive permissions (owner read/write only)
        self.env_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    def _load_env(self) -> dict[str, str]:
        """Load key-value pairs from .env file.

        Returns:
            Dict of key names to values
        """
        if not self.env_file.exists():
            return {}

        env_vars = {}
        with open(self.env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        return env_vars

    def _save_env(self, env_vars: dict[str, str]) -> None:
        """Save key-value pairs to .env file.

        Args:
            env_vars: Dict of key names to values
        """
        self._ensure_file_exists()
        with open(self.env_file, "w", encoding="utf-8") as f:
            f.write("# Yanhu Game Sessions - API Keys\n")
            f.write("# This file stores API keys for local use\n")
            f.write("# Permissions: 600 (owner read/write only)\n\n")
            for key, value in sorted(env_vars.items()):
                f.write(f"{key}={value}\n")
        # Ensure permissions are correct after write
        self.env_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600

    def get_key(self, key_name: str) -> str | None:
        """Get API key from .env file."""
        env_vars = self._load_env()
        return env_vars.get(key_name)

    def set_key(self, key_name: str, key_value: str) -> None:
        """Set API key in .env file."""
        env_vars = self._load_env()
        env_vars[key_name] = key_value
        self._save_env(env_vars)

    def delete_key(self, key_name: str) -> None:
        """Delete API key from .env file."""
        env_vars = self._load_env()
        if key_name in env_vars:
            del env_vars[key_name]
            self._save_env(env_vars)

    def get_backend_name(self) -> str:
        """Get backend name."""
        return "envfile"


def get_default_keystore() -> KeyStore:
    """Get default key store (keychain if available, else envfile).

    Returns:
        KeyStore instance
    """
    keychain = KeychainKeyStore()
    if keychain.is_available():
        return keychain
    return EnvFileKeyStore()


# Supported API key names
SUPPORTED_KEYS = [
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
]
