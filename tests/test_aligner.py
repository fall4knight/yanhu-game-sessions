"""Tests for OCR/ASR alignment."""

import json

from yanhu.aligner import (
    AlignedQuote,
    align_ocr_asr,
    align_segment,
    get_first_quote,
    merge_aligned_quotes_to_analysis,
)
from yanhu.analyzer import OcrItem
from yanhu.transcriber import AsrItem


class TestAlignedQuote:
    """Test AlignedQuote dataclass."""

    def test_to_dict_ocr_only(self):
        """Should serialize OCR-only quote."""
        quote = AlignedQuote(t=5.0, source="ocr", ocr="Hello")
        d = quote.to_dict()
        assert d == {"t": 5.0, "source": "ocr", "ocr": "Hello"}

    def test_to_dict_asr_only(self):
        """Should serialize ASR-only quote."""
        quote = AlignedQuote(t=5.0, source="asr", asr="Hello ASR")
        d = quote.to_dict()
        assert d == {"t": 5.0, "source": "asr", "asr": "Hello ASR"}

    def test_to_dict_both(self):
        """Should serialize both OCR and ASR."""
        quote = AlignedQuote(t=5.0, source="both", ocr="OCR文本", asr="ASR文本")
        d = quote.to_dict()
        assert d == {"t": 5.0, "source": "both", "ocr": "OCR文本", "asr": "ASR文本"}

    def test_from_dict_new_format(self):
        """Should deserialize new format with ocr/asr fields."""
        d = {"t": 10.0, "source": "both", "ocr": "OCR", "asr": "ASR"}
        quote = AlignedQuote.from_dict(d)
        assert quote.t == 10.0
        assert quote.source == "both"
        assert quote.ocr == "OCR"
        assert quote.asr == "ASR"

    def test_from_dict_backward_compat(self):
        """Should support old 'quote' field for backward compatibility."""
        d = {"t": 5.0, "quote": "Legacy", "source": "ocr"}
        quote = AlignedQuote.from_dict(d)
        assert quote.t == 5.0
        assert quote.source == "ocr"
        assert quote.ocr == "Legacy"

    def test_get_display_text_ocr_only(self):
        """Should return OCR text for ocr-only."""
        quote = AlignedQuote(t=5.0, source="ocr", ocr="OCR文本")
        assert quote.get_display_text() == "OCR文本"

    def test_get_display_text_asr_only(self):
        """Should return ASR text for asr-only."""
        quote = AlignedQuote(t=5.0, source="asr", asr="ASR文本")
        assert quote.get_display_text() == "ASR文本"

    def test_get_display_text_both(self):
        """Should return OCR with ASR annotation for both."""
        quote = AlignedQuote(t=5.0, source="both", ocr="OCR文本", asr="ASR文本")
        assert quote.get_display_text() == "OCR文本 (asr: ASR文本)"


