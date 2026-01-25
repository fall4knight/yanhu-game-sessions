"""Tests for per-OCR symbol binding in quote generation."""


from yanhu.analyzer import AnalysisResult, OcrItem, UiSymbolItem
from yanhu.composer import apply_symbols_to_text_items, get_highlight_text
from yanhu.manifest import Manifest, SegmentInfo


class TestPerOcrSymbolBinding:
    """Test per-OCR symbol binding (not global prefix)."""

    def test_symbol_on_second_ocr_item(self):
        """Symbol at frame_0004 should prefix only the second OCR item."""
        # Three OCR items
        ocr_items = [
            OcrItem(text="第一句", t_rel=5.0, source_frame="frame_0001.jpg"),
            OcrItem(text="都做过", t_rel=8.0, source_frame="frame_0004.jpg"),
            OcrItem(text="第三句", t_rel=10.0, source_frame="frame_0006.jpg"),
        ]

        # Symbol at frame_0004 (same as second OCR)
        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=8.0, source_frame="frame_0004.jpg")
        ]

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["第一句", "都做过", "第三句"],
            facts=["test"],
            caption="test",
            ocr_items=ocr_items,
            ui_symbol_items=ui_symbol_items,
        )

        # Apply symbols to text items
        text_items = ["第一句", "都做过", "第三句"]
        result = apply_symbols_to_text_items(text_items, analysis)

        # Expected: only second item prefixed
        assert result == ["第一句", "❤️ 都做过", "第三句"]

    def test_symbol_on_first_of_two_items(self):
        """Symbol binds to first item when ui_key_text has two items."""
        ocr_items = [
            OcrItem(text="知不知道自己在干嘛？", t_rel=5.0, source_frame="frame_0001.jpg"),
            OcrItem(text="daddy也叫了", t_rel=10.0, source_frame="frame_0006.jpg"),
        ]

        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=5.0, source_frame="frame_0001.jpg")
        ]

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["知不知道自己在干嘛？", "daddy也叫了"],
            facts=["test"],
            caption="test",
            ui_key_text=["知不知道自己在干嘛？", "daddy也叫了"],
            ocr_items=ocr_items,
            ui_symbol_items=ui_symbol_items,
        )

        # Test with ui_key_text
        filtered_ui = ["知不知道自己在干嘛？", "daddy也叫了"]
        quote = get_highlight_text(analysis, filtered_ui)

        # Expected: "❤️ 知不知道自己在干嘛？ / daddy也叫了"
        assert quote == "❤️ 知不知道自己在干嘛？ / daddy也叫了"

    def test_no_symbol_binding_without_match(self):
        """Text items without matching symbols remain unchanged."""
        ocr_items = [
            OcrItem(text="第一句", t_rel=5.0, source_frame="frame_0001.jpg"),
            OcrItem(text="第二句", t_rel=8.0, source_frame="frame_0004.jpg"),
        ]

        # Symbol at different time (no match)
        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=15.0, source_frame="frame_0010.jpg")
        ]

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["第一句", "第二句"],
            facts=["test"],
            caption="test",
            ocr_items=ocr_items,
            ui_symbol_items=ui_symbol_items,
        )

        text_items = ["第一句", "第二句"]
        result = apply_symbols_to_text_items(text_items, analysis)

        # Expected: no change (symbol too far)
        assert result == ["第一句", "第二句"]

    def test_multiple_symbols_on_different_items(self):
        """Multiple symbols can bind to different OCR items."""
        ocr_items = [
            OcrItem(text="第一句", t_rel=5.0, source_frame="frame_0001.jpg"),
            OcrItem(text="第二句", t_rel=8.0, source_frame="frame_0004.jpg"),
            OcrItem(text="第三句", t_rel=10.0, source_frame="frame_0006.jpg"),
        ]

        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=5.0, source_frame="frame_0001.jpg"),
            UiSymbolItem(symbol="⭐", t_rel=10.0, source_frame="frame_0006.jpg"),
        ]

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["第一句", "第二句", "第三句"],
            facts=["test"],
            caption="test",
            ocr_items=ocr_items,
            ui_symbol_items=ui_symbol_items,
        )

        text_items = ["第一句", "第二句", "第三句"]
        result = apply_symbols_to_text_items(text_items, analysis)

        # Expected: first and third items prefixed
        assert result == ["❤️ 第一句", "第二句", "⭐ 第三句"]

    def test_empty_symbol_items(self):
        """Empty ui_symbol_items should not modify text."""
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["第一句", "第二句"],
            facts=["test"],
            caption="test",
            ui_symbol_items=[],
        )

        text_items = ["第一句", "第二句"]
        result = apply_symbols_to_text_items(text_items, analysis)

        assert result == ["第一句", "第二句"]


