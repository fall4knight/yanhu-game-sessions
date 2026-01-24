"""Tests for evidence-layer emoji extraction from OCR items."""

from yanhu.analyzer import OcrItem, extract_emojis_from_ocr


class TestEmojiExtractionFromOcr:
    """Test emoji extraction from OCR items (evidence layer)."""

    def test_heart_emoji_with_vs16_extracted(self):
        """Test heart emoji with variation selector (U+2764 + U+FE0F) is extracted."""
        heart_with_vs16 = "\u2764\uFE0F"  # ❤️
        ocr_items = [
            OcrItem(
                text=f"{heart_with_vs16}都做过",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 1
        assert result[0].symbol == heart_with_vs16
        assert result[0].t_rel == 5.0
        assert result[0].source_frame == "frame_0001.jpg"
        assert result[0].type == "emoji"
        assert result[0].name is not None  # Should have canonical name
        assert "都做过" in result[0].source_text

    def test_heart_emoji_without_vs16_extracted(self):
        """Test heart emoji without variation selector (U+2764 only) is extracted."""
        heart_without_vs16 = "\u2764"  # ❤ (text form)
        ocr_items = [
            OcrItem(
                text=f"{heart_without_vs16}都做过",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 1
        assert result[0].symbol == heart_without_vs16
        assert result[0].type == "emoji"

    def test_colored_heart_emoji_extracted(self):
        """Test colored heart emoji (💛) is extracted."""
        yellow_heart = "💛"
        ocr_items = [
            OcrItem(
                text=f"{yellow_heart}都做过",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 1
        assert result[0].symbol == yellow_heart
        assert result[0].type == "emoji"
        assert result[0].name is not None  # Should have name like "yellow_heart"

    def test_multiple_emojis_in_one_text_extracted(self):
        """Test multiple emojis in one OCR text are extracted as separate items."""
        ocr_items = [
            OcrItem(
                text="❤️都做过💛測試🔥結束",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        # Should extract 3 distinct emojis
        assert len(result) == 3
        symbols = [item.symbol for item in result]
        assert "❤️" in symbols or "❤" in symbols  # Heart (with or without VS16)
        assert "💛" in symbols  # Yellow heart
        assert "🔥" in symbols  # Fire

        # All should have same source_frame and t_rel
        assert all(item.source_frame == "frame_0001.jpg" for item in result)
        assert all(item.t_rel == 5.0 for item in result)

    def test_no_emoji_returns_empty_list(self):
        """Test OCR text without emojis returns empty list."""
        ocr_items = [
            OcrItem(
                text="都做过沒有emoji",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 0

    def test_duplicate_emoji_same_frame_deduplicated(self):
        """Test same emoji in same frame is deduplicated (only one item)."""
        ocr_items = [
            OcrItem(
                text="❤️都做過❤️",  # Same emoji appears twice
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        # Should only emit one item despite two occurrences
        assert len(result) == 1
        assert result[0].symbol in ["❤️", "❤"]

    def test_same_emoji_different_frames_not_deduplicated(self):
        """Test same emoji in different frames creates separate items."""
        ocr_items = [
            OcrItem(
                text="❤️都做过",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            ),
            OcrItem(
                text="❤️測試",
                t_rel=8.0,
                source_frame="frame_0002.jpg",
            ),
        ]

        result = extract_emojis_from_ocr(ocr_items)

        # Should have 2 items (same emoji, different frames)
        assert len(result) == 2
        assert result[0].source_frame == "frame_0001.jpg"
        assert result[1].source_frame == "frame_0002.jpg"

    def test_empty_ocr_text_handled(self):
        """Test empty OCR text is handled gracefully."""
        ocr_items = [
            OcrItem(
                text="",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 0

    def test_emoji_with_skin_tone_modifier_extracted(self):
        """Test emoji with skin tone modifier is extracted as single item."""
        # Thumbs up with medium skin tone: U+1F44D + U+1F3FD
        thumbs_up_skin_tone = "👍🏽"
        ocr_items = [
            OcrItem(
                text=f"好{thumbs_up_skin_tone}讚",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 1
        assert thumbs_up_skin_tone in result[0].symbol
        assert result[0].type == "emoji"

    def test_flag_emoji_extracted(self):
        """Test flag emoji (regional indicator pairs) is extracted."""
        # Chinese flag: U+1F1E8 + U+1F1F3
        chinese_flag = "🇨🇳"
        ocr_items = [
            OcrItem(
                text=f"中國{chinese_flag}加油",
                t_rel=5.0,
                source_frame="frame_0001.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) >= 1  # Flag should be detected
        # Find the flag emoji in results
        flag_items = [item for item in result if chinese_flag in item.symbol]
        assert len(flag_items) >= 1

    def test_source_text_snippet_captured(self):
        """Test source_text captures surrounding context."""
        ocr_items = [
            OcrItem(
                text="daddy也叫了❤️都做過",
                t_rel=8.0,
                source_frame="frame_0004.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 1
        # Source text should contain context around the emoji
        assert result[0].source_text is not None
        assert "❤" in result[0].source_text or "❤️" in result[0].source_text
        # Should have some surrounding text (not just the emoji)
        assert len(result[0].source_text) > len(result[0].symbol)

    def test_source_part_id_set_when_provided(self):
        """Test source_part_id is set when part_id parameter is provided."""
        ocr_items = [
            OcrItem(
                text="❤️都做過",
                t_rel=5.0,
                source_frame="frame_0003.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items, part_id="part_0002")

        assert len(result) == 1
        assert result[0].source_part_id == "part_0002"
        assert result[0].symbol in ["❤️", "❤"]

    def test_source_part_id_none_when_not_provided(self):
        """Test source_part_id is None when part_id parameter is not provided."""
        ocr_items = [
            OcrItem(
                text="❤️都做過",
                t_rel=5.0,
                source_frame="frame_0003.jpg",
            )
        ]

        result = extract_emojis_from_ocr(ocr_items)

        assert len(result) == 1
        assert result[0].source_part_id is None
