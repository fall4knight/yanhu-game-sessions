"""Tests for symbol-to-OCR binding (time-based, no keyword rules)."""

from yanhu.analyzer import OcrItem, UiSymbolItem
from yanhu.symbol_binder import bind_symbols_to_ocr


class TestSymbolBinding:
    """Test symbol binding to nearest OCR by time."""

    def test_bind_symbol_to_nearest_ocr(self):
        """Should bind symbol to nearest OCR item within threshold."""
        ocr_items = [
            OcrItem(text="对话1", t_rel=10.0, source_frame="frame_0001.jpg"),
            OcrItem(text="对话2", t_rel=20.0, source_frame="frame_0002.jpg"),
            OcrItem(text="对话3", t_rel=30.0, source_frame="frame_0003.jpg"),
        ]

        # Symbol appears near second OCR (delta=0.5s)
        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=20.5, source_frame="frame_0002.jpg"),
        ]

        results = bind_symbols_to_ocr(ui_symbol_items, ocr_items, threshold=1.5)

        assert len(results) == 1
        bound = results[0]
        assert bound.symbol == "❤️"
        assert bound.ocr_text == "对话2"
        assert bound.source == "bound"
        assert bound.time_delta == 0.5

    def test_symbol_beyond_threshold_standalone(self):
        """Should create standalone quote when symbol exceeds threshold."""
        ocr_items = [
            OcrItem(text="对话1", t_rel=10.0, source_frame="frame_0001.jpg"),
            OcrItem(text="对话2", t_rel=20.0, source_frame="frame_0002.jpg"),
        ]

        # Symbol far from any OCR (delta=5s from nearest)
        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=25.0, source_frame="frame_0005.jpg"),
        ]

        results = bind_symbols_to_ocr(ui_symbol_items, ocr_items, threshold=1.5)

        assert len(results) == 1
        standalone = results[0]
        assert standalone.symbol == "❤️"
        assert standalone.ocr_text is None
        assert standalone.source == "symbol"
        assert standalone.time_delta is None

    def test_no_keyword_matching(self):
        """Should NOT use keyword matching, only time-based alignment."""
        ocr_items = [
            OcrItem(text="普通对话", t_rel=10.0, source_frame="frame_0001.jpg"),
            OcrItem(text="爱你哦", t_rel=20.0, source_frame="frame_0002.jpg"),
        ]

        # Symbol near first OCR (no keyword match), should still bind by time
        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=10.3, source_frame="frame_0001.jpg"),
        ]

        results = bind_symbols_to_ocr(ui_symbol_items, ocr_items, threshold=1.5)

        # Should bind to first OCR by time, NOT second OCR by keyword
        assert len(results) == 1
        assert results[0].ocr_text == "普通对话"
        assert results[0].source == "bound"

    def test_multiple_symbols_different_bindings(self):
        """Should handle multiple symbols with different binding results."""
        ocr_items = [
            OcrItem(text="对话1", t_rel=10.0, source_frame="frame_0001.jpg"),
            OcrItem(text="对话2", t_rel=20.0, source_frame="frame_0002.jpg"),
        ]

        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=10.5, source_frame="frame_0001.jpg"),  # bind to OCR1
            UiSymbolItem(symbol="⭐", t_rel=30.0, source_frame="frame_0006.jpg"),  # standalone
        ]

        results = bind_symbols_to_ocr(ui_symbol_items, ocr_items, threshold=1.5)

        assert len(results) == 2
        # First symbol bound
        assert results[0].symbol == "❤️"
        assert results[0].ocr_text == "对话1"
        assert results[0].source == "bound"
        # Second symbol standalone
        assert results[1].symbol == "⭐"
        assert results[1].ocr_text is None
        assert results[1].source == "symbol"

    def test_empty_inputs(self):
        """Should handle empty inputs gracefully."""
        # No symbols
        results = bind_symbols_to_ocr([], [], threshold=1.5)
        assert results == []

        # Symbols but no OCR
        ui_symbol_items = [
            UiSymbolItem(symbol="❤️", t_rel=10.0, source_frame="frame_0001.jpg"),
        ]
        results = bind_symbols_to_ocr(ui_symbol_items, [], threshold=1.5)
        assert len(results) == 1
        assert results[0].ocr_text is None
        assert results[0].source == "symbol"
