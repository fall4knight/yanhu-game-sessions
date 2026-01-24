"""Tests for video segmentation."""

from pathlib import Path

from yanhu.segmenter import (
    build_segment_command,
    calculate_segments,
    generate_segment_filename,
    generate_segment_id,
)


class TestSegmentIdGeneration:
    """Test segment ID generation."""

    def test_segment_id_format(self):
        """Segment ID should be part_NNNN with 4-digit zero-padding."""
        assert generate_segment_id(1) == "part_0001"
        assert generate_segment_id(10) == "part_0010"
        assert generate_segment_id(100) == "part_0100"
        assert generate_segment_id(1000) == "part_1000"
        assert generate_segment_id(9999) == "part_9999"

    def test_segment_id_starts_at_one(self):
        """First segment should be part_0001, not part_0000."""
        assert generate_segment_id(1) == "part_0001"


class TestSegmentFilenameGeneration:
    """Test segment filename generation."""

    def test_filename_format(self):
        """Filename should be <session_id>_part_NNNN.mp4."""
        session_id = "2026-01-19_21-45-00_gnosia_run01"
        assert generate_segment_filename(session_id, 1) == (
            "2026-01-19_21-45-00_gnosia_run01_part_0001.mp4"
        )
        assert generate_segment_filename(session_id, 42) == (
            "2026-01-19_21-45-00_gnosia_run01_part_0042.mp4"
        )

    def test_filename_extension_is_mp4(self):
        """Output should always be .mp4."""
        filename = generate_segment_filename("test_session", 1)
        assert filename.endswith(".mp4")


class TestCalculateSegments:
    """Test segment time calculation."""

    def test_exact_division(self):
        """Should handle exact division of duration."""
        segments = calculate_segments(120.0, 60)
        assert len(segments) == 2
        assert segments[0] == (0.0, 60.0)
        assert segments[1] == (60.0, 120.0)

    def test_remainder_segment(self):
        """Last segment should capture remaining time."""
        segments = calculate_segments(150.0, 60)
        assert len(segments) == 3
        assert segments[0] == (0.0, 60.0)
        assert segments[1] == (60.0, 120.0)
        assert segments[2] == (120.0, 150.0)

    def test_short_video(self):
        """Video shorter than segment duration should produce one segment."""
        segments = calculate_segments(30.0, 60)
        assert len(segments) == 1
        assert segments[0] == (0.0, 30.0)

    def test_empty_video(self):
        """Zero duration should produce no segments."""
        segments = calculate_segments(0.0, 60)
        assert len(segments) == 0


class TestBuildSegmentCommand:
    """Test ffmpeg command building."""

    def test_command_structure(self):
        """Command should have correct ffmpeg arguments."""
        cmd = build_segment_command(
            input_path=Path("/input/video.mp4"),
            output_path=Path("/output/segment.mp4"),
            start_time=60.0,
            duration=30.0,
        )

        # Should include overwrite flag
        assert "-y" in cmd

        # Should include start time
        ss_index = cmd.index("-ss")
        assert cmd[ss_index + 1] == "60.0"

        # Should include input
        i_index = cmd.index("-i")
        assert cmd[i_index + 1] == "/input/video.mp4"

        # Should include duration
        t_index = cmd.index("-t")
        assert cmd[t_index + 1] == "30.0"

        # Should use stream copy (no re-encoding)
        c_index = cmd.index("-c")
        assert cmd[c_index + 1] == "copy"

        # Should include output path at end
        assert cmd[-1] == "/output/segment.mp4"

    def test_command_seeks_before_input(self):
        """Seek (-ss) should come before input (-i) for fast seeking."""
        cmd = build_segment_command(
            input_path=Path("/input/video.mp4"),
            output_path=Path("/output/segment.mp4"),
            start_time=60.0,
            duration=30.0,
        )
        ss_index = cmd.index("-ss")
        i_index = cmd.index("-i")
        assert ss_index < i_index, "Seek should come before input for fast seeking"

    def test_command_avoids_negative_timestamps(self):
        """Should include avoid_negative_ts flag."""
        cmd = build_segment_command(
            input_path=Path("/input/video.mp4"),
            output_path=Path("/output/segment.mp4"),
            start_time=0.0,
            duration=30.0,
        )
        assert "-avoid_negative_ts" in cmd
        idx = cmd.index("-avoid_negative_ts")
        assert cmd[idx + 1] == "make_zero"
