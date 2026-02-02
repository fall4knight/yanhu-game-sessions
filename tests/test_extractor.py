"""Tests for frame extraction."""

from dataclasses import dataclass
from pathlib import Path

from yanhu.extractor import (
    SubtitleFocusedSample,
    build_extract_frame_command,
    calculate_sample_timestamps,
    calculate_subtitle_focused_timestamps,
    generate_frame_filename,
    generate_frame_path,
)


@dataclass
class MockAsrItem:
    """Mock ASR item for testing (matches AsrItem interface)."""

    text: str
    t_start: float
    t_end: float


class TestCalculateSampleTimestamps:
    """Test timestamp calculation for frame sampling."""

    def test_single_frame_returns_middle(self):
        """Single frame should be at 50% of duration."""
        timestamps = calculate_sample_timestamps(60.0, 1)
        assert len(timestamps) == 1
        assert timestamps[0] == 30.0  # middle of 60s

    def test_multiple_frames_includes_middle(self):
        """Multiple frames should include middle frame."""
        timestamps = calculate_sample_timestamps(60.0, 5)
        middle = 30.0
        assert middle in timestamps or any(abs(t - middle) < 0.1 for t in timestamps)

    def test_no_duplicate_timestamps(self):
        """Should not return duplicate timestamps."""
        timestamps = calculate_sample_timestamps(60.0, 10)
        assert len(timestamps) == len(set(timestamps))

    def test_timestamps_are_sorted(self):
        """Timestamps should be in ascending order."""
        timestamps = calculate_sample_timestamps(120.0, 8)
        assert timestamps == sorted(timestamps)

    def test_timestamps_within_duration(self):
        """All timestamps should be within video duration."""
        duration = 45.0
        timestamps = calculate_sample_timestamps(duration, 8)
        for t in timestamps:
            assert 0 <= t <= duration

    def test_zero_duration_returns_empty(self):
        """Zero duration should return empty list."""
        assert calculate_sample_timestamps(0.0, 5) == []

    def test_zero_frames_returns_empty(self):
        """Zero frames requested should return empty list."""
        assert calculate_sample_timestamps(60.0, 0) == []

    def test_negative_values_return_empty(self):
        """Negative values should return empty list."""
        assert calculate_sample_timestamps(-10.0, 5) == []
        assert calculate_sample_timestamps(60.0, -1) == []

    def test_more_frames_than_needed_limited(self):
        """Should limit to num_frames even if more timestamps generated."""
        timestamps = calculate_sample_timestamps(10.0, 5)
        assert len(timestamps) <= 5

    def test_evenly_distributed(self):
        """Frames should be roughly evenly distributed."""
        timestamps = calculate_sample_timestamps(100.0, 5)
        # Check that gaps between consecutive timestamps are reasonable
        gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        # No gap should be more than 3x the average
        avg_gap = 100.0 / (len(timestamps) + 1)
        for gap in gaps:
            assert gap < avg_gap * 3


class TestGenerateFrameFilename:
    """Test frame filename generation."""

    def test_filename_format(self):
        """Filename should be frame_NNNN.jpg with 4-digit padding."""
        assert generate_frame_filename(1) == "frame_0001.jpg"
        assert generate_frame_filename(10) == "frame_0010.jpg"
        assert generate_frame_filename(100) == "frame_0100.jpg"
        assert generate_frame_filename(1000) == "frame_1000.jpg"

    def test_extension_is_jpg(self):
        """Extension should be .jpg."""
        filename = generate_frame_filename(1)
        assert filename.endswith(".jpg")


class TestGenerateFramePath:
    """Test frame path generation."""

    def test_path_format(self):
        """Path should be frames/<segment_id>/frame_NNNN.jpg."""
        path = generate_frame_path("part_0001", 1)
        assert path == "frames/part_0001/frame_0001.jpg"

    def test_path_is_relative(self):
        """Path should be relative (not start with /)."""
        path = generate_frame_path("part_0001", 1)
        assert not path.startswith("/")

    def test_path_uses_segment_id(self):
        """Path should include segment ID as directory."""
        path = generate_frame_path("part_0042", 5)
        assert "part_0042" in path
        assert path == "frames/part_0042/frame_0005.jpg"


