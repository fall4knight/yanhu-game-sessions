"""Tests for cross-platform paths module."""

from pathlib import Path


class TestGetDirs:
    """Test directory path functions."""

    def test_get_data_dir_returns_path(self):
        """get_data_dir should return a Path object."""
        from yanhu.paths import get_data_dir

        data_dir = get_data_dir()
        assert isinstance(data_dir, Path)
        assert "yanhu-sessions" in str(data_dir)

    def test_get_config_dir_returns_path(self):
        """get_config_dir should return a Path object."""
        from yanhu.paths import get_config_dir

        config_dir = get_config_dir()
        assert isinstance(config_dir, Path)
        assert "yanhu-sessions" in str(config_dir)

    def test_get_env_file_path_in_config_dir(self):
        """get_env_file_path should return path in config dir."""
        from yanhu.paths import get_config_dir, get_env_file_path

        env_path = get_env_file_path()
        config_dir = get_config_dir()

        assert env_path.parent == config_dir
        assert env_path.name == ".env"

    def test_get_sessions_dir_in_data_dir(self):
        """get_sessions_dir should return path in data dir."""
        from yanhu.paths import get_data_dir, get_sessions_dir

        sessions_dir = get_sessions_dir()
        data_dir = get_data_dir()

        assert sessions_dir.parent == data_dir
        assert sessions_dir.name == "sessions"

    def test_get_raw_dir_in_data_dir(self):
        """get_raw_dir should return path in data dir."""
        from yanhu.paths import get_data_dir, get_raw_dir

        raw_dir = get_raw_dir()
        data_dir = get_data_dir()

        assert raw_dir.parent == data_dir
        assert raw_dir.name == "raw"


class TestMigration:
    """Test migration from legacy path."""

    def test_migrate_no_legacy_file(self, tmp_path, monkeypatch):
        """No migration if legacy .env doesn't exist."""
        from yanhu import paths

        # Mock legacy path to tmp location
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        monkeypatch.setattr(paths, "LEGACY_BASE_DIR", legacy_dir)

        # Mock config dir
        new_config_dir = tmp_path / "new_config"
        monkeypatch.setattr(paths, "get_config_dir", lambda: new_config_dir)

        result = paths.migrate_from_legacy_path()

        assert result is False

    def test_migrate_copies_env_file(self, tmp_path, monkeypatch):
        """Migration copies .env from legacy to new location."""
        from yanhu import paths

        # Create legacy .env
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        legacy_env = legacy_dir / ".env"
        legacy_env.write_text("TEST_KEY=test_value\n")
        monkeypatch.setattr(paths, "LEGACY_BASE_DIR", legacy_dir)

        # Mock config dir
        new_config_dir = tmp_path / "new_config"
        monkeypatch.setattr(paths, "get_config_dir", lambda: new_config_dir)

        result = paths.migrate_from_legacy_path()

        assert result is True
        # New .env should exist with same content
        new_env = new_config_dir / ".env"
        assert new_env.exists()
        assert "TEST_KEY=test_value" in new_env.read_text()
        # Legacy should be renamed to .env.migrated
        assert not legacy_env.exists()
        assert (legacy_dir / ".env.migrated").exists()

    def test_migrate_skips_if_already_migrated(self, tmp_path, monkeypatch):
        """Skip migration if .env.migrated marker exists."""
        from yanhu import paths

        # Create legacy .env and .env.migrated marker
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        legacy_env = legacy_dir / ".env"
        legacy_env.write_text("OLD_KEY=old_value\n")
        (legacy_dir / ".env.migrated").touch()
        monkeypatch.setattr(paths, "LEGACY_BASE_DIR", legacy_dir)

        # Mock config dir
        new_config_dir = tmp_path / "new_config"
        monkeypatch.setattr(paths, "get_config_dir", lambda: new_config_dir)

        result = paths.migrate_from_legacy_path()

        assert result is False
        # New .env should NOT be created
        assert not (new_config_dir / ".env").exists()

    def test_migrate_skips_if_new_env_exists(self, tmp_path, monkeypatch):
        """Skip migration if new .env already has content."""
        from yanhu import paths

        # Create legacy .env
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        legacy_env = legacy_dir / ".env"
        legacy_env.write_text("OLD_KEY=old_value\n")
        monkeypatch.setattr(paths, "LEGACY_BASE_DIR", legacy_dir)

        # Create new .env with content
        new_config_dir = tmp_path / "new_config"
        new_config_dir.mkdir()
        new_env = new_config_dir / ".env"
        new_env.write_text("NEW_KEY=new_value\n")
        monkeypatch.setattr(paths, "get_config_dir", lambda: new_config_dir)

        result = paths.migrate_from_legacy_path()

        assert result is False
        # New .env should keep its content
        assert "NEW_KEY=new_value" in new_env.read_text()
        # Legacy should remain untouched
        assert legacy_env.exists()


class TestEnsureDirectories:
    """Test ensure_directories function."""

    def test_creates_directories(self, tmp_path, monkeypatch):
        """ensure_directories creates sessions and raw dirs."""
        from yanhu import paths

        # Mock data dir
        data_dir = tmp_path / "data"
        monkeypatch.setattr(paths, "get_data_dir", lambda: data_dir)
        monkeypatch.setattr(paths, "get_sessions_dir", lambda: data_dir / "sessions")
        monkeypatch.setattr(paths, "get_raw_dir", lambda: data_dir / "raw")

        # Mock migration to skip
        legacy_dir = tmp_path / "legacy_empty"
        monkeypatch.setattr(paths, "LEGACY_BASE_DIR", legacy_dir)
        monkeypatch.setattr(paths, "get_config_dir", lambda: tmp_path / "config")

        sessions_dir, raw_dir = paths.ensure_directories()

        assert sessions_dir.exists()
        assert raw_dir.exists()
        assert sessions_dir.name == "sessions"
        assert raw_dir.name == "raw"


class TestDisplayPath:
    """Test get_display_path function."""

    def test_display_path_uses_tilde(self):
        """Display path should use ~ for home directory."""
        from yanhu.paths import get_display_path

        home = Path.home()
        test_path = home / "some" / "nested" / "path"

        display = get_display_path(test_path)

        assert display.startswith("~/")
        assert "some/nested/path" in display

    def test_display_path_non_home_path(self, tmp_path):
        """Display path for non-home path returns str."""
        from yanhu.paths import get_display_path

        # tmp_path is typically not under home
        test_path = tmp_path / "test"

        display = get_display_path(test_path)

        # Should return string representation
        assert str(tmp_path) in display or display.startswith("~/")