class TestAlignOcrAsr:
    """Test align_ocr_asr function."""

    def test_empty_inputs(self):
        """Should handle empty inputs."""
        assert align_ocr_asr([], []) == []

    def test_asr_only_no_ocr(self):
        """Should add ASR as source='asr' when no OCR."""
        asr_items = [AsrItem(text="ASR only", t_start=0, t_end=1)]
        result = align_ocr_asr([], asr_items)
        # ASR items are added as unmatched
        assert len(result) == 1
        assert result[0].asr == "ASR only"
        assert result[0].ocr is None
        assert result[0].source == "asr"

    def test_ocr_only_no_asr(self):
        """Should mark OCR as source='ocr' when no ASR."""
        ocr_items = [
            OcrItem(text="Hello", t_rel=5.0, source_frame="frame1.jpg"),
            OcrItem(text="World", t_rel=10.0, source_frame="frame2.jpg"),
        ]
        result = align_ocr_asr(ocr_items, [])

        assert len(result) == 2
        assert result[0].ocr == "Hello"
        assert result[0].asr is None
        assert result[0].source == "ocr"
        assert result[0].t == 5.0
        assert result[1].ocr == "World"
        assert result[1].source == "ocr"

    def test_matching_within_window(self):
        """Should mark as 'both' and preserve both texts when ASR within window."""
        ocr_items = [
            OcrItem(text="OCR Text", t_rel=5.0, source_frame="frame1.jpg"),
        ]
        asr_items = [
            AsrItem(text="ASR Text", t_start=5.5, t_end=7.0),  # Within 1.5s window
        ]
        result = align_ocr_asr(ocr_items, asr_items, window=1.5)

        assert len(result) == 1
        assert result[0].ocr == "OCR Text"  # OCR text preserved
        assert result[0].asr == "ASR Text"  # ASR text preserved
        assert result[0].source == "both"
        assert result[0].t == 5.0

    def test_no_matching_outside_window(self):
        """Should not match ASR outside window."""
        ocr_items = [
            OcrItem(text="OCR Text", t_rel=5.0, source_frame="frame1.jpg"),
        ]
        asr_items = [
            AsrItem(text="ASR Text", t_start=10.0, t_end=12.0),  # Outside 1.5s window
        ]
        result = align_ocr_asr(ocr_items, asr_items, window=1.5)

        # OCR item marked as 'ocr', ASR item added as 'asr'
        assert len(result) == 2
        assert result[0].ocr == "OCR Text"
        assert result[0].source == "ocr"
        assert result[1].asr == "ASR Text"
        assert result[1].source == "asr"

    def test_unmatched_asr_added(self):
        """Should add unmatched ASR items as source='asr'."""
        ocr_items = [
            OcrItem(text="OCR1", t_rel=5.0, source_frame="frame1.jpg"),
        ]
        asr_items = [
            AsrItem(text="ASR1", t_start=5.2, t_end=6.0),  # Matched
            AsrItem(text="ASR2", t_start=15.0, t_end=16.0),  # Unmatched
        ]
        result = align_ocr_asr(ocr_items, asr_items, window=1.5)

        assert len(result) == 2
        # First is OCR matched with ASR1 - both preserved
        assert result[0].ocr == "OCR1"
        assert result[0].asr == "ASR1"
        assert result[0].source == "both"
        # Second is unmatched ASR2
        assert result[1].asr == "ASR2"
        assert result[1].ocr is None
        assert result[1].source == "asr"

    def test_sorted_by_timestamp(self):
        """Should return results sorted by timestamp."""
        ocr_items = [
            OcrItem(text="Later", t_rel=10.0, source_frame="frame2.jpg"),
            OcrItem(text="Earlier", t_rel=5.0, source_frame="frame1.jpg"),
        ]
        result = align_ocr_asr(ocr_items, [])

        assert result[0].t == 5.0
        assert result[0].ocr == "Earlier"
        assert result[1].t == 10.0
        assert result[1].ocr == "Later"

    def test_max_quotes_limit(self):
        """Should limit to max_quotes."""
        ocr_items = [
            OcrItem(text=f"OCR{i}", t_rel=float(i), source_frame=f"f{i}.jpg") for i in range(10)
        ]
        result = align_ocr_asr(ocr_items, [], max_quotes=3)

        assert len(result) == 3

    def test_preserves_original_text_verbatim(self):
        """Should preserve both OCR and ASR text exactly (no modification)."""
        ocr_items = [
            OcrItem(text="原文：不要改", t_rel=5.0, source_frame="frame1.jpg"),
        ]
        asr_items = [
            AsrItem(text="ASR版本", t_start=5.2, t_end=6.0),
        ]
        result = align_ocr_asr(ocr_items, asr_items, window=1.5)

        assert result[0].ocr == "原文：不要改"  # Exact OCR original
        assert result[0].asr == "ASR版本"  # Exact ASR original
        assert result[0].source == "both"

    def test_nearest_asr_selected(self):
        """Should select nearest ASR when multiple within window."""
        ocr_items = [
            OcrItem(text="OCR", t_rel=5.0, source_frame="frame1.jpg"),
        ]
        asr_items = [
            AsrItem(text="Far", t_start=6.0, t_end=7.0),  # 1.0s away
            AsrItem(text="Near", t_start=5.2, t_end=6.0),  # 0.2s away
            AsrItem(text="Medium", t_start=4.5, t_end=5.0),  # 0.5s away
        ]
        result = align_ocr_asr(ocr_items, asr_items, window=1.5)

        # Should match with "Near" (closest)
        # The other two become unmatched ASR
        assert len(result) == 3
        # First by time is Medium (4.5s)
        matched = [r for r in result if r.source == "both"]
        assert len(matched) == 1
        assert matched[0].ocr == "OCR"
        assert matched[0].asr == "Near"  # Matched with nearest ASR

    def test_custom_window_size(self):
        """Should use custom window size."""
        ocr_items = [
            OcrItem(text="OCR", t_rel=5.0, source_frame="frame1.jpg"),
        ]
        asr_items = [
            AsrItem(text="ASR", t_start=7.0, t_end=8.0),  # 2.0s away
        ]

        # With default window (1.5s) - no match
        result_default = align_ocr_asr(ocr_items, asr_items, window=1.5)
        assert result_default[0].source == "ocr"
        assert result_default[0].ocr == "OCR"
        assert result_default[0].asr is None

        # With larger window (3.0s) - should match and preserve both
        result_large = align_ocr_asr(ocr_items, asr_items, window=3.0)
        assert result_large[0].source == "both"
        assert result_large[0].ocr == "OCR"
        assert result_large[0].asr == "ASR"


