"""Tests for transcribe limits and progress observability."""

import json

from yanhu.transcriber import transcribe_session


class TestTranscribeLimits:
    """Test transcribe limit parameters."""

    def test_limit_processes_only_n_segments(self, tmp_path):
        """Should only transcribe first N segments when limit is set."""
        from yanhu.manifest import Manifest, SegmentInfo

        segments = [
            SegmentInfo(
                id=f"part_{i:04d}",
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                video_path=f"segments/part_{i:04d}.mp4",
                frames=[],
            )
            for i in range(5)
        ]
        manifest = Manifest(
            session_id="test_limit",
            created_at="2026-01-23",
            source_video="/test/video.mp4",
            source_video_local="video.mp4",
            segment_duration_seconds=10,
            segments=segments,
        )

        (tmp_path / "analysis").mkdir()

        stats = transcribe_session(
            manifest=manifest,
            session_dir=tmp_path,
            backend="mock",
            limit=2,
            force=False,
        )

        assert stats.processed == 2
        assert stats.skipped_limit == 3
        assert stats.total == 5

    def test_progress_callback_called(self, tmp_path):
        """Should call on_progress callback after each segment."""
        from yanhu.manifest import Manifest, SegmentInfo

        segments = [
            SegmentInfo(
                id=f"part_{i:04d}",
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                video_path=f"segments/part_{i:04d}.mp4",
                frames=[],
            )
            for i in range(3)
        ]
        manifest = Manifest(
            session_id="test_progress",
            created_at="2026-01-23",
            source_video="/test/video.mp4",
            source_video_local="video.mp4",
            segment_duration_seconds=10,
            segments=segments,
        )

        (tmp_path / "analysis").mkdir()

        progress_calls = []

        def progress_callback(seg_id, status, result, stats):
            progress_calls.append((seg_id, status))

        transcribe_session(
            manifest=manifest,
            session_dir=tmp_path,
            backend="mock",
            on_progress=progress_callback,
            force=False,
        )

        assert len([c for c in progress_calls if c[1] == "done"]) == 3

    def test_compose_with_partial_asr(self, tmp_path):
        """Should generate outputs even with partial ASR data."""
        from yanhu.composer import write_highlights, write_overview, write_timeline
        from yanhu.manifest import Manifest, SegmentInfo

        segments = [
            SegmentInfo(
                id=f"part_{i:04d}",
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                video_path=f"segments/part_{i:04d}.mp4",
                frames=[f"frames/part_{i:04d}_001.jpg"],
            )
            for i in range(3)
        ]
        manifest = Manifest(
            session_id="test_partial",
            created_at="2026-01-23",
            source_video="/test/video.mp4",
            source_video_local="video.mp4",
            segment_duration_seconds=10,
            segments=segments,
        )

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Only first segment has ASR
        for i in range(3):
            data = {
                "segment_id": f"part_{i:04d}",
                "scene_type": "gameplay",
                "caption": f"Segment {i}",
                "facts": [f"Fact {i}"],
            }
            if i == 0:
                data["asr_items"] = [{"text": "Test", "t_start": 0.0, "t_end": 10.0}]
            (analysis_dir / f"part_{i:04d}.json").write_text(
                json.dumps(data, ensure_ascii=False)
            )

        # Should generate all outputs
        timeline_path = write_timeline(manifest, tmp_path)
        overview_path = write_overview(manifest, tmp_path)
        highlights_path = write_highlights(manifest, tmp_path)

        assert timeline_path.exists()
        assert overview_path.exists()
        assert highlights_path.exists()

        timeline_content = timeline_path.read_text()
        assert "### part_0000" in timeline_content
        assert "### part_0002" in timeline_content
