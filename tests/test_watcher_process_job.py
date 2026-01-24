"""Tests for process_job path handling."""

from pathlib import Path

from yanhu.watcher import QueueJob, process_job


class TestProcessJobPaths:
    """Test process_job path construction."""

    def test_session_dir_path_order_correct(self, tmp_path, monkeypatch):
        """CRITICAL: session_dir must be <output_dir>/<session_id>, not reversed."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        output_dir = tmp_path / "sessions"

        # Create a test video file
        video_file = raw_dir / "test_video.mp4"
        video_file.write_bytes(b"fake video")

        # Create a job
        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
            suggested_game="testgame",
        )

        # Mock the pipeline steps to fail early (we only test path construction)
        def mock_segment_video(manifest, session_dir):
            # Verify session_dir is correct: <output_dir>/<session_id>
            # NOT <session_id>/<output_dir>
            assert session_dir.parent == output_dir
            assert session_dir.name.startswith("2026-01-23")
            assert session_dir.name.endswith("_testgame_run01")
            # Raise to stop pipeline after validation
            raise RuntimeError("Test validation passed - stopping pipeline")

        monkeypatch.setattr("yanhu.segmenter.segment_video", mock_segment_video)

        # Process job - should fail at segment step with our validation message
        result = process_job(job, output_dir, force=False)

        # Should fail (we raised in mock), but error message confirms path was correct
        assert not result.success
        assert "Test validation passed" in result.error

    def test_session_dir_exists_after_ingest(self, tmp_path, monkeypatch):
        """Session directory should exist at <output_dir>/<session_id>."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        output_dir = tmp_path / "sessions"

        video_file = raw_dir / "game_clip.mp4"
        video_file.write_bytes(b"fake video")

        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
            suggested_game="mygame",
        )

        # Track created session_dir
        created_dirs = []

        def mock_segment_video(manifest, session_dir):
            created_dirs.append(session_dir)
            # Verify session_dir is absolute and correctly structured
            assert session_dir.is_absolute()
            assert output_dir.resolve() in session_dir.parents
            raise RuntimeError("Stop after validation")

        monkeypatch.setattr("yanhu.segmenter.segment_video", mock_segment_video)

        process_job(job, output_dir, force=False)

        # Verify session_dir was created in correct location
        assert len(created_dirs) == 1
        session_dir = created_dirs[0]
        assert session_dir.exists()
        assert session_dir.parent == output_dir.resolve()

    def test_source_video_local_path_relative(self, tmp_path, monkeypatch):
        """source_video_local in manifest should be relative to session_dir."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        output_dir = tmp_path / "sessions"

        video_file = raw_dir / "clip.mp4"
        video_file.write_bytes(b"fake video")

        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
            suggested_game="game",
        )

        # Capture manifest
        saved_manifests = []

        def mock_manifest_save(self, path):
            saved_manifests.append((self, path))
            # Don't actually save to avoid file I/O issues

        # Monkey-patch Manifest.save
        from yanhu import manifest as manifest_module

        monkeypatch.setattr(manifest_module.Manifest, "save", mock_manifest_save)

        def mock_segment_video(manifest, session_dir):
            raise RuntimeError("Stop after ingest")

        monkeypatch.setattr("yanhu.segmenter.segment_video", mock_segment_video)

        process_job(job, output_dir, force=False)

        # Check manifest was created
        assert len(saved_manifests) >= 1
        manifest, manifest_path = saved_manifests[0]

        # Verify source_video_local is relative (not absolute)
        assert not Path(manifest.source_video_local).is_absolute()
        assert manifest.source_video_local.startswith("source/")
        assert manifest.source_video_local == "source/clip.mp4"

    def test_no_reverse_path_construction(self, tmp_path, monkeypatch):
        """Ensure we never create <session_id>/sessions pattern."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        output_dir = tmp_path / "sessions"

        video_file = raw_dir / "video.mp4"
        video_file.write_bytes(b"fake")

        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
        )

        def mock_segment_video(manifest, session_dir):
            # CRITICAL: session_dir should NOT contain pattern <session_id>/sessions
            # It should be sessions/<session_id>
            session_parts = session_dir.parts

            # Check that "sessions" is NOT the last part (would indicate reversal)
            assert session_parts[-1] != "sessions", (
                f"Session dir incorrectly constructed as <session_id>/sessions: {session_dir}"
            )

            # Check that "sessions" comes before session_id in path hierarchy
            if "sessions" in session_parts:
                sessions_idx = session_parts.index("sessions")
                # session_id (starts with YYYY-MM-DD) should come AFTER "sessions"
                assert any(
                    part.startswith("2026-") for part in session_parts[sessions_idx + 1 :]
                ), f"Session ID should come after 'sessions' in path: {session_dir}"

            raise RuntimeError("Validation passed")

        monkeypatch.setattr("yanhu.segmenter.segment_video", mock_segment_video)

        result = process_job(job, output_dir, force=False)
        assert "Validation passed" in result.error
