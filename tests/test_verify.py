"""Tests for session output verification."""

import json
from pathlib import Path

from yanhu.verify import validate_outputs, validate_partial_consistency, validate_progress_json


class TestValidateProgressJson:
    """Test progress.json validation."""

    def test_fails_when_progress_json_missing(self, tmp_path):
        """Validation fails when progress.json does not exist."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "Missing required file: outputs/progress.json" in error

    def test_fails_when_progress_json_invalid_json(self, tmp_path):
        """Validation fails when progress.json is not valid JSON."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        # Write invalid JSON
        progress_file = outputs_dir / "progress.json"
        progress_file.write_text("{ invalid json }")

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "not valid JSON" in error

    def test_fails_when_missing_required_field(self, tmp_path):
        """Validation fails when required field is missing."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        # Missing 'stage' field
        data = {
            "session_id": "test",
            "done": 5,
            "total": 10,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "missing required field: stage" in error

    def test_fails_when_stage_invalid(self, tmp_path):
        """Validation fails when stage is not in allowed set."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "invalid_stage",
            "done": 5,
            "total": 10,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "stage must be one of" in error

    def test_fails_when_done_exceeds_total(self, tmp_path):
        """Validation fails when done > total."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "transcribe",
            "done": 15,
            "total": 10,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "done (15) cannot exceed total (10)" in error

    def test_fails_when_done_negative(self, tmp_path):
        """Validation fails when done is negative."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "transcribe",
            "done": -1,
            "total": 10,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "done must be >= 0" in error

    def test_fails_when_elapsed_negative(self, tmp_path):
        """Validation fails when elapsed_sec is negative."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "transcribe",
            "done": 5,
            "total": 10,
            "elapsed_sec": -1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "elapsed_sec must be >= 0" in error

    def test_fails_when_updated_at_invalid(self, tmp_path):
        """Validation fails when updated_at is not ISO-8601."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "transcribe",
            "done": 5,
            "total": 10,
            "elapsed_sec": 1.0,
            "updated_at": "not a timestamp",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "updated_at must be ISO-8601" in error

    def test_fails_when_stage_done_but_incomplete(self, tmp_path):
        """Validation fails when stage is 'done' but done != total."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "done",
            "done": 5,
            "total": 10,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert not valid
        assert "stage is 'done' but done (5) != total (10)" in error

    def test_passes_for_valid_transcribe_stage(self, tmp_path):
        """Validation passes for valid progress.json in transcribe stage."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "transcribe",
            "done": 5,
            "total": 10,
            "elapsed_sec": 1.5,
            "eta_sec": 1.5,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert valid
        assert error == ""

    def test_passes_for_valid_done_stage(self, tmp_path):
        """Validation passes for valid progress.json in done stage."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "done",
            "done": 10,
            "total": 10,
            "elapsed_sec": 3.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert valid
        assert error == ""

    def test_passes_with_coverage_field(self, tmp_path):
        """Validation passes when coverage field is present (optional)."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        data = {
            "session_id": "test",
            "stage": "transcribe",
            "done": 2,
            "total": 5,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
            "coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(data))

        valid, error = validate_progress_json(session_dir)
        assert valid
        assert error == ""


class TestValidatePartialConsistency:
    """Test partial-by-limit consistency validation."""

    def test_passes_when_no_coverage_in_manifest(self, tmp_path):
        """Validation passes when manifest has no transcribe_coverage (full session)."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest without transcribe_coverage
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        valid, error = validate_partial_consistency(session_dir)
        assert valid
        assert error == ""

    def test_fails_when_coverage_but_no_partial_marker(self, tmp_path):
        """Validation fails when manifest has coverage but overview lacks PARTIAL marker."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest with transcribe_coverage
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
            "transcribe_coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        # Create overview without PARTIAL marker
        overview_file = session_dir / "overview.md"
        overview_file.write_text("# Overview\n\nNo partial marker here.")

        valid, error = validate_partial_consistency(session_dir)
        assert not valid
        assert "lacks PARTIAL SESSION marker" in error

    def test_fails_when_coverage_but_no_coverage_section(self, tmp_path):
        """Validation fails when manifest has coverage but overview lacks coverage section."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest with transcribe_coverage
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
            "transcribe_coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        # Create overview with PARTIAL marker but no coverage section
        overview_file = session_dir / "overview.md"
        overview_file.write_text("# Overview\n\n⚠️ PARTIAL SESSION\n\nBut no coverage section.")

        valid, error = validate_partial_consistency(session_dir)
        assert not valid
        assert "lacks Transcription Coverage section" in error

    def test_fails_when_coverage_stats_missing(self, tmp_path):
        """Validation fails when overview has section but missing expected stats."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest with transcribe_coverage
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
            "transcribe_coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        # Create overview with section but incomplete stats
        overview_file = session_dir / "overview.md"
        overview_content = """# Overview

⚠️ PARTIAL SESSION

## Transcription Coverage

Some text but no stats.
"""
        overview_file.write_text(overview_content)

        valid, error = validate_partial_consistency(session_dir)
        assert not valid
        assert "missing expected coverage stat" in error

    def test_passes_when_coverage_and_overview_match(self, tmp_path):
        """Validation passes when manifest has coverage and overview has correct markers."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest with transcribe_coverage
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
            "transcribe_coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        # Create overview with proper PARTIAL marker and coverage stats
        overview_file = session_dir / "overview.md"
        overview_content = """# Overview

