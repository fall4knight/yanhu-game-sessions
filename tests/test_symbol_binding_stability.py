"""Tests for emoji symbol binding stability and evidence vs inference separation."""

import json

from yanhu.analyzer import UiSymbolItem
from yanhu.composer import get_segment_symbols
from yanhu.manifest import Manifest


class TestSymbolOriginSeparation:
    """Test origin field separates evidence_ocr from inferred_llm symbols."""

    def test_evidence_ocr_symbols_displayed(self, tmp_path):
        """Symbols with origin=evidence_ocr should appear in timeline/highlights."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create manifest
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

        # Analysis with evidence_ocr symbol
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",  # Evidence layer
                    "type": "emoji",
                    "name": "red_heart",
                    "source_part_id": "part_0001",
                }
            ],
            "ocr_items": [
                {"text": "都做过", "t_rel": 3.0, "source_frame": "frame_0003.jpg"}
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        # Get symbols - should include evidence_ocr
        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        assert result is not None, "Evidence OCR symbols should be displayed"
        assert "❤️" in result, "Should include evidence_ocr emoji"
        assert "/s/test_session/frames/part_0001/frame_0003.jpg" in result

    def test_inferred_llm_symbols_filtered(self, tmp_path):
        """Symbols with origin=inferred_llm should NOT appear in timeline/highlights."""
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

        # Analysis with ONLY inferred_llm symbol (no OCR emoji)
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,
                    "source_frame": "frame_0003.jpg",
                    "origin": "inferred_llm",  # Inference layer - should be filtered
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
            "ocr_items": [
                # OCR has NO emoji - Claude inferred it
                {"text": "都做过", "t_rel": 3.0, "source_frame": "frame_0003.jpg"}
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        # Get symbols - should filter out inferred_llm
        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # CRITICAL: Must NOT include inferred symbols
        assert result is None, "Inferred LLM symbols should be filtered out"

    def test_mixed_origins_only_shows_evidence(self, tmp_path):
        """When both evidence_ocr and inferred_llm exist, only show evidence_ocr."""
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

        # Analysis with both evidence and inferred symbols
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",  # Should be shown
                    "type": "emoji",
                    "name": "red_heart",
                    "source_part_id": "part_0001",
                },
                {
                    "symbol": "💔",
                    "t_rel": 5.0,
                    "source_frame": "frame_0005.jpg",
                    "origin": "inferred_llm",  # Should be filtered
                    "type": "emoji",
                    "source_part_id": "part_0001",
                },
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        assert result is not None
        assert "❤️" in result, "Should include evidence_ocr emoji"
        assert "💔" not in result, "Should NOT include inferred_llm emoji"


class TestNearBindingPriority:
    """Test near-binding prioritizes OCR → aligned_quotes → ASR."""

    def test_near_binding_prefers_ocr_over_asr(self, tmp_path):
        """When OCR text exists, bind to nearest OCR (not ASR)."""
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

        # Analysis with emoji at t=3.0, OCR at t=3.1, ASR at t=2.5
        # OCR is closer in time to emoji, so should bind to OCR
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,  # Emoji at t=3.0
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
            "ocr_items": [
                {"text": "都做过", "t_rel": 3.1, "source_frame": "frame_0003.jpg"}  # OCR at t=3.1
            ],
            "asr_items": [
                {
                    "text": "wrong ASR text",
                    "t_start": 2.0,
                    "t_end": 3.0,  # ASR mid=2.5
                }
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # Should bind to nearest OCR "都做过", not ASR
        assert result is not None
        assert "都做过" in result, "Should bind to nearest OCR text"
        assert "wrong ASR text" not in result, "Should NOT bind to ASR when OCR is available"

    def test_near_binding_uses_aligned_quotes_when_no_ocr(self, tmp_path):
        """When no OCR items, bind to aligned_quotes."""
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

        # Analysis with emoji, aligned_quotes, ASR (no ocr_items)
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
            "ocr_items": [],  # No OCR items
            "aligned_quotes": [
                {"t": 3.2, "source": "asr", "asr": "quote text from ASR"}
            ],
            "asr_items": [
                {
                    "text": "different ASR text",
                    "t_start": 5.0,
                    "t_end": 6.0,
                }
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # Should bind to aligned_quotes (priority B)
        assert result is not None
        assert "quote text from ASR" in result
        assert "different ASR text" not in result

    def test_near_binding_fallback_to_asr(self, tmp_path):
        """When no OCR or aligned_quotes, bind to ASR (fallback)."""
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

        # Analysis with emoji, ASR only
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
            "ocr_items": [],
            "aligned_quotes": [],
            "asr_items": [
                {
                    "text": "ASR fallback text",
                    "t_start": 2.5,
                    "t_end": 3.5,  # mid=3.0, exact match
                }
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # Should bind to ASR (priority C fallback)
        assert result is not None
        assert "ASR fallback text" in result


class TestTimebaseConsistency:
    """Test that time base is global session time throughout."""

    def test_global_timebase_used_for_binding(self, tmp_path):
        """Verify t_rel is global session time, not segment-relative."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Segment starts at 10.0 seconds
        manifest_data = {
            "session_id": "test_session",
            "created_at": "2026-01-24T00:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [
                {
                    "id": "part_0002",
                    "start_time": 10.0,  # Second segment
                    "end_time": 20.0,
                    "video_path": "segments/segment.mp4",
                    "analysis_path": "analysis/part_0002.json",
                }
            ],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Analysis with global times (emoji at t=13.0, OCR at t=13.2)
        analysis_data = {
            "segment_id": "part_0002",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 13.0,  # Global time: 13.0 (3 seconds into segment)
                    "source_frame": "frame_0003.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0002",
                }
            ],
            "ocr_items": [
                {"text": "正确的文字", "t_rel": 13.2, "source_frame": "frame_0003.jpg"}
            ],
        }
        (analysis_dir / "part_0002.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # Should bind to OCR at t=13.2 using global time base
        assert result is not None
        assert "正确的文字" in result, "Should bind using global time base"


class TestUiSymbolItemOriginField:
    """Test UiSymbolItem origin field serialization."""

    def test_origin_field_serializes(self):
        """Origin field should serialize to/from dict."""
        item = UiSymbolItem(
            symbol="❤️",
            t_rel=3.0,
            source_frame="frame_0003.jpg",
            origin="evidence_ocr",
            type="emoji",
            name="red_heart",
        )

        data = item.to_dict()
        assert data["origin"] == "evidence_ocr"

        restored = UiSymbolItem.from_dict(data)
        assert restored.origin == "evidence_ocr"

    def test_origin_field_optional(self):
        """Origin field should be optional for backward compatibility."""
        # Old data without origin field
        data = {
            "symbol": "❤️",
            "t_rel": 3.0,
            "source_frame": "frame_0003.jpg",
        }

        item = UiSymbolItem.from_dict(data)
        assert item.origin is None  # Should handle missing origin gracefully

    def test_origin_none_symbols_not_displayed(self, tmp_path):
        """Symbols with origin=None should NOT be displayed (conservative default)."""
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

        # Analysis with symbol that has origin=None (legacy data or missing field)
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,
                    "source_frame": "frame_0003.jpg",
                    # No origin field - will be None
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # CRITICAL: Must NOT display symbols with origin=None
        assert result is None, "Symbols with origin=None should be filtered out"


class TestSameFrameOcrBinding:
    """Test same-frame OCR binding preference (spatial locality)."""

    def test_same_frame_ocr_preferred_over_time_distance(self, tmp_path):
        """When OCR exists on same frame as symbol, prefer it over time-closer OCR."""
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

        # Symbol at t=8.0 on frame_0004
        # OCR on frame_0004 at t=8.5 (same frame, slightly later time)
        # OCR on different frame at t=8.1 (closer in time, different frame)
        # Should prefer same-frame OCR "都做过" over time-closer "wrong text"
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "gameplay",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 8.0,
                    "source_frame": "frame_0004.jpg",
                    "origin": "evidence_ocr",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
            "ocr_items": [
                {
                    "text": "wrong text",
                    "t_rel": 8.1,  # Closer in time
                    "source_frame": "frame_0003.jpg",  # Different frame
                },
                {
                    "text": "都做过",
                    "t_rel": 8.5,  # Farther in time
                    "source_frame": "frame_0004.jpg",  # Same frame as symbol
                },
            ],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # Should bind to same-frame OCR "都做过"
        assert result is not None
        assert "都做过" in result, "Should prefer same-frame OCR over time-closer OCR"
        assert "wrong text" not in result

    def test_real_case_heart_emoji_with_ocr_text(self, tmp_path):
        """Regression test: ❤️都做过 case - symbol extracted from frame with OCR."""
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
                    "id": "part_0002",
                    "start_time": 5.0,
                    "end_time": 15.0,
                    "video_path": "segments/segment.mp4",
                    "analysis_path": "analysis/part_0002.json",
                }
            ],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))
        manifest = Manifest.load(session_dir)

        # Real scenario:
        # - OCR text on frame_0004: "❤️都做过"
        # - Symbol ❤️ extracted from same frame_0004
        # - Other OCR text: "daddy也叫了" on different frame
        # Must bind to "❤️都做过" or at least "都做过", NOT "daddy也叫了"
        analysis_data = {
            "segment_id": "part_0002",
            "scene_type": "dialogue",
            "model": "test-model",
            "facts": ["Test fact"],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 8.0,
                    "source_frame": "frame_0004.jpg",
                    "origin": "evidence_ocr",  # Extracted from OCR
                    "type": "emoji",
                    "name": "red_heart",
                    "source_part_id": "part_0002",
                }
            ],
            "ocr_items": [
                {
                    "text": "❤️都做过",  # Same frame as symbol
                    "t_rel": 8.0,
                    "source_frame": "frame_0004.jpg",
                },
                {
                    "text": "daddy也叫了",  # Different frame
                    "t_rel": 9.5,
                    "source_frame": "frame_0005.jpg",
                },
            ],
        }
        (analysis_dir / "part_0002.json").write_text(json.dumps(analysis_data))

        segment = manifest.segments[0]
        result = get_segment_symbols(segment, session_dir, "test_session")

        # CRITICAL: Must bind to same-frame OCR
        assert result is not None
        assert (
            "❤️都做过" in result or "都做过" in result
        ), "Should bind to same-frame OCR containing emoji"
        assert "daddy也叫了" not in result, "Should NOT bind to different-frame OCR"
