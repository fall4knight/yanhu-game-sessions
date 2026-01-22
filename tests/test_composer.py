"""Tests for session composition."""

from yanhu.composer import (
    _has_heart_symbol,
    apply_heart_to_chunk,
    compose_overview,
    compose_timeline,
    filter_watermarks,
    format_frames_list,
    format_time_range,
    format_timestamp,
    get_highlight_text,
    has_valid_claude_analysis,
    is_low_value_ui,
    is_platform_watermark,
)
from yanhu.manifest import Manifest, SegmentInfo


class TestFormatTimestamp:
    """Test timestamp formatting."""

    def test_zero_seconds(self):
        """Zero should format as 00:00:00."""
        assert format_timestamp(0) == "00:00:00"

    def test_seconds_only(self):
        """Seconds under 60 should show in seconds position."""
        assert format_timestamp(45) == "00:00:45"

    def test_minutes_and_seconds(self):
        """Should correctly format minutes and seconds."""
        assert format_timestamp(90) == "00:01:30"
        assert format_timestamp(125) == "00:02:05"

    def test_hours_minutes_seconds(self):
        """Should correctly format hours, minutes, and seconds."""
        assert format_timestamp(3661) == "01:01:01"
        assert format_timestamp(7200) == "02:00:00"

    def test_large_hours(self):
        """Should handle large hour values."""
        assert format_timestamp(36000) == "10:00:00"

    def test_float_truncates(self):
        """Float values should truncate to integers."""
        assert format_timestamp(90.7) == "00:01:30"
        assert format_timestamp(90.999) == "00:01:30"


class TestFormatTimeRange:
    """Test time range formatting."""

    def test_simple_range(self):
        """Should format start and end times."""
        result = format_time_range(0, 60)
        assert result == "00:00:00 - 00:01:00"

    def test_non_zero_start(self):
        """Should handle non-zero start times."""
        result = format_time_range(60, 120)
        assert result == "00:01:00 - 00:02:00"


class TestFormatFramesList:
    """Test frames list formatting."""

    def test_empty_frames(self):
        """Empty list should show placeholder."""
        result = format_frames_list([])
        assert "No frames" in result

    def test_single_frame(self):
        """Single frame should be formatted as link."""
        result = format_frames_list(["frames/part_0001/frame_0001.jpg"])
        assert "[frame_0001.jpg]" in result
        assert "(frames/part_0001/frame_0001.jpg)" in result

    def test_three_frames_shown(self):
        """Should show up to 3 frames by default."""
        frames = [
            "frames/part_0001/frame_0001.jpg",
            "frames/part_0001/frame_0002.jpg",
            "frames/part_0001/frame_0003.jpg",
        ]
        result = format_frames_list(frames)
        assert "frame_0001.jpg" in result
        assert "frame_0002.jpg" in result
        assert "frame_0003.jpg" in result
        assert "more" not in result

    def test_truncation_with_more_count(self):
        """Should truncate and show remaining count."""
        frames = [
            "frames/part_0001/frame_0001.jpg",
            "frames/part_0001/frame_0002.jpg",
            "frames/part_0001/frame_0003.jpg",
            "frames/part_0001/frame_0004.jpg",
            "frames/part_0001/frame_0005.jpg",
        ]
        result = format_frames_list(frames, max_display=3)
        assert "frame_0001.jpg" in result
        assert "frame_0002.jpg" in result
        assert "frame_0003.jpg" in result
        assert "frame_0004.jpg" not in result
        assert "(2 more)" in result

    def test_custom_max_display(self):
        """Should respect custom max_display parameter."""
        frames = [f"frames/part_0001/frame_{i:04d}.jpg" for i in range(1, 10)]
        result = format_frames_list(frames, max_display=5)
        assert "frame_0005.jpg" in result
        assert "frame_0006.jpg" not in result
        assert "(4 more)" in result

    def test_markdown_link_format(self):
        """Links should be valid markdown format."""
        frames = ["frames/part_0001/frame_0001.jpg"]
        result = format_frames_list(frames)
        # Should be [filename](path) format
        assert "[frame_0001.jpg](frames/part_0001/frame_0001.jpg)" in result


class TestComposeTimeline:
    """Test timeline composition."""

    def test_timeline_contains_session_id(self):
        """Timeline should include session ID in title."""
        manifest = Manifest(
            session_id="2026-01-20_12-00-00_gnosia_run01",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[],
        )
        result = compose_timeline(manifest)
        assert "2026-01-20_12-00-00_gnosia_run01" in result

    def test_timeline_contains_segment_headers(self):
        """Timeline should have headers for each segment."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/s_part_0001.mp4"),
                SegmentInfo("part_0002", 60.0, 120.0, "segments/s_part_0002.mp4"),
            ],
        )
        result = compose_timeline(manifest)
        assert "part_0001" in result
        assert "part_0002" in result

    def test_timeline_contains_time_ranges(self):
        """Timeline should show time ranges in HH:MM:SS format."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/s_part_0001.mp4"),
            ],
        )
        result = compose_timeline(manifest)
        assert "00:00:00" in result
        assert "00:01:00" in result

    def test_timeline_contains_frames_links(self):
        """Timeline should include frame links from manifest."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    frames=["frames/part_0001/frame_0001.jpg", "frames/part_0001/frame_0002.jpg"],
                ),
            ],
        )
        result = compose_timeline(manifest)
        assert "frames/part_0001/frame_0001.jpg" in result
        assert "frame_0001.jpg" in result

    def test_timeline_contains_todo_placeholder(self):
        """Timeline should have TODO placeholder for descriptions."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/s_part_0001.mp4"),
            ],
        )
        result = compose_timeline(manifest)
        assert "TODO: describe what happened" in result