class TestAlignSegment:
    """Test align_segment function."""

    def test_nonexistent_file(self, tmp_path):
        """Should return empty list for nonexistent file."""
        result = align_segment(tmp_path / "missing.json")
        assert result == []

    def test_invalid_json(self, tmp_path):
        """Should return empty list for invalid JSON."""
        path = tmp_path / "invalid.json"
        path.write_text("not valid json")
        result = align_segment(path)
        assert result == []

    def test_align_from_analysis_file(self, tmp_path):
        """Should align from analysis JSON file."""
        path = tmp_path / "part_0001.json"
        path.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "ocr_items": [
                        {"text": "Hello", "t_rel": 5.0, "source_frame": "frame1.jpg"},
                    ],
                    "asr_items": [
                        {"text": "Hello ASR", "t_start": 5.2, "t_end": 6.0},
                    ],
                }
            )
        )

        result = align_segment(path, window=1.5)

        assert len(result) == 1
        assert result[0].ocr == "Hello"
        assert result[0].asr == "Hello ASR"
        assert result[0].source == "both"

    def test_no_ocr_no_asr(self, tmp_path):
        """Should return empty for no OCR/ASR data."""
        path = tmp_path / "part_0001.json"
        path.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                }
            )
        )

        result = align_segment(path)
        assert result == []


