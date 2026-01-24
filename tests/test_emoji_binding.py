"""Tests for emoji symbol binding in timeline and highlights."""

from yanhu.analyzer import AnalysisResult, UiSymbolItem
from yanhu.composer import compose_highlights, compose_timeline
from yanhu.manifest import Manifest, SegmentInfo


class TestEmojiBindingInTimeline:
    """Test emoji symbols appear in timeline.md with frame links."""

    def test_timeline_includes_symbols_line(self, tmp_path):
        """Test timeline segment includes Symbols line when ui_symbol_items present."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis with emoji ui_symbol_item
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["Scene description"],
            ui_key_text=["都做過"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=5.0,
                    source_frame="frame_0003.jpg",
                    type="emoji",
                    name="red_heart",
                )
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_test_emoji_binding",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Should contain Symbols line
        assert "**Symbols**:" in result
        # Should contain heart emoji
        assert "❤️" in result or "❤" in result
        # Should have frame link
        assert "/s/2026-01-24_test_emoji_binding/frames/part_0001/frame_0003.jpg" in result

    def test_timeline_no_symbols_line_when_no_emojis(self, tmp_path):
        """Test timeline segment has no Symbols line when no ui_symbol_items."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis without ui_symbol_items
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["Scene description"],
            ui_key_text=["都做過"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_test_no_emoji",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Should NOT contain Symbols line
        assert "**Symbols**:" not in result

    def test_timeline_multiple_emojis_linked(self, tmp_path):
        """Test timeline shows multiple emojis with separate frame links."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis with multiple emoji symbols
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["Scene description"],
            ui_key_text=["測試"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=3.0,
                    source_frame="frame_0002.jpg",
                    type="emoji",
                ),
                UiSymbolItem(
                    symbol="💛",
                    t_rel=5.0,
                    source_frame="frame_0003.jpg",
                    type="emoji",
                ),
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_test_multi",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Should contain both emojis
        assert "❤️" in result or "❤" in result
        assert "💛" in result
        # Should have separate frame links
        assert "frame_0002.jpg" in result
        assert "frame_0003.jpg" in result


class TestEmojiBindingInHighlights:
    """Test emoji symbols appear in highlights.md with frame links."""

    def test_highlights_includes_symbols_line(self, tmp_path):
        """Test highlights entry includes symbols line when ui_symbol_items present."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis with emoji and high score content
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["Important scene", "Key moment", "Critical action"],
            ui_key_text=["❤️都做過", "daddy也叫了"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=5.0,
                    source_frame="frame_0003.jpg",
                    type="emoji",
                    name="red_heart",
                    source_text="❤️都做過",
                )
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_highlights_test",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, session_dir, min_score=0)

        # Should contain symbols line
        assert "symbols:" in result
        # Should contain heart emoji
        assert "❤️" in result or "❤" in result
        # Should have frame link in symbols line
        assert "frames/part_0001/frame_0003.jpg" in result

    def test_highlights_no_symbols_line_when_no_emojis(self, tmp_path):
        """Test highlights has no symbols line when segment has no ui_symbol_items."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis without ui_symbol_items but high score
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["Important scene", "Key moment", "Critical action"],
            ui_key_text=["都做過", "daddy也叫了"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_no_emoji_hl",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, session_dir, min_score=0)

        # Should NOT contain symbols line
        assert "symbols:" not in result

    def test_highlights_merged_segments_combine_symbols(self, tmp_path):
        """Test merged highlight entries combine symbols from both segments."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # First segment with ❤️
        analysis1 = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["First scene"],
            ui_key_text=["第一段"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=3.0,
                    source_frame="frame_0002.jpg",
                    type="emoji",
                )
            ],
        )
        analysis1.save(analysis_dir / "part_0001.json")

        # Second segment with 💛
        analysis2 = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["Second scene"],
            ui_key_text=["第二段"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="💛",
                    t_rel=8.0,
                    source_frame="frame_0002.jpg",
                    type="emoji",
                )
            ],
        )
        analysis2.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="2026-01-24_merged",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    id="part_0002",
                    start_time=5.0,
                    end_time=10.0,
                    video_path="segments/part_0002.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg"],
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, session_dir, min_score=0)

        # Should contain both emojis in symbols line
        assert "❤️" in result or "❤" in result
        assert "💛" in result
        # Should reference merged segment
        assert "part_0001+0002" in result

    def test_highlights_emoji_frame_url_format(self, tmp_path):
        """Test emoji frame URL follows correct format for web serving."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["Test scene", "Important", "Critical"],
            ui_key_text=["都做過"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=8.0,
                    source_frame="frame_0004.jpg",
                    type="emoji",
                )
            ],
        )
        analysis.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="2026-01-23_05-28-49_unknown_actor_clip__b999e892",
            created_at="2026-01-23T05:28:49",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0002",
                    start_time=5.0,
                    end_time=10.0,
                    video_path="segments/part_0002.mp4",
                    frames=["frame_0001.jpg", "frame_0004.jpg"],
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, session_dir, min_score=0)

        # Should have correct URL format matching Flask route
        expected_url = (
            "/s/2026-01-23_05-28-49_unknown_actor_clip__b999e892/frames/part_0002/frame_0004.jpg"
        )
        assert expected_url in result


class TestEmojiPartIdFiltering:
    """Test emoji symbols are correctly filtered by source_part_id."""

    def test_timeline_filters_symbols_by_part_id(self, tmp_path):
        """Test timeline only shows symbols from the correct part."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis with symbols having different source_part_ids
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["First segment"],
            ui_key_text=["測試"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=3.0,
                    source_frame="frame_0002.jpg",
                    type="emoji",
                    source_part_id="part_0001",  # Belongs to this part
                ),
                UiSymbolItem(
                    symbol="💛",
                    t_rel=8.0,
                    source_frame="frame_0003.jpg",
                    type="emoji",
                    source_part_id="part_0002",  # Belongs to different part
                ),
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_part_filter",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Should contain ❤️ from part_0001
        assert "❤️" in result or "❤" in result
        assert "frame_0002.jpg" in result
        # Should NOT contain 💛 from part_0002
        assert "💛" not in result

    def test_highlights_filters_symbols_by_part_id(self, tmp_path):
        """Test highlights only shows symbols from correct part.

        Uses non-consecutive segments to avoid merging.
        """
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create two non-consecutive segments with symbols having correct source_part_ids
        # Use different facts to prevent merging
        analysis1 = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["First important scene", "Opening moment", "Starting event"],
            ui_key_text=["第一段"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=3.0,
                    source_frame="frame_0002.jpg",
                    type="emoji",
                    source_part_id="part_0001",
                )
            ],
        )
        analysis1.save(analysis_dir / "part_0001.json")

        # Create a middle segment with low score to separate them
        analysis2 = AnalysisResult(
            segment_id="part_0002",
            scene_type="transition",
            facts=["Transition"],
            ui_key_text=[],
        )
        analysis2.save(analysis_dir / "part_0002.json")

        analysis3 = AnalysisResult(
            segment_id="part_0003",
            scene_type="dialogue",
            facts=["Second important scene", "Closing moment", "Ending event"],
            ui_key_text=["第三段"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="💛",
                    t_rel=13.0,
                    source_frame="frame_0003.jpg",
                    type="emoji",
                    source_part_id="part_0003",
                )
            ],
        )
        analysis3.save(analysis_dir / "part_0003.json")

        manifest = Manifest(
            session_id="2026-01-24_hl_part_filter",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    id="part_0002",
                    start_time=5.0,
                    end_time=10.0,
                    video_path="segments/part_0002.mp4",
                    frames=["frame_0001.jpg"],
                    analysis_path="analysis/part_0002.json",
                ),
                SegmentInfo(
                    id="part_0003",
                    start_time=10.0,
                    end_time=15.0,
                    video_path="segments/part_0003.mp4",
                    frames=["frame_0001.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0003.json",
                ),
            ],
        )

        result = compose_highlights(manifest, session_dir, min_score=0)

        # Should have separate entries for part_0001 and part_0003 (not merged)
        # Verify symbols are bound to correct parts
        assert "part_0001" in result
        assert "part_0003" in result

        # Split result into lines and find symbol lines
        lines = result.split("\n")
        for i, line in enumerate(lines):
            # When we find part_0001, check the symbols line below
            if "part_0001" in line and "part_0003" not in line:
                # Look for symbols line in next few lines
                for j in range(i, min(i + 5, len(lines))):
                    if "symbols:" in lines[j]:
                        # This symbols line should have ❤️ but not 💛
                        assert "❤️" in lines[j] or "❤" in lines[j]
                        assert "💛" not in lines[j]
                        break
            # When we find part_0003, check the symbols line below
            elif "part_0003" in line and "part_0001" not in line:
                # Look for symbols line in next few lines
                for j in range(i, min(i + 5, len(lines))):
                    if "symbols:" in lines[j]:
                        # This symbols line should have 💛 but not ❤️
                        assert "💛" in lines[j]
                        assert "❤️" not in lines[j] and "❤" not in lines[j]
                        break