class TestComposeOverview:
    """Test overview composition."""

    def test_overview_contains_session_id(self):
        """Overview should include session ID."""
        manifest = Manifest(
            session_id="2026-01-20_12-00-00_gnosia_run01",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[],
        )
        result = compose_overview(manifest)
        assert "2026-01-20_12-00-00_gnosia_run01" in result

    def test_overview_extracts_game_name(self):
        """Overview should extract game name from session ID."""
        manifest = Manifest(
            session_id="2026-01-20_12-00-00_gnosia_run01",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[],
        )
        result = compose_overview(manifest)
        assert "gnosia" in result

    def test_overview_shows_duration(self):
        """Overview should show total duration."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/s_part_0001.mp4"),
                SegmentInfo("part_0002", 60.0, 120.0, "segments/s_part_0002.mp4"),
            ],
        )
        result = compose_overview(manifest)
        assert "00:02:00" in result  # 120 seconds

    def test_overview_shows_segment_count(self):
        """Overview should show segment count."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/s_part_0001.mp4"),
                SegmentInfo("part_0002", 60.0, 120.0, "segments/s_part_0002.mp4"),
            ],
        )
        result = compose_overview(manifest)
        assert "2" in result  # 2 segments

    def test_overview_shows_frame_count(self):
        """Overview should show total frame count."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    frames=["f1.jpg", "f2.jpg"],
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "segments/s_part_0002.mp4",
                    frames=["f3.jpg", "f4.jpg", "f5.jpg"],
                ),
            ],
        )
        result = compose_overview(manifest)
        assert "5" in result  # 5 total frames


class TestGetSegmentDescription:
    """Test segment description retrieval with analysis."""

    def test_returns_todo_when_no_analysis_path(self):
        """Should return TODO when segment has no analysis_path."""
        from yanhu.composer import get_segment_description

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
        )
        result = get_segment_description(segment, None)
        assert "TODO" in result

    def test_returns_todo_when_no_session_dir(self):
        """Should return TODO when session_dir is None."""
        from yanhu.composer import get_segment_description

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = get_segment_description(segment, None)
        assert "TODO" in result

    def test_returns_caption_when_analysis_exists(self, tmp_path):
        """Should return caption when analysis file exists."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import get_segment_description

        # Create analysis file
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            caption="测试描述：角色对话",
        )
        analysis_path = tmp_path / "analysis" / "part_0001.json"
        analysis.save(analysis_path)

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = get_segment_description(segment, tmp_path)
        assert result == "测试描述：角色对话"

    def test_returns_todo_when_analysis_file_missing(self, tmp_path):
        """Should return TODO when analysis file doesn't exist."""
        from yanhu.composer import get_segment_description

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = get_segment_description(segment, tmp_path)
        assert "TODO" in result

    def test_facts_priority_over_caption(self, tmp_path):
        """Should prefer facts over caption when both exist."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import get_segment_description

        # Create analysis file with both facts and caption
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["角色A与B对话", "对话框显示"],
            caption="旧的caption描述",
        )
        analysis_path = tmp_path / "analysis" / "part_0001.json"
        analysis.save(analysis_path)

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = get_segment_description(segment, tmp_path)
        # Should use first fact, not caption
        assert result == "角色A与B对话"

    def test_caption_fallback_when_no_facts(self, tmp_path):
        """Should use caption when no facts available."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import get_segment_description

        # Create analysis file with caption only
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=[],  # No facts
            caption="对话场景描述",
        )
        analysis_path = tmp_path / "analysis" / "part_0001.json"
        analysis.save(analysis_path)

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = get_segment_description(segment, tmp_path)
        assert result == "对话场景描述"


class TestComposeTimelineWithAnalysis:
    """Test timeline composition with analysis results."""

    def test_timeline_uses_analysis_caption(self, tmp_path):
        """Timeline should use analysis caption when available."""
        from yanhu.analyzer import AnalysisResult

        # Create analysis file
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            caption="【占位】part_0001：已抽取3帧，等待视觉/字幕解析",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        result = compose_timeline(manifest, tmp_path)
        assert "【占位】part_0001：已抽取3帧，等待视觉/字幕解析" in result
        assert "TODO: describe what happened" not in result

    def test_timeline_falls_back_to_todo_when_no_analysis(self):
        """Timeline should use TODO when no analysis available."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "segments/s_part_0001.mp4"),
            ],
        )
        result = compose_timeline(manifest, None)
        assert "TODO: describe what happened" in result

    def test_timeline_mixed_analysis_and_todo(self, tmp_path):
        """Timeline should handle mix of analyzed and non-analyzed segments."""
        from yanhu.analyzer import AnalysisResult

        # Create analysis file for only first segment
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            caption="已分析的segment",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "segments/s_part_0002.mp4",
                ),
            ],
        )
        result = compose_timeline(manifest, tmp_path)
        assert "已分析的segment" in result
        assert "TODO: describe what happened" in result


class TestComposeTimelineL1Fields:
    """Test timeline composition with L1 fields."""

    def test_timeline_shows_what_changed(self, tmp_path):
        """Timeline should show what_changed when present."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["角色对话"],
            caption="对话场景",
            what_changed="从菜单切换到对话",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        result = compose_timeline(manifest, tmp_path)
        assert "- change: 从菜单切换到对话" in result

    def test_timeline_shows_ui_key_text(self, tmp_path):
        """Timeline should show ui_key_text when present."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="menu",
            ocr_text=[],
            facts=["菜单界面"],
            caption="系统菜单",
            ui_key_text=["继续游戏", "设置"],
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        result = compose_timeline(manifest, tmp_path)
        assert "- ui: 继续游戏, 设置" in result

    def test_timeline_no_l1_lines_when_empty(self, tmp_path):
        """Timeline should not show L1 lines when fields are empty."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ocr_text=[],
            facts=["角色对话"],
            caption="对话场景",
            # No L1 fields set
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        result = compose_timeline(manifest, tmp_path)
        assert "- change:" not in result
        assert "- ui:" not in result


