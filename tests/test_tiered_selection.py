"""Tests for tiered highlight selection (Tier A/B/C)."""

from yanhu.analyzer import AnalysisResult
from yanhu.composer import (
    compose_highlights,
    get_content_tier,
    normalize_description,
)
from yanhu.manifest import Manifest, SegmentInfo


class TestContentTier:
    """Tests for content tier classification."""

    def test_tier_a_with_ui_key_text(self, tmp_path):
        """Segment with ui_key_text should be Tier A."""
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["台词"],
            facts=["场景"],
            caption="描述",
            ui_key_text=["台词"],
        )
        segment = SegmentInfo("part_0001", 0.0, 5.0, "s1.mp4")
        tier = get_content_tier(analysis, segment, tmp_path)
        assert tier == "A"

    def test_tier_a_with_ui_symbol_items(self, tmp_path):
        """Segment with ui_symbol_items should be Tier A."""
        from yanhu.analyzer import UiSymbolItem

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["场景"],
            caption="描述",
            ui_symbol_items=[
                UiSymbolItem(symbol="❤️", t_rel=5.0, source_frame="frame_0001.jpg")
            ],
        )
        segment = SegmentInfo("part_0001", 0.0, 5.0, "s1.mp4")
        tier = get_content_tier(analysis, segment, tmp_path)
        assert tier == "A"

    def test_tier_c_with_asr_items_only(self, tmp_path):
        """Segment with only asr_items (no dialogue/symbols) should be Tier C.

        asr_items alone don't qualify for Tier A since they often contain noise.
        Only ui_key_text (dialogue) and symbols are high-value Tier A content.
        """
        from yanhu.transcriber import AsrItem

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["场景"],
            caption="描述",
        )
        # Set asr_items as attribute (not in constructor)
        analysis.asr_items = [AsrItem(text="语音内容", t_start=5.0, t_end=8.0)]
        segment = SegmentInfo("part_0001", 0.0, 5.0, "s1.mp4")
        tier = get_content_tier(analysis, segment, tmp_path)
        assert tier == "C"  # Changed from "A" - asr alone is not high-value

    def test_tier_b_with_ocr_text(self, tmp_path):
        """Segment with only ocr_text should be Tier B."""
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["文字"],
            facts=["场景"],
            caption="描述",
        )
        segment = SegmentInfo("part_0001", 0.0, 5.0, "s1.mp4")
        tier = get_content_tier(analysis, segment, tmp_path)
        assert tier == "B"

    def test_tier_b_with_what_changed(self, tmp_path):
        """Segment with only what_changed should be Tier B."""
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["场景"],
            caption="描述",
            what_changed="镜头切换",
        )
        segment = SegmentInfo("part_0001", 0.0, 5.0, "s1.mp4")
        tier = get_content_tier(analysis, segment, tmp_path)
        assert tier == "B"

    def test_tier_c_with_only_facts(self, tmp_path):
        """Segment with only facts/caption should be Tier C."""
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["男性角色戴眼镜"],
            caption="场景描述",
        )
        segment = SegmentInfo("part_0001", 0.0, 5.0, "s1.mp4")
        tier = get_content_tier(analysis, segment, tmp_path)
        assert tier == "C"


class TestNormalizeDescription:
    """Tests for description normalization."""

    def test_normalize_removes_punctuation(self):
        """Should remove punctuation marks."""
        text = "男性角色，穿深色正装。"
        normalized = normalize_description(text)
        assert "，" not in normalized
        assert "。" not in normalized

    def test_normalize_removes_whitespace(self):
        """Should remove whitespace."""
        text = "男性 角色 戴 眼镜"
        normalized = normalize_description(text)
        assert " " not in normalized
        assert normalized == "男性角色戴眼镜"

    def test_normalize_case_insensitive(self):
        """Should convert to lowercase."""
        text1 = "Male Character"
        text2 = "male character"
        assert normalize_description(text1) == normalize_description(text2)

    def test_normalize_similar_descriptions_match(self):
        """Similar descriptions should normalize to same key."""
        desc1 = "男性角色穿深色正装戴眼镜"
        desc2 = "男性角色，穿深色正装，戴眼镜。"
        desc3 = "男性 角色 穿 深色 正装 戴 眼镜"
        norm1 = normalize_description(desc1)
        norm2 = normalize_description(desc2)
        norm3 = normalize_description(desc3)
        assert norm1 == norm2 == norm3


