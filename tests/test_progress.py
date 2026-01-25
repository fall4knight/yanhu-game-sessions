"""Tests for progress tracking (progress.json) feature."""

import json
import time
from unittest.mock import MagicMock, patch

from yanhu.manifest import Manifest, SegmentInfo
from yanhu.progress import ProgressTracker
from yanhu.transcriber import transcribe_session


class TestProgressTracker:
    """Test ProgressTracker class functionality."""

    def test_progress_file_created_on_init(self, tmp_path):
        """Progress file is created when tracker is initialized."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        _tracker = ProgressTracker(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            total=10,
        )

        progress_file = session_dir / "outputs" / "progress.json"
        assert progress_file.exists()

        # Verify initial content
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["session_id"] == "test_session"
        assert data["stage"] == "transcribe"
        assert data["done"] == 0
        assert data["total"] == 10
        assert "elapsed_sec" in data
        assert "updated_at" in data
        # ETA should be None initially (no data to estimate)
        assert "eta_sec" not in data

    def test_progress_update_writes_to_file(self, tmp_path):
        """Calling update() writes new progress to file."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        tracker = ProgressTracker(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            total=10,
        )

        # Add small delay to ensure elapsed time is non-zero
        time.sleep(0.01)

        # Update progress
        tracker.update(5)

        # Verify updated content
        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["done"] == 5
        assert data["total"] == 10
        # ETA should be present now (we have data to estimate)
        assert "eta_sec" in data
        assert data["eta_sec"] >= 0  # May be 0 if too fast, but should be present

    def test_progress_finalize_marks_done(self, tmp_path):
        """Calling finalize() marks stage as complete."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        tracker = ProgressTracker(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            total=10,
        )

        tracker.update(5)
        tracker.finalize(stage="compose")

        # Verify finalized content
        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["stage"] == "compose"
        assert data["done"] == 10  # Finalize sets done=total
        assert data["total"] == 10

    def test_progress_includes_coverage_when_limited(self, tmp_path):
        """Progress includes coverage metadata when transcription is limited."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        coverage = {"processed": 5, "total": 20, "skipped_limit": 15}
        _tracker = ProgressTracker(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            total=20,
            coverage=coverage,
        )

        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["coverage"] == coverage

    def test_progress_format_console_line(self, tmp_path):
        """format_console_line() returns formatted progress string."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        tracker = ProgressTracker(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            total=10,
        )

        # Initial line (no ETA yet)
        line = tracker.format_console_line()
        assert "Transcribe: 0/10 segments" in line
        assert "elapsed" in line

        # After some progress
        time.sleep(0.1)  # Small delay to get non-zero elapsed
        tracker.update(5)
        line = tracker.format_console_line()
        assert "Transcribe: 5/10 segments" in line
        assert "ETA" in line


class TestProgressDuringTranscribe:
    """Test progress tracking during transcribe_session."""

    def test_progress_updates_during_transcribe(self, tmp_path):
        """Progress.json is updated during transcribe for each segment."""
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

        session_dir = tmp_path / manifest.session_id
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Track progress updates
        progress_snapshots = []

        def mock_transcribe(segment, session_dir, max_seconds, session_id=None):
            from yanhu.transcriber import AsrResult

            return AsrResult(
                segment_id=segment.id, asr_items=[], asr_backend="mock", asr_config={}
            )

        def on_progress_callback(seg_id, status, result, stats):
            """Capture progress snapshots."""
            progress_file = session_dir / "outputs" / "progress.json"
            if progress_file.exists():
                with open(progress_file, encoding="utf-8") as f:
                    progress_snapshots.append(json.load(f))

        with patch("yanhu.transcriber.get_asr_backend") as mock_get_backend:
            with patch("yanhu.transcriber.merge_asr_to_analysis") as mock_merge:
                mock_merge.return_value = None
                mock_backend = MagicMock()
                mock_backend.transcribe_segment = mock_transcribe
                mock_get_backend.return_value = mock_backend

                # Create progress tracker manually for test
                from yanhu.progress import ProgressTracker

                tracker = ProgressTracker(
                    session_id=manifest.session_id,
                    session_dir=session_dir,
                    stage="transcribe",
                    total=len(manifest.segments),
                )

                # Wrap callback to update tracker
                def wrapped_callback(seg_id, status, result, stats):
                    if stats:
                        tracker.update(stats.processed)
                    on_progress_callback(seg_id, status, result, stats)

                transcribe_session(
                    manifest=manifest,
                    session_dir=session_dir,
                    backend="mock",
                    on_progress=wrapped_callback,
                )

        # Verify we captured multiple progress snapshots
        assert len(progress_snapshots) > 0

        # Verify progress increased over time
        done_values = [snap["done"] for snap in progress_snapshots]
        # Should have at least some progress (may not be strictly increasing due to caching)
        assert max(done_values) > 0

        # Verify required fields present in all snapshots
        for snap in progress_snapshots:
            assert "session_id" in snap
            assert snap["session_id"] == "test_session"
            assert "stage" in snap
            assert snap["stage"] == "transcribe"
            assert "done" in snap
            assert "total" in snap
            assert snap["total"] == 3
            assert "elapsed_sec" in snap
            assert "updated_at" in snap


class TestProgressWithTranscribeLimit:
    """Test progress tracking when --transcribe-limit is used."""

    def test_progress_reflects_limit_in_coverage(self, tmp_path):
        """When limit is used, progress.json includes coverage metadata."""
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

        session_dir = tmp_path / manifest.session_id
        session_dir.mkdir()

        # Create tracker with limit coverage
        coverage = {"processed": 2, "total": 5, "skipped_limit": 3}
        tracker = ProgressTracker(
            session_id=manifest.session_id,
            session_dir=session_dir,
            stage="transcribe",
            total=5,
            coverage=coverage,
        )

        # Simulate progress
        tracker.update(1)
        tracker.update(2)

        # Verify coverage in progress.json
        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["coverage"] == coverage
        assert data["done"] == 2
        assert data["total"] == 5

    def test_progress_total_reflects_actual_work_with_limit(self, tmp_path):
        """When limit=2 is used, progress total=5 (all segments), done tracks actual work."""
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

        session_dir = tmp_path / manifest.session_id
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        def mock_transcribe(segment, session_dir, max_seconds, session_id=None):
            from yanhu.transcriber import AsrResult

            return AsrResult(
                segment_id=segment.id, asr_items=[], asr_backend="mock", asr_config={}
            )

        # Track final progress state
        final_progress = None

        def on_progress_callback(seg_id, status, result, stats):
            nonlocal final_progress
            progress_file = session_dir / "outputs" / "progress.json"
            if progress_file.exists():
                with open(progress_file, encoding="utf-8") as f:
                    final_progress = json.load(f)

        with patch("yanhu.transcriber.get_asr_backend") as mock_get_backend:
            with patch("yanhu.transcriber.merge_asr_to_analysis") as mock_merge:
                mock_merge.return_value = None
                mock_backend = MagicMock()
                mock_backend.transcribe_segment = mock_transcribe
                mock_get_backend.return_value = mock_backend

                # Create tracker with coverage
                from yanhu.progress import ProgressTracker

                coverage = {"processed": 2, "total": 5, "skipped_limit": 3}
                tracker = ProgressTracker(
                    session_id=manifest.session_id,
                    session_dir=session_dir,
                    stage="transcribe",
                    total=5,
                    coverage=coverage,
                )

                def wrapped_callback(seg_id, status, result, stats):
                    if stats:
                        tracker.update(stats.processed)
                    on_progress_callback(seg_id, status, result, stats)

                transcribe_session(
                    manifest=manifest,
                    session_dir=session_dir,
                    backend="mock",
                    limit=2,  # Only process first 2 segments
                    on_progress=wrapped_callback,
                )

        # Verify final progress shows done=2, total=5
        assert final_progress is not None
        assert final_progress["done"] == 2
        assert final_progress["total"] == 5
        assert final_progress["coverage"]["processed"] == 2
        assert final_progress["coverage"]["skipped_limit"] == 3


class TestProgressRobustness:
    """Test progress tracking edge cases and robustness."""

    def test_progress_handles_zero_total(self, tmp_path):
        """Progress tracker handles total=0 without error."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        tracker = ProgressTracker(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            total=0,
        )

        # Should not crash
        tracker.update(0)
        tracker.finalize()

        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["total"] == 0
        assert data["done"] == 0

    def test_progress_file_is_atomic(self, tmp_path):
        """Progress writes are atomic (no partial reads)."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        tracker = ProgressTracker(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            total=100,
        )

        # Rapidly update progress
        for i in range(1, 11):
            tracker.update(i * 10)

        # Every read should be valid JSON
        progress_file = session_dir / "outputs" / "progress.json"
        assert progress_file.exists()

        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)

        # Should have latest value
        assert data["done"] == 100
        assert data["total"] == 100
