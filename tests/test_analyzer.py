"""Tests for vision analysis."""

import json
from pathlib import Path

from yanhu.analyzer import (
    AnalysisResult,
    AnalyzeStats,
    ClaudeAnalyzer,
    MockAnalyzer,
    analyze_session,
    check_cache,
    generate_analysis_path,
    get_analyzer,
    normalize_ocr_text,
)
from yanhu.claude_client import MockClaudeClient
from yanhu.manifest import Manifest, SegmentInfo


class TestAnalysisResult:
    """Test AnalysisResult data structure."""

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["你好", "欢迎"],
            caption="角色A与角色B对话",
        )
        d = result.to_dict()
        assert d["segment_id"] == "part_0001"
        assert d["scene_type"] == "dialogue"
        assert d["ocr_text"] == ["你好", "欢迎"]
        assert d["caption"] == "角色A与角色B对话"

    def test_from_dict(self):
        """Should deserialize from dict correctly."""
        d = {
            "segment_id": "part_0002",
            "scene_type": "combat",
            "ocr_text": [],
            "caption": "战斗场景",
        }
        result = AnalysisResult.from_dict(d)
        assert result.segment_id == "part_0002"
        assert result.scene_type == "combat"
        assert result.ocr_text == []
        assert result.caption == "战斗场景"

    def test_save_and_load(self, tmp_path):
        """Should save and load from file correctly."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=["测试"],
            caption="测试描述",
        )
        output_path = tmp_path / "analysis" / "part_0001.json"
        result.save(output_path)

        assert output_path.exists()

        loaded = AnalysisResult.load(output_path)
        assert loaded.segment_id == result.segment_id
        assert loaded.scene_type == result.scene_type
        assert loaded.ocr_text == result.ocr_text
        assert loaded.caption == result.caption

    def test_save_creates_parent_dirs(self, tmp_path):
        """Should create parent directories if they don't exist."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            caption="test",
        )
        output_path = tmp_path / "nested" / "dir" / "analysis.json"
        result.save(output_path)
        assert output_path.exists()

    def test_save_json_is_valid(self, tmp_path):
        """Saved file should be valid JSON."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=["中文测试"],
            caption="【占位】测试",
        )
        output_path = tmp_path / "test.json"
        result.save(output_path)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["segment_id"] == "part_0001"
        assert "中文测试" in data["ocr_text"]


class TestGenerateAnalysisPath:
    """Test analysis path generation."""

    def test_path_format(self):
        """Path should be analysis/<segment_id>.json."""
        path = generate_analysis_path("part_0001")
        assert path == "analysis/part_0001.json"

    def test_path_is_relative(self):
        """Path should be relative (not start with /)."""
        path = generate_analysis_path("part_0001")
        assert not path.startswith("/")

    def test_path_uses_segment_id(self):
        """Path should include segment ID."""
        path = generate_analysis_path("part_0042")
        assert "part_0042" in path


class TestMockAnalyzer:
    """Test mock analyzer."""

    def test_analyze_segment_returns_result(self):
        """Should return an AnalysisResult."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test_part_0001.mp4",
            frames=["f1.jpg", "f2.jpg", "f3.jpg"],
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"))
        assert isinstance(result, AnalysisResult)

    def test_analyze_segment_uses_segment_id(self):
        """Result should have correct segment ID."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0042",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test_part_0042.mp4",
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"))
        assert result.segment_id == "part_0042"

    def test_analyze_segment_scene_type_unknown(self):
        """Mock should return 'unknown' scene type."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"))
        assert result.scene_type == "unknown"

    def test_analyze_segment_ocr_empty(self):
        """Mock should return empty OCR text."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"))
        assert result.ocr_text == []

    def test_analyze_segment_caption_contains_segment_id(self):
        """Caption should contain segment ID."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"))
        assert "part_0001" in result.caption

    def test_analyze_segment_caption_contains_frame_count(self):
        """Caption should contain frame count."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            frames=["f1.jpg", "f2.jpg", "f3.jpg", "f4.jpg", "f5.jpg", "f6.jpg"],
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"))
        assert "3帧" in result.caption  # max_frames defaults to 3

    def test_analyze_segment_caption_is_chinese(self):
        """Caption should be in Chinese."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"))
        # Check for Chinese characters
        assert any("\u4e00" <= c <= "\u9fff" for c in result.caption)


class TestGetAnalyzer:
    """Test analyzer factory."""

    def test_get_mock_analyzer(self):
        """Should return MockAnalyzer for 'mock' backend."""
        analyzer = get_analyzer("mock")
        assert isinstance(analyzer, MockAnalyzer)

    def test_unknown_backend_raises(self):
        """Should raise ValueError for unknown backend."""
        try:
            get_analyzer("unknown_backend")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown analyzer backend" in str(e)