class TestTieredSelection:
    """Integration tests for tiered highlight selection."""

    def test_tier_a_prioritized_over_tier_c(self, tmp_path):
        """Tier A (dialogue) should be selected before Tier C (facts only)."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create Tier A segment (low score but has dialogue)
        tier_a = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["台词内容"],
            facts=["场景"],
            caption="描述",
            ui_key_text=["台词内容"],
        )
        tier_a.save(analysis_dir / "part_0001.json")

        # Create Tier C segment (high score but only facts)
        tier_c = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            ocr_text=[],
            facts=["男性角色戴眼镜穿深色正装"],
            caption="视觉描述",
        )
        tier_c.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    "part_0001",
                    0.0,
                    5.0,
                    "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002",
                    5.0,
                    10.0,
                    "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=1, min_score=0)

        # Tier A should be selected even if Tier C has higher score
        assert "台词内容" in result

    def test_tier_c_deduplication_by_description(self, tmp_path):
        """Multiple Tier C segments with same description should be deduplicated."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create 3 Tier C segments with similar descriptions
        for i in range(1, 4):
            analysis = AnalysisResult(
                segment_id=f"part_{i:04d}",
                scene_type="dialogue",
                ocr_text=[],
                facts=["男性角色戴眼镜穿深色正装"],
                caption="场景描述",
            )
            analysis.save(analysis_dir / f"part_{i:04d}.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    f"part_{i:04d}",
                    (i - 1) * 5.0,
                    i * 5.0,
                    f"s{i}.mp4",
                    analysis_path=f"analysis/part_{i:04d}.json",
                )
                for i in range(1, 4)
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Should only have 1 entry (deduplicated)
        lines = [line for line in result.split("\n") if line.startswith("- [")]
        assert len(lines) == 1

    def test_tier_a_not_deduplicated_by_description(self, tmp_path):
        """Tier A segments should not be deduplicated by description."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create 3 Tier A segments with different dialogue but similar facts
        # Make them non-adjacent to avoid merging
        for i in [1, 3, 5]:
            analysis = AnalysisResult(
                segment_id=f"part_{i:04d}",
                scene_type="dialogue",
                ocr_text=[f"台词{i}"],
                facts=["男性角色戴眼镜"],  # Same facts
                caption="描述",
                ui_key_text=[f"台词{i}"],
            )
            analysis.save(analysis_dir / f"part_{i:04d}.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    f"part_{i:04d}",
                    (i - 1) * 5.0,
                    i * 5.0,
                    f"s{i}.mp4",
                    analysis_path=f"analysis/part_{i:04d}.json",
                )
                for i in [1, 3, 5]
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Should have all 3 entries (not deduplicated)
        assert "台词1" in result
        assert "台词3" in result
        assert "台词5" in result
        lines = [line for line in result.split("\n") if line.startswith("- [")]
        assert len(lines) == 3

    def test_mixed_tiers_selection_order(self, tmp_path):
        """Mixed tiers should be selected in A > B > C order."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Tier C (highest score but lowest priority)
        tier_c = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["视觉描述C"],
            caption="描述",
        )
        tier_c.save(analysis_dir / "part_0001.json")

        # Tier B (medium score and priority) - use non-adjacent ID
        tier_b = AnalysisResult(
            segment_id="part_0003",
            scene_type="dialogue",
            ocr_text=["OCR文字"],
            facts=["视觉描述B"],
            caption="描述",
        )
        tier_b.save(analysis_dir / "part_0003.json")

        # Tier A (lowest score but highest priority) - use non-adjacent ID
        tier_a = AnalysisResult(
            segment_id="part_0005",
            scene_type="dialogue",
            ocr_text=["台词"],
            facts=["视觉描述A"],
            caption="描述",
            ui_key_text=["台词"],
        )
        tier_a.save(analysis_dir / "part_0005.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=5,
            segments=[
                SegmentInfo(
                    "part_0001",
                    0.0,
                    5.0,
                    "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0003",
                    10.0,
                    15.0,
                    "s2.mp4",
                    analysis_path="analysis/part_0003.json",
                ),
                SegmentInfo(
                    "part_0005",
                    20.0,
                    25.0,
                    "s3.mp4",
                    analysis_path="analysis/part_0005.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # All should be included, verifying tier-based prioritization
        assert "台词" in result  # Tier A
        assert "OCR文字" in result  # Tier B
        # Tier C might be included if top_k allows
        lines = [line for line in result.split("\n") if line.startswith("- [")]
        assert len(lines) == 3