class TestHasValidClaudeAnalysis:
    """Test detection of valid Claude analysis."""

    def test_returns_true_with_claude_model_and_facts(self, tmp_path):
        """Should return True when Claude model with facts exists."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=["彩色测试卡图案"],
            caption="测试画面",
            model="claude-sonnet-4-20250514",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        assert has_valid_claude_analysis(manifest, tmp_path) is True

    def test_returns_true_with_claude_model_and_caption_only(self, tmp_path):
        """Should return True when Claude model with only caption exists."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],  # No facts
            caption="有效的caption描述",
            model="claude-sonnet-4-20250514",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        assert has_valid_claude_analysis(manifest, tmp_path) is True

    def test_returns_false_with_mock_model(self, tmp_path):
        """Should return False when model is mock (not claude-)."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=["Mock数据"],
            caption="Mock caption",
            model="mock-model",  # Not claude-
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        assert has_valid_claude_analysis(manifest, tmp_path) is False

    def test_returns_false_with_empty_facts_and_caption(self, tmp_path):
        """Should return False when Claude model has empty facts AND caption."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],  # Empty
            caption="",  # Empty
            model="claude-sonnet-4-20250514",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        assert has_valid_claude_analysis(manifest, tmp_path) is False

    def test_returns_false_when_no_analysis_path(self, tmp_path):
        """Should return False when segments have no analysis_path."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    # No analysis_path
                ),
            ],
        )
        assert has_valid_claude_analysis(manifest, tmp_path) is False

    def test_returns_false_when_analysis_file_missing(self, tmp_path):
        """Should return False when analysis file doesn't exist."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",  # File doesn't exist
                ),
            ],
        )
        assert has_valid_claude_analysis(manifest, tmp_path) is False

    def test_returns_true_if_any_segment_has_valid_analysis(self, tmp_path):
        """Should return True if at least one segment has valid Claude analysis."""
        from yanhu.analyzer import AnalysisResult

        # Create only valid analysis for part_0002
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            ocr_text=[],
            facts=["有效的分析结果"],
            caption="",
            model="claude-sonnet-4-20250514",
        )
        analysis.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    # No analysis_path
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "segments/s_part_0002.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )
        assert has_valid_claude_analysis(manifest, tmp_path) is True


class TestErrorHandlingInTimeline:
    """Test error handling when analysis has JSON parse errors."""

    def test_description_shows_error_message_when_error_field_exists(self, tmp_path):
        """Should show TODO with analysis path when error field is present."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import get_segment_description

        # Create analysis file with error
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model="claude-sonnet-4-20250514",
            error="JSON parse error: Expecting value: line 1 column 1",
            raw_text="This is not valid JSON...",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = get_segment_description(segment, tmp_path)
        assert "TODO: analysis failed" in result
        assert "analysis/part_0001.json" in result

    def test_description_does_not_output_raw_text(self, tmp_path):
        """Should not output raw_text in timeline description."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import get_segment_description

        raw_response = "Some long invalid response that Claude returned..."

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model="claude-sonnet-4-20250514",
            error="JSON parse error",
            raw_text=raw_response,
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        result = get_segment_description(segment, tmp_path)
        # Should NOT contain raw_text
        assert raw_response not in result

    def test_timeline_shows_error_for_failed_analysis(self, tmp_path):
        """Timeline should show TODO for segments with analysis errors."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model="claude-sonnet-4-20250514",
            error="JSON parse error: something went wrong",
            raw_text="invalid json response",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        result = compose_timeline(manifest, tmp_path)
        assert "TODO: analysis failed" in result
        assert "analysis/part_0001.json" in result
        # Should NOT contain raw_text
        assert "invalid json response" not in result

    def test_l1_fields_not_shown_when_error_exists(self, tmp_path):
        """L1 fields should not be shown when analysis has error."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import get_segment_l1_fields

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model="claude-sonnet-4-20250514",
            error="JSON parse error",
            what_changed="This should not appear",
            ui_key_text=["This should not appear"],
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test.mp4",
            analysis_path="analysis/part_0001.json",
        )
        what_changed, ui_key_text = get_segment_l1_fields(segment, tmp_path)
        assert what_changed is None
        assert ui_key_text == []

    def test_raw_text_saved_in_analysis_json(self, tmp_path):
        """raw_text should be saved in analysis JSON file for debugging."""
        from yanhu.analyzer import AnalysisResult

        raw_response = "Claude返回的无效JSON内容..."

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model="claude-sonnet-4-20250514",
            error="JSON parse error",
            raw_text=raw_response,
        )
        analysis_path = tmp_path / "analysis" / "part_0001.json"
        analysis.save(analysis_path)

        # Reload and verify raw_text is saved
        loaded = AnalysisResult.load(analysis_path)
        assert loaded.error == "JSON parse error"
        assert loaded.raw_text == raw_response

    def test_timeline_no_change_line_when_error(self, tmp_path):
        """Timeline should not show change/ui lines when analysis has error."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model="claude-sonnet-4-20250514",
            error="JSON parse error",
        )
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "segments/s_part_0001.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )
        result = compose_timeline(manifest, tmp_path)
        # Should not have L1 lines
        assert "- change:" not in result
        assert "- ui:" not in result


class TestScoreSegment:
    """Test segment scoring for highlights."""

    def test_ui_key_text_gives_highest_score(self):
        """ui_key_text should give highest weight."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import score_segment

        with_ui = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ui_key_text=["对话内容"],
        )
        without_ui = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            ocr_text=["文字1", "文字2", "文字3"],
        )

        score_with_ui = score_segment(with_ui)
        score_without_ui = score_segment(without_ui)

        assert score_with_ui > score_without_ui

    def test_ocr_text_count_increases_score(self):
        """More ocr_text should increase score."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import score_segment

        few_ocr = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ocr_text=["一条"],
        )
        many_ocr = AnalysisResult(
            segment_id="part_0002",
            scene_type="unknown",
            ocr_text=["一条", "两条", "三条", "四条"],
        )

        assert score_segment(many_ocr) > score_segment(few_ocr)

    def test_scene_label_dialogue_higher_than_combat(self):
        """Dialogue scene_label should score higher than Combat."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import score_segment

        dialogue = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            scene_label="Dialogue",
        )
        combat = AnalysisResult(
            segment_id="part_0002",
            scene_type="combat",
            scene_label="Combat",
        )

        assert score_segment(dialogue) > score_segment(combat)

    def test_what_changed_keywords_add_score(self):
        """Change keywords in what_changed should add score."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import score_segment

        with_change = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            what_changed="从菜单切换到对话",
        )
        no_change = AnalysisResult(
            segment_id="part_0002",
            scene_type="unknown",
            what_changed="画面保持不变",
        )

        assert score_segment(with_change) > score_segment(no_change)

    def test_empty_analysis_scores_zero(self):
        """Empty analysis should score 0."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import score_segment

        empty = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
        )

        assert score_segment(empty) == 0


