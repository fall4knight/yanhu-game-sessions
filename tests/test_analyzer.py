"""Tests for vision analysis."""

import json

from yanhu.analyzer import (
    AnalysisResult,
    MockAnalyzer,
    generate_analysis_path,
    get_analyzer,
)
from yanhu.manifest import SegmentInfo


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
        result = analyzer.analyze_segment(segment)
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
        result = analyzer.analyze_segment(segment)
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
        result = analyzer.analyze_segment(segment)
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
        result = analyzer.analyze_segment(segment)
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
        result = analyzer.analyze_segment(segment)
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
        result = analyzer.analyze_segment(segment)
        assert "6帧" in result.caption

    def test_analyze_segment_caption_is_chinese(self):
        """Caption should be in Chinese."""
        analyzer = MockAnalyzer()
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        result = analyzer.analyze_segment(segment)
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