class TestPerOcrSymbolBindingIntegration:
    """Integration tests for per-OCR symbol binding in highlights."""

    def test_highlights_with_symbol_on_specific_ocr(self, tmp_path):
        """Highlights should show symbol only on the matching OCR item."""
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create analysis with symbol bound to "都做过"
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["知不知道自己在干嘛？", "都做过", "daddy也叫了"],
            facts=["test"],
            caption="test",
            ui_key_text=["知不知道自己在干嘛？", "都做过"],  # Include "都做过"
            ocr_items=[
                OcrItem(text="知不知道自己在干嘛？", t_rel=5.0, source_frame="frame_0001.jpg"),
                OcrItem(text="都做过", t_rel=8.0, source_frame="frame_0004.jpg"),
                OcrItem(text="daddy也叫了", t_rel=10.0, source_frame="frame_0006.jpg"),
            ],
            ui_symbol_items=[
                UiSymbolItem(symbol="❤️", t_rel=8.0, source_frame="frame_0004.jpg")
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001",
                    0.0,
                    60.0,
                    "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Expected: "知不知道自己在干嘛？ / ❤️ 都做过"
        # Symbol should be on second item only, not global prefix
        assert "❤️ 都做过" in result
        assert "知不知道自己在干嘛？ / ❤️ 都做过" in result
        # Should NOT be global prefix
        assert not result.startswith("- [00:00:00] ❤️ 知不知道")

    def test_highlights_without_matching_ocr(self, tmp_path):
        """Symbol far from all OCR items should NOT create standalone highlight (Step 18c)."""
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["第一句", "第二句"],
            facts=["test"],
            caption="test",
            ui_key_text=["第一句", "第二句"],
            ocr_items=[
                OcrItem(text="第一句", t_rel=5.0, source_frame="frame_0001.jpg"),
                OcrItem(text="第二句", t_rel=8.0, source_frame="frame_0004.jpg"),
            ],
            ui_symbol_items=[
                # Symbol far away (no match) - should NOT create standalone highlight
                UiSymbolItem(symbol="❤️", t_rel=20.0, source_frame="frame_0010.jpg")
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001",
                    0.0,
                    60.0,
                    "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # The main quote with readable text should appear
        assert "第一句 / 第二句" in result
        # Should have only ONE entry (readable text), NOT a standalone symbol entry
        lines = [line for line in result.split("\n") if line.startswith("- [")]
        assert len(lines) == 1, "Should only have 1 readable highlight, not standalone symbol"
        # Standalone symbols should NOT appear as separate highlights
        # (they may appear as metadata in symbols line, but not as quote)

    def test_standalone_symbol_quote_format(self, tmp_path):
        """Standalone symbols should NOT create separate highlights (Step 18c)."""
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["对话内容"],
            facts=["test"],
            caption="test",
            ui_key_text=["对话内容"],
            ocr_items=[
                OcrItem(text="对话内容", t_rel=5.0, source_frame="frame_0001.jpg"),
            ],
            ui_symbol_items=[
                # Symbol far away (standalone)
                UiSymbolItem(symbol="⭐", t_rel=25.0, source_frame="frame_0010.jpg")
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001",
                    0.0,
                    60.0,
                    "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have main quote with readable text
        assert "对话内容" in result
        # Should have only ONE entry (readable text), NOT a standalone symbol entry
        lines = [line for line in result.split("\n") if line.startswith("- [")]
        assert len(lines) == 1, "Should only have 1 readable highlight, not standalone symbol"
        # Standalone symbols should NOT appear as separate highlights (Step 18c)
        assert "- [00:00:25] ⭐" not in result
