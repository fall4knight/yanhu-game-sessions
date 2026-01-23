"""Tests for manifest handling."""

import json
from pathlib import Path

from yanhu.manifest import Manifest, SegmentInfo, SourceMetadata, create_manifest


class TestSegmentInfo:
    """Test SegmentInfo data structure."""

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        seg = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/session_part_0001.mp4",
        )
        d = seg.to_dict()
        assert d["id"] == "part_0001"
        assert d["start_time"] == 0.0
        assert d["end_time"] == 60.0
        assert d["video_path"] == "segments/session_part_0001.mp4"

    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        d = {
            "id": "part_0002",
            "start_time": 60.0,
            "end_time": 120.0,
            "video_path": "segments/session_part_0002.mp4",
        }
        seg = SegmentInfo.from_dict(d)
        assert seg.id == "part_0002"
        assert seg.start_time == 60.0
        assert seg.end_time == 120.0
        assert seg.video_path == "segments/session_part_0002.mp4"

    def test_video_path_is_relative(self):
        """Video path should be relative to session directory."""
        seg = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test_part_0001.mp4",
        )
        # Should not start with /
        assert not seg.video_path.startswith("/")
        # Should be relative path format
        assert seg.video_path.startswith("segments/")


class TestManifest:
    """Test Manifest data structure."""

    def test_create_manifest(self):
        """Should create manifest with correct fields."""
        manifest = create_manifest(
            session_id="2026-01-19_21-45-00_gnosia_run01",
            source_video=Path("/videos/game.mp4"),
            source_video_local="source/game.mp4",
            segment_duration=60,
        )
        assert manifest.session_id == "2026-01-19_21-45-00_gnosia_run01"
        assert manifest.source_video_local == "source/game.mp4"
        assert manifest.segment_duration_seconds == 60
        assert manifest.segments == []
        assert manifest.created_at  # should be set

    def test_to_dict_and_from_dict_roundtrip(self):
        """Should serialize and deserialize correctly."""
        original = Manifest(
            session_id="2026-01-19_21-45-00_gnosia_run01",
            created_at="2026-01-19T21:45:00",
            source_video="/videos/game.mp4",
            source_video_local="source/game.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/s_part_0001.mp4"),
                SegmentInfo("part_0002", 60.0, 120.0, "segments/s_part_0002.mp4"),
            ],
        )
        d = original.to_dict()
        restored = Manifest.from_dict(d)

        assert restored.session_id == original.session_id
        assert restored.created_at == original.created_at
        assert restored.source_video == original.source_video
        assert restored.source_video_local == original.source_video_local
        assert restored.segment_duration_seconds == original.segment_duration_seconds
        assert len(restored.segments) == 2
        assert restored.segments[0].id == "part_0001"
        assert restored.segments[1].id == "part_0002"

    def test_save_and_load(self, tmp_path):
        """Should save to file and load back correctly."""
        session_dir = tmp_path / "2026-01-19_21-45-00_gnosia_run01"
        session_dir.mkdir()

        manifest = Manifest(
            session_id="2026-01-19_21-45-00_gnosia_run01",
            created_at="2026-01-19T21:45:00",
            source_video="/videos/game.mp4",
            source_video_local="source/game.mp4",
            segment_duration_seconds=60,
            segments=[],
        )

        # Save
        manifest_path = manifest.save(session_dir)
        assert manifest_path.exists()
        assert manifest_path.name == "manifest.json"

        # Load
        loaded = Manifest.load(session_dir)
        assert loaded.session_id == manifest.session_id
        assert loaded.source_video_local == manifest.source_video_local

    def test_manifest_json_is_valid(self, tmp_path):
        """Saved manifest should be valid JSON."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        manifest = create_manifest(
            session_id="2026-01-19_21-45-00_gnosia_run01",
            source_video=Path("/videos/game.mp4"),
            source_video_local="source/game.mp4",
            segment_duration=60,
        )
        manifest_path = manifest.save(session_dir)

        # Should be parseable JSON
        with open(manifest_path) as f:
            data = json.load(f)

        # Should have required fields
        assert "session_id" in data
        assert "created_at" in data
        assert "source_video" in data
        assert "source_video_local" in data
        assert "segment_duration_seconds" in data
        assert "segments" in data


class TestManifestPathRelativization:
    """Test that manifest paths are properly relative."""

    def test_source_video_local_is_relative(self):
        """source_video_local should be relative to session directory."""
        manifest = create_manifest(
            session_id="test",
            source_video=Path("/absolute/path/video.mp4"),
            source_video_local="source/video.mp4",  # relative
            segment_duration=60,
        )
        # Should not start with /
        assert not manifest.source_video_local.startswith("/")

    def test_segment_video_path_is_relative(self):
        """Segment video_path should be relative to session directory."""
        manifest = Manifest(
            session_id="test",
            created_at="2026-01-19T21:45:00",
            source_video="/absolute/path.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/test_part_0001.mp4"),
            ],
        )
        for seg in manifest.segments:
            assert not seg.video_path.startswith("/")
            assert seg.video_path.startswith("segments/")


class TestSourceMetadata:
    """Test SourceMetadata data structure (P2.1 observability)."""

    def test_to_dict_hardlink(self):
        """Should serialize hardlink metadata correctly."""
        metadata = SourceMetadata(
            source_mode="hardlink",
            source_inode_raw=12345,
            source_inode_session=12345,
            source_link_count=2,
        )
        d = metadata.to_dict()
        assert d["source_mode"] == "hardlink"
        assert d["source_inode_raw"] == 12345
        assert d["source_inode_session"] == 12345
        assert d["source_link_count"] == 2
        assert "source_fallback_error" not in d
        assert "source_symlink_target" not in d

    def test_to_dict_symlink(self):
        """Should serialize symlink metadata correctly."""
        metadata = SourceMetadata(
            source_mode="symlink",
            source_inode_raw=12345,
            source_inode_session=67890,
            source_link_count=1,
            source_fallback_error="Hardlink failed (EXDEV), used symlink",
            source_symlink_target="/absolute/path/to/video.mp4",
        )
        d = metadata.to_dict()
        assert d["source_mode"] == "symlink"
        assert d["source_inode_raw"] == 12345
        assert d["source_inode_session"] == 67890
        assert d["source_link_count"] == 1
        assert d["source_fallback_error"] == "Hardlink failed (EXDEV), used symlink"
        assert d["source_symlink_target"] == "/absolute/path/to/video.mp4"

    def test_to_dict_copy(self):
        """Should serialize copy metadata correctly."""
        fallback_msg = (
            "Hardlink failed (EXDEV), symlink failed (errno 1), "
            "used copy (disk usage doubled)"
        )
        metadata = SourceMetadata(
            source_mode="copy",
            source_inode_raw=12345,
            source_inode_session=99999,
            source_link_count=1,
            source_fallback_error=fallback_msg,
        )
        d = metadata.to_dict()
        assert d["source_mode"] == "copy"
        assert d["source_inode_raw"] == 12345
        assert d["source_inode_session"] == 99999
        assert d["source_link_count"] == 1
        assert "Hardlink failed" in d["source_fallback_error"]
        assert "source_symlink_target" not in d

    def test_from_dict_roundtrip(self):
        """Should deserialize from dict correctly."""
        original = SourceMetadata(
            source_mode="symlink",
            source_inode_raw=111,
            source_inode_session=222,
            source_link_count=1,
            source_fallback_error="test error",
            source_symlink_target="/path/to/target",
        )
        d = original.to_dict()
        restored = SourceMetadata.from_dict(d)
        assert restored.source_mode == original.source_mode
        assert restored.source_inode_raw == original.source_inode_raw
        assert restored.source_inode_session == original.source_inode_session
        assert restored.source_link_count == original.source_link_count
        assert restored.source_fallback_error == original.source_fallback_error
        assert restored.source_symlink_target == original.source_symlink_target


class TestManifestWithSourceMetadata:
    """Test Manifest with source_metadata field."""

    def test_manifest_with_source_metadata(self):
        """Should include source_metadata in serialization."""
        metadata = SourceMetadata(
            source_mode="hardlink",
            source_inode_raw=12345,
            source_inode_session=12345,
            source_link_count=2,
        )
        manifest = create_manifest(
            session_id="test",
            source_video=Path("/videos/game.mp4"),
            source_video_local="source/game.mp4",
            segment_duration=60,
            source_metadata=metadata,
        )
        assert manifest.source_metadata is not None
        assert manifest.source_metadata.source_mode == "hardlink"
        assert manifest.source_metadata.source_inode_raw == 12345

    def test_manifest_to_dict_includes_source_metadata(self):
        """Should serialize source_metadata to dict."""
        metadata = SourceMetadata(
            source_mode="copy",
            source_inode_raw=111,
            source_inode_session=222,
            source_link_count=1,
        )
        manifest = Manifest(
            session_id="test",
            created_at="2026-01-23T00:00:00",
            source_video="/videos/game.mp4",
            source_video_local="source/game.mp4",
            segment_duration_seconds=60,
            segments=[],
            source_metadata=metadata,
        )
        d = manifest.to_dict()
        assert "source_metadata" in d
        assert d["source_metadata"]["source_mode"] == "copy"
        assert d["source_metadata"]["source_inode_raw"] == 111
        assert d["source_metadata"]["source_inode_session"] == 222

    def test_manifest_from_dict_with_source_metadata(self):
        """Should deserialize source_metadata from dict."""
        d = {
            "session_id": "test",
            "created_at": "2026-01-23T00:00:00",
            "source_video": "/videos/game.mp4",
            "source_video_local": "source/game.mp4",
            "segment_duration_seconds": 60,
            "segments": [],
            "source_metadata": {
                "source_mode": "symlink",
                "source_inode_raw": 333,
                "source_inode_session": 444,
                "source_link_count": 1,
                "source_symlink_target": "/path/to/video.mp4",
            },
        }
        manifest = Manifest.from_dict(d)
        assert manifest.source_metadata is not None
        assert manifest.source_metadata.source_mode == "symlink"
        assert manifest.source_metadata.source_inode_raw == 333
        assert manifest.source_metadata.source_inode_session == 444
        assert manifest.source_metadata.source_symlink_target == "/path/to/video.mp4"

    def test_manifest_without_source_metadata(self):
        """Should handle legacy manifests without source_metadata."""
        d = {
            "session_id": "test",
            "created_at": "2026-01-23T00:00:00",
            "source_video": "/videos/game.mp4",
            "source_video_local": "source/game.mp4",
            "segment_duration_seconds": 60,
            "segments": [],
        }
        manifest = Manifest.from_dict(d)
        assert manifest.source_metadata is None

    def test_manifest_save_load_with_source_metadata(self, tmp_path):
        """Should save and load source_metadata correctly."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        metadata = SourceMetadata(
            source_mode="hardlink",
            source_inode_raw=12345,
            source_inode_session=12345,
            source_link_count=2,
        )
        manifest = create_manifest(
            session_id="test",
            source_video=Path("/videos/game.mp4"),
            source_video_local="source/game.mp4",
            segment_duration=60,
            source_metadata=metadata,
        )

        # Save
        manifest_path = manifest.save(session_dir)
        assert manifest_path.exists()

        # Verify JSON contains source_metadata
        with open(manifest_path) as f:
            data = json.load(f)
        assert "source_metadata" in data
        assert data["source_metadata"]["source_mode"] == "hardlink"

        # Load
        loaded = Manifest.load(session_dir)
        assert loaded.source_metadata is not None
        assert loaded.source_metadata.source_mode == "hardlink"
        assert loaded.source_metadata.source_inode_raw == 12345
