"""Tests for transcribe limits (partial-by-limit) feature."""

from unittest.mock import MagicMock, patch

from yanhu.manifest import Manifest, SegmentInfo
from yanhu.transcriber import TranscribeStats, transcribe_session


class TestTranscribeLimits:
    """Test transcribe limit and max_total_seconds parameters."""

    def test_limit_transcribes_only_first_n_segments(self, tmp_path):
        """With --transcribe-limit N, only first N segments are transcribed."""
        # Create manifest with 5 segments
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T10:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "seg1.mp4"),
                SegmentInfo("part_0002", 10.0, 20.0, "seg2.mp4"),
                SegmentInfo("part_0003", 20.0, 30.0, "seg3.mp4"),
                SegmentInfo("part_0004", 30.0, 40.0, "seg4.mp4"),
                SegmentInfo("part_0005", 40.0, 50.0, "seg5.mp4"),
            ],
        )

        # Create analysis directory
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Mock the ASR backend to track which segments were called
        transcribed_segments = []

        def mock_transcribe(segment, session_dir, max_seconds, session_id=None):
            transcribed_segments.append(segment.id)
            from yanhu.transcriber import AsrResult

            return AsrResult(
                segment_id=segment.id, asr_items=[], asr_backend="mock", asr_config={}
            )

        with patch("yanhu.transcriber.get_asr_backend") as mock_get_backend:
            with patch("yanhu.transcriber.merge_asr_to_analysis") as mock_merge:
                # Make merge a no-op
                mock_merge.return_value = None
                mock_backend = MagicMock()
                mock_backend.transcribe_segment = mock_transcribe
                mock_get_backend.return_value = mock_backend

                # Transcribe with limit=2
                stats = transcribe_session(
                    manifest=manifest,
                    session_dir=tmp_path,
                    backend="mock",
                    limit=2,
                )

                # Assert only first 2 segments were transcribed
                assert len(transcribed_segments) == 2
                assert transcribed_segments == ["part_0001", "part_0002"]

                # Assert stats
                assert stats.processed == 2
                assert stats.total == 5
                assert stats.skipped_limit == 3  # Remaining 3 segments

    def test_manifest_coverage_saved_when_limit_used(self, tmp_path):
        """When limit is used, manifest.transcribe_coverage is saved to manifest."""
        # Simulate what process_job does after transcribe_session
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T10:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "seg1.mp4"),
                SegmentInfo("part_0002", 10.0, 20.0, "seg2.mp4"),
                SegmentInfo("part_0003", 20.0, 30.0, "seg3.mp4"),
            ],
        )

        # Create session dir
        session_dir = tmp_path / manifest.session_id
        session_dir.mkdir()

        # Simulate transcribe stats with skipped_limit > 0
        stats = TranscribeStats()
        stats.processed = 2
        stats.total = 3
        stats.skipped_limit = 1

        # This is what process_job does when skipped_limit > 0
        if stats.skipped_limit > 0:
            manifest.transcribe_coverage = {
                "processed": stats.processed,
                "total": stats.total,
                "skipped_limit": stats.skipped_limit,
            }
            manifest.save(session_dir)

        # Load manifest and verify coverage was saved
        loaded_manifest = Manifest.load(session_dir)

        assert loaded_manifest.transcribe_coverage is not None
        assert loaded_manifest.transcribe_coverage["processed"] == 2
        assert loaded_manifest.transcribe_coverage["total"] == 3
        assert loaded_manifest.transcribe_coverage["skipped_limit"] == 1

    def test_overview_shows_partial_marker_when_limit_used(self, tmp_path):
        """Overview.md shows PARTIAL marker when transcribe_coverage exists."""
        from yanhu.composer import compose_overview

        manifest = Manifest(
            session_id="2026-01-23_10-00-00_testgame_run01",
            created_at="2026-01-23T10:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "seg1.mp4"),
                SegmentInfo("part_0002", 10.0, 20.0, "seg2.mp4"),
                SegmentInfo("part_0003", 20.0, 30.0, "seg3.mp4"),
            ],
            transcribe_coverage={
                "processed": 2,
                "total": 3,
                "skipped_limit": 1,
            },
        )

        overview = compose_overview(manifest)

        # Assert PARTIAL marker exists
        assert "PARTIAL SESSION" in overview
        assert "Transcription Coverage" in overview
        assert "Transcribed**: 2/3 segments" in overview
        assert "Skipped**: 1 segments" in overview

    def test_overview_no_partial_marker_when_no_limit(self, tmp_path):
        """Overview.md has no PARTIAL marker when transcribe_coverage is None."""
        from yanhu.composer import compose_overview

        manifest = Manifest(
            session_id="2026-01-23_10-00-00_testgame_run01",
            created_at="2026-01-23T10:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "seg1.mp4"),
                SegmentInfo("part_0002", 10.0, 20.0, "seg2.mp4"),
            ],
            transcribe_coverage=None,
        )

        overview = compose_overview(manifest)

        # Assert no PARTIAL marker
        assert "PARTIAL SESSION" not in overview
        assert "Transcription Coverage" not in overview

    def test_compose_succeeds_with_missing_transcripts(self, tmp_path):
        """Compose generates all outputs even when some segments lack ASR."""
        from yanhu.composer import write_highlights, write_overview, write_timeline

        manifest = Manifest(
            session_id="2026-01-23_10-00-00_testgame_run01",
            created_at="2026-01-23T10:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    "part_0001",
                    0.0,
                    10.0,
                    "seg1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002",
                    10.0,
                    20.0,
                    "seg2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        # Create session directory
        session_dir = tmp_path / manifest.session_id
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis files: first has ASR, second doesn't
        import json

        (analysis_dir / "part_0001.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "facts": ["Scene 1"],
                    "caption": "First segment",
                    "asr_items": [{"text": "Hello world", "t_start": 0.0, "t_end": 2.0}],
                }
            )
        )

        (analysis_dir / "part_0002.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0002",
                    "scene_type": "action",
                    "facts": ["Scene 2"],
                    "caption": "Second segment",
                    # No asr_items - simulates skipped transcription
                }
            )
        )

        # Compose should succeed without errors
        write_timeline(manifest, session_dir)
        write_overview(manifest, session_dir)
        write_highlights(manifest, session_dir)

        # Assert all files created
        assert (session_dir / "timeline.md").exists()
        assert (session_dir / "overview.md").exists()
        assert (session_dir / "highlights.md").exists()

        # Timeline should handle missing ASR gracefully
        timeline_content = (session_dir / "timeline.md").read_text()
        assert "part_0001" in timeline_content
        assert "part_0002" in timeline_content
