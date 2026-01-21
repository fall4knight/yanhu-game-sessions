"""Tests for session composition."""

from yanhu.composer import (
    compose_overview,
    compose_timeline,
    format_frames_list,
    format_time_range,
    format_timestamp,
    has_valid_claude_analysis,
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