class TestBuildExtractFrameCommand:
    """Test ffmpeg frame extraction command building."""

    def test_command_structure(self):
        """Command should have correct ffmpeg arguments."""
        cmd = build_extract_frame_command(
            input_path=Path("/input/segment.mp4"),
            output_path=Path("/output/frame.jpg"),
            timestamp=30.5,
        )

        # Should include overwrite flag
        assert "-y" in cmd

        # Should include seek time
        ss_index = cmd.index("-ss")
        assert "30.500" in cmd[ss_index + 1]

        # Should include input
        i_index = cmd.index("-i")
        assert cmd[i_index + 1] == "/input/segment.mp4"

        # Should extract exactly 1 frame
        frames_index = cmd.index("-frames:v")
        assert cmd[frames_index + 1] == "1"

        # Should include quality setting
        assert "-q:v" in cmd

        # Output should be at end
        assert cmd[-1] == "/output/frame.jpg"

    def test_seek_before_input(self):
        """Seek (-ss) should come before input (-i) for fast seeking."""
        cmd = build_extract_frame_command(
            input_path=Path("/input/segment.mp4"),
            output_path=Path("/output/frame.jpg"),
            timestamp=10.0,
        )
        ss_index = cmd.index("-ss")
        i_index = cmd.index("-i")
        assert ss_index < i_index, "Seek should come before input"

    def test_timestamp_precision(self):
        """Timestamp should have millisecond precision."""
        cmd = build_extract_frame_command(
            input_path=Path("/input/segment.mp4"),
            output_path=Path("/output/frame.jpg"),
            timestamp=15.123,
        )
        ss_index = cmd.index("-ss")
        timestamp_str = cmd[ss_index + 1]
        assert "15.123" in timestamp_str


class TestManifestFramesIntegration:
    """Test manifest frames field handling."""

    def test_segment_info_frames_field(self):
        """SegmentInfo should have frames field."""
        from yanhu.manifest import SegmentInfo

        seg = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test_part_0001.mp4",
            frames=["frames/part_0001/frame_0001.jpg", "frames/part_0001/frame_0002.jpg"],
        )
        assert len(seg.frames) == 2
        assert seg.frames[0] == "frames/part_0001/frame_0001.jpg"

    def test_segment_info_to_dict_includes_frames(self):
        """to_dict should include frames when present."""
        from yanhu.manifest import SegmentInfo

        seg = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test_part_0001.mp4",
            frames=["frames/part_0001/frame_0001.jpg"],
        )
        d = seg.to_dict()
        assert "frames" in d
        assert d["frames"] == ["frames/part_0001/frame_0001.jpg"]

    def test_segment_info_to_dict_omits_empty_frames(self):
        """to_dict should omit frames when empty."""
        from yanhu.manifest import SegmentInfo

        seg = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=60.0,
            video_path="segments/test_part_0001.mp4",
        )
        d = seg.to_dict()
        assert "frames" not in d

    def test_segment_info_from_dict_with_frames(self):
        """from_dict should parse frames field."""
        from yanhu.manifest import SegmentInfo

        d = {
            "id": "part_0001",
            "start_time": 0.0,
            "end_time": 60.0,
            "video_path": "segments/test_part_0001.mp4",
            "frames": ["frames/part_0001/frame_0001.jpg"],
        }
        seg = SegmentInfo.from_dict(d)
        assert seg.frames == ["frames/part_0001/frame_0001.jpg"]

    def test_segment_info_from_dict_without_frames(self):
        """from_dict should handle missing frames field."""
        from yanhu.manifest import SegmentInfo

        d = {
            "id": "part_0001",
            "start_time": 0.0,
            "end_time": 60.0,
            "video_path": "segments/test_part_0001.mp4",
        }
        seg = SegmentInfo.from_dict(d)
        assert seg.frames == []

    def test_frame_paths_are_relative(self):
        """All frame paths should be relative to session directory."""
        paths = [
            generate_frame_path("part_0001", 1),
            generate_frame_path("part_0002", 5),
            generate_frame_path("part_0010", 8),
        ]
        for path in paths:
            assert not path.startswith("/")
            assert path.startswith("frames/")


