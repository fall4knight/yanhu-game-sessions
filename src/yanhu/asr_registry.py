"""ASR model registry and validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AsrModelInfo:
    """Information about a registered ASR model."""

    key: str  # Unique identifier (e.g., "whisper_local", "mock")
    display_name: str  # Human-readable name
    description: str  # Brief description
    requires_deps: list[str]  # Required dependencies (e.g., ["faster-whisper"])


# Registry of available ASR models
ASR_MODELS: dict[str, AsrModelInfo] = {
    "mock": AsrModelInfo(
        key="mock",
        display_name="Mock ASR",
        description="Mock ASR backend for testing (uses OCR data)",
        requires_deps=[],
    ),
    "whisper_local": AsrModelInfo(
        key="whisper_local",
        display_name="Whisper (Local)",
        description="Local Whisper ASR using faster-whisper or openai-whisper",
        requires_deps=["faster-whisper or openai-whisper"],
    ),
}

# Default ASR models (used if not specified)
DEFAULT_ASR_MODELS = ["mock"]


def validate_asr_models(models: list[str]) -> tuple[bool, str | None]:
    """Validate a list of ASR model keys.

    Args:
        models: List of model keys to validate

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is None.
        If invalid, error_message contains the reason.
    """
    if not models:
        return False, "No ASR models specified"

    for model in models:
        if model not in ASR_MODELS:
            available = ", ".join(sorted(ASR_MODELS.keys()))
            return False, f"Unknown ASR model: '{model}'. Available: {available}"

    # Check for duplicates
    if len(models) != len(set(models)):
        return False, f"Duplicate ASR models: {models}"

    return True, None


def get_asr_model_info(key: str) -> AsrModelInfo | None:
    """Get information about an ASR model.

    Args:
        key: Model key

    Returns:
        Model info, or None if not found
    """
    return ASR_MODELS.get(key)


def list_asr_models() -> list[AsrModelInfo]:
    """List all registered ASR models.

    Returns:
        List of model info objects
    """
    return list(ASR_MODELS.values())
