"""Tests for frame extraction."""

from pathlib import Path

from yanhu.extractor import (
    build_extract_frame_command,
    calculate_sample_timestamps,
    generate_frame_filename,
    generate_frame_path,
)


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