class TestEmojiAsrTimeBasedMatching:
    """Test emoji→ASR binding uses correct time-based matching with segment-relative times."""

    def test_nearest_asr_binding_by_midpoint_distance(self, tmp_path):
        """Test symbol binds to ASR with nearest midpoint (segment-relative time base).

        Setup:
        - Segment starts at 5.0s (absolute), duration 10s (5.0–15.0s absolute)
        - ASR items (absolute times):
          [5.00–6.64] "你知道自己在做什麼嗎" (mid=5.82, rel=0.82)
          [6.64–7.92] "我和你" (mid=7.28, rel=2.28)
          [7.92–9.48] "愛都做了" (mid=8.70, rel=3.70)
          [9.48–11.16] "爸爸也做了" (mid=10.32, rel=5.32)
        - Symbol at t_rel=3.7 (segment-relative)

        Expected: symbol should bind to "愛都做了" (distance 0.0)
        """
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis with asr_items (absolute times) and symbol (segment-relative time)
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "facts": ["Test scene"],
            "ui_key_text": [
                "你知道自己在做什麼嗎",
                "我和你",
                "愛都做了",
                "爸爸也做了",
            ],
            "asr_items": [
                {"text": "你知道自己在做什麼嗎", "t_start": 5.00, "t_end": 6.64},
                {"text": "我和你", "t_start": 6.64, "t_end": 7.92},
                {"text": "愛都做了", "t_start": 7.92, "t_end": 9.48},
                {"text": "爸爸也做了", "t_start": 9.48, "t_end": 11.16},
            ],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.7,  # Segment-relative: should match mid=3.70
                    "source_frame": "frame_0003.jpg",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
        }

        import json

        with open(analysis_dir / "part_0001.json", "w", encoding="utf-8") as f:
            json.dump(analysis_data, f, ensure_ascii=False)

        manifest = Manifest(
            session_id="2026-01-24_time_match",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=5.0,  # Absolute start time
                    end_time=15.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Should bind to "愛都做了" (closest midpoint)
        assert "愛都做了" in result
        assert "**Symbols**:" in result
        # Verify the Symbols line contains "愛都做了"
        lines = result.split("\n")
        symbols_line = [line for line in lines if "**Symbols**:" in line][0]
        assert "愛都做了" in symbols_line
        # Should NOT have first sentence in symbols line
        assert "你知道自己在做什麼嗎" not in symbols_line

    def test_nearest_asr_binding_early_symbol(self, tmp_path):
        """Test symbol near segment start binds to first ASR sentence.

        Setup:
        - Segment starts at 5.0s, duration 10s
        - Symbol at t_rel=0.9 (segment-relative)
        - Should bind to first ASR item (mid=0.82, distance=0.08)
        """
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "facts": ["Test scene"],
            "ui_key_text": ["你知道自己在做什麼嗎", "我和你"],
            "asr_items": [
                {"text": "你知道自己在做什麼嗎", "t_start": 5.00, "t_end": 6.64},
                {"text": "我和你", "t_start": 6.64, "t_end": 7.92},
            ],
            "ui_symbol_items": [
                {
                    "symbol": "💙",
                    "t_rel": 0.9,  # Near start, closest to first ASR
                    "source_frame": "frame_0001.jpg",
                    "type": "emoji",
                    "source_part_id": "part_0001",
                }
            ],
        }

        import json

        with open(analysis_dir / "part_0001.json", "w", encoding="utf-8") as f:
            json.dump(analysis_data, f, ensure_ascii=False)

        manifest = Manifest(
            session_id="2026-01-24_early_match",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=5.0,
                    end_time=15.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Should bind to first sentence
        assert "你知道自己在做什麼嗎" in result
        assert "💙" in result

    def test_timeline_asr_integration_realistic_scenario(self, tmp_path):
        """Integration test: realistic scenario matching issue description.

        Simulates part_0002 scenario:
        - Segment at 5.0s–10.0s (duration 5s)
        - Symbol at t_rel=3.0 (segment-relative, 8.0s absolute)
        - ASR at 7.92–9.48 "愛都做了" (mid=8.70 absolute, 3.70 rel)
        - Distance: |3.0 - 3.70| = 0.70

        Should display: Symbols: ❤️ (near: "愛都做了")
        """
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        analysis_data = {
            "segment_id": "part_0002",
            "scene_type": "dialogue",
            "facts": ["Test scene"],
            "ui_key_text": ["你不知道自己在干嘛？", "愛都做了", "daddy也做了"],
            "asr_items": [
                {"text": "你不知道自己在干嘛？", "t_start": 5.00, "t_end": 6.64},
                {"text": "愛都做了", "t_start": 7.92, "t_end": 9.48},
                {"text": "daddy也做了", "t_start": 9.48, "t_end": 10.00},
            ],
            "ui_symbol_items": [
                {
                    "symbol": "❤️",
                    "t_rel": 3.0,  # 8.0s absolute
                    "source_frame": "frame_0004.jpg",
                    "type": "emoji",
                    "name": "red_heart",
                    "source_part_id": "part_0002",
                }
            ],
        }

        import json

        with open(analysis_dir / "part_0002.json", "w", encoding="utf-8") as f:
            json.dump(analysis_data, f, ensure_ascii=False)

        manifest = Manifest(
            session_id="2026-01-23_realistic",
            created_at="2026-01-23T05:28:49",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0002",
                    start_time=5.0,
                    end_time=10.0,
                    video_path="segments/part_0002.mp4",
                    frames=["frame_0001.jpg", "frame_0004.jpg"],
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Must bind to "愛都做了", not first sentence
        assert "❤️" in result or "❤" in result
        assert "愛都做了" in result
        # Verify it's in the Symbols line (not just elsewhere)
        lines = result.split("\n")
        for line in lines:
            if "symbols:" in line.lower() or ("❤" in line and "frame_0004" in line):
                assert "愛都做了" in line
                # Should NOT have first sentence in symbols line
                assert "你不知道自己在干嘛" not in line
                break


class TestEmojiAsrContext:
    """Test emoji symbols include nearest ASR text context."""

    def test_timeline_shows_asr_context_with_symbols(self, tmp_path):
        """Test timeline symbols include ASR context when available."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis with emoji and ASR text
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["Scene description"],
            ui_key_text=["都做過", "daddy也叫了"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=5.0,
                    source_frame="frame_0003.jpg",
                    type="emoji",
                    name="red_heart",
                    source_part_id="part_0001",
                )
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_asr_context",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_timeline(manifest, session_dir)

        # Should contain emoji with ASR context
        assert "❤️" in result or "❤" in result
        assert "(near:" in result
        # Should contain at least one of the ASR texts
        assert "都做過" in result or "daddy也叫了" in result

    def test_highlights_shows_asr_context_with_symbols(self, tmp_path):
        """Test highlights symbols include ASR context when available."""
        session_dir = tmp_path
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create analysis with emoji, ASR text, and high score content
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["Important scene", "Key moment", "Critical action"],
            ui_key_text=["❤️都做過", "daddy也叫了"],
            ui_symbol_items=[
                UiSymbolItem(
                    symbol="❤️",
                    t_rel=5.0,
                    source_frame="frame_0003.jpg",
                    type="emoji",
                    name="red_heart",
                    source_text="❤️都做過",
                    source_part_id="part_0001",
                )
            ],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="2026-01-24_hl_asr_ctx",
            created_at="2026-01-24T10:00:00",
            source_video="test.mp4",
            source_video_local="source.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=5.0,
                    video_path="segments/part_0001.mp4",
                    frames=["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"],
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, session_dir, min_score=0)

        # Should contain emoji with ASR context
        assert "❤️" in result or "❤" in result
        assert "(near:" in result
        # Should contain at least one of the ASR texts
        assert "都做過" in result or "daddy也叫了" in result