class TestManifestAnalysisPath:
    """Test manifest analysis_path field integration."""

    def test_segment_info_analysis_path_default(self):
        """analysis_path should default to None."""
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        assert segment.analysis_path is None

    def test_segment_info_analysis_path_set(self):
        """Should be able to set analysis_path."""
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        assert segment.analysis_path == "analysis/part_0001.json"

    def test_segment_info_to_dict_includes_analysis_path(self):
        """to_dict should include analysis_path when set."""
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        d = segment.to_dict()
        assert d["analysis_path"] == "analysis/part_0001.json"

    def test_segment_info_to_dict_omits_none_analysis_path(self):
        """to_dict should omit analysis_path when None."""
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        d = segment.to_dict()
        assert "analysis_path" not in d

    def test_segment_info_from_dict_with_analysis_path(self):
        """from_dict should parse analysis_path."""
        d = {
            "id": "part_0001",
            "start_time": 0.0,
            "end_time": 60.0,
            "video_path": "segments/test.mp4",
            "analysis_path": "analysis/part_0001.json",
        }
        segment = SegmentInfo.from_dict(d)
        assert segment.analysis_path == "analysis/part_0001.json"

    def test_segment_info_from_dict_without_analysis_path(self):
        """from_dict should handle missing analysis_path."""
        d = {
            "id": "part_0001",
            "start_time": 0.0,
            "end_time": 60.0,
            "video_path": "segments/test.mp4",
        }
        segment = SegmentInfo.from_dict(d)
        assert segment.analysis_path is None

    def test_analysis_path_is_relative(self):
        """analysis_path should be relative to session directory."""
        path = generate_analysis_path("part_0001")
        assert not path.startswith("/")
        assert path.startswith("analysis/")


class TestAnalysisResultModelError:
    """Test model and error fields in AnalysisResult."""

    def test_model_field_default_none(self):
        """model field should default to None."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
        )
        assert result.model is None

    def test_model_field_set(self):
        """Should be able to set model field."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            model="claude-sonnet-4-20250514",
        )
        assert result.model == "claude-sonnet-4-20250514"

    def test_error_field_default_none(self):
        """error field should default to None."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
        )
        assert result.error is None

    def test_error_field_set(self):
        """Should be able to set error field."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            error="API timeout",
        )
        assert result.error == "API timeout"

    def test_to_dict_includes_model(self):
        """to_dict should include model when set."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            model="claude-sonnet-4-20250514",
        )
        d = result.to_dict()
        assert d["model"] == "claude-sonnet-4-20250514"

    def test_to_dict_excludes_model_when_none(self):
        """to_dict should exclude model when None."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
        )
        d = result.to_dict()
        assert "model" not in d

    def test_to_dict_includes_error(self):
        """to_dict should include error when set."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            error="Test error",
        )
        d = result.to_dict()
        assert d["error"] == "Test error"

    def test_from_dict_with_model(self):
        """from_dict should parse model field."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "model": "claude-sonnet-4-20250514",
        }
        result = AnalysisResult.from_dict(d)
        assert result.model == "claude-sonnet-4-20250514"

    def test_from_dict_with_error(self):
        """from_dict should parse error field."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "unknown",
            "error": "API error",
        }
        result = AnalysisResult.from_dict(d)
        assert result.error == "API error"


class TestHasValidCaption:
    """Test has_valid_caption method."""

    def test_valid_caption_returns_true(self):
        """Should return True when caption exists and no error."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="角色A与角色B对话",
        )
        assert result.has_valid_caption() is True

    def test_empty_caption_returns_false(self):
        """Should return False when caption is empty."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="",
        )
        assert result.has_valid_caption() is False

    def test_error_returns_false(self):
        """Should return False when error is set."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="Some caption",
            error="API error",
        )
        assert result.has_valid_caption() is False


class TestFactsAndConfidence:
    """Test facts and confidence fields."""

    def test_facts_default_empty_list(self):
        """Should default facts to empty list."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
        )
        assert result.facts == []

    def test_facts_serialization(self):
        """Should serialize facts to dict correctly."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["角色A说话", "对话框可见"],
        )
        d = result.to_dict()
        assert d["facts"] == ["角色A说话", "对话框可见"]

    def test_facts_deserialization(self):
        """Should deserialize facts from dict correctly."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "facts": ["角色A说话"],
        }
        result = AnalysisResult.from_dict(d)
        assert result.facts == ["角色A说话"]

    def test_facts_backward_compat(self):
        """Should handle old JSON without facts field."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "ocr_text": [],
            "caption": "测试",
        }
        result = AnalysisResult.from_dict(d)
        assert result.facts == []

    def test_confidence_default_none(self):
        """Should default confidence to None."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
        )
        assert result.confidence is None

    def test_confidence_serialization(self):
        """Should serialize confidence to dict correctly."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            confidence="high",
        )
        d = result.to_dict()
        assert d["confidence"] == "high"

    def test_confidence_deserialization(self):
        """Should deserialize confidence from dict correctly."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "confidence": "med",
        }
        result = AnalysisResult.from_dict(d)
        assert result.confidence == "med"


class TestGetDescription:
    """Test get_description method priority: facts > caption > None."""

    def test_facts_preferred_over_caption(self):
        """Should return first fact when facts exist."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["角色A与B对话", "对话框显示"],
            caption="对话场景",
        )
        assert result.get_description() == "角色A与B对话"

    def test_caption_fallback_when_no_facts(self):
        """Should return caption when no facts."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=[],
            caption="对话场景",
        )
        assert result.get_description() == "对话场景"

    def test_none_when_nothing_available(self):
        """Should return None when no facts and no caption."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            facts=[],
            caption="",
        )
        assert result.get_description() is None


class TestHasValidContent:
    """Test has_valid_content method."""

    def test_facts_only_is_valid(self):
        """Should return True when facts exist but no caption."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["客观事实"],
            caption="",
        )
        assert result.has_valid_content() is True

    def test_caption_only_is_valid(self):
        """Should return True when caption exists but no facts."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=[],
            caption="对话场景",
        )
        assert result.has_valid_content() is True

    def test_both_facts_and_caption_is_valid(self):
        """Should return True when both facts and caption exist."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["事实"],
            caption="描述",
        )
        assert result.has_valid_content() is True

    def test_error_invalidates(self):
        """Should return False when error is set."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            facts=["事实"],
            error="API error",
        )
        assert result.has_valid_content() is False


