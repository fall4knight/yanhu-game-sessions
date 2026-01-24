"""Tests for preset configurations and parameter overrides."""

from pathlib import Path

from yanhu.watcher import PRESETS, RunQueueConfig, get_preset_config


class TestPresetConfigurations:
    """Test preset definitions."""

    def test_presets_exist(self):
        """Should have fast and quality presets."""
        assert "fast" in PRESETS
        assert "quality" in PRESETS

    def test_fast_preset_params(self):
        """Fast preset should have conservative parameters."""
        fast = get_preset_config("fast")
        assert fast["max_frames"] == 3
        assert fast["max_facts"] == 3
        assert fast["detail_level"] == "L1"
        assert fast["transcribe_backend"] == "whisper_local"
        assert fast["transcribe_model"] == "base"
        assert fast["transcribe_compute"] == "int8"
        assert fast["transcribe_beam_size"] == 1
        assert fast["transcribe_vad_filter"] is True

    def test_quality_preset_params(self):
        """Quality preset should have better parameters."""
        quality = get_preset_config("quality")
        assert quality["max_frames"] == 6
        assert quality["max_facts"] == 5
        assert quality["detail_level"] == "L1"
        assert quality["transcribe_backend"] == "whisper_local"
        assert quality["transcribe_model"] == "small"
        assert quality["transcribe_compute"] == "float32"
        assert quality["transcribe_beam_size"] == 5
        assert quality["transcribe_vad_filter"] is True

    def test_quality_better_than_fast(self):
        """Quality should have higher quality params than fast."""
        fast = get_preset_config("fast")
        quality = get_preset_config("quality")

        assert quality["max_frames"] > fast["max_frames"]
        assert quality["max_facts"] > fast["max_facts"]
        assert quality["transcribe_beam_size"] > fast["transcribe_beam_size"]

    def test_invalid_preset_raises(self):
        """Should raise for unknown preset."""
        import pytest

        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset_config("invalid")


class TestRunQueueConfigResolve:
    """Test RunQueueConfig.resolve_config()."""

    def test_resolve_fast_preset_default(self):
        """Should use fast preset by default."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"), output_dir=Path("/tmp/output")
        )
        resolved = config.resolve_config()

        assert resolved["preset"] == "fast"
        assert resolved["max_frames"] == 3
        assert resolved["max_facts"] == 3
        assert resolved["transcribe_model"] == "base"

    def test_resolve_quality_preset(self):
        """Should use quality preset when specified."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            preset="quality",
        )
        resolved = config.resolve_config()

        assert resolved["preset"] == "quality"
        assert resolved["max_frames"] == 6
        assert resolved["max_facts"] == 5
        assert resolved["transcribe_model"] == "small"
        assert resolved["transcribe_compute"] == "float32"

    def test_override_max_frames(self):
        """Should override max_frames from preset."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            preset="fast",
            max_frames=10,  # Override
        )
        resolved = config.resolve_config()

        assert resolved["max_frames"] == 10  # Overridden
        assert resolved["max_facts"] == 3  # Still from preset

    def test_override_multiple_params(self):
        """Should override multiple parameters."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            preset="fast",
            max_frames=8,
            max_facts=6,
            transcribe_model="small",
        )
        resolved = config.resolve_config()

        assert resolved["max_frames"] == 8
        assert resolved["max_facts"] == 6
        assert resolved["transcribe_model"] == "small"
        assert resolved["transcribe_compute"] == "int8"  # Still from fast preset

    def test_override_quality_to_fast_model(self):
        """Should allow overriding quality preset to use fast model."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            preset="quality",
            transcribe_model="base",  # Override to fast model
        )
        resolved = config.resolve_config()

        assert resolved["preset"] == "quality"
        assert resolved["max_frames"] == 6  # From quality
        assert resolved["transcribe_model"] == "base"  # Overridden
        assert resolved["transcribe_compute"] == "float32"  # Still from quality

    def test_resolved_config_includes_source_mode(self):
        """Should include source_mode in resolved config."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            source_mode="copy",
        )
        resolved = config.resolve_config()

        assert resolved["source_mode"] == "copy"

    def test_none_overrides_use_preset(self):
        """None overrides should use preset values."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"),
            output_dir=Path("/tmp/output"),
            preset="quality",
            max_frames=None,  # Explicitly None
            max_facts=None,
        )
        resolved = config.resolve_config()

        # Should use quality preset values
        assert resolved["max_frames"] == 6
        assert resolved["max_facts"] == 5


class TestPresetIntegration:
    """Test preset integration with process_job."""

    def test_run_config_has_all_expected_fields(self):
        """Resolved config should have all expected fields."""
        config = RunQueueConfig(
            queue_dir=Path("/tmp/queue"), output_dir=Path("/tmp/output")
        )
        resolved = config.resolve_config()

        # Analysis fields
        assert "max_frames" in resolved
        assert "max_facts" in resolved
        assert "detail_level" in resolved

        # Transcribe fields
        assert "transcribe_backend" in resolved
        assert "transcribe_model" in resolved
        assert "transcribe_compute" in resolved
        assert "transcribe_beam_size" in resolved
        assert "transcribe_vad_filter" in resolved

        # Metadata
        assert "preset" in resolved
        assert "source_mode" in resolved

    def test_fast_preset_for_quick_processing(self):
        """Fast preset should be optimized for speed."""
        fast = get_preset_config("fast")

        # Fast should use smaller model and int8 for speed
        assert fast["transcribe_model"] == "base"
        assert fast["transcribe_compute"] == "int8"
        assert fast["transcribe_beam_size"] == 1  # Faster
        assert fast["max_frames"] <= 3  # Fewer frames to process

    def test_quality_preset_for_better_results(self):
        """Quality preset should be optimized for quality."""
        quality = get_preset_config("quality")

        # Quality should use better model and float32 for accuracy
        assert quality["transcribe_model"] == "small"
        assert quality["transcribe_compute"] == "float32"
        assert quality["transcribe_beam_size"] == 5  # More thorough
        assert quality["max_frames"] >= 6  # More frames for analysis