## Transcription Coverage

⚠️ **PARTIAL SESSION**: Transcription was limited.

- **Transcribed**: 2/5 segments
- **Skipped**: 3 segments
"""
        overview_file.write_text(overview_content)

        valid, error = validate_partial_consistency(session_dir)
        assert valid
        assert error == ""

    def test_fails_when_progress_coverage_mismatch(self, tmp_path):
        """Validation fails when progress.json coverage doesn't match manifest."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest with transcribe_coverage
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
            "transcribe_coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        # Create overview with proper markers
        overview_file = session_dir / "overview.md"
        overview_content = """# Overview

## Transcription Coverage

⚠️ **PARTIAL SESSION**: Transcription was limited.

- **Transcribed**: 2/5 segments
- **Skipped**: 3 segments
"""
        overview_file.write_text(overview_content)

        # Create progress.json with mismatched coverage
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 5,
            "total": 5,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
            "coverage": {"processed": 3, "total": 5, "skipped_limit": 2},  # Mismatch
        }
        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(json.dumps(progress_data))

        valid, error = validate_partial_consistency(session_dir)
        assert not valid
        assert "coverage" in error
        assert "does not match manifest" in error


class TestValidateOutputs:
    """Test comprehensive output validation."""

    def create_valid_session(self, session_dir: Path, partial: bool = False):
        """Helper to create a valid session directory."""
        session_dir.mkdir(exist_ok=True)

        # Create manifest
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        if partial:
            manifest_data["transcribe_coverage"] = {
                "processed": 2,
                "total": 5,
                "skipped_limit": 3,
            }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        # Create markdown outputs
        (session_dir / "overview.md").write_text(
            """# Overview

## Transcription Coverage

⚠️ **PARTIAL SESSION**: Transcription was limited.

- **Transcribed**: 2/5 segments
- **Skipped**: 3 segments
"""
            if partial
            else "# Overview\n\nFull session."
        )
        (session_dir / "timeline.md").write_text("### part_0001\n\nSome content.")
        (session_dir / "highlights.md").write_text("- [00:00] Some highlight")

        # Create progress.json
        # Note: when stage="done", done always equals total (finalize() behavior)
        # The coverage field tracks the partial transcription info
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 5,  # Always equal to total when stage="done"
            "total": 5,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
        }
        if partial:
            progress_data["coverage"] = {"processed": 2, "total": 5, "skipped_limit": 3}
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

    def test_passes_for_valid_full_session(self, tmp_path):
        """Validation passes for a valid full session."""
        session_dir = tmp_path / "test_session"
        self.create_valid_session(session_dir, partial=False)

        valid, error = validate_outputs(session_dir)
        assert valid, f"Validation should pass but got error: {error}"
        assert error == ""

    def test_passes_for_valid_partial_session(self, tmp_path):
        """Validation passes for a valid partial session."""
        session_dir = tmp_path / "test_session"
        self.create_valid_session(session_dir, partial=True)

        valid, error = validate_outputs(session_dir)
        assert valid, f"Validation should pass but got error: {error}"
        assert error == ""

    def test_fails_when_progress_json_missing(self, tmp_path):
        """Validation fails when progress.json is missing."""
        session_dir = tmp_path / "test_session"
        self.create_valid_session(session_dir, partial=False)

        # Remove progress.json
        (session_dir / "outputs" / "progress.json").unlink()

        valid, error = validate_outputs(session_dir)
        assert not valid
        assert "progress.json" in error

    def test_fails_for_partial_without_marker(self, tmp_path):
        """Validation fails for partial session without PARTIAL marker."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest with coverage
        manifest_data = {
            "session_id": "test",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
            "transcribe_coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        # Create overview WITHOUT partial marker
        (session_dir / "overview.md").write_text("# Overview\n\nNo marker here.")
        (session_dir / "timeline.md").write_text("### part_0001\n\nSome content.")
        (session_dir / "highlights.md").write_text("- [00:00] Some highlight")

        # Create valid progress.json
        # Note: when stage="done", done must equal total
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": "test",
            "stage": "done",
            "done": 5,  # Must equal total when stage="done"
            "total": 5,
            "elapsed_sec": 1.0,
            "updated_at": "2026-01-24T00:00:00+00:00",
            "coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

        valid, error = validate_outputs(session_dir)
        assert not valid
        assert "PARTIAL SESSION marker" in error