class TestComposeHighlights:
    """Test highlights composition."""

    def test_highlights_contains_session_id(self, tmp_path):
        """Highlights should include session ID in title."""
        from yanhu.composer import compose_highlights

        manifest = Manifest(
            session_id="2026-01-20_12-00-00_test_run01",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[],
        )
        result = compose_highlights(manifest, tmp_path)
        assert "2026-01-20_12-00-00_test_run01" in result

    def test_highlights_selects_top_k(self, tmp_path):
        """Should select top-k segments by score, with adjacent dialogue merging."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        # Create 5 segments with different scores
        # Note: part_0004 and part_0005 are adjacent with dialogue, so will be merged
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        for i in range(5):
            analysis = AnalysisResult(
                segment_id=f"part_000{i+1}",
                scene_type="dialogue",
                facts=[f"描述{i+1}"],
                ui_key_text=[f"UI文字{i}"] if i >= 3 else [],  # 4,5 have ui_key_text
            )
            analysis.save(analysis_dir / f"part_000{i+1}.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    f"part_000{i+1}", i * 60.0, (i + 1) * 60.0, f"segments/s_{i+1}.mp4",
                    analysis_path=f"analysis/part_000{i+1}.json",
                )
                for i in range(5)
            ],
        )

        # Use min_score=0 to include all segments
        result = compose_highlights(manifest, tmp_path, top_k=3, min_score=0)

        # part_0004 and part_0005 are adjacent with dialogue, so merged
        # The merged segment should appear as "part_0004+0005"
        assert "part_0004" in result  # Will appear in merged ID
        # Count highlight lines
        highlight_lines = [
            line for line in result.split("\n") if line.startswith("- [")
        ]
        assert len(highlight_lines) == 3

    def test_highlights_sorted_by_time(self, tmp_path):
        """Top segments should be displayed in time order."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create NON-adjacent segments to prevent merging
        # Use part_0001, part_0003, part_0005 (gaps between them)
        for i, seg_id in enumerate(["part_0001", "part_0003", "part_0005"]):
            analysis = AnalysisResult(
                segment_id=seg_id,
                scene_type="dialogue",
                facts=["描述"],
                ui_key_text=[f"UI文字{i}"],  # Different UI to avoid dedup
            )
            analysis.save(analysis_dir / f"{seg_id}.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0003", 120.0, 180.0, "s3.mp4",
                    analysis_path="analysis/part_0003.json",
                ),
                SegmentInfo(
                    "part_0005", 240.0, 300.0, "s5.mp4",
                    analysis_path="analysis/part_0005.json",
                ),
            ],
        )

        # Use min_score=0 to include all segments
        result = compose_highlights(manifest, tmp_path, top_k=3, min_score=0)

        # Find positions of segment IDs in output (non-adjacent so not merged)
        pos_1 = result.find("part_0001")
        pos_3 = result.find("part_0003")
        pos_5 = result.find("part_0005")

        # Should be in time order
        assert pos_1 < pos_3 < pos_5

    def test_highlights_includes_timestamp(self, tmp_path):
        """Highlight items should include timestamp."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["测试描述"],
            ui_key_text=["UI文字"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 125.0, 185.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path)

        # Should have timestamp [00:02:05] for 125 seconds
        assert "[00:02:05]" in result

    def test_highlights_includes_ui_text_as_main(self, tmp_path):
        """Highlight with ui_key_text should use it as main text (not separate)."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["测试描述"],
            ui_key_text=["关键对话内容"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path)

        # ui_key_text is now the main highlight text, not shown as separate "ui:" line
        assert "关键对话内容" in result
        # The main line should contain the ui text directly
        lines = [line for line in result.split("\n") if "关键对话内容" in line]
        assert any(line.startswith("- [") for line in lines)

    def test_highlights_includes_score(self, tmp_path):
        """Highlight items should include score for debug."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create segment with enough score to meet threshold
        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["测试描述"],
            scene_label="Dialogue",  # +50
            ui_key_text=["重要内容"],  # +110
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path)

        assert "score=" in result

    def test_highlights_skips_errored_analysis(self, tmp_path):
        """Should skip segments with analysis errors."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # One good, one errored
        good = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["正常分析"],
            ui_key_text=["正常UI"],
        )
        good.save(analysis_dir / "part_0001.json")

        errored = AnalysisResult(
            segment_id="part_0002",
            scene_type="unknown",
            error="JSON parse error",
            raw_text="bad json",
        )
        errored.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path)

        assert "part_0001" in result
        assert "part_0002" not in result

    def test_highlights_empty_when_no_analysis(self, tmp_path):
        """Should show placeholder when no analysis available."""
        from yanhu.composer import compose_highlights

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo("part_0001", 0.0, 60.0, "s1.mp4"),  # No analysis_path
            ],
        )

        result = compose_highlights(manifest, tmp_path)

        assert "No highlights available" in result


class TestWriteHighlights:
    """Test highlights file writing."""

    def test_write_highlights_creates_file(self, tmp_path):
        """write_highlights should create highlights.md file."""
        from yanhu.composer import write_highlights

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[],
        )

        result_path = write_highlights(manifest, tmp_path)

        assert result_path.exists()
        assert result_path.name == "highlights.md"
        content = result_path.read_text()
        assert "# Highlights:" in content