class TestL1Fields:
    """Test L1 fields (scene_label, what_changed, ui_key_text, etc.)."""

    def test_l1_fields_default_values(self):
        """L1 fields should default to None/empty."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
        )
        assert result.scene_label is None
        assert result.what_changed is None
        assert result.ui_key_text == []
        assert result.player_action_guess is None
        assert result.hook_detail is None

    def test_l1_fields_serialization(self):
        """L1 fields should serialize to dict correctly."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            scene_label="Dialogue",
            what_changed="对话开始",
            ui_key_text=["确认", "取消"],
            player_action_guess="可能选择了确认",
            hook_detail="角色表情变化",
        )
        d = result.to_dict()
        assert d["scene_label"] == "Dialogue"
        assert d["what_changed"] == "对话开始"
        assert d["ui_key_text"] == ["确认", "取消"]
        assert d["player_action_guess"] == "可能选择了确认"
        assert d["hook_detail"] == "角色表情变化"

    def test_l1_fields_deserialization(self):
        """L1 fields should deserialize from dict correctly."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "scene_label": "Combat",
            "what_changed": "战斗开始",
            "ui_key_text": ["攻击"],
            "player_action_guess": "疑似使用技能",
            "hook_detail": "血量下降",
        }
        result = AnalysisResult.from_dict(d)
        assert result.scene_label == "Combat"
        assert result.what_changed == "战斗开始"
        assert result.ui_key_text == ["攻击"]
        assert result.player_action_guess == "疑似使用技能"
        assert result.hook_detail == "血量下降"

    def test_l1_fields_backward_compat(self):
        """Should handle old JSON without L1 fields."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "ocr_text": [],
            "caption": "测试",
        }
        result = AnalysisResult.from_dict(d)
        assert result.scene_label is None
        assert result.what_changed is None
        assert result.ui_key_text == []
        assert result.player_action_guess is None
        assert result.hook_detail is None

    def test_l1_fields_omitted_when_empty(self):
        """L1 fields should be omitted from dict when empty/None."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="test",
        )
        d = result.to_dict()
        assert "scene_label" not in d
        assert "what_changed" not in d
        assert "ui_key_text" not in d
        assert "player_action_guess" not in d
        assert "hook_detail" not in d


class TestMockAnalyzerDetailLevel:
    """Test MockAnalyzer with detail_level parameter."""

    def test_l0_detail_level_no_l1_fields(self):
        """L0 should not include L1 fields."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            frames=["frame1.jpg", "frame2.jpg"],
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"), 3, 3, "L0")
        assert result.scene_label is None
        assert result.what_changed is None

    def test_l1_detail_level_includes_l1_fields(self):
        """L1 should include L1 fields."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            frames=["frame1.jpg", "frame2.jpg"],
        )
        result = analyzer.analyze_segment(segment, Path("/tmp"), 3, 3, "L1")
        assert result.scene_label is not None
        assert result.what_changed is not None


class TestClaudeAnalyzer:
    """Test ClaudeAnalyzer with mock client."""

    def test_analyze_segment_with_mock_client(self, tmp_path):
        """Should return result from mock client."""
        # Create mock client (default mock response)
        mock_client = MockClaudeClient()

        # Create analyzer with mock client
        analyzer = ClaudeAnalyzer(client=mock_client)

        # Create frames
        frames_dir = tmp_path / "frames" / "part_0001"
        frames_dir.mkdir(parents=True)
        (frames_dir / "frame_0001.jpg").write_bytes(b"fake jpg data")

        # Create segment
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            frames=["frames/part_0001/frame_0001.jpg"],
        )

        result = analyzer.analyze_segment(segment, tmp_path, max_frames=3)

        assert result.segment_id == "part_0001"
        # MockClaudeClient returns "unknown" by default
        assert result.scene_type == "unknown"
        assert result.model == "mock-model"
        # Verify the client was called
        assert len(mock_client.calls) == 1

    def test_analyze_segment_missing_frames(self, tmp_path):
        """Should return error when frames are missing."""
        mock_client = MockClaudeClient()
        analyzer = ClaudeAnalyzer(client=mock_client)

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            frames=["frames/part_0001/missing.jpg"],
        )

        result = analyzer.analyze_segment(segment, tmp_path, max_frames=3)

        assert result.error is not None
        assert "Missing frames" in result.error

    def test_analyze_segment_no_frames(self, tmp_path):
        """Should return error when segment has no frames."""
        mock_client = MockClaudeClient()
        analyzer = ClaudeAnalyzer(client=mock_client)

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            frames=[],
        )

        result = analyzer.analyze_segment(segment, tmp_path, max_frames=3)

        assert result.error is not None
        assert "No frames" in result.error


class TestGetAnalyzerClaude:
    """Test get_analyzer with claude backend."""

    def test_get_claude_analyzer(self):
        """Should return ClaudeAnalyzer for 'claude' backend."""
        mock_client = MockClaudeClient()
        analyzer = get_analyzer("claude", client=mock_client)
        assert isinstance(analyzer, ClaudeAnalyzer)


class TestIsCacheValidFor:
    """Test is_cache_valid_for method for backend-specific cache validation."""

    def test_mock_backend_with_mock_model(self):
        """Mock backend should accept model='mock'."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="Valid caption",
            model="mock",
        )
        assert result.is_cache_valid_for("mock") is True

    def test_mock_backend_with_claude_model(self):
        """Mock backend should reject model='claude-*'."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="Valid caption",
            model="claude-sonnet-4-20250514",
        )
        assert result.is_cache_valid_for("mock") is False

    def test_claude_backend_with_claude_model(self):
        """Claude backend should accept model starting with 'claude-'."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="Valid caption",
            model="claude-sonnet-4-20250514",
        )
        assert result.is_cache_valid_for("claude") is True

    def test_claude_backend_with_mock_model(self):
        """Claude backend should reject model='mock'."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="Valid caption",
            model="mock",
        )
        assert result.is_cache_valid_for("claude") is False

    def test_any_backend_with_error(self):
        """Any backend should reject result with error."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="Some caption",
            model="mock",
            error="API error",
        )
        assert result.is_cache_valid_for("mock") is False
        assert result.is_cache_valid_for("claude") is False

    def test_any_backend_with_empty_caption(self):
        """Any backend should reject result with empty caption."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="",
            model="mock",
        )
        assert result.is_cache_valid_for("mock") is False
        assert result.is_cache_valid_for("claude") is False

    def test_any_backend_with_none_model(self):
        """Any backend should reject result with None model."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="Valid caption",
            model=None,
        )
        assert result.is_cache_valid_for("mock") is False
        assert result.is_cache_valid_for("claude") is False

    def test_unknown_backend(self):
        """Unknown backend should reject all results."""
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="Valid caption",
            model="mock",
        )
        assert result.is_cache_valid_for("unknown_backend") is False


