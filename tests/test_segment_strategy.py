"""Tests for adaptive segment duration strategy."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from yanhu.watcher import (
    SEGMENT_STRATEGIES,
    RunQueueConfig,
    determine_segment_duration,
    get_video_duration,
)


class TestSegmentStrategies:
    """Test segment duration strategy definitions."""

    def test_strategies_exist(self):
        """Should have short, medium, long strategies."""
        assert "short" in SEGMENT_STRATEGIES
        assert "medium" in SEGMENT_STRATEGIES
        assert "long" in SEGMENT_STRATEGIES

    def test_strategy_values(self):
        """Should have correct duration values."""
        assert SEGMENT_STRATEGIES["short"] == 5
        assert SEGMENT_STRATEGIES["medium"] == 15
        assert SEGMENT_STRATEGIES["long"] == 30

    def test_short_less_than_medium(self):
        """Short should be less than medium."""
        assert SEGMENT_STRATEGIES["short"] < SEGMENT_STRATEGIES["medium"]
        assert SEGMENT_STRATEGIES["medium"] < SEGMENT_STRATEGIES["long"]


class TestGetVideoDuration:
    """Test get_video_duration with ffprobe."""

    @patch("subprocess.run")
    def test_get_duration_success(self, mock_run):
        """Should return duration from ffprobe."""
        mock_run.return_value = Mock(returncode=0, stdout="123.456\n")

        duration = get_video_duration(Path("/path/to/video.mp4"))

        assert duration == 123.456
        # Verify ffprobe was called
        assert mock_run.called
        args = mock_run.call_args[0][0]
        assert "ffprobe" in args
        assert "/path/to/video.mp4" in args

    @patch("subprocess.run")
    def test_get_duration_ffprobe_error(self, mock_run):
        """Should return 0 on ffprobe error."""
        mock_run.return_value = Mock(returncode=1, stdout="")

        duration = get_video_duration(Path("/path/to/video.mp4"))

        assert duration == 0

    @patch("subprocess.run")
    def test_get_duration_timeout(self, mock_run):
        """Should return 0 on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("ffprobe", 10)

        duration = get_video_duration(Path("/path/to/video.mp4"))

        assert duration == 0

    @patch("subprocess.run")
    def test_get_duration_invalid_output(self, mock_run):
        """Should return 0 on invalid output."""
        mock_run.return_value = Mock(returncode=0, stdout="not_a_number\n")

        duration = get_video_duration(Path("/path/to/video.mp4"))

        assert duration == 0