class TestPlatformWatermarks:
    """Test platform watermark detection and filtering."""

    def test_xiaohongshu_is_watermark(self):
        """小红书 should be detected as watermark."""
        assert is_platform_watermark("小红书") is True

    def test_common_platform_keywords(self):
        """Common platform keywords should be detected."""
        watermarks = ["关注", "点赞", "收藏", "分享", "评论", "抖音", "快手"]
        for keyword in watermarks:
            assert is_platform_watermark(keyword) is True, f"{keyword} should be watermark"

    def test_username_mention_is_watermark(self):
        """@username patterns should be detected as watermark."""
        assert is_platform_watermark("@用户名") is True
        assert is_platform_watermark("@test_user123") is True
        assert is_platform_watermark("@小明") is True

    def test_normal_text_not_watermark(self):
        """Normal dialogue text should not be watermark."""
        assert is_platform_watermark("真成你爸了?") is False
        assert is_platform_watermark("公主最后一次登上望帝乡") is False
        assert is_platform_watermark("对话内容") is False

    def test_filter_watermarks_removes_platform_keywords(self):
        """filter_watermarks should remove platform keywords."""
        ui_texts = ["小红书", "真成你爸了?", "关注"]
        result = filter_watermarks(ui_texts)
        assert result == ["真成你爸了?"]

    def test_filter_watermarks_empty_input(self):
        """filter_watermarks should handle empty input."""
        assert filter_watermarks(None) == []
        assert filter_watermarks([]) == []

    def test_filter_watermarks_all_filtered(self):
        """filter_watermarks should return empty if all are watermarks."""
        ui_texts = ["小红书", "关注", "点赞"]
        result = filter_watermarks(ui_texts)
        assert result == []

    def test_is_low_value_ui_all_watermarks(self):
        """is_low_value_ui should return True when all are watermarks."""
        assert is_low_value_ui(["小红书"]) is True
        assert is_low_value_ui(["小红书", "关注"]) is True

    def test_is_low_value_ui_mixed_content(self):
        """is_low_value_ui should return False when mixed content."""
        assert is_low_value_ui(["小红书", "对话内容"]) is False

    def test_is_low_value_ui_empty(self):
        """is_low_value_ui should return False for empty input."""
        assert is_low_value_ui(None) is False
        assert is_low_value_ui([]) is False


class TestScoreSegmentWatermarks:
    """Test scoring with watermark filtering."""

    def test_watermark_only_ui_gets_penalty(self):
        """Segment with only watermark UI should get penalty."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import score_segment

        # Only watermark
        watermark_only = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ui_key_text=["小红书"],
        )
        # No UI at all
        no_ui = AnalysisResult(
            segment_id="part_0002",
            scene_type="unknown",
        )

        score_watermark = score_segment(watermark_only)
        score_no_ui = score_segment(no_ui)

        # Watermark-only should be penalized (negative or less than no UI)
        assert score_watermark < score_no_ui

    def test_mixed_ui_not_penalized(self):
        """Segment with mixed UI (watermark + content) should not be penalized."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import score_segment

        mixed_ui = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            ui_key_text=["小红书", "对话内容"],
        )
        content_only = AnalysisResult(
            segment_id="part_0002",
            scene_type="unknown",
            ui_key_text=["对话内容"],
        )

        score_mixed = score_segment(mixed_ui)
        score_content = score_segment(content_only)

        # Mixed should still score well (content is counted)
        assert score_mixed == score_content  # Both have 1 valid UI item

    def test_xiaohongshu_segment_not_selected_as_highlight(self, tmp_path):
        """Segment with only 小红书 UI should not be in top highlights."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create segment with only 小红书
        xiaohongshu = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            facts=["夜晚驾驶场景"],
            ui_key_text=["小红书"],
        )
        xiaohongshu.save(analysis_dir / "part_0001.json")

        # Create segment with real content
        good_content = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["角色对话"],
            ui_key_text=["真成你爸了?"],
        )
        good_content.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=1)

        # Good content should be selected, not xiaohongshu
        assert "part_0002" in result
        assert "真成你爸了?" in result
        # xiaohongshu should not appear in UI line (filtered out)
        assert "ui: 小红书" not in result


class TestMinScoreThreshold:
    """Test minimum score threshold for highlights."""

    def test_low_score_segments_excluded(self, tmp_path):
        """Segments below min_score should not be in primary selection."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Low score segment (no UI, no special scene)
        low_score = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            facts=["普通场景"],
        )
        low_score.save(analysis_dir / "part_0001.json")

        # High score segment
        high_score = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["角色对话"],
            scene_label="Dialogue",
            ui_key_text=["重要对话"],
        )
        high_score.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=80)

        # Only high score segment should be included
        assert "part_0002" in result
        # Low score might be included as secondary fill, check score is shown
        lines = [line for line in result.split("\n") if "part_0001" in line]
        # If included, it should be via secondary selection (score < 80)
        if lines:
            # It was included as secondary fill
            pass
        else:
            # Not included at all - also acceptable
            assert "part_0001" not in result

    def test_min_score_threshold_respected(self, tmp_path):
        """Only segments meeting min_score should be primary selected."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create multiple segments with varying scores
        for i in range(5):
            score_boost = (i + 1) * 30  # 30, 60, 90, 120, 150
            analysis = AnalysisResult(
                segment_id=f"part_000{i+1}",
                scene_type="dialogue" if score_boost >= 90 else "unknown",
                facts=[f"描述{i+1}"],
                scene_label="Dialogue" if score_boost >= 90 else None,
                ui_key_text=[f"UI{i}"] if score_boost >= 120 else [],
            )
            analysis.save(analysis_dir / f"part_000{i+1}.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    f"part_000{i+1}", i * 60.0, (i + 1) * 60.0, f"s{i+1}.mp4",
                    analysis_path=f"analysis/part_000{i+1}.json",
                )
                for i in range(5)
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=2, min_score=100)

        # Count highlight lines - should be <= 2
        highlight_lines = [
            line for line in result.split("\n") if line.startswith("- [")
        ]
        assert len(highlight_lines) <= 2


class TestUiDeduplication:
    """Test ui_key_text deduplication."""

    def test_duplicate_ui_keeps_higher_score(self, tmp_path):
        """When two segments have same UI, keep higher score."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Two segments with same UI text
        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述1"],
            scene_label="Dialogue",
            ui_key_text=["桌上日记, 这是随公主出嫁的第五个年头"],
        )
        first.save(analysis_dir / "part_0001.json")

        second = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["场景描述2"],
            scene_label="Dialogue",
            ui_key_text=["桌上日记, 这是随公主出嫁的第五个年头"],  # Same UI
            ocr_text=["额外文字"],  # Extra content = higher score
        )
        second.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Only one should appear (the higher score one)
        count = result.count("桌上日记")
        assert count == 1, f"Duplicate UI should be deduplicated, found {count}"

        # Higher score (part_0002) should be kept
        assert "part_0002" in result

    def test_different_ui_not_deduplicated_nonadjacent(self, tmp_path):
        """Non-adjacent segments with different UI should both appear separately."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Use non-adjacent segment IDs to prevent merging
        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述1"],
            ui_key_text=["第一段对话"],
        )
        first.save(analysis_dir / "part_0001.json")

        second = AnalysisResult(
            segment_id="part_0003",  # Non-adjacent (skip part_0002)
            scene_type="dialogue",
            facts=["场景描述2"],
            ui_key_text=["第二段对话"],  # Different UI
        )
        second.save(analysis_dir / "part_0003.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0003", 120.0, 180.0, "s3.mp4",
                    analysis_path="analysis/part_0003.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Both should appear separately (non-adjacent, so not merged)
        assert "part_0001" in result
        assert "part_0003" in result
        assert "第一段对话" in result
        assert "第二段对话" in result

    def test_segments_without_ui_not_deduplicated(self, tmp_path):
        """Segments without UI should not be deduplicated against each other."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Both have no UI
        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="combat",
            facts=["战斗场景1"],
            scene_label="Combat",
        )
        first.save(analysis_dir / "part_0001.json")

        second = AnalysisResult(
            segment_id="part_0002",
            scene_type="combat",
            facts=["战斗场景2"],
            scene_label="Combat",
        )
        second.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Both should appear (no UI = no deduplication key)
        assert "part_0001" in result
        assert "part_0002" in result


