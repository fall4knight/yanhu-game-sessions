"""Tests for API key storage and management."""

from yanhu.keystore import (
    EnvFileKeyStore,
    get_key_status,
    mask_key,
)


class TestMasking:
    """Test key masking functions."""

    def test_mask_key_long_key(self):
        """Mask long API key correctly."""
        key = "sk-ant-1234567890abcdef"
        masked = mask_key(key)
        assert masked == "sk-ant…cdef"
        assert "1234567890ab" not in masked

    def test_mask_key_short_key(self):
        """Don't mask short keys."""
        key = "short"
        masked = mask_key(key)
        assert masked == "short"

    def test_mask_key_none(self):
        """Handle None key."""
        masked = mask_key(None)
        assert masked == ""

    def test_mask_key_empty(self):
        """Handle empty key."""
        masked = mask_key("")
        assert masked == ""

    def test_get_key_status_set(self):
        """Get status for set key."""
        status = get_key_status("sk-ant-1234567890abcdef")
        assert status["set"] is True
        assert status["present"] is True
        assert status["masked"] == "sk-ant…cdef"

    def test_get_key_status_not_set(self):
        """Get status for unset key."""
        status = get_key_status(None)
        assert status["set"] is False
        assert status["present"] is False
        assert status["masked"] == ""


class TestEnvFileKeyStore:
    """Test env file key store."""

    def test_set_and_get_key(self, tmp_path):
        """Set and retrieve key from env file."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        store.set_key("TEST_KEY", "test-value-123")
        value = store.get_key("TEST_KEY")

        assert value == "test-value-123"

    def test_get_nonexistent_key(self, tmp_path):
        """Get nonexistent key returns None."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        value = store.get_key("NONEXISTENT")
        assert value is None

    def test_delete_key(self, tmp_path):
        """Delete key from env file."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        store.set_key("TEST_KEY", "test-value")
        store.delete_key("TEST_KEY")

        value = store.get_key("TEST_KEY")
        assert value is None

    def test_multiple_keys(self, tmp_path):
        """Store and retrieve multiple keys."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        store.set_key("KEY1", "value1")
        store.set_key("KEY2", "value2")
        store.set_key("KEY3", "value3")

        assert store.get_key("KEY1") == "value1"
        assert store.get_key("KEY2") == "value2"
        assert store.get_key("KEY3") == "value3"

    def test_update_existing_key(self, tmp_path):
        """Update existing key value."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        store.set_key("TEST_KEY", "old-value")
        store.set_key("TEST_KEY", "new-value")

        value = store.get_key("TEST_KEY")
        assert value == "new-value"

    def test_env_file_has_secure_permissions(self, tmp_path):
        """Env file should have 600 permissions."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        store.set_key("TEST_KEY", "test-value")

        # Check file exists and has correct permissions
        assert env_file.exists()
        # On Unix-like systems, check for 600 permissions
        import stat
        mode = env_file.stat().st_mode
        # Should be owner read/write only (0o600)
        assert mode & stat.S_IRUSR  # Owner read
        assert mode & stat.S_IWUSR  # Owner write
        assert not (mode & stat.S_IRGRP)  # No group read
        assert not (mode & stat.S_IWGRP)  # No group write
        assert not (mode & stat.S_IROTH)  # No other read
        assert not (mode & stat.S_IWOTH)  # No other write

    def test_get_backend_name(self, tmp_path):
        """Get backend name."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)
        assert store.get_backend_name() == "envfile"

    def test_env_file_format(self, tmp_path):
        """Env file should have readable format."""
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        store.set_key("KEY1", "value1")
        store.set_key("KEY2", "value2")

        content = env_file.read_text()
        assert "KEY1=value1" in content
        assert "KEY2=value2" in content
        assert "# Yanhu Game Sessions" in content  # Header comment
