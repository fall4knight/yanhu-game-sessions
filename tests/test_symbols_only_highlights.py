"""Tests for preventing symbols-only highlights (Step 18c)."""

import json

from yanhu.composer import compose_highlights
from yanhu.manifest import Manifest


class TestSymbolsOnlyPrevention:
    """Test that symbols-only highlights are filtered out."""

    def test_symbols_only_segment_not_highlighted(self, tmp_path):
        """Segment with only symbols (no OCR/ASR text) should NOT create highlight."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create manifest with two segments
        manifest_data = {
            "session_id": "test_session",
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
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Part 1: High score content with readable text
        analysis_part1 = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "model": "test-model",
            "facts": ["Important dialogue scene"],
            "ui_key_text": ["都做过"],
            "ocr_items": [
                {"text": "都做过", "t_rel": 5.0, "source_frame": "frame_0003.jpg"}
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_part1))

        # Part 2: Only symbols, no readable text (symbols-only)
        analysis_part2 = {
            "segment_id": "part_0002",
            "scene_type": "dialogue",
            "model": "test-model",
            "facts": [],  # No facts
            "caption": "",  # No caption
            "ui_key_text": [],  # No UI text
            "ocr_items": [],  # No OCR text
            "aligned_quotes": [],  # No quotes
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 13.0,
                    "source_frame": "frame_0004.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0002",
                }
            ],
        }
        (analysis_dir / "part_0002.json").write_text(json.dumps(analysis_part2))

        # Compose highlights
        content = compose_highlights(manifest, session_dir, top_k=8, min_score=0)

        # Part 1 with readable text should appear
        assert "都做过" in content, "Readable highlight should appear"

        # Part 2 with symbols-only should NOT appear
        # Check that there's no standalone "❤️" entry without readable context
        lines = content.split("\n")
        highlight_lines = [line for line in lines if line.startswith("- [")]

        for line in highlight_lines:
            # If this is part_0002 line, it should NOT be symbols-only
            if "part_0002" in line:
                # Should have readable text, not just emoji
                assert (
                    "都做过" in line or "Important" in line or "dialogue" in line
                ), f"part_0002 should not create symbols-only highlight: {line}"

        # Verify we only have 1 highlight (part_0001), not 2
        assert len(highlight_lines) == 1, "Should only have 1 readable highlight, not symbols-only"

    def test_symbols_with_readable_text_shown(self, tmp_path):
        """Symbols co-occurring with readable text should be shown as metadata."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        manifest_data = {
            "session_id": "test_session",
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
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Segment with BOTH symbols AND readable text
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "model": "test-model",
            "facts": ["都做过的事情", "Important moment"],
            "ui_key_text": ["❤️都做过"],
            "ocr_items": [
                {"text": "❤️都做过", "t_rel": 5.0, "source_frame": "frame_0003.jpg"}
            ],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 5.0,
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        content = compose_highlights(manifest, session_dir, top_k=8, min_score=0)

        # Should have highlight with readable text
        assert "都做过" in content, "Should include readable text"

        # Symbols should appear as metadata (symbols line)
        assert "symbols:" in content or "❤️" in content, "Symbols should appear as metadata"

        # Should NOT be standalone emoji
        lines = content.split("\n")
        highlight_lines = [line for line in lines if line.startswith("- [")]
        for line in highlight_lines:
            # Highlight line should have readable text, not just emoji
            if "❤️" in line:
                # Extract quote part (between "] " and " (segment=")
                import re

                match = re.search(r"\] (.+?) \(segment=", line)
                if match:
                    quote = match.group(1)
                    # Quote should contain readable text, not just emoji
                    readable = re.sub(r"[^\w\s]", "", quote, flags=re.UNICODE).strip()
                    assert (
                        readable
                    ), f"Highlight should have readable text, not just emoji: {line}"

    def test_standalone_symbol_entry_filtered(self, tmp_path):
        """Standalone symbol entries (quote=emoji, summary=None) should be filtered."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        manifest_data = {
            "session_id": "test_session",
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
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Minimal analysis with good score but symbols-only
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "model": "test-model",
            "scene_label": "Dialogue",
            "facts": [],  # Empty facts
            "caption": "",  # Empty caption
            "ui_key_text": [],  # No UI text
            "ocr_items": [],  # No OCR
            "ui_symbol_items": [
                {
                    "symbol": "💔",
                    "t_rel": 5.0,
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        content = compose_highlights(manifest, session_dir, top_k=8, min_score=0)

        # Should have fallback (not standalone symbol)
        assert (
            "fallback" in content.lower() or "No highlights available" in content
        ), "Should use fallback when only symbols-only entries exist"

        # Should NOT have standalone emoji highlight
        lines = content.split("\n")
        highlight_lines = [line for line in lines if line.startswith("- [")]

        for line in highlight_lines:
            # No line should be just "💔" with no readable text
            if "💔" in line:
                import re

                match = re.search(r"\] (.+?) \(segment=", line)
                if match:
                    quote = match.group(1)
                    # If quote is just the emoji, it's invalid
                    if quote.strip() == "💔":
                        assert (
                            False
                        ), f"Should not have standalone emoji highlight: {line}"


class TestHighlightEntryValidation:
    """Test HighlightEntry.has_readable_content() method."""

    def test_has_readable_content_with_quote(self):
        """Highlight with readable quote should be valid."""
        from yanhu.composer import HighlightEntry

        entry = HighlightEntry(
            score=100,
            segment_id="part_0001",
            start_time=5.0,
            quote="都做过",
            summary=None,
        )

        assert entry.has_readable_content(), "Quote with readable text should be valid"

    def test_has_readable_content_with_summary(self):
        """Highlight with summary should be valid even without quote."""
        from yanhu.composer import HighlightEntry

        entry = HighlightEntry(
            score=100,
            segment_id="part_0001",
            start_time=5.0,
            quote=None,
            summary="Important scene",
        )

        assert entry.has_readable_content(), "Summary makes highlight valid"

    def test_symbols_only_not_readable(self):
        """Highlight with only emoji should NOT be valid."""
        from yanhu.composer import HighlightEntry

        entry = HighlightEntry(
            score=100,
            segment_id="part_0001",
            start_time=5.0,
            quote="❤️",
            summary=None,
        )

        assert not entry.has_readable_content(), "Emoji-only should not be valid"

    def test_emoji_with_text_readable(self):
        """Highlight with emoji AND readable text should be valid."""
        from yanhu.composer import HighlightEntry

        entry = HighlightEntry(
            score=100,
            segment_id="part_0001",
            start_time=5.0,
            quote="❤️都做过",
            summary=None,
        )

        assert (
            entry.has_readable_content()
        ), "Emoji with readable text should be valid"

    def test_punctuation_only_not_readable(self):
        """Highlight with only punctuation should NOT be valid."""
        from yanhu.composer import HighlightEntry

        entry = HighlightEntry(
            score=100,
            segment_id="part_0001",
            start_time=5.0,
            quote="...!!!",
            summary=None,
        )

        assert not entry.has_readable_content(), "Punctuation-only should not be valid"

    def test_whitespace_only_not_readable(self):
        """Highlight with only whitespace should NOT be valid."""
        from yanhu.composer import HighlightEntry

        entry = HighlightEntry(
            score=100,
            segment_id="part_0001",
            start_time=5.0,
            quote="   ",
            summary="  ",
        )

        assert not entry.has_readable_content(), "Whitespace-only should not be valid"