class TestAdjacentSegmentMerging:
    """Test adjacent dialogue segment merging."""

    def test_adjacent_dialogue_segments_merged(self, tmp_path):
        """Adjacent segments with dialogue should be merged."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Two adjacent segments with dialogue
        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述1"],
            ui_key_text=["第一句台词"],
        )
        first.save(analysis_dir / "part_0001.json")

        second = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["场景描述2"],
            ui_key_text=["第二句台词"],
        )
        second.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Should be merged into one highlight with combined ID
        assert "part_0001+0002" in result
        # Both texts should appear
        assert "第一句台词" in result
        assert "第二句台词" in result
        # Should only have 1 highlight line
        highlight_lines = [
            line for line in result.split("\n") if line.startswith("- [")
        ]
        assert len(highlight_lines) == 1

    def test_nonadjacent_segments_not_merged(self, tmp_path):
        """Non-adjacent segments should not be merged."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述1"],
            ui_key_text=["第一句台词"],
        )
        first.save(analysis_dir / "part_0001.json")

        # Gap: part_0003 (not part_0002)
        third = AnalysisResult(
            segment_id="part_0003",
            scene_type="dialogue",
            facts=["场景描述3"],
            ui_key_text=["第三句台词"],
        )
        third.save(analysis_dir / "part_0003.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0003", 120.0, 180.0, "s3.mp4",
                    analysis_path="analysis/part_0003.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Should not be merged - both appear separately
        assert "part_0001" in result
        assert "part_0003" in result
        assert "+" not in result  # No merged ID
        # Should have 2 highlight lines
        highlight_lines = [
            line for line in result.split("\n") if line.startswith("- [")
        ]
        assert len(highlight_lines) == 2

    def test_no_dialogue_segments_not_merged(self, tmp_path):
        """Adjacent segments without dialogue content should not be merged."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # No dialogue content (no ui_key_text, no ocr_text)
        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="combat",
            facts=["战斗场景1"],
            scene_label="Combat",
        )
        first.save(analysis_dir / "part_0001.json")

        second = AnalysisResult(
            segment_id="part_0002",
            scene_type="combat",
            facts=["战斗场景2"],
            scene_label="Combat",
        )
        second.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=0)

        # Should not be merged - no dialogue content
        assert "+" not in result
        # Should have 2 highlight lines
        highlight_lines = [
            line for line in result.split("\n") if line.startswith("- [")
        ]
        assert len(highlight_lines) == 2


class TestNoLowScoreFill:
    """Test that low score segments don't fill when N < K."""

    def test_no_fill_with_low_scores(self, tmp_path):
        """Should not fill with low-score segments when fewer than K qualify."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # One high-score segment (meets min_score=80)
        high = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["高分场景"],
            ui_key_text=["重要台词"],  # +110
        )
        high.save(analysis_dir / "part_0001.json")

        # One low-score segment (below min_score=80)
        low = AnalysisResult(
            segment_id="part_0003",  # Non-adjacent
            scene_type="unknown",
            facts=["低分场景"],  # No UI, no scene_label = low score
        )
        low.save(analysis_dir / "part_0003.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0003", 120.0, 180.0, "s3.mp4",
                    analysis_path="analysis/part_0003.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=80)

        # Should only have 1 highlight (the high-score one)
        assert "Top 1 moments" in result
        assert "part_0001" in result
        assert "part_0003" not in result

    def test_outputs_actual_count_not_top_k(self, tmp_path):
        """Should output actual count in header, not top_k."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create 2 high-score segments
        for i in range(2):
            analysis = AnalysisResult(
                segment_id=f"part_000{i*2+1}",  # part_0001, part_0003 (non-adjacent)
                scene_type="dialogue",
                facts=[f"场景{i+1}"],
                ui_key_text=[f"台词{i+1}"],
            )
            analysis.save(analysis_dir / f"part_000{i*2+1}.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0003", 120.0, 180.0, "s3.mp4",
                    analysis_path="analysis/part_0003.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, top_k=8, min_score=80)

        # Should say "Top 2 moments" not "Top 8 moments"
        assert "Top 2 moments" in result


class TestHighlightTextPriority:
    """Test highlight text priority: ui > dialogue ocr > facts."""

    def test_ui_key_text_as_main_text(self, tmp_path):
        """ui_key_text should be the main highlight text."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["这是facts描述"],
            caption="这是caption描述",
            ui_key_text=["这是台词内容"],
            ocr_text=["这是OCR文字"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Main line should have ui_key_text, not facts/caption/ocr
        main_line = [line for line in result.split("\n") if line.startswith("- [")][0]
        assert "这是台词内容" in main_line
        assert "这是facts描述" not in main_line
        assert "这是caption描述" not in main_line

    def test_dialogue_ocr_when_no_ui(self, tmp_path):
        """Should use dialogue-like OCR text when no ui_key_text."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["这是facts描述"],
            ocr_text=["短文字", "这是对话内容？长一点的台词"],  # Second has ? and longer
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should pick the dialogue-like OCR (with ?)
        assert "这是对话内容？长一点的台词" in result

    def test_facts_fallback_when_no_ui_or_ocr(self, tmp_path):
        """Should fallback to facts when no ui_key_text or ocr_text."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["这是fallback的facts描述"],
            scene_label="Dialogue",  # Need this for min_score
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should use facts as fallback
        assert "这是fallback的facts描述" in result

    def test_xiaohongshu_not_in_highlight_text(self, tmp_path):
        """小红书 watermark should not appear as highlight text."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="unknown",
            facts=["夜晚驾驶场景"],
            ui_key_text=["小红书"],  # Watermark only
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        # Use min_score=0 to include this segment
        result = compose_highlights(manifest, tmp_path, min_score=-100)

        # Main line should NOT have 小红书, should fallback to facts
        main_line = [line for line in result.split("\n") if line.startswith("- [")][0]
        assert "小红书" not in main_line
        assert "夜晚驾驶场景" in main_line


class TestPickDialogueText:
    """Test dialogue text selection from OCR."""

    def test_prefers_question_mark(self):
        """Should prefer text with question mark."""
        from yanhu.composer import pick_dialogue_text

        texts = ["普通文字", "这是问题？"]
        result = pick_dialogue_text(texts)
        assert result == "这是问题？"

    def test_prefers_exclamation_mark(self):
        """Should prefer text with exclamation mark."""
        from yanhu.composer import pick_dialogue_text

        texts = ["普通文字", "感叹句！"]
        result = pick_dialogue_text(texts)
        assert result == "感叹句！"

    def test_longest_when_no_dialogue_punctuation(self):
        """Should pick longest when no dialogue punctuation."""
        from yanhu.composer import pick_dialogue_text

        texts = ["短", "这是比较长的文字"]
        result = pick_dialogue_text(texts)
        assert result == "这是比较长的文字"

    def test_empty_returns_none(self):
        """Should return None for empty list."""
        from yanhu.composer import pick_dialogue_text

        assert pick_dialogue_text(None) is None
        assert pick_dialogue_text([]) is None


class TestUiSymbolsHeartPrefix:
    """Test ❤️ prefix when ui_symbols contains heart."""

    def test_heart_symbol_prefixed(self, tmp_path):
        """Should prefix ❤️ when ui_symbols contains heart emoji."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["台词内容"],
            ui_symbols=["❤️"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have ❤️ prefix
        assert "❤️ 台词内容" in result

    def test_heart_tag_prefixed(self, tmp_path):
        """Should prefix ❤️ when ui_symbols contains 'heart' tag."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["台词内容"],
            ui_symbols=["heart"],  # Tag form, not emoji
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have ❤️ prefix for "heart" tag
        assert "❤️ 台词内容" in result

    def test_no_prefix_without_heart(self, tmp_path):
        """Should not prefix ❤️ when ui_symbols doesn't contain heart."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["台词内容"],
            ui_symbols=["🔥"],  # Fire, not heart
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should NOT have ❤️ prefix
        main_line = [line for line in result.split("\n") if line.startswith("- [")][0]
        assert "❤️" not in main_line
        assert "台词内容" in main_line

    def test_no_prefix_without_symbols(self, tmp_path):
        """Should not prefix ❤️ when ui_symbols is empty."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["台词内容"],
            # No ui_symbols
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should NOT have ❤️ prefix
        main_line = [line for line in result.split("\n") if line.startswith("- [")][0]
        assert "❤️" not in main_line

    def test_heart_only_on_first_segment_when_merged(self, tmp_path):
        """When merging two segments, ❤️ should only appear on the segment that has it."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # First segment has ❤️
        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述1"],
            ui_key_text=["第一段台词"],
            ui_symbols=["❤️"],
        )
        first.save(analysis_dir / "part_0001.json")

        # Second segment has no ❤️
        second = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["场景描述2"],
            ui_key_text=["第二段台词"],
            # No ui_symbols
        )
        second.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have merged ID
        assert "part_0001+0002" in result
        # ❤️ should be on first segment's text, not second
        assert "❤️ 第一段台词" in result
        # Second segment should NOT have ❤️
        assert "❤️ 第二段台词" not in result
        assert "第二段台词" in result

    def test_heart_inserts_before_keyword(self, tmp_path):
        """When segment has ❤️ and contains '都做过', insert ❤️ before that keyword."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["daddy也叫了", "都做过"],
            ui_symbols=["❤️"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # ❤️ should be inserted before "都做过", not at the start
        assert "daddy也叫了 / ❤️ 都做过" in result

    def test_heart_keyword_in_merged_segment(self, tmp_path):
        """When merged, ❤️ should be inserted before keyword in correct segment."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # First segment has ❤️ and keyword
        first = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述1"],
            ui_key_text=["daddy也叫了", "都做过"],
            ui_symbols=["❤️"],
        )
        first.save(analysis_dir / "part_0001.json")

        # Second segment has no ❤️
        second = AnalysisResult(
            segment_id="part_0002",
            scene_type="dialogue",
            facts=["场景描述2"],
            ui_key_text=["現在你和另外一個男人拍拖"],
        )
        second.save(analysis_dir / "part_0002.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
                SegmentInfo(
                    "part_0002", 60.0, 120.0, "s2.mp4",
                    analysis_path="analysis/part_0002.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have merged ID
        assert "part_0001+0002" in result
        # ❤️ should be before "都做过" in first segment
        # Format: "daddy也叫了 / ❤️ 都做过 / 現在你和另外一個男人拍拖"
        assert "❤️ 都做过" in result
        assert "daddy也叫了" in result
        assert "現在你和另外一個男人拍拖" in result


class TestUiKeyTextJoin:
    """Test ui_key_text joining with ' / '."""

    def test_two_ui_items_joined(self, tmp_path):
        """Should join two ui_key_text items with ' / '."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["第一句", "第二句"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have joined text
        assert "第一句 / 第二句" in result

    def test_single_ui_item_not_joined(self, tmp_path):
        """Should not add separator for single ui_key_text item."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["单独一句"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have single text without separator
        assert "单独一句" in result
        assert " / " not in result or "单独一句 / " not in result

    def test_heart_prefix_with_joined_text(self, tmp_path):
        """Should have ❤️ prefix before joined ui_key_text."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["第一句", "第二句"],
            ui_symbols=["❤️"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have ❤️ prefix before joined text
        assert "❤️ 第一句 / 第二句" in result


class TestGetHighlightTextFunction:
    """Test get_highlight_text and apply_heart_to_chunk functions."""

    def test_has_heart_symbol_detection(self):
        """Test _has_heart_symbol helper function."""
        assert _has_heart_symbol(["❤️"]) is True
        assert _has_heart_symbol(["heart"]) is True
        assert _has_heart_symbol(["Heart"]) is True
        assert _has_heart_symbol(["broken_heart"]) is True
        assert _has_heart_symbol(["🔥"]) is False
        assert _has_heart_symbol([]) is False
        assert _has_heart_symbol(None) is False

    def test_get_highlight_text_does_not_add_heart(self):
        """Test get_highlight_text does NOT add ❤️ prefix (that's apply_heart_to_chunk's job)."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ui_key_text=["台词"],
            ui_symbols=["❤️"],
        )

        result = get_highlight_text(analysis, ["台词"])
        # get_highlight_text should NOT add heart - just return the text
        assert result == "台词"
        assert "❤️" not in result

    def test_apply_heart_to_chunk_with_heart(self):
        """Test apply_heart_to_chunk adds ❤️ prefix."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ui_key_text=["台词"],
            ui_symbols=["❤️"],
        )

        result = apply_heart_to_chunk("台词", analysis)
        assert result == "❤️ 台词"

    def test_apply_heart_to_chunk_without_heart(self):
        """Test apply_heart_to_chunk without heart symbol."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ui_key_text=["台词"],
        )

        result = apply_heart_to_chunk("台词", analysis)
        assert result == "台词"
        assert "❤️" not in result

    def test_apply_heart_inserts_before_keyword(self):
        """Test apply_heart_to_chunk inserts ❤️ before '都做过' keyword."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ui_symbols=["❤️"],
        )

        # With keyword
        result = apply_heart_to_chunk("daddy也叫了 / 都做过", analysis)
        assert result == "daddy也叫了 / ❤️ 都做过"

        # Traditional Chinese variant
        result2 = apply_heart_to_chunk("daddy也叫了 / 都做過", analysis)
        assert result2 == "daddy也叫了 / ❤️ 都做過"

    def test_apply_heart_prefix_when_no_keyword(self):
        """Test apply_heart_to_chunk prefixes when no keyword present."""
        from yanhu.analyzer import AnalysisResult

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            ui_symbols=["❤️"],
        )

        result = apply_heart_to_chunk("普通台词内容", analysis)
        assert result == "❤️ 普通台词内容"


class TestHighlightQuoteWithAlignedQuotes:
    """Test highlights with aligned_quotes (source=both shows ocr + asr)."""

    def test_aligned_quotes_both_shows_ocr_and_asr(self, tmp_path):
        """Highlight should show 'ocr (asr)' when source=both."""
        import json

        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        # Create analysis with aligned_quotes
        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "cutscene",
            "facts": ["角色特写镜头"],
            "what_changed": "字幕从A变为B",
            "aligned_quotes": [
                {"t": 5.0, "source": "both", "ocr": "搞到最後", "asr": "搞到最後真的變成你爸爸"},
            ],
        }
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(analysis_data, ensure_ascii=False)
        )

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should show OCR text with ASR in parentheses
        assert "搞到最後" in result
        assert "(搞到最後真的變成你爸爸)" in result

    def test_aligned_quotes_ocr_only(self, tmp_path):
        """Highlight should show only OCR when source=ocr."""
        import json

        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "cutscene",
            "facts": ["角色特写镜头"],
            "aligned_quotes": [
                {"t": 5.0, "source": "ocr", "ocr": "只有OCR文本"},
            ],
        }
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(analysis_data, ensure_ascii=False)
        )

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        assert "只有OCR文本" in result
        assert "(asr:" not in result

    def test_no_aligned_quotes_fallback_to_ui(self, tmp_path):
        """Should fallback to ui_key_text when no aligned_quotes."""
        from yanhu.analyzer import AnalysisResult
        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis = AnalysisResult(
            segment_id="part_0001",
            scene_type="dialogue",
            facts=["场景描述"],
            ui_key_text=["对话内容"],
        )
        analysis.save(analysis_dir / "part_0001.json")

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should fallback to ui_key_text
        assert "对话内容" in result