class TestMergeAlignedQuotesToAnalysis:
    """Test merge_aligned_quotes_to_analysis function."""

    def test_merge_into_existing(self, tmp_path):
        """Should merge aligned quotes into existing analysis."""
        path = tmp_path / "part_0001.json"
        path.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "caption": "Test caption",
                }
            )
        )

        quotes = [
            AlignedQuote(t=5.0, source="ocr", ocr="Hello"),
            AlignedQuote(t=10.0, source="both", ocr="World", asr="World ASR"),
        ]
        merge_aligned_quotes_to_analysis(quotes, path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["segment_id"] == "part_0001"
        assert data["scene_type"] == "dialogue"
        assert data["caption"] == "Test caption"
        assert "aligned_quotes" in data
        assert len(data["aligned_quotes"]) == 2
        assert data["aligned_quotes"][0]["ocr"] == "Hello"
        assert data["aligned_quotes"][1]["source"] == "both"
        assert data["aligned_quotes"][1]["ocr"] == "World"
        assert data["aligned_quotes"][1]["asr"] == "World ASR"

    def test_nonexistent_file_no_error(self, tmp_path):
        """Should not error on nonexistent file."""
        path = tmp_path / "missing.json"
        quotes = [AlignedQuote(t=5.0, source="ocr", ocr="Test")]
        # Should not raise
        merge_aligned_quotes_to_analysis(quotes, path)


class TestGetFirstQuote:
    """Test get_first_quote function."""

    def test_returns_first_quote_new_format(self, tmp_path):
        """Should return first quote display text from new format."""
        path = tmp_path / "part_0001.json"
        path.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "aligned_quotes": [
                        {"t": 5.0, "source": "ocr", "ocr": "First OCR"},
                        {"t": 10.0, "source": "both", "ocr": "Second", "asr": "Second ASR"},
                    ],
                }
            )
        )

        result = get_first_quote(path)
        assert result == "First OCR"

    def test_returns_display_text_with_asr_annotation(self, tmp_path):
        """Should return OCR with ASR annotation for source=both."""
        path = tmp_path / "part_0001.json"
        path.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "aligned_quotes": [
                        {"t": 5.0, "source": "both", "ocr": "OCR文本", "asr": "ASR文本"},
                    ],
                }
            )
        )

        result = get_first_quote(path)
        assert result == "OCR文本 (asr: ASR文本)"

    def test_backward_compat_old_quote_field(self, tmp_path):
        """Should support old 'quote' field for backward compatibility."""
        path = tmp_path / "part_0001.json"
        path.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "aligned_quotes": [
                        {"t": 5.0, "quote": "Legacy Quote", "source": "ocr"},
                    ],
                }
            )
        )

        result = get_first_quote(path)
        assert result == "Legacy Quote"

    def test_returns_none_if_no_quotes(self, tmp_path):
        """Should return None if no aligned_quotes."""
        path = tmp_path / "part_0001.json"
        path.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                }
            )
        )

        result = get_first_quote(path)
        assert result is None

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        """Should return None for nonexistent file."""
        result = get_first_quote(tmp_path / "missing.json")
        assert result is None


class TestTimelineQuoteIntegration:
    """Test that quote appears in timeline."""

    def test_quote_in_timeline_new_format(self, tmp_path):
        """Should show quote line with ASR annotation for source=both."""
        from yanhu.composer import compose_timeline
        from yanhu.manifest import Manifest, SegmentInfo

        # Create analysis with aligned_quotes (new format)
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "facts": ["Test fact"],
                    "aligned_quotes": [
                        {"t": 5.0, "source": "both", "ocr": "OCR文本", "asr": "ASR文本"},
                    ],
                }
            )
        )

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                    frames=[],
                    analysis_path="analysis/part_0001.json",
                )
            ],
        )

        timeline = compose_timeline(manifest, tmp_path)

        assert "- quote: OCR文本 (asr: ASR文本)" in timeline

    def test_quote_backward_compat_old_format(self, tmp_path):
        """Should support old 'quote' field for backward compatibility."""
        from yanhu.composer import compose_timeline
        from yanhu.manifest import Manifest, SegmentInfo

        # Create analysis with old format
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "facts": ["Test fact"],
                    "aligned_quotes": [
                        {"t": 5.0, "quote": "Legacy quote", "source": "ocr"},
                    ],
                }
            )
        )

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                    frames=[],
                    analysis_path="analysis/part_0001.json",
                )
            ],
        )

        timeline = compose_timeline(manifest, tmp_path)

        assert "- quote: Legacy quote" in timeline

    def test_no_quote_line_without_aligned_quotes(self, tmp_path):
        """Should not show quote line if no aligned_quotes."""
        from yanhu.composer import compose_timeline
        from yanhu.manifest import Manifest, SegmentInfo

        # Create analysis WITHOUT aligned_quotes
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "facts": ["Test fact"],
                }
            )
        )

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                    frames=[],
                    analysis_path="analysis/part_0001.json",
                )
            ],
        )

        timeline = compose_timeline(manifest, tmp_path)

        assert "- quote:" not in timeline
