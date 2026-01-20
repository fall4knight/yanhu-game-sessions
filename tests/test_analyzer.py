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
