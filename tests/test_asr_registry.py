"""Tests for ASR model registry."""

from yanhu.asr_registry import (
    ASR_MODELS,
    DEFAULT_ASR_MODELS,
    get_asr_model_info,
    list_asr_models,
    validate_asr_models,
)


class TestAsrModelRegistry:
    """Test ASR model registry."""

    def test_default_models_exist(self):
        """Default models should exist in registry."""
        for model in DEFAULT_ASR_MODELS:
            assert model in ASR_MODELS

    def test_registry_has_required_models(self):
        """Registry should contain mock and whisper_local."""
        assert "mock" in ASR_MODELS
        assert "whisper_local" in ASR_MODELS

    def test_get_asr_model_info_valid(self):
        """Get info for valid model."""
        info = get_asr_model_info("mock")
        assert info is not None
        assert info.key == "mock"
        assert info.display_name == "Mock ASR"
        assert len(info.description) > 0

    def test_get_asr_model_info_invalid(self):
        """Get info for invalid model returns None."""
        info = get_asr_model_info("nonexistent")
        assert info is None

    def test_list_asr_models(self):
        """List all models."""
        models = list_asr_models()
        assert len(models) >= 2
        keys = [m.key for m in models]
        assert "mock" in keys
        assert "whisper_local" in keys


class TestValidateAsrModels:
    """Test validate_asr_models function."""

    def test_validate_single_valid_model(self):
        """Valid single model."""
        is_valid, error = validate_asr_models(["mock"])
        assert is_valid
        assert error is None

    def test_validate_multiple_valid_models(self):
        """Valid multiple models."""
        is_valid, error = validate_asr_models(["mock", "whisper_local"])
        assert is_valid
        assert error is None

    def test_validate_empty_list(self):
        """Empty list is invalid."""
        is_valid, error = validate_asr_models([])
        assert not is_valid
        assert "No ASR models specified" in error

    def test_validate_unknown_model(self):
        """Unknown model is invalid."""
        is_valid, error = validate_asr_models(["unknown_model"])
        assert not is_valid
        assert "Unknown ASR model" in error
        assert "unknown_model" in error

    def test_validate_duplicate_models(self):
        """Duplicate models are invalid."""
        is_valid, error = validate_asr_models(["mock", "mock"])
        assert not is_valid
        assert "Duplicate ASR models" in error

    def test_validate_mixed_valid_invalid(self):
        """Mix of valid and invalid models fails."""
        is_valid, error = validate_asr_models(["mock", "invalid", "whisper_local"])
        assert not is_valid
        assert "Unknown ASR model" in error
        assert "invalid" in error