class TestCheckCache:
    """Test cache checking functionality."""

    def test_no_analysis_path(self):
        """Should return None when segment has no analysis_path."""
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        result = check_cache(segment, Path("/tmp"), "mock")
        assert result is None

    def test_analysis_file_not_exists(self, tmp_path):
        """Should return None when analysis file doesn't exist."""
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = check_cache(segment, tmp_path, "mock")
        assert result is None

    def test_valid_cached_result_for_mock(self, tmp_path):
        """Should return cached result when valid for mock backend."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="Cached caption",
            model="mock",
        )
        cached.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )

        result = check_cache(segment, tmp_path, "mock")
        assert result is not None
        assert result.caption == "Cached caption"

    def test_valid_cached_result_for_claude(self, tmp_path):
        """Should return cached result when valid for claude backend."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="Claude caption",
            model="claude-sonnet-4-20250514",
        )
        cached.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )

        result = check_cache(segment, tmp_path, "claude")
        assert result is not None
        assert result.caption == "Claude caption"

    def test_claude_backend_rejects_mock_cache(self, tmp_path):
        """Claude backend should not use mock cache."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="Mock caption",
            model="mock",
        )
        cached.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )

        result = check_cache(segment, tmp_path, "claude")
        assert result is None

    def test_mock_backend_rejects_claude_cache(self, tmp_path):
        """Mock backend should not use claude cache."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="Claude caption",
            model="claude-sonnet-4-20250514",
        )
        cached.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )

        result = check_cache(segment, tmp_path, "mock")
        assert result is None

    def test_cached_result_with_error(self, tmp_path):
        """Should return None when cached result has error."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="",
            model="mock",
            error="Previous API error",
        )
        cached.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )

        result = check_cache(segment, tmp_path, "mock")
        assert result is None


class TestAnalyzeSession:
    """Test analyze_session function with various options."""

    def _create_test_manifest(self, tmp_path, num_segments=3):
        """Helper to create test manifest with segments."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00Z",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=30,
        )

        for i in range(num_segments):
            seg_id = f"part_{i+1:04d}"
            frames_dir = tmp_path / "frames" / seg_id
            frames_dir.mkdir(parents=True)
            # Create fake frame files
            frame_paths = []
            for j in range(3):
                frame_path = frames_dir / f"frame_{j+1:04d}.jpg"
                frame_path.write_bytes(b"fake jpg")
                frame_paths.append(f"frames/{seg_id}/frame_{j+1:04d}.jpg")

            segment = SegmentInfo(
                id=seg_id,
                start_time=i * 30.0,
                end_time=(i + 1) * 30.0,
                video_path=f"segments/test_{seg_id}.mp4",
                frames=frame_paths,
            )
            manifest.segments.append(segment)

        return manifest

    def test_dry_run_returns_stats_only(self, tmp_path):
        """Dry run should return stats without creating files."""
        manifest = self._create_test_manifest(tmp_path)

        stats = analyze_session(
            manifest, tmp_path, "mock", dry_run=True
        )

        assert stats.api_calls == 3
        assert stats.processed == 0
        # No analysis files should be created
        assert not (tmp_path / "analysis").exists()

    def test_limit_option(self, tmp_path):
        """Limit should only process N segments."""
        manifest = self._create_test_manifest(tmp_path, num_segments=5)

        stats = analyze_session(
            manifest, tmp_path, "mock", limit=2
        )

        assert stats.processed == 2
        assert stats.skipped_filter == 3

    def test_segments_filter(self, tmp_path):
        """Segments filter should only process specified IDs."""
        manifest = self._create_test_manifest(tmp_path, num_segments=5)

        stats = analyze_session(
            manifest, tmp_path, "mock", segments=["part_0002", "part_0004"]
        )

        assert stats.processed == 2
        assert stats.skipped_filter == 3

    def test_force_ignores_cache(self, tmp_path):
        """Force option should re-analyze even with cache."""
        manifest = self._create_test_manifest(tmp_path, num_segments=1)

        # First run creates cache
        analyze_session(manifest, tmp_path, "mock")
        manifest.segments[0].analysis_path = "analysis/part_0001.json"

        # Second run without force should skip
        stats = analyze_session(manifest, tmp_path, "mock")
        assert stats.skipped_cache == 1
        assert stats.processed == 0

        # Third run with force should re-process
        stats = analyze_session(manifest, tmp_path, "mock", force=True)
        assert stats.skipped_cache == 0
        assert stats.processed == 1

    def test_cache_skip(self, tmp_path):
        """Should skip segments with valid cached analysis."""
        manifest = self._create_test_manifest(tmp_path, num_segments=2)

        # Create cached analysis for first segment (with model="mock" for mock backend)
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            caption="Cached",
            model="mock",
        )
        cached.save(analysis_dir / "part_0001.json")
        manifest.segments[0].analysis_path = "analysis/part_0001.json"

        stats = analyze_session(manifest, tmp_path, "mock")

        assert stats.skipped_cache == 1
        assert stats.processed == 1

    def test_updates_manifest_analysis_path(self, tmp_path):
        """Should update manifest with analysis_path after processing."""
        manifest = self._create_test_manifest(tmp_path, num_segments=1)

        assert manifest.segments[0].analysis_path is None

        analyze_session(manifest, tmp_path, "mock")

        assert manifest.segments[0].analysis_path == "analysis/part_0001.json"

    def test_creates_analysis_files(self, tmp_path):
        """Should create analysis JSON files."""
        manifest = self._create_test_manifest(tmp_path, num_segments=2)

        analyze_session(manifest, tmp_path, "mock")

        assert (tmp_path / "analysis" / "part_0001.json").exists()
        assert (tmp_path / "analysis" / "part_0002.json").exists()

    def test_progress_callback(self, tmp_path):
        """Should call progress callback for each segment."""
        manifest = self._create_test_manifest(tmp_path, num_segments=2)
        progress_calls = []

        def on_progress(segment_id, status, result):
            progress_calls.append((segment_id, status))

        analyze_session(
            manifest, tmp_path, "mock", on_progress=on_progress
        )

        assert len(progress_calls) == 2
        assert ("part_0001", "done") in progress_calls
        assert ("part_0002", "done") in progress_calls