class TestDetermineSegmentDuration:
    """Test determine_segment_duration with different strategies."""

    def test_explicit_duration_takes_precedence(self):
        """Explicit duration should override strategy."""
        with patch("yanhu.watcher.get_video_duration", return_value=120):
            duration = determine_segment_duration(
                Path("/video.mp4"), strategy="auto", explicit_duration=42
            )

        assert duration == 42

    def test_short_strategy(self):
        """Short strategy should return 5s."""
        with patch("yanhu.watcher.get_video_duration", return_value=120):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="short")

        assert duration == 5

    def test_medium_strategy(self):
        """Medium strategy should return 15s."""
        with patch("yanhu.watcher.get_video_duration", return_value=120):
            duration = determine_segment_duration(
                Path("/video.mp4"), strategy="medium"
            )

        assert duration == 15

    def test_long_strategy(self):
        """Long strategy should return 30s."""
        with patch("yanhu.watcher.get_video_duration", return_value=120):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="long")

        assert duration == 30

    def test_auto_strategy_very_short_video(self):
        """Auto strategy for <=3min video should use 5s segments."""
        # Test various durations <= 180s
        test_cases = [30, 60, 120, 179, 180]
        for video_duration in test_cases:
            with patch("yanhu.watcher.get_video_duration", return_value=video_duration):
                duration = determine_segment_duration(
                    Path("/video.mp4"), strategy="auto"
                )

            assert (
                duration == 5
            ), f"Video {video_duration}s should use 5s segments (got {duration}s)"

    def test_auto_strategy_medium_video(self):
        """Auto strategy for <=15min video should use 15s segments."""
        # Test various durations > 180s and <= 900s
        test_cases = [181, 300, 600, 899, 900]
        for video_duration in test_cases:
            with patch("yanhu.watcher.get_video_duration", return_value=video_duration):
                duration = determine_segment_duration(
                    Path("/video.mp4"), strategy="auto"
                )

            assert (
                duration == 15
            ), f"Video {video_duration}s should use 15s segments (got {duration}s)"

    def test_auto_strategy_long_video(self):
        """Auto strategy for >15min video should use 30s segments."""
        # Test various durations > 900s
        test_cases = [901, 1800, 3600, 7200]
        for video_duration in test_cases:
            with patch("yanhu.watcher.get_video_duration", return_value=video_duration):
                duration = determine_segment_duration(
                    Path("/video.mp4"), strategy="auto"
                )

            assert (
                duration == 30
            ), f"Video {video_duration}s should use 30s segments (got {duration}s)"

    def test_auto_strategy_actor_clip_44s(self):
        """Auto strategy for 44s video (actor_clip) should use 5s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=44):
            duration = determine_segment_duration(Path("/actor_clip.mp4"), strategy="auto")

        assert duration == 5

    def test_auto_strategy_cannot_determine_duration(self):
        """Auto strategy should fallback to medium if duration unknown."""
        with patch("yanhu.watcher.get_video_duration", return_value=0):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 15  # Fallback to medium

    def test_unknown_strategy_defaults_to_medium(self):
        """Unknown strategy should default to medium."""
        with patch("yanhu.watcher.get_video_duration", return_value=120):
            duration = determine_segment_duration(
                Path("/video.mp4"), strategy="unknown"
            )

        assert duration == 15


class TestRunQueueConfigSegmentParams:
    """Test RunQueueConfig segment parameters."""

    def test_default_segment_strategy(self):
        """Default segment strategy should be auto."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"), output_dir=Path("/tmp/output")
        )

        assert config.segment_strategy == "auto"
        assert config.segment_duration is None

    def test_explicit_segment_duration(self):
        """Should allow explicit segment duration."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            segment_duration=10,
        )

        assert config.segment_duration == 10

    def test_resolve_config_includes_segment_params(self):
        """Resolved config should include segment parameters."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            segment_duration=20,
            segment_strategy="short",
        )

        resolved = config.resolve_config()

        assert resolved["segment_duration"] == 20
        assert resolved["segment_strategy"] == "short"

    def test_resolve_config_segment_defaults(self):
        """Resolved config should include segment defaults."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"), output_dir=Path("/tmp/output")
        )

        resolved = config.resolve_config()

        assert resolved["segment_duration"] is None
        assert resolved["segment_strategy"] == "auto"


class TestSegmentStrategyThresholds:
    """Test specific duration thresholds for auto strategy."""

    def test_threshold_120s_uses_5s(self):
        """120s video (2 minutes) should use 5s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=120):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 5

    def test_threshold_600s_uses_15s(self):
        """600s video (10 minutes) should use 15s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=600):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 15

    def test_threshold_3600s_uses_30s(self):
        """3600s video (1 hour) should use 30s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=3600):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 30

    def test_boundary_180s_uses_5s(self):
        """180s (exactly 3 minutes) should use 5s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=180):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 5

    def test_boundary_181s_uses_15s(self):
        """181s (just over 3 minutes) should use 15s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=181):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 15

    def test_boundary_900s_uses_15s(self):
        """900s (exactly 15 minutes) should use 15s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=900):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 15

    def test_boundary_901s_uses_30s(self):
        """901s (just over 15 minutes) should use 30s segments."""
        with patch("yanhu.watcher.get_video_duration", return_value=901):
            duration = determine_segment_duration(Path("/video.mp4"), strategy="auto")

        assert duration == 30