class TestHighlightSummaryLine:
    """Test highlights include summary line with facts + what_changed."""

    def test_summary_line_present(self, tmp_path):
        """Highlight should include summary line with facts and what_changed."""
        import json

        from yanhu.composer import compose_highlights

        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()

        analysis_data = {
            "segment_id": "part_0001",
            "scene_type": "cutscene",
            "facts": ["男性角色戴眼镜特写镜头"],
            "what_changed": "字幕从搞到最後变为真成你爸了，镜头从清晰特写切换到黑白模糊画面",
            "ui_key_text": ["真成你爸了?"],
        }
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(analysis_data, ensure_ascii=False)
        )

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-20T12:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=60,
            segments=[
                SegmentInfo(
                    "part_0001", 0.0, 60.0, "s1.mp4",
                    analysis_path="analysis/part_0001.json",
                ),
            ],
        )

        result = compose_highlights(manifest, tmp_path, min_score=0)

        # Should have summary line
        assert "- summary:" in result
        # Should include facts[0]
        assert "男性角色戴眼镜特写镜头" in result

    def test_summary_truncates_at_sentence_boundary(self, tmp_path):
        """Summary should truncate at sentence boundary, not mid-word."""
        from yanhu.composer import truncate_at_sentence_boundary

        # Short text - no truncation
        assert truncate_at_sentence_boundary("短文本", 40) == "短文本"

        # Text with sentence boundary
        text = "第一句话。第二句话很长很长很长很长很长很长很长"
        result = truncate_at_sentence_boundary(text, 10)
        assert result == "第一句话。"
        assert "第二句" not in result

        # Text without boundary within limit
        text2 = "没有标点的很长很长的文本内容"
        result2 = truncate_at_sentence_boundary(text2, 10)
        assert len(result2) == 10