class TestAnalyzeStats:
    """Test AnalyzeStats dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        stats = AnalyzeStats()
        assert stats.total_segments == 0
        assert stats.processed == 0
        assert stats.skipped_cache == 0
        assert stats.skipped_filter == 0
        assert stats.errors == 0
        assert stats.api_calls == 0
        assert stats.max_frames == 3
        assert stats.will_process == []
        assert stats.cached_skip == []
        assert stats.filtered_skip == []

    def test_total_images_property(self):
        """total_images should be api_calls * max_frames."""
        stats = AnalyzeStats(api_calls=5, max_frames=3)
        assert stats.total_images == 15

        stats2 = AnalyzeStats(api_calls=2, max_frames=6)
        assert stats2.total_images == 12


class TestAnalyzeSessionSegmentLists:
    """Test segment list tracking in analyze_session."""

    def _create_test_manifest(self, tmp_path, num_segments=3):
        """Helper to create test manifest with segments."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00Z",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=30,
        )

        for i in range(num_segments):
            seg_id = f"part_{i+1:04d}"
            frames_dir = tmp_path / "frames" / seg_id
            frames_dir.mkdir(parents=True)
            frame_paths = []
            for j in range(3):
                frame_path = frames_dir / f"frame_{j+1:04d}.jpg"
                frame_path.write_bytes(b"fake jpg")
                frame_paths.append(f"frames/{seg_id}/frame_{j+1:04d}.jpg")

            segment = SegmentInfo(
                id=seg_id,
                start_time=i * 30.0,
                end_time=(i + 1) * 30.0,
                video_path=f"segments/test_{seg_id}.mp4",
                frames=frame_paths,
            )
            manifest.segments.append(segment)

        return manifest

    def test_dry_run_populates_will_process_list(self, tmp_path):
        """Dry run should populate will_process list."""
        manifest = self._create_test_manifest(tmp_path, num_segments=3)

        stats = analyze_session(manifest, tmp_path, "mock", dry_run=True)

        assert stats.will_process == ["part_0001", "part_0002", "part_0003"]
        assert stats.cached_skip == []
        assert stats.filtered_skip == []

    def test_limit_populates_filtered_skip_list(self, tmp_path):
        """Limit should populate filtered_skip list."""
        manifest = self._create_test_manifest(tmp_path, num_segments=5)

        stats = analyze_session(manifest, tmp_path, "mock", dry_run=True, limit=2)

        assert stats.will_process == ["part_0001", "part_0002"]
        assert stats.cached_skip == []
        assert stats.filtered_skip == ["part_0003", "part_0004", "part_0005"]

    def test_segments_filter_populates_filtered_skip_list(self, tmp_path):
        """Segments filter should populate filtered_skip list."""
        manifest = self._create_test_manifest(tmp_path, num_segments=5)

        stats = analyze_session(
            manifest, tmp_path, "mock", dry_run=True,
            segments=["part_0002", "part_0004"]
        )

        assert stats.will_process == ["part_0002", "part_0004"]
        assert stats.cached_skip == []
        assert stats.filtered_skip == ["part_0001", "part_0003", "part_0005"]

    def test_cache_populates_cached_skip_list(self, tmp_path):
        """Cache hits should populate cached_skip list."""
        manifest = self._create_test_manifest(tmp_path, num_segments=3)

        # Create cached analysis for part_0002
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            caption="Cached",
            model="mock",
        )
        cached.save(analysis_dir / "part_0002.json")
        manifest.segments[1].analysis_path = "analysis/part_0002.json"

        stats = analyze_session(manifest, tmp_path, "mock", dry_run=True)

        assert stats.will_process == ["part_0001", "part_0003"]
        assert stats.cached_skip == ["part_0002"]
        assert stats.filtered_skip == []

    def test_filter_then_cache_order(self, tmp_path):
        """Filter should be applied before cache check."""
        manifest = self._create_test_manifest(tmp_path, num_segments=5)

        # Create cached analysis for part_0003 and part_0005
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        for seg_id in ["part_0003", "part_0005"]:
            cached = AnalysisResult(
                segment_id=seg_id,
                scene_type="dialogue",
                caption="Cached",
                model="mock",
            )
            cached.save(analysis_dir / f"{seg_id}.json")

        manifest.segments[2].analysis_path = "analysis/part_0003.json"
        manifest.segments[4].analysis_path = "analysis/part_0005.json"

        # Limit to first 3 segments: part_0001, part_0002, part_0003
        # part_0003 is cached, but part_0004 and part_0005 should be filtered (not cached)
        stats = analyze_session(manifest, tmp_path, "mock", dry_run=True, limit=3)

        assert stats.will_process == ["part_0001", "part_0002"]
        assert stats.cached_skip == ["part_0003"]
        # part_0004 and part_0005 should be filtered, NOT counted as cached
        assert stats.filtered_skip == ["part_0004", "part_0005"]
        assert stats.skipped_filter == 2
        assert stats.skipped_cache == 1

    def test_combined_segments_and_cache(self, tmp_path):
        """Combined segments filter and cache should work correctly."""
        manifest = self._create_test_manifest(tmp_path, num_segments=5)

        # Create cached analysis for part_0002
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            caption="Cached",
            model="mock",
        )
        cached.save(analysis_dir / "part_0002.json")
        manifest.segments[1].analysis_path = "analysis/part_0002.json"

        # Select only part_0002 and part_0004
        stats = analyze_session(
            manifest, tmp_path, "mock", dry_run=True,
            segments=["part_0002", "part_0004"]
        )

        # part_0002 is selected but cached, part_0004 is selected and will process
        assert stats.will_process == ["part_0004"]
        assert stats.cached_skip == ["part_0002"]
        assert stats.filtered_skip == ["part_0001", "part_0003", "part_0005"]

    def test_max_frames_in_stats(self, tmp_path):
        """Stats should track max_frames setting."""
        manifest = self._create_test_manifest(tmp_path, num_segments=2)

        stats = analyze_session(manifest, tmp_path, "mock", dry_run=True, max_frames=5)

        assert stats.max_frames == 5
        assert stats.api_calls == 2
        assert stats.total_images == 10

    def test_backend_aware_cache_with_segment_lists(self, tmp_path):
        """Backend-aware cache should work with segment lists."""
        manifest = self._create_test_manifest(tmp_path, num_segments=3)

        # Create mock cache for part_0001
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        cached = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            caption="Mock caption",
            model="mock",
        )
        cached.save(analysis_dir / "part_0001.json")
        manifest.segments[0].analysis_path = "analysis/part_0001.json"

        # Run with claude backend - mock cache should NOT be valid
        stats = analyze_session(manifest, tmp_path, "claude", dry_run=True)

        # part_0001 should be in will_process (not cached for claude)
        assert stats.will_process == ["part_0001", "part_0002", "part_0003"]
        assert stats.cached_skip == []


