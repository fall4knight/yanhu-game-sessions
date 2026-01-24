"""ASR transcription for video segments."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from yanhu.analyzer import OcrItem
from yanhu.manifest import Manifest, SegmentInfo


@dataclass
class AsrItem:
    """A single ASR transcription item with timestamps."""

    text: str
    t_start: float  # Start time in seconds (relative to session)
    t_end: float  # End time in seconds (relative to session)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "t_start": self.t_start,
            "t_end": self.t_end,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AsrItem":
        return cls(
            text=data["text"],
            t_start=data["t_start"],
            t_end=data["t_end"],
        )


@dataclass
class AsrConfig:
    """Configuration for ASR transcription (for reproducibility)."""

    device: str = "cpu"
    compute_type: str = "int8"
    model_size: str = "base"
    language: str | None = None
    beam_size: int = 5
    vad_filter: bool = True

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "compute_type": self.compute_type,
            "model_size": self.model_size,
            "language": self.language,
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AsrConfig":
        return cls(
            device=data.get("device", "cpu"),
            compute_type=data.get("compute_type", "int8"),
            model_size=data.get("model_size", "base"),
            language=data.get("language"),
            beam_size=data.get("beam_size", 5),
            vad_filter=data.get("vad_filter", True),
        )


@dataclass
class AsrResult:
    """Result of ASR transcription for a segment."""

    segment_id: str
    asr_items: list[AsrItem] = field(default_factory=list)
    asr_backend: str = "mock"
    asr_error: str | None = None
    asr_config: AsrConfig | None = None

    def to_dict(self) -> dict:
        result = {
            "asr_backend": self.asr_backend,
        }
        if self.asr_items:
            result["asr_items"] = [item.to_dict() for item in self.asr_items]
        if self.asr_error:
            result["asr_error"] = self.asr_error
        if self.asr_config:
            result["asr_config"] = self.asr_config.to_dict()
        return result


class AsrBackend(Protocol):
    """Protocol for ASR backends."""

    def transcribe_segment(
        self,
        segment: SegmentInfo,
        session_dir: Path,
        max_seconds: int | None = None,
    ) -> AsrResult:
        """Transcribe a single segment.

        Args:
            segment: Segment info
            session_dir: Path to session directory
            max_seconds: Optional limit on audio duration to transcribe

        Returns:
            ASR result with transcription items
        """
        ...


class MockAsrBackend:
    """Mock ASR backend that generates fake transcription from OCR data."""

    def transcribe_segment(
        self,
        segment: SegmentInfo,
        session_dir: Path,
        max_seconds: int | None = None,
    ) -> AsrResult:
        """Generate mock ASR items from existing OCR data.

        Uses ocr_items or ui_key_text from analysis to create fake ASR items
        with monotonically increasing timestamps covering the segment duration.
        """
        analysis_path = session_dir / "analysis" / f"{segment.id}.json"

        # Try to load existing analysis
        ocr_items: list[OcrItem] = []
        ui_key_text: list[str] = []

        if analysis_path.exists():
            try:
                with open(analysis_path, encoding="utf-8") as f:
                    data = json.load(f)
                ocr_items = [OcrItem.from_dict(item) for item in data.get("ocr_items", [])]
                ui_key_text = data.get("ui_key_text", [])
            except (json.JSONDecodeError, KeyError):
                pass

        # Generate ASR items from OCR data
        asr_items: list[AsrItem] = []
        segment_duration = segment.end_time - segment.start_time

        if ocr_items:
            # Use ocr_items with their t_rel timestamps
            for ocr_item in ocr_items:
                # t_rel is already relative to session start
                t_start = ocr_item.t_rel
                # Estimate duration: 2 seconds per item or until next item
                t_end = min(t_start + 2.0, segment.end_time)
                asr_items.append(
                    AsrItem(
                        text=ocr_item.text,
                        t_start=round(t_start, 2),
                        t_end=round(t_end, 2),
                    )
                )
        elif ui_key_text:
            # Fall back to ui_key_text with evenly distributed timestamps
            num_items = len(ui_key_text)
            interval = segment_duration / max(num_items, 1)
            for i, text in enumerate(ui_key_text):
                t_start = segment.start_time + i * interval
                t_end = min(t_start + interval, segment.end_time)
                asr_items.append(
                    AsrItem(
                        text=text,
                        t_start=round(t_start, 2),
                        t_end=round(t_end, 2),
                    )
                )
        else:
            # No OCR data available - create single placeholder
            asr_items.append(
                AsrItem(
                    text="[无字幕]",
                    t_start=round(segment.start_time, 2),
                    t_end=round(segment.end_time, 2),
                )
            )

        # Ensure monotonically increasing timestamps
        asr_items = _ensure_monotonic(asr_items)

        return AsrResult(
            segment_id=segment.id,
            asr_items=asr_items,
            asr_backend="mock",
        )


class WhisperLocalBackend:
    """Local Whisper ASR backend using faster-whisper or openai-whisper.

    Requires:
    - ffmpeg for audio extraction
    - faster-whisper or whisper Python package

    Audio files are extracted to sessions/<id>/audio/<seg>.wav
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str | None = None,
        vad_filter: bool = True,
        force_audio: bool = False,
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 5,
    ):
        """Initialize Whisper backend.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            language: Language code (e.g., "zh", "en") or None for auto-detect
            vad_filter: Enable VAD filter for better results (default True)
            force_audio: Force re-extract audio even if cached
            device: Device for inference ("cpu", "cuda", "auto")
            compute_type: Quantization type ("int8", "float16", "float32")
            beam_size: Beam size for decoding (default 5)
        """
        self.model_size = model_size
        self.language = language
        self.vad_filter = vad_filter
        self.force_audio = force_audio
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self._model = None
        self._backend_type: str | None = None

    def _extract_audio(
        self, segment: SegmentInfo, session_dir: Path
    ) -> tuple[Path | None, str | None]:
        """Extract audio from video segment to WAV file.

        Args:
            segment: Segment info with video path
            session_dir: Session directory

        Returns:
            Tuple of (audio_path, error_message)
        """
        audio_dir = session_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        video_path = session_dir / segment.video_path
        audio_path = audio_dir / f"{segment.id}.wav"

        # Use cached audio if exists and not forcing
        if audio_path.exists() and not self.force_audio:
            return audio_path, None

        if not video_path.exists():
            return None, f"Video file not found: {video_path}"

        try:
            # Extract audio using ffmpeg
            # -vn: no video, -ac 1: mono, -ar 16000: 16kHz, -f wav: WAV format
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(audio_path),
            ]
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
            return audio_path, None
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            return None, f"ffmpeg failed: {stderr[:200]}"
        except FileNotFoundError:
            return None, "ffmpeg not found. Install ffmpeg to use whisper_local backend."

    def _load_model(self) -> str | None:
        """Load Whisper model (lazy initialization).

        Returns:
            Error message if loading failed, None on success.
        """
        if self._model is not None:
            return None

        # Try faster-whisper first, fall back to openai-whisper
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._backend_type = "faster_whisper"
            return None
        except ImportError:
            pass

        try:
            import whisper

            self._model = whisper.load_model(self.model_size)
            self._backend_type = "openai_whisper"
            return None
        except ImportError:
            pass

        return (
            "Neither faster-whisper nor openai-whisper is installed. "
            "Install with: pip install 'yanhu-game-sessions[asr]'"
        )

    def _get_asr_config(self) -> AsrConfig:
        """Create AsrConfig from current settings."""
        return AsrConfig(
            device=self.device,
            compute_type=self.compute_type,
            model_size=self.model_size,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
        )

    def transcribe_segment(
        self,
        segment: SegmentInfo,
        session_dir: Path,
        max_seconds: int | None = None,
    ) -> AsrResult:
        """Transcribe a segment using local Whisper model.

        Args:
            segment: Segment info
            session_dir: Session directory
            max_seconds: Optional limit on audio duration

        Returns:
            ASR result with transcription items
        """
        asr_config = self._get_asr_config()

        # Extract audio
        audio_path, audio_error = self._extract_audio(segment, session_dir)
        if audio_path is None:
            return AsrResult(
                segment_id=segment.id,
                asr_backend="whisper_local",
                asr_error=audio_error or "Failed to extract audio",
                asr_config=asr_config,
            )

        # Load model
        model_error = self._load_model()
        if model_error:
            return AsrResult(
                segment_id=segment.id,
                asr_backend="whisper_local",
                asr_error=model_error,
                asr_config=asr_config,
            )

        # Transcribe
        try:
            asr_items = self._transcribe_audio(audio_path, segment.start_time, max_seconds)
            # Ensure monotonic timestamps
            asr_items = _ensure_monotonic(asr_items)
            return AsrResult(
                segment_id=segment.id,
                asr_items=asr_items,
                asr_backend="whisper_local",
                asr_config=asr_config,
            )
        except Exception as e:
            return AsrResult(
                segment_id=segment.id,
                asr_backend="whisper_local",
                asr_error=f"Transcription failed: {e}",
                asr_config=asr_config,
            )

    def _transcribe_audio(
        self,
        audio_path: Path,
        segment_start: float,
        max_seconds: int | None = None,
    ) -> list[AsrItem]:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file
            segment_start: Start time of segment (for absolute timestamps)
            max_seconds: Optional limit on duration

        Returns:
            List of ASR items with timestamps
        """
        asr_items: list[AsrItem] = []

        if self._backend_type == "faster_whisper":
            # faster-whisper API
            transcribe_opts: dict = {
                "vad_filter": self.vad_filter,
                "beam_size": self.beam_size,
            }
            if self.language:
                transcribe_opts["language"] = self.language

            segments, _ = self._model.transcribe(
                str(audio_path),
                **transcribe_opts,
            )
            for seg in segments:
                if max_seconds and seg.start > max_seconds:
                    break
                text = seg.text.strip()
                if text:  # Skip empty segments
                    asr_items.append(
                        AsrItem(
                            text=text,
                            t_start=round(segment_start + seg.start, 2),
                            t_end=round(segment_start + seg.end, 2),
                        )
                    )
        else:  # openai_whisper
            transcribe_opts: dict = {
                "beam_size": self.beam_size,
            }
            if self.language:
                transcribe_opts["language"] = self.language

            result = self._model.transcribe(
                str(audio_path),
                **transcribe_opts,
            )
            for seg in result.get("segments", []):
                if max_seconds and seg["start"] > max_seconds:
                    break
                text = seg["text"].strip()
                if text:  # Skip empty segments
                    asr_items.append(
                        AsrItem(
                            text=text,
                            t_start=round(segment_start + seg["start"], 2),
                            t_end=round(segment_start + seg["end"], 2),
                        )
                    )

        return asr_items


def _ensure_monotonic(items: list[AsrItem]) -> list[AsrItem]:
    """Ensure ASR items have monotonically increasing timestamps.

    Args:
        items: List of ASR items

    Returns:
        List with corrected timestamps (t_start <= t_end, overall increasing)
    """
    if not items:
        return items

    result: list[AsrItem] = []
    prev_end = 0.0

    for item in items:
        # Ensure t_start >= prev_end
        t_start = max(item.t_start, prev_end)
        # Ensure t_end >= t_start
        t_end = max(item.t_end, t_start + 0.1)

        result.append(
            AsrItem(
                text=item.text,
                t_start=round(t_start, 2),
                t_end=round(t_end, 2),
            )
        )
        prev_end = t_end

    return result


def get_asr_backend(
    backend: str,
    model_size: str = "base",
    language: str | None = None,
    vad_filter: bool = True,
    force_audio: bool = False,
    device: str = "cpu",
    compute_type: str = "int8",
    beam_size: int = 5,
) -> AsrBackend:
    """Get ASR backend by name.

    Args:
        backend: Backend name ("mock" or "whisper_local")
        model_size: Whisper model size (for whisper_local)
        language: Language code (for whisper_local, None = auto)
        vad_filter: Enable VAD filter (for whisper_local)
        force_audio: Force re-extract audio (for whisper_local)
        device: Device for inference ("cpu", "cuda", "auto")
        compute_type: Quantization type ("int8", "float16", "float32")
        beam_size: Beam size for decoding (default 5)

    Returns:
        ASR backend instance

    Raises:
        ValueError: If backend is unknown
    """
    if backend == "mock":
        return MockAsrBackend()
    elif backend == "whisper_local":
        return WhisperLocalBackend(
            model_size=model_size,
            language=language,
            vad_filter=vad_filter,
            force_audio=force_audio,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
        )
    else:
        raise ValueError(f"Unknown ASR backend: {backend}")


@dataclass
class TranscribeStats:
    """Statistics from transcribe_session."""

    processed: int = 0
    skipped_cache: int = 0
    skipped_filter: int = 0
    skipped_limit: int = 0  # Skipped due to limit constraints
    errors: int = 0
    total: int = 0  # Total segments considered


def merge_asr_to_analysis(
    asr_result: AsrResult,
    analysis_path: Path,
    segment: SegmentInfo,
) -> None:
    """Merge ASR result into existing analysis JSON.

    If analysis file exists, load it and merge ASR fields.
    If not, create minimal analysis with ASR fields.

    Args:
        asr_result: ASR transcription result
        analysis_path: Path to analysis JSON file
        segment: Segment info (for creating minimal analysis)
    """
    # Load existing analysis or create minimal
    if analysis_path.exists():
        try:
            with open(analysis_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    # Ensure minimal fields
    if "segment_id" not in data:
        data["segment_id"] = segment.id
    if "scene_type" not in data:
        data["scene_type"] = "unknown"
    if "caption" not in data:
        data["caption"] = ""

    # Merge ASR fields
    asr_dict = asr_result.to_dict()
    data.update(asr_dict)

    # Write back
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def transcribe_session(
    manifest: Manifest,
    session_dir: Path,
    backend: str = "mock",
    max_seconds: int | None = None,
    force: bool = False,
    limit: int | None = None,
    max_total_seconds: float | None = None,
    segments: list[str] | None = None,
    on_progress: Callable[[str, str, AsrResult | None, TranscribeStats | None], None] | None = None,
    # Whisper-specific options
    model_size: str = "base",
    language: str | None = None,
    vad_filter: bool = True,
    device: str = "cpu",
    compute_type: str = "int8",
    beam_size: int = 5,
) -> TranscribeStats:
    """Transcribe all segments in a session.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory
        backend: ASR backend ("mock" or "whisper_local")
        max_seconds: Optional limit on audio duration per segment
        force: Re-transcribe even if ASR data exists
        limit: Only process first N segments
        max_total_seconds: Optional limit on total transcription duration
            (stops when cumulative duration exceeds this)
        segments: Optional list of segment IDs to process
        on_progress: Callback(segment_id, status, result, stats) - called after each segment
        model_size: Whisper model size (for whisper_local)
        language: Language code (for whisper_local, None = auto)
        vad_filter: Enable VAD filter (for whisper_local)
        device: Device for inference ("cpu", "cuda", "auto")
        compute_type: Quantization type ("int8", "float16", "float32")
        beam_size: Beam size for decoding (default 5)

    Returns:
        Transcription statistics
    """
    asr_backend = get_asr_backend(
        backend,
        model_size=model_size,
        language=language,
        vad_filter=vad_filter,
        force_audio=force,
        device=device,
        compute_type=compute_type,
        beam_size=beam_size,
    )
    stats = TranscribeStats()
    stats.total = len(manifest.segments)
    cumulative_duration = 0.0  # Track total transcribed duration

    for i, segment in enumerate(manifest.segments):
        # Apply segment count limit
        if limit is not None and i >= limit:
            # Mark remaining segments as skipped due to limit
            stats.skipped_limit = stats.total - i
            if on_progress:
                on_progress("", "limit_reached", None, stats)
            break

        # Apply filter
        if segments is not None and segment.id not in segments:
            stats.skipped_filter += 1
            continue

        # Apply total duration limit
        if max_total_seconds is not None and cumulative_duration >= max_total_seconds:
            stats.skipped_limit = stats.total - i
            if on_progress:
                on_progress("", "duration_limit_reached", None, stats)
            break

        # Check cache
        analysis_path = session_dir / "analysis" / f"{segment.id}.json"
        if not force and analysis_path.exists():
            try:
                with open(analysis_path, encoding="utf-8") as f:
                    data = json.load(f)
                if "asr_items" in data or "asr_error" in data:
                    stats.skipped_cache += 1
                    if on_progress:
                        on_progress(segment.id, "cached", None, stats)
                    continue
            except (json.JSONDecodeError, OSError):
                pass

        # Transcribe
        try:
            result = asr_backend.transcribe_segment(segment, session_dir, max_seconds)

            # Merge into analysis
            merge_asr_to_analysis(result, analysis_path, segment)

            if result.asr_error:
                stats.errors += 1
                if on_progress:
                    on_progress(segment.id, "error", result, stats)
            else:
                stats.processed += 1
                # Update cumulative duration
                segment_duration = segment.end_time - segment.start_time
                cumulative_duration += segment_duration
                if on_progress:
                    on_progress(segment.id, "done", result, stats)

        except Exception as e:
            stats.errors += 1
            error_result = AsrResult(
                segment_id=segment.id,
                asr_backend=backend,
                asr_error=str(e),
            )
            merge_asr_to_analysis(error_result, analysis_path, segment)
            if on_progress:
                on_progress(segment.id, "error", error_result, stats)

    return stats
