"""Tests for process_job output validation (P0)."""

import json

from yanhu.verify import validate_outputs
from yanhu.watcher import QueueJob, process_job


class TestOutputValidation:
    """Test output validation in process_job."""

    def test_validate_outputs_success(self, tmp_path):
        """Validate outputs succeeds when all files exist with content."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Create manifest.json
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        # Create valid output files
        (session_dir / "overview.md").write_text("# Overview\n\nContent here")
        (session_dir / "timeline.md").write_text("### part_0001\n\nTimeline content")
        (session_dir / "highlights.md").write_text("# Highlights\n\n- [00:01:23] Quote here")

        # Create valid progress.json
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 1,
            "total": 1,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

        valid, error = validate_outputs(session_dir)
        assert valid
        assert error == ""

    def test_validate_outputs_missing_file(self, tmp_path):
        """Validate outputs fails when file is missing."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Create manifest.json and progress.json
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 1,
            "total": 1,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

        # Only create 2 of 3 required files
        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "timeline.md").write_text("### part_0001")

        valid, error = validate_outputs(session_dir)
        assert not valid
        assert "Missing required output: highlights.md" in error

    def test_validate_outputs_empty_highlights(self, tmp_path):
        """Validate outputs fails when highlights has no entries."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Create manifest.json and progress.json
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 1,
            "total": 1,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "timeline.md").write_text("### part_0001")
        (session_dir / "highlights.md").write_text("# Highlights\n\nNo entries here")

        valid, error = validate_outputs(session_dir)
        assert not valid
        assert "highlights.md contains no highlight entries" in error

    def test_validate_outputs_empty_timeline(self, tmp_path):
        """Validate outputs fails when timeline has no segment/quote content."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Create manifest.json and progress.json
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 1,
            "total": 1,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "timeline.md").write_text("# Timeline\n\nNo segments")
        (session_dir / "highlights.md").write_text("- [00:01:23] Quote")

        valid, error = validate_outputs(session_dir)
        assert not valid
        assert "timeline.md contains no segment or quote content" in error

    def test_validate_outputs_timeline_with_quote_line(self, tmp_path):
        """Validate outputs succeeds when timeline has quote line."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Create manifest.json and progress.json
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 1,
            "total": 1,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "timeline.md").write_text("# Timeline\n\n- quote: Some quote here")
        (session_dir / "highlights.md").write_text("- [00:01:23] Quote")

        valid, error = validate_outputs(session_dir)
        assert valid
        assert error == ""

    def test_process_job_success_produces_valid_outputs(self, tmp_path, monkeypatch):
        """Process job success path must produce valid non-empty outputs."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        output_dir = tmp_path / "sessions"

        # Create test video
        video_file = raw_dir / "test_video.mp4"
        video_file.write_bytes(b"fake video content")

        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
            suggested_game="testgame",
        )

        # Mock all pipeline steps
        def mock_segment_video(manifest, session_dir):
            # Create a fake segment and return it (like real segment_video does)
            from yanhu.manifest import SegmentInfo

            segments_dir = session_dir / "segments"
            segments_dir.mkdir(exist_ok=True)
            (segments_dir / "part_0001.mp4").write_bytes(b"segment")

            segment = SegmentInfo(
                id="part_0001",
                start_time=0,
                end_time=10,
                video_path="segments/part_0001.mp4",
                frames=[],
            )
            return [segment]  # Return list of segments

        def mock_extract_frames(manifest, session_dir, frames_per_segment):
            pass

        def mock_analyze_session(manifest, session_dir, **kwargs):
            # Create fake analysis with enough score to generate highlights (>80)
            # facts: 50 base + 30 (3 facts * 10) = 80
            # caption: +20 = 100 total
            # scene_type: Dialogue +50 = 150 total (well above min_score)
            analysis_dir = session_dir / "analysis"
            analysis_dir.mkdir(exist_ok=True)
            analysis_file = analysis_dir / "part_0001.json"
            analysis_file.write_text(
                '{"segment_id": "part_0001", '
                '"scene_type": "dialogue", '
                '"facts": ["Test fact 1", "Test fact 2", "Test fact 3"], '
                '"caption": "Test caption", '
                '"ocr_text": [], '
                '"model": "mock"}'
            )

            # Update manifest to point to analysis file (like real analyze_session does)
            for segment in manifest.segments:
                if segment.id == "part_0001":
                    segment.analysis_path = "analysis/part_0001.json"

        def mock_transcribe_session(manifest, session_dir, **kwargs):
            from yanhu.transcriber import TranscribeStats
            return TranscribeStats(processed=1, total=1)

        monkeypatch.setattr("yanhu.segmenter.segment_video", mock_segment_video)
        monkeypatch.setattr("yanhu.extractor.extract_frames", mock_extract_frames)
        monkeypatch.setattr("yanhu.analyzer.analyze_session", mock_analyze_session)
        monkeypatch.setattr("yanhu.transcriber.transcribe_session", mock_transcribe_session)

        # Process job
        result = process_job(job, output_dir, force=False)

        # Should succeed
        assert result.success, f"Job failed: {result.error}"
        assert result.session_id is not None

        # Verify outputs exist
        session_dir = output_dir / result.session_id
        assert (session_dir / "overview.md").exists()
        assert (session_dir / "timeline.md").exists()
        assert (session_dir / "highlights.md").exists()

        # Verify outputs are non-empty and valid
        overview_content = (session_dir / "overview.md").read_text()
        assert len(overview_content) > 0
        assert "testgame" in overview_content.lower() or "test" in overview_content.lower()

        timeline_content = (session_dir / "timeline.md").read_text()
        assert len(timeline_content) > 0
        assert "### part_" in timeline_content or "- quote:" in timeline_content

        highlights_content = (session_dir / "highlights.md").read_text()
        assert len(highlights_content) > 0
        assert "- [" in highlights_content

    def test_process_job_validation_failure_marks_failed(self, tmp_path, monkeypatch):
        """Process job should fail if output validation fails."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        output_dir = tmp_path / "sessions"

        video_file = raw_dir / "test_video.mp4"
        video_file.write_bytes(b"fake video")

        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
        )

        # Mock pipeline steps
        def mock_segment_video(manifest, session_dir):
            # Return a segment with minimal data (no analysis → empty highlights)
            from yanhu.manifest import SegmentInfo

            segments_dir = session_dir / "segments"
            segments_dir.mkdir(exist_ok=True)
            (segments_dir / "part_0001.mp4").write_bytes(b"segment")

            segment = SegmentInfo(
                id="part_0001",
                start_time=0,
                end_time=10,
                video_path="segments/part_0001.mp4",
                frames=[],
            )
            return [segment]

        def mock_extract_frames(manifest, session_dir, frames_per_segment):
            pass

        def mock_analyze_session(manifest, session_dir, **kwargs):
            # Create analysis but with no facts (will produce empty highlights)
            analysis_dir = session_dir / "analysis"
            analysis_dir.mkdir(exist_ok=True)
            analysis_json = (
                '{"segment_id": "part_0001", "scene_type": "unknown", '
                '"ocr_text": [], "caption": "Test"}'
            )
            (analysis_dir / "part_0001.json").write_text(analysis_json)
            # Update manifest analysis path
            for segment in manifest.segments:
                if segment.id == "part_0001":
                    segment.analysis_path = "analysis/part_0001.json"

        def mock_transcribe_session(manifest, session_dir, **kwargs):
            from yanhu.transcriber import TranscribeStats
            return TranscribeStats(processed=1, total=1)

        monkeypatch.setattr("yanhu.segmenter.segment_video", mock_segment_video)
        monkeypatch.setattr("yanhu.extractor.extract_frames", mock_extract_frames)
        monkeypatch.setattr("yanhu.analyzer.analyze_session", mock_analyze_session)
        monkeypatch.setattr("yanhu.transcriber.transcribe_session", mock_transcribe_session)

        # Process job
        result = process_job(job, output_dir, force=False)

        # Should fail due to validation
        assert not result.success
        assert "Output validation failed" in result.error
        # Could fail on either highlights or timeline depending on composer logic
        assert (
            "highlights.md" in result.error or "timeline.md" in result.error
        ), f"Expected validation error, got: {result.error}"
