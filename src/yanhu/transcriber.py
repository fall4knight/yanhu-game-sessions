"""ASR transcription for video segments."""

from __future__ import annotations

import json
import subprocess
import threading
import time
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
        session_id: str | None = None,
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

    def _check_model_cached(self) -> bool:
        """Check if Whisper model is already cached locally.

        Returns:
            True if model is cached, False if needs download
        """
        try:
            from pathlib import Path

            # Check faster-whisper cache location
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            if not cache_dir.exists():
                return False

            # Model names in huggingface format
            model_name = f"models--Systran--faster-whisper-{self.model_size}"
            model_path = cache_dir / model_name

            return model_path.exists()
        except Exception:
            # If we can't determine, assume not cached (will trigger progress)
            return False

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
            # Find ffmpeg executable (supports packaged apps without PATH)
            from yanhu.ffmpeg_utils import find_ffmpeg
            ffmpeg_path = find_ffmpeg()
            if not ffmpeg_path:
                return None, "ffmpeg not found. Install ffmpeg to use whisper_local backend."

            # Extract audio using ffmpeg
            # -vn: no video, -ac 1: mono, -ar 16000: 16kHz, -f wav: WAV format
            cmd = [
                ffmpeg_path,
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

    def _load_model(
        self, session_id: str | None = None, session_dir: Path | None = None
    ) -> str | None:
        """Load Whisper model (lazy initialization with download progress).

        Args:
            session_id: Session ID for progress tracking
            session_dir: Session directory for progress.json

        Returns:
            Error message if loading failed, None on success.
        """
        if self._model is not None:
            return None

        # Check if model needs download and create progress tracker
        model_cached = self._check_model_cached()
        progress_tracker = None

        if not model_cached and session_id and session_dir:
            from yanhu.progress import ProgressTracker

            # Model sizes (approximate, for display only)
            model_sizes = {
                "tiny": "75 MB",
                "base": "145 MB",
                "small": "490 MB",
                "medium": "1.5 GB",
                "large": "3.0 GB",
            }
            size_str = model_sizes.get(self.model_size, "unknown size")

            progress_tracker = ProgressTracker(
                session_id=session_id,
                session_dir=session_dir,
                stage="download_model",
                total=1,
                message=f"Downloading Whisper model '{self.model_size}' (~{size_str}). "
                "This may take a few minutes on first run...",
            )

        # Try faster-whisper first, fall back to openai-whisper
        # Collect errors from each backend attempt for diagnostics
        load_errors: list[str] = []

        try:
            from faster_whisper import WhisperModel

            # If downloading, start a background thread to update progress
            if progress_tracker:
                stop_event = threading.Event()

                def update_download_progress():
                    """Update progress message periodically during download."""
                    elapsed = 0
                    while not stop_event.is_set():
                        time.sleep(2)
                        elapsed += 2
                        if not stop_event.is_set():
                            progress_tracker.update(
                                done=0,
                                message=f"Downloading Whisper model '{self.model_size}'... "
                                f"({elapsed}s elapsed)",
                            )

                progress_thread = threading.Thread(target=update_download_progress, daemon=True)
                progress_thread.start()

                try:
                    self._model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
                finally:
                    stop_event.set()
                    progress_thread.join(timeout=1)
                    # Mark download complete
                    progress_tracker.update(
                        done=1, message=f"Model '{self.model_size}' ready"
                    )
            else:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )

            self._backend_type = "faster_whisper"
            return None
        except ImportError:
            load_errors.append("faster-whisper: not installed")
        except Exception as e:
            # Capture initialization errors (CUDA, DLL, model download, etc.)
            load_errors.append(f"faster-whisper: {type(e).__name__}: {e}")

        try:
            import whisper

            self._model = whisper.load_model(self.model_size)
            self._backend_type = "openai_whisper"
            return None
        except ImportError:
            load_errors.append("openai-whisper: not installed")
        except Exception as e:
            # Capture initialization errors
            load_errors.append(f"openai-whisper: {type(e).__name__}: {e}")

        # If we get here, both backends failed
        # Return detailed error message with all collected errors
        return f"ASR model load failed: {'; '.join(load_errors)}"

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
        session_id: str | None = None,
    ) -> AsrResult:
        """Transcribe a segment using local Whisper model.

        Args:
            segment: Segment info
            session_dir: Session directory
            max_seconds: Optional limit on audio duration
            session_id: Optional session ID for progress tracking

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

        # Load model (with download progress if needed)
        model_error = self._load_model(session_id=session_id, session_dir=session_dir)
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


def save_asr_result_per_model(
    asr_result: AsrResult,
    session_dir: Path,
    model_key: str,
) -> None:
    """Save ASR result to per-model transcript file.

    Saves to: <session_dir>/outputs/asr/<model_key>/transcript.json

    Format: List of per-segment results:
    [
        {"segment_id": "part_0001", "asr_items": [...], "asr_backend": "...", ...},
        {"segment_id": "part_0002", "asr_items": [...], ...},
    ]

    Args:
        asr_result: ASR transcription result
        session_dir: Path to session directory
        model_key: Model identifier (e.g., "whisper_local", "mock")
    """
    asr_dir = session_dir / "outputs" / "asr" / model_key
    asr_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = asr_dir / "transcript.json"

    # Load existing transcript or create new
    results: list[dict] = []
    if transcript_path.exists():
        try:
            with open(transcript_path, encoding="utf-8") as f:
                results = json.load(f)
        except (json.JSONDecodeError, OSError):
            results = []

    # Update or append result for this segment
    result_dict = asr_result.to_dict()
    result_dict["segment_id"] = asr_result.segment_id

    # Find and update existing entry, or append new
    updated = False
    for i, r in enumerate(results):
        if r.get("segment_id") == asr_result.segment_id:
            results[i] = result_dict
            updated = True
            break
    if not updated:
        results.append(result_dict)

    # Write back
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


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
    # Multi-model support
    asr_models: list[str] | None = None,
) -> TranscribeStats:
    """Transcribe all segments in a session.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory
        backend: ASR backend ("mock" or "whisper_local") - deprecated, use asr_models
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
        asr_models: List of ASR models to run (e.g., ["whisper_local", "mock"])
            If None, uses backend parameter for backward compatibility

    Returns:
        Transcription statistics
    """
    # Determine which models to run
    if asr_models is None:
        # Backward compatibility: use backend parameter
        models_to_run = [backend]
    else:
        models_to_run = asr_models

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

        # Check cache (only for primary model in analysis/)
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

        # Transcribe with all models
        segment_has_error = False
        for model_idx, model_key in enumerate(models_to_run):
            is_primary = model_idx == 0

            try:
                # Get backend for this model
                model_backend = get_asr_backend(
                    model_key,
                    model_size=model_size,
                    language=language,
                    vad_filter=vad_filter,
                    force_audio=force,
                    device=device,
                    compute_type=compute_type,
                    beam_size=beam_size,
                )

                # Transcribe (pass session_id for progress tracking)
                result = model_backend.transcribe_segment(
                    segment, session_dir, max_seconds, session_id=manifest.session_id
                )

                # Save to per-model transcript
                save_asr_result_per_model(result, session_dir, model_key)

                # If this is the primary model, also merge into analysis/
                if is_primary:
                    merge_asr_to_analysis(result, analysis_path, segment)

                if result.asr_error:
                    segment_has_error = True

            except Exception as e:
                segment_has_error = True
                error_result = AsrResult(
                    segment_id=segment.id,
                    asr_backend=model_key,
                    asr_error=str(e),
                )
                # Save error to per-model transcript
                save_asr_result_per_model(error_result, session_dir, model_key)

                # If this is the primary model, also merge into analysis/
                if is_primary:
                    merge_asr_to_analysis(error_result, analysis_path, segment)

        # Update stats (count once per segment, not per model)
        if segment_has_error:
            stats.errors += 1
            if on_progress:
                on_progress(segment.id, "error", None, stats)
        else:
            stats.processed += 1
            # Update cumulative duration
            segment_duration = segment.end_time - segment.start_time
            cumulative_duration += segment_duration
            if on_progress:
                on_progress(segment.id, "done", None, stats)

    return stats
