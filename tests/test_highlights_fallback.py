"""Tests for highlights fallback when no content passes threshold."""

import json

from yanhu.composer import compose_highlights
from yanhu.manifest import Manifest


class TestHighlightsFallback:
    """Test highlights fallback logic when no highlights pass threshold."""

    def test_fallback_when_no_highlights(self, tmp_path):
        """Compose should create fallback entry when no highlights pass threshold."""
        # Create a session with one segment but low-scoring content
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create manifest with one segment
        manifest_data = {
            "session_id": "test_fallback",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [
                {
                    "id": "part_0001",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "video_path": "segments/segment.mp4",
                    "analysis_path": "analysis/part_0001.json",
                }
            ],
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Create minimal analysis (no quotes, low score content)
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "scene_label": "Other",
            "what_changed": "Test scene",
            "facts": ["This is a test fact"],
            "caption": "Test caption",
            "ui_key_text": [],
            "ocr_items": [],
            "aligned_quotes": [],  # No quotes
        }
        analysis_file = analysis_dir / "part_0001.json"
        analysis_file.write_text(json.dumps(analysis_data))

        # Compose highlights with high min_score (nothing will pass)
        content = compose_highlights(manifest, session_dir, top_k=8, min_score=999)

        # Should have fallback entry
        assert "- [00:00:00]" in content, "Should have canonical timestamp format"
        assert "score=0" in content, "Fallback should have score=0"
        assert "part_0001" in content, "Should reference the segment"
        assert "Fallback highlight" in content or "This is a test fact" in content, (
            "Should have fallback text or fact"
        )

    def test_fallback_uses_first_segment_with_analysis(self, tmp_path):
        """Fallback should use first segment that has analysis."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create manifest with two segments
        manifest_data = {
            "session_id": "test_fallback",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [
                {
                    "id": "part_0001",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "video_path": "segments/segment1.mp4",
                    "analysis_path": "analysis/part_0001.json",
                },
                {
                    "id": "part_0002",
                    "start_time": 10.0,
                    "end_time": 20.0,
                    "video_path": "segments/segment2.mp4",
                    "analysis_path": "analysis/part_0002.json",
                },
            ],
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Only create analysis for part_0002
        analysis_data = {
            "segment_id": "part_0002",
            "scene_type": "gameplay",
            "model": "test-model",
            "scene_label": "Other",
            "what_changed": "Second segment content",
            "facts": ["Fact from second segment"],
            "caption": "Caption from second segment",
            "ui_key_text": [],
            "ocr_items": [],
            "aligned_quotes": [],
        }
        analysis_file = analysis_dir / "part_0002.json"
        analysis_file.write_text(json.dumps(analysis_data))

        # Compose with high threshold (nothing passes)
        content = compose_highlights(manifest, session_dir, top_k=8, min_score=999)

        # Should use part_0002 (first with analysis)
        assert "part_0002" in content, "Should use second segment (first with analysis)"
        assert "Fact from second segment" in content or "Fallback highlight" in content

    def test_fallback_format_matches_canonical(self, tmp_path):
        """Fallback entry should match canonical '- [HH:MM:SS]' format."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        manifest_data = {
            "session_id": "test_fallback",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [
                {
                    "id": "part_0001",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "video_path": "segments/segment.mp4",
                    "analysis_path": "analysis/part_0001.json",
                }
            ],
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "scene_label": "Other",
            "what_changed": "Test",
            "facts": ["Test fact"],
            "caption": None,
            "ui_key_text": [],
            "ocr_items": [],
            "aligned_quotes": [],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        content = compose_highlights(manifest, session_dir, top_k=8, min_score=999)

        # Verify format matches "- [HH:MM:SS] ..."
        import re

        pattern = r"^- \[\d\d:\d\d:\d\d\]"
        lines = content.split("\n")
        highlight_lines = [line for line in lines if line.startswith("- [")]

        assert len(highlight_lines) >= 1, "Should have at least one highlight line"
        assert re.match(pattern, highlight_lines[0]), f"Format should match '{pattern}'"

    def test_fallback_with_aligned_quote(self, tmp_path):
        """Fallback should use aligned quote if available."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        manifest_data = {
            "session_id": "test_fallback",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [
                {
                    "id": "part_0001",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "video_path": "segments/segment.mp4",
                    "analysis_path": "analysis/part_0001.json",
                }
            ],
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Analysis with aligned quote
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "scene_label": "Other",
            "what_changed": "Test",
            "facts": ["Test fact"],
            "caption": None,
            "ui_key_text": [],
            "ocr_items": [],
            "aligned_quotes": [{"t": 1.0, "source": "ocr", "ocr": "This is a quote"}],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        content = compose_highlights(manifest, session_dir, top_k=8, min_score=999)

        # Should use the aligned quote
        assert "This is a quote" in content, "Should use aligned quote as fallback text"

    def test_fallback_when_analysis_missing(self, tmp_path):
        """Fallback should work even when analysis files are missing."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create manifest with segment but NO analysis files
        manifest_data = {
            "session_id": "test_fallback",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [
                {
                    "id": "part_0001",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "video_path": "segments/segment.mp4",
                    "analysis_path": "analysis/part_0001.json",
                }
            ],
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Do NOT create analysis file - it's missing

        # Compose with high threshold
        content = compose_highlights(manifest, session_dir, top_k=8, min_score=999)

        # Should have fallback with "analysis unavailable"
        assert "- [00:00:00]" in content, "Should have canonical timestamp format"
        assert "score=0" in content, "Fallback should have score=0"
        assert "part_0001" in content, "Should reference the segment"
        assert (
            "analysis unavailable" in content.lower()
            or "fallback highlight" in content.lower()
        ), "Should have fallback text indicating missing analysis"

    def test_no_fallback_when_highlights_pass_threshold(self, tmp_path):
        """Should not use fallback when highlights pass threshold."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        manifest_data = {
            "session_id": "test_fallback",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [
                {
                    "id": "part_0001",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "video_path": "segments/segment.mp4",
                    "analysis_path": "analysis/part_0001.json",
                }
            ],
        }
        manifest_file = session_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Analysis with good content (high score)
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "model": "test-model",
            "scene_label": "Dialogue",
            "what_changed": "Test",
            "facts": ["Important content", "More facts", "Even more"],
            "caption": "Caption",
            "ui_key_text": ["Text 1", "Text 2", "Text 3"],
            "ocr_items": [
                {"text": "OCR 1", "t_rel": 1.0, "source_frame": "frame_001.jpg"},
                {"text": "OCR 2", "t_rel": 2.0, "source_frame": "frame_002.jpg"},
            ],
            "aligned_quotes": [{"t": 1.0, "source": "ocr", "ocr": "Good quote"}],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        # Use low threshold so content passes
        content = compose_highlights(manifest, session_dir, top_k=8, min_score=50)

        # Should NOT have fallback marker
        assert "fallback" not in content.lower() or "score=0" not in content, (
            "Should not use fallback when content passes threshold"
        )
        # Should have normal highlight
        assert "Good quote" in content, "Should have normal highlight with quote"


class TestValidationWithFallback:
    """Test validate_outputs accepts fallback highlights."""

    def test_validate_accepts_fallback(self, tmp_path):
        """validate_outputs should accept fallback highlight format."""
        from yanhu.verify import validate_outputs

        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Create required files
        (session_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "created_at": "2026-01-24T00:00:00",
                    "source_video": "/path/to/video.mp4",
                    "source_video_local": "source/video.mp4",
                    "segment_duration_seconds": 10,
                    "segments": [],
                }
            )
        )

        (session_dir / "overview.md").write_text("# Overview\n\nTest overview.")
        (session_dir / "timeline.md").write_text("### part_0001\n\nTest timeline.")

        # Create highlights with fallback format
        (session_dir / "highlights.md").write_text(
            "# Highlights\n\n"
            "**Top 1 moments** (fallback entry - no highlights above threshold)\n\n"
            "- [00:00:00] Fallback highlight (no content above threshold) "
            "(segment=part_0001, score=0)\n"
            "  - summary: Test fact\n"
        )

        # Create valid progress.json
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / "progress.json").write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "stage": "done",
                    "done": 1,
                    "total": 1,
                    "elapsed_sec": 1.0,
                    "updated_at": "2026-01-24T00:00:00+00:00",
                }
            )
        )

        # Should pass validation
        valid, error = validate_outputs(session_dir)
        assert valid, f"Should accept fallback highlight but got error: {error}"

    def test_validate_accepts_canonical_format(self, tmp_path):
        """validate_outputs should still accept canonical format."""
        from yanhu.verify import validate_outputs

        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        (session_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "created_at": "2026-01-24T00:00:00",
                    "source_video": "/path/to/video.mp4",
                    "source_video_local": "source/video.mp4",
                    "segment_duration_seconds": 10,
                    "segments": [],
                }
            )
        )

        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "timeline.md").write_text("### part_0001")

        # Canonical format (no fallback marker)
        (session_dir / "highlights.md").write_text(
            "# Highlights\n\n" "- [00:00:05] Good content (segment=part_0001, score=120)\n"
        )

        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / "progress.json").write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "stage": "done",
                    "done": 1,
                    "total": 1,
                    "elapsed_sec": 1.0,
                    "updated_at": "2026-01-24T00:00:00+00:00",
                }
            )
        )

        valid, error = validate_outputs(session_dir)
        assert valid, f"Should accept canonical format but got error: {error}"

    def test_validate_rejects_missing_highlights(self, tmp_path):
        """validate_outputs should reject missing highlights file."""
        from yanhu.verify import validate_outputs

        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        (session_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "session_id": "test",
                    "created_at": "2026-01-24T00:00:00",
                    "source_video": "/path/to/video.mp4",
                    "source_video_local": "source/video.mp4",
                    "segment_duration_seconds": 10,
                    "segments": [],
                }
            )
        )

        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "timeline.md").write_text("### part_0001")

        # No highlights.md file

        valid, error = validate_outputs(session_dir)
        assert not valid, "Should reject missing highlights.md"
        assert "highlights.md" in error.lower()
