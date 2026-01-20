"""Tests for manifest handling."""

import json
from pathlib import Path

from yanhu.manifest import Manifest, SegmentInfo, create_manifest


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
