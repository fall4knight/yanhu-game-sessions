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
class AsrResult:
    """Result of ASR transcription for a segment."""

    segment_id: str
    asr_items: list[AsrItem] = field(default_factory=list)
    asr_backend: str = "mock"
    asr_error: str | None = None

    def to_dict(self) -> dict:
        result = {
            "asr_backend": self.asr_backend,
        }
        if self.asr_items:
            result["asr_items"] = [item.to_dict() for item in self.asr_items]
        if self.asr_error:
            result["asr_error"] = self.asr_error
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
                ocr_items = [
                    OcrItem.from_dict(item)
                    for item in data.get("ocr_items", [])
                ]
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
                asr_items.append(AsrItem(
                    text=ocr_item.text,
                    t_start=round(t_start, 2),
                    t_end=round(t_end, 2),
                ))
        elif ui_key_text:
            # Fall back to ui_key_text with evenly distributed timestamps
            num_items = len(ui_key_text)
            interval = segment_duration / max(num_items, 1)
            for i, text in enumerate(ui_key_text):
                t_start = segment.start_time + i * interval
                t_end = min(t_start + interval, segment.end_time)
                asr_items.append(AsrItem(
                    text=text,
                    t_start=round(t_start, 2),
                    t_end=round(t_end, 2),
                ))
        else:
            # No OCR data available - create single placeholder
            asr_items.append(AsrItem(
                text="[无字幕]",
                t_start=round(segment.start_time, 2),
                t_end=round(segment.end_time, 2),
            ))

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

    def __init__(self, model_size: str = "base"):
        """Initialize Whisper backend.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self._model = None

    def _extract_audio(
        self, segment: SegmentInfo, session_dir: Path
    ) -> Path | None:
        """Extract audio from video segment to WAV file.

        Args:
            segment: Segment info with video path
            session_dir: Session directory

        Returns:
            Path to extracted audio file, or None on error
        """
        audio_dir = session_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        video_path = session_dir / segment.video_path
        audio_path = audio_dir / f"{segment.id}.wav"

        if audio_path.exists():
            return audio_path

        if not video_path.exists():
            return None

        try:
            # Extract audio using ffmpeg
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # PCM 16-bit
                "-ar", "16000",  # 16kHz sample rate (Whisper default)
                "-ac", "1",  # Mono
                str(audio_path),
            ]
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
            return audio_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _load_model(self):
        """Load Whisper model (lazy initialization)."""
        if self._model is not None:
            return

        # Try faster-whisper first, fall back to openai-whisper
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self.model_size, device="cpu")
            self._backend_type = "faster_whisper"
        except ImportError:
            try:
                import whisper
                self._model = whisper.load_model(self.model_size)
                self._backend_type = "openai_whisper"
            except ImportError:
                raise ImportError(
                    "Neither faster-whisper nor openai-whisper is installed. "
                    "Install with: pip install faster-whisper"
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
        # Extract audio
        audio_path = self._extract_audio(segment, session_dir)
        if audio_path is None:
            return AsrResult(
                segment_id=segment.id,
                asr_backend="whisper_local",
                asr_error="Failed to extract audio from video segment",
            )

        # Load model
        try:
            self._load_model()
        except ImportError as e:
            return AsrResult(
                segment_id=segment.id,
                asr_backend="whisper_local",
                asr_error=str(e),
            )

        # Transcribe
        try:
            asr_items = self._transcribe_audio(
                audio_path, segment.start_time, max_seconds
            )
            return AsrResult(
                segment_id=segment.id,
                asr_items=asr_items,
                asr_backend="whisper_local",
            )
        except Exception as e:
            return AsrResult(
                segment_id=segment.id,
                asr_backend="whisper_local",
                asr_error=f"Transcription failed: {e}",
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
            segments, _ = self._model.transcribe(
                str(audio_path),
                language="zh",
                vad_filter=True,
            )
            for seg in segments:
                if max_seconds and seg.start > max_seconds:
                    break
                asr_items.append(AsrItem(
                    text=seg.text.strip(),
                    t_start=round(segment_start + seg.start, 2),
                    t_end=round(segment_start + seg.end, 2),
                ))
        else:  # openai_whisper
            result = self._model.transcribe(
                str(audio_path),
                language="zh",
            )
            for seg in result.get("segments", []):
                if max_seconds and seg["start"] > max_seconds:
                    break
                asr_items.append(AsrItem(
                    text=seg["text"].strip(),
                    t_start=round(segment_start + seg["start"], 2),
                    t_end=round(segment_start + seg["end"], 2),
                ))

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

        result.append(AsrItem(
            text=item.text,
            t_start=round(t_start, 2),
            t_end=round(t_end, 2),
        ))
        prev_end = t_end

    return result


def get_asr_backend(backend: str) -> AsrBackend:
    """Get ASR backend by name.

    Args:
        backend: Backend name ("mock" or "whisper_local")

    Returns:
        ASR backend instance

    Raises:
        ValueError: If backend is unknown
    """
    if backend == "mock":
        return MockAsrBackend()
    elif backend == "whisper_local":
        return WhisperLocalBackend()
    else:
        raise ValueError(f"Unknown ASR backend: {backend}")


@dataclass
class TranscribeStats:
    """Statistics from transcribe_session."""

    processed: int = 0
    skipped_cache: int = 0
    skipped_filter: int = 0
    errors: int = 0


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
    segments: list[str] | None = None,
    on_progress: Callable[[str, str, AsrResult | None], None] | None = None,
) -> TranscribeStats:
    """Transcribe all segments in a session.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory
        backend: ASR backend ("mock" or "whisper_local")
        max_seconds: Optional limit on audio duration per segment
        force: Re-transcribe even if ASR data exists
        limit: Only process first N segments
        segments: Optional list of segment IDs to process
        on_progress: Callback(segment_id, status, result)

    Returns:
        Transcription statistics
    """
    asr_backend = get_asr_backend(backend)
    stats = TranscribeStats()

    for i, segment in enumerate(manifest.segments):
        # Apply limit
        if limit is not None and i >= limit:
            break

        # Apply filter
        if segments is not None and segment.id not in segments:
            stats.skipped_filter += 1
            continue

        # Check cache
        analysis_path = session_dir / "analysis" / f"{segment.id}.json"
        if not force and analysis_path.exists():
            try:
                with open(analysis_path, encoding="utf-8") as f:
                    data = json.load(f)
                if "asr_items" in data or "asr_error" in data:
                    stats.skipped_cache += 1
                    if on_progress:
                        on_progress(segment.id, "cached", None)
                    continue
            except (json.JSONDecodeError, OSError):
                pass

        # Transcribe
        try:
            result = asr_backend.transcribe_segment(
                segment, session_dir, max_seconds
            )

            # Merge into analysis
            merge_asr_to_analysis(result, analysis_path, segment)

            if result.asr_error:
                stats.errors += 1
                if on_progress:
                    on_progress(segment.id, "error", result)
            else:
                stats.processed += 1
                if on_progress:
                    on_progress(segment.id, "done", result)

        except Exception as e:
            stats.errors += 1
            error_result = AsrResult(
                segment_id=segment.id,
                asr_backend=backend,
                asr_error=str(e),
            )
            merge_asr_to_analysis(error_result, analysis_path, segment)
            if on_progress:
                on_progress(segment.id, "error", error_result)

    return stats