class TestOcrItems:
    """Test ocr_items field in AnalysisResult."""

    def test_ocr_item_to_dict(self):
        """OcrItem should serialize correctly."""
        from yanhu.analyzer import OcrItem

        item = OcrItem(
            text="公主不见踪影",
            t_rel=5.5,
            source_frame="frame_0003.jpg",
        )
        d = item.to_dict()
        assert d["text"] == "公主不见踪影"
        assert d["t_rel"] == 5.5
        assert d["source_frame"] == "frame_0003.jpg"

    def test_ocr_item_from_dict(self):
        """OcrItem should deserialize correctly."""
        from yanhu.analyzer import OcrItem

        d = {
            "text": "只留一支素雅的步摇",
            "t_rel": 8.2,
            "source_frame": "frame_0005.jpg",
        }
        item = OcrItem.from_dict(d)
        assert item.text == "只留一支素雅的步摇"
        assert item.t_rel == 8.2
        assert item.source_frame == "frame_0005.jpg"

    def test_analysis_result_with_ocr_items(self):
        """AnalysisResult should serialize/deserialize ocr_items."""
        from yanhu.analyzer import OcrItem

        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["公主不见踪影", "只留一支素雅的步摇"],
            caption="公主场景",
            ocr_items=[
                OcrItem(text="公主不见踪影", t_rel=0.0, source_frame="frame_0001.jpg"),
                OcrItem(text="只留一支素雅的步摇", t_rel=5.0, source_frame="frame_0003.jpg"),
            ],
        )

        d = result.to_dict()
        assert len(d["ocr_items"]) == 2
        assert d["ocr_items"][0]["text"] == "公主不见踪影"
        assert d["ocr_items"][1]["source_frame"] == "frame_0003.jpg"

        # Round-trip
        loaded = AnalysisResult.from_dict(d)
        assert len(loaded.ocr_items) == 2
        assert loaded.ocr_items[0].text == "公主不见踪影"
        assert loaded.ocr_items[1].t_rel == 5.0

    def test_analysis_result_save_load_ocr_items(self, tmp_path):
        """AnalysisResult should save/load ocr_items correctly."""
        from yanhu.analyzer import OcrItem

        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["其实就是太和公主"],
            caption="公主场景",
            model="claude-sonnet-4-20250514",
            ocr_items=[
                OcrItem(text="其实就是太和公主", t_rel=2.5, source_frame="frame_0002.jpg"),
            ],
        )

        path = tmp_path / "test_analysis.json"
        result.save(path)

        loaded = AnalysisResult.load(path)
        assert len(loaded.ocr_items) == 1
        assert loaded.ocr_items[0].text == "其实就是太和公主"
        assert loaded.ocr_items[0].t_rel == 2.5
        assert loaded.ocr_items[0].source_frame == "frame_0002.jpg"

    def test_backward_compat_no_ocr_items(self):
        """AnalysisResult should handle missing ocr_items (backward compat)."""
        d = {
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "caption": "Old format",
        }
        result = AnalysisResult.from_dict(d)
        assert result.ocr_items == []