class TestCalculateSubtitleFocusedTimestamps:
    """Test subtitle-focused frame sampling with ASR data."""

    def test_includes_asr_midpoints(self):
        """Should include midpoint of each ASR segment."""
        # Segment: 0-60s (absolute: 100-160s)
        segment_start = 100.0
        duration = 60.0

        # ASR item from 110-120s (relative: 10-20s, midpoint: 15s)
        asr_items = [MockAsrItem(text="Hello", t_start=110.0, t_end=120.0)]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
        )

        # Midpoint should be 15.0 (relative)
        assert 15.0 in result.timestamps
        assert 15.0 in result.asr_midpoints

    def test_includes_speech_boundaries(self):
        """Should include t_start and t_end of ASR segments."""
        segment_start = 0.0
        duration = 60.0

        # ASR item from 10-20s
        asr_items = [MockAsrItem(text="Test", t_start=10.0, t_end=20.0)]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
        )

        # Should include t_start (10.0) and t_end (20.0)
        assert 10.0 in result.timestamps
        assert 20.0 in result.timestamps

    def test_includes_boundary_offsets(self):
        """Should include +/- offsets around speech boundaries."""
        segment_start = 0.0
        duration = 60.0

        # ASR item from 10-50s
        asr_items = [MockAsrItem(text="Long speech", t_start=10.0, t_end=50.0)]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
            boundary_offsets=(0.3, 0.8),
        )

        # Should include t_start + offsets (10.3, 10.8)
        assert 10.3 in result.timestamps
        assert 10.8 in result.timestamps

        # Should include t_end - offsets (49.7, 49.2)
        assert 49.7 in result.timestamps
        assert 49.2 in result.timestamps

    def test_clamps_to_segment_bounds(self):
        """Should clamp timestamps to segment duration."""
        segment_start = 0.0
        duration = 30.0

        # ASR item from -5 to 35s (extends beyond segment)
        asr_items = [MockAsrItem(text="Extended", t_start=-5.0, t_end=35.0)]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
        )

        # All timestamps should be within segment
        for t in result.timestamps:
            assert 0 <= t <= duration

    def test_deduplicates_timestamps(self):
        """Should deduplicate timestamps."""
        segment_start = 0.0
        duration = 60.0

        # Two ASR items with same midpoint
        asr_items = [
            MockAsrItem(text="A", t_start=10.0, t_end=20.0),
            MockAsrItem(text="B", t_start=10.0, t_end=20.0),
        ]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
        )

        # Should not have duplicates
        assert len(result.timestamps) == len(set(result.timestamps))

    def test_respects_min_spacing(self):
        """Should respect minimum spacing between samples."""
        segment_start = 0.0
        duration = 60.0
        min_spacing = 0.5

        # ASR items very close together
        asr_items = [
            MockAsrItem(text="A", t_start=10.0, t_end=10.2),
            MockAsrItem(text="B", t_start=10.3, t_end=10.5),
        ]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
            min_spacing=min_spacing,
        )

        # Check spacing between consecutive timestamps
        sorted_ts = sorted(result.timestamps)
        for i in range(1, len(sorted_ts)):
            assert sorted_ts[i] - sorted_ts[i - 1] >= min_spacing

    def test_fills_with_uniform_samples(self):
        """Should fill remaining budget with uniform samples if needed."""
        segment_start = 0.0
        duration = 60.0
        base_frames = 8

        # Only one short ASR item
        asr_items = [MockAsrItem(text="Short", t_start=30.0, t_end=31.0)]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=base_frames,
        )

        # Should have at least base_frames timestamps
        assert len(result.timestamps) >= base_frames

    def test_empty_asr_returns_middle_and_fills(self):
        """Should still include middle frame and fill when no ASR."""
        segment_start = 0.0
        duration = 60.0
        base_frames = 4

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=[],
            base_frames=base_frames,
        )

        # Should include middle (30.0)
        assert 30.0 in result.timestamps
        # Should have base_frames timestamps
        assert len(result.timestamps) >= base_frames

    def test_timestamps_are_sorted(self):
        """Timestamps should be in ascending order."""
        segment_start = 0.0
        duration = 60.0

        asr_items = [
            MockAsrItem(text="A", t_start=40.0, t_end=50.0),
            MockAsrItem(text="B", t_start=10.0, t_end=20.0),
        ]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
        )

        assert result.timestamps == sorted(result.timestamps)

    def test_skips_asr_outside_segment(self):
        """Should skip ASR items completely outside segment."""
        segment_start = 100.0
        duration = 60.0  # Segment: 100-160s

        # ASR item completely before segment
        asr_items = [MockAsrItem(text="Before", t_start=50.0, t_end=60.0)]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
        )

        # Should not include any ASR-derived timestamps
        assert len(result.asr_midpoints) == 0
        assert len(result.boundary_offsets) == 0

    def test_zero_duration_returns_empty(self):
        """Zero duration should return empty result."""
        result = calculate_subtitle_focused_timestamps(
            duration=0.0,
            segment_start=0.0,
            asr_items=[MockAsrItem(text="Test", t_start=0.0, t_end=1.0)],
            base_frames=4,
        )

        assert result.timestamps == []

    def test_result_dataclass_fields(self):
        """Should return SubtitleFocusedSample with all fields populated."""
        segment_start = 0.0
        duration = 60.0

        asr_items = [MockAsrItem(text="Test", t_start=10.0, t_end=20.0)]

        result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=4,
        )

        assert isinstance(result, SubtitleFocusedSample)
        assert isinstance(result.timestamps, list)
        assert isinstance(result.asr_midpoints, list)
        assert isinstance(result.boundary_offsets, list)