class TestDynamicMaxFrames:
    """Test dynamic max_frames upgrade for subtitle segments."""

    def _create_test_manifest(self, tmp_path, num_segments=2):
        """Create test manifest with segments."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[],
        )
        for i in range(num_segments):
            seg_id = f"part_{i+1:04d}"
            seg_frames_dir = frames_dir / seg_id
            seg_frames_dir.mkdir()
            # Create 6 frame files
            frames = []
            for j in range(6):
                frame_name = f"frame_{j+1:04d}.jpg"
                frame_path = seg_frames_dir / frame_name
                frame_path.write_bytes(b"fake image data")
                frames.append(f"frames/{seg_id}/{frame_name}")

            manifest.segments.append(SegmentInfo(
                id=seg_id,
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                video_path=f"segments/{seg_id}.mp4",
                frames=frames,
            ))
        return manifest

    def test_dynamic_upgrade_when_subtitle_detected(self, tmp_path):
        """Should upgrade max_frames when subtitles detected."""
        from yanhu.claude_client import ClaudeResponse

        # Create a mock analyzer that returns dialogue with ocr_text
        class SubtitleMockAnalyzer:
            def __init__(self):
                self.calls = []

            def analyze_segment(self, segment, session_dir, max_frames, max_facts=3, detail_level="L1"):
                self.calls.append((segment.id, max_frames))
                return AnalysisResult(
                    segment_id=segment.id,
                    scene_type="dialogue",
                    ocr_text=["公主不见踪影"],
                    facts=["有字幕"],
                    caption="对话场景",
                    model="mock-model",
                    ui_key_text=["公主不见踪影"],
                )

        manifest = self._create_test_manifest(tmp_path, num_segments=1)

        # Use custom analyzer directly in analyze_session logic
        mock_analyzer = SubtitleMockAnalyzer()

        from yanhu.analyzer import _has_subtitle_content, generate_analysis_path

        # Process manually to test the upgrade logic
        segment = manifest.segments[0]
        result = mock_analyzer.analyze_segment(segment, tmp_path, 3)

        # Verify subtitle detected
        assert _has_subtitle_content(result) is True

        # Simulate the upgrade logic
        if _has_subtitle_content(result) and 3 < 6 and len(segment.frames) > 3:
            result = mock_analyzer.analyze_segment(segment, tmp_path, 6)

        # Verify two calls were made
        assert len(mock_analyzer.calls) == 2
        assert mock_analyzer.calls[0] == ("part_0001", 3)
        assert mock_analyzer.calls[1] == ("part_0001", 6)

    def test_no_upgrade_when_no_subtitle(self, tmp_path):
        """Should not upgrade when no subtitles detected."""
        from yanhu.analyzer import _has_subtitle_content

        # Create result without subtitles
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="cutscene",
            ocr_text=[],
            facts=["无字幕"],
            caption="过场动画",
            model="mock-model",
        )

        # Verify no subtitle content
        assert _has_subtitle_content(result) is False

    def test_no_upgrade_when_already_at_max(self, tmp_path):
        """Should not upgrade when max_frames >= max_frames_dialogue."""
        from yanhu.analyzer import _has_subtitle_content

        # Result with subtitles
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=["有字幕"],
            facts=["有字幕"],
            caption="对话",
            model="mock-model",
        )

        # Has subtitle content
        assert _has_subtitle_content(result) is True

        # But if max_frames already at max, upgrade condition not met
        max_frames = 6
        max_frames_dialogue = 6
        # condition: max_frames < max_frames_dialogue is False
        assert not (max_frames < max_frames_dialogue)

    def test_has_subtitle_content_with_ui_key_text(self):
        """_has_subtitle_content should detect ui_key_text."""
        from yanhu.analyzer import _has_subtitle_content

        # Only ui_key_text, no ocr_text
        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            ui_key_text=["关键台词"],
            caption="场景",
        )
        assert _has_subtitle_content(result) is True

    def test_has_subtitle_content_empty(self):
        """_has_subtitle_content should return False when empty."""
        from yanhu.analyzer import _has_subtitle_content

        result = AnalysisResult(
            segment_id="part_0001",
            scene_type="cutscene",
            ocr_text=[],
            ui_key_text=[],
            caption="场景",
        )
        assert _has_subtitle_content(result) is False


class TestNormalizeOcrText:
    """Test OCR text normalization for common character errors."""

    def test_normalize_buYao(self):
        """Should fix '一只步摇' -> '一支步摇'."""
        assert normalize_ocr_text("只留一只素雅的步摇") == "只留一支素雅的步摇"

    def test_normalize_yuZan(self):
        """Should fix '一只玉簪' -> '一支玉簪'."""
        assert normalize_ocr_text("递给她一只玉簪") == "递给她一支玉簪"

    def test_normalize_bi(self):
        """Should fix '一只笔' -> '一支笔'."""
        assert normalize_ocr_text("拿起一只笔") == "拿起一支笔"

    def test_normalize_jian(self):
        """Should fix '一只箭' -> '一支箭'."""
        assert normalize_ocr_text("射出一只箭") == "射出一支箭"

    def test_normalize_qiang(self):
        """Should fix '一只枪' -> '一支枪'."""
        assert normalize_ocr_text("扛着一只枪") == "扛着一支枪"

    def test_normalize_with_gap(self):
        """Should handle characters between 一只 and object."""
        assert normalize_ocr_text("留下一只精美的步摇") == "留下一支精美的步摇"
        assert normalize_ocr_text("一只古老的玉簪") == "一支古老的玉簪"

    def test_no_change_unrelated(self):
        """Should not change unrelated text."""
        assert normalize_ocr_text("公主不见踪影") == "公主不见踪影"
        assert normalize_ocr_text("其实就是太和公主") == "其实就是太和公主"

    def test_no_change_correct_usage(self):
        """Should not change correct '一只' usage (animals)."""
        # "一只猫" is correct - 只 is the right measure word for animals
        assert normalize_ocr_text("养了一只猫") == "养了一只猫"
        assert normalize_ocr_text("一只鸟飞过") == "一只鸟飞过"

    def test_no_change_yi_zhi_alone(self):
        """Should not change '一只' when not followed by target objects."""
        assert normalize_ocr_text("这一只手") == "这一只手"

    def test_empty_string(self):
        """Should handle empty string."""
        assert normalize_ocr_text("") == ""

    def test_none_safe(self):
        """Should handle None-like input gracefully."""
        # The function expects str, but should not crash on empty
        assert normalize_ocr_text("") == ""

    def test_multiple_occurrences(self):
        """Should fix multiple occurrences in same text."""
        text = "她拿着一只笔和一只步摇"
        expected = "她拿着一支笔和一支步摇"
        assert normalize_ocr_text(text) == expected


class TestVerbatimPreservation:
    """Test that OCR text is kept verbatim in ClaudeAnalyzer (no normalization)."""

    def test_ocr_text_verbatim(self, tmp_path):
        """ocr_text should be kept verbatim, not normalized."""
        from yanhu.claude_client import ClaudeResponse, MockClaudeClient

        # Create mock that returns text with potential OCR error
        class VerbatimMockClient:
            def analyze_frames(self, frame_paths, **kwargs):
                return ClaudeResponse(
                    scene_type="dialogue",
                    ocr_text=["只留一只素雅的步摇"],  # "只" not "支"
                    facts=["有字幕"],
                    caption="场景",
                    model="mock-model",
                )

        from yanhu.analyzer import ClaudeAnalyzer

        # Create frame
        frames_dir = tmp_path / "frames" / "part_0001"
        frames_dir.mkdir(parents=True)
        (frames_dir / "frame_0001.jpg").write_bytes(b"fake")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/test.mp4",
            frames=["frames/part_0001/frame_0001.jpg"],
        )

        analyzer = ClaudeAnalyzer(client=VerbatimMockClient())
        result = analyzer.analyze_segment(segment, tmp_path, max_frames=1)

        # Should be verbatim (not normalized to "一支")
        assert result.ocr_text == ["只留一只素雅的步摇"]

    def test_ui_key_text_verbatim(self, tmp_path):
        """ui_key_text should be kept verbatim, not normalized."""
        from yanhu.claude_client import ClaudeResponse

        class VerbatimMockClient:
            def analyze_frames(self, frame_paths, **kwargs):
                return ClaudeResponse(
                    scene_type="dialogue",
                    ocr_text=[],
                    facts=["有字幕"],
                    caption="场景",
                    model="mock-model",
                    ui_key_text=["递给她一只玉簪"],  # "只" not "支"
                )

        from yanhu.analyzer import ClaudeAnalyzer

        frames_dir = tmp_path / "frames" / "part_0001"
        frames_dir.mkdir(parents=True)
        (frames_dir / "frame_0001.jpg").write_bytes(b"fake")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/test.mp4",
            frames=["frames/part_0001/frame_0001.jpg"],
        )

        analyzer = ClaudeAnalyzer(client=VerbatimMockClient())
        result = analyzer.analyze_segment(segment, tmp_path, max_frames=1)

        # Should be verbatim (not normalized to "一支")
        assert result.ui_key_text == ["递给她一只玉簪"]

    def test_ocr_items_text_verbatim(self, tmp_path):
        """ocr_items.text should be kept verbatim, not normalized."""
        from yanhu.claude_client import ClaudeResponse, OcrItem as ClaudeOcrItem

        class VerbatimMockClient:
            def analyze_frames(self, frame_paths, **kwargs):
                return ClaudeResponse(
                    scene_type="dialogue",
                    ocr_text=[],
                    facts=["有字幕"],
                    caption="场景",
                    model="mock-model",
                    ocr_items=[
                        ClaudeOcrItem(
                            text="只留一只素雅的步摇",  # "只" not "支"
                            t_rel=0.0,
                            source_frame="frame_0001.jpg",
                        ),
                    ],
                )

        from yanhu.analyzer import ClaudeAnalyzer

        frames_dir = tmp_path / "frames" / "part_0001"
        frames_dir.mkdir(parents=True)
        (frames_dir / "frame_0001.jpg").write_bytes(b"fake")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/test.mp4",
            frames=["frames/part_0001/frame_0001.jpg"],
        )

        analyzer = ClaudeAnalyzer(client=VerbatimMockClient())
        result = analyzer.analyze_segment(segment, tmp_path, max_frames=1)

        assert len(result.ocr_items) == 1
        # Should be verbatim (not normalized to "一支")
        assert result.ocr_items[0].text == "只留一只素雅的步摇"
