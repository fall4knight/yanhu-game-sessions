"""Vision analysis for video segments."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from yanhu.manifest import Manifest, SegmentInfo

# OCR normalization patterns: (pattern, replacement)
# NOTE: Normalization is DISABLED - OCR text must be kept verbatim.
# These patterns are kept for reference but NOT applied to output fields.
_OCR_NORMALIZE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # "一只...步摇/玉簪/笔/箭/枪" -> "一支..."
    (re.compile(r"一只(.{0,6}?)(步摇|玉簪|笔|箭|枪)"), r"一支\1\2"),
]


def normalize_ocr_text(text: str) -> str:
    """Normalize OCR text to fix common character errors.

    WARNING: This function is NOT applied to ocr_text/ui_key_text/ocr_items.
    OCR output must be kept verbatim (逐字保真) without any corrections.

    This function is kept for potential future use in non-output contexts
    (e.g., search indexing), but is disabled for all analysis output fields.

    Args:
        text: Raw OCR text

    Returns:
        Normalized text with common errors fixed (if applied)
    """
    if not text:
        return text

    result = text
    for pattern, replacement in _OCR_NORMALIZE_PATTERNS:
        result = pattern.sub(replacement, result)

    return result


@dataclass
class OcrItem:
    """A single OCR text item with source tracking."""

    text: str
    t_rel: float  # Relative time in seconds (from session start)
    source_frame: str  # Frame filename (e.g., "frame_0005.jpg")

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "t_rel": self.t_rel,
            "source_frame": self.source_frame,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OcrItem":
        return cls(
            text=data["text"],
            t_rel=data.get("t_rel", 0.0),
            source_frame=data.get("source_frame", ""),
        )


@dataclass
class AnalysisResult:
    """Result of analyzing a video segment."""

    segment_id: str
    scene_type: str  # e.g., "dialogue", "combat", "menu", "unknown"
    ocr_text: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)  # 1-3 objective facts
    caption: str = ""
    confidence: str | None = None  # "low", "med", "high"
    model: str | None = None
    error: str | None = None
    raw_text: str | None = None  # Raw API response when JSON parse fails
    # L1 fields (optional, for detail_level=L1)
    scene_label: str | None = None  # Loading|Menu|Cutscene|Combat|Dialogue|Error|TVTest|Unknown
    what_changed: str | None = None  # Short description of changes
    ui_key_text: list[str] = field(default_factory=list)  # 0-2 key UI text items
    ui_symbols: list[str] = field(default_factory=list)  # 0-3 emoji/symbols like ❤️
    player_action_guess: str | None = None  # Optional guess with uncertainty markers
    hook_detail: str | None = None  # Optional detail worth noting
    # OCR items with source tracking (for ASR alignment)
    ocr_items: list[OcrItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {
            "segment_id": self.segment_id,
            "scene_type": self.scene_type,
            "ocr_text": self.ocr_text,
        }
        if self.facts:
            result["facts"] = self.facts
        result["caption"] = self.caption
        if self.confidence:
            result["confidence"] = self.confidence
        if self.model:
            result["model"] = self.model
        if self.error:
            result["error"] = self.error
        if self.raw_text:
            result["raw_text"] = self.raw_text
        # L1 fields (only include if present)
        if self.scene_label:
            result["scene_label"] = self.scene_label
        if self.what_changed:
            result["what_changed"] = self.what_changed
        if self.ui_key_text:
            result["ui_key_text"] = self.ui_key_text
        if self.ui_symbols:
            result["ui_symbols"] = self.ui_symbols
        if self.player_action_guess:
            result["player_action_guess"] = self.player_action_guess
        if self.hook_detail:
            result["hook_detail"] = self.hook_detail
        if self.ocr_items:
            result["ocr_items"] = [item.to_dict() for item in self.ocr_items]
        return result

    @classmethod
    def from_dict(cls, data: dict) -> AnalysisResult:
        return cls(
            segment_id=data["segment_id"],
            scene_type=data["scene_type"],
            ocr_text=data.get("ocr_text", []),
            facts=data.get("facts", []),
            caption=data.get("caption", ""),
            confidence=data.get("confidence"),
            model=data.get("model"),
            error=data.get("error"),
            raw_text=data.get("raw_text"),
            # L1 fields (backward compatible)
            scene_label=data.get("scene_label"),
            what_changed=data.get("what_changed"),
            ui_key_text=data.get("ui_key_text", []),
            ui_symbols=data.get("ui_symbols", []),
            player_action_guess=data.get("player_action_guess"),
            hook_detail=data.get("hook_detail"),
            # OCR items
            ocr_items=[
                OcrItem.from_dict(item)
                for item in data.get("ocr_items", [])
            ],
        )

    def save(self, output_path: Path) -> None:
        """Save analysis result to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> AnalysisResult:
        """Load analysis result from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def has_valid_content(self) -> bool:
        """Check if this result has valid content (facts or caption, no error)."""
        return (bool(self.facts) or bool(self.caption)) and not self.error

    def has_valid_caption(self) -> bool:
        """Check if this result has a valid caption (not error). For backward compat."""
        return self.has_valid_content()

    def get_description(self) -> str | None:
        """Get best description: facts (first) > caption > None."""
        if self.facts:
            return self.facts[0]
        if self.caption:
            return self.caption
        return None

    def is_cache_valid_for(self, backend: str) -> bool:
        """Check if this cached result is valid for a specific backend.

        Args:
            backend: The backend requesting cache validation ("mock" or "claude")

        Returns:
            True if cache is valid for this backend, False otherwise

        Rules:
            - mock backend: valid if model == "mock"
            - claude backend: valid if model starts with "claude-"
            - Both require: non-empty caption AND no error
        """
        # Must have valid caption and no error
        if not self.has_valid_caption():
            return False

        # Check model matches backend
        if backend == "mock":
            return self.model == "mock"
        elif backend == "claude":
            return bool(self.model) and self.model.startswith("claude-")

        # Unknown backend - no cache valid
        return False


def generate_analysis_path(segment_id: str) -> str:
    """Generate relative path for analysis file.

    Args:
        segment_id: Segment ID (e.g., "part_0001")

    Returns:
        Relative path like "analysis/part_0001.json"
    """
    return f"analysis/{segment_id}.json"


class Analyzer(Protocol):
    """Protocol for segment analyzers."""

    def analyze_segment(
        self,
        segment: SegmentInfo,
        session_dir: Path,
        max_frames: int,
        max_facts: int = 3,
        detail_level: str = "L1",
    ) -> AnalysisResult:
        """Analyze a segment and return results."""
        ...


class MockAnalyzer:
    """Mock analyzer that generates placeholder analysis results."""

    def analyze_segment(
        self,
        segment: SegmentInfo,
        session_dir: Path,
        max_frames: int = 3,
        max_facts: int = 3,
        detail_level: str = "L1",
    ) -> AnalysisResult:
        """Generate mock analysis for a segment.

        Args:
            segment: Segment info from manifest
            session_dir: Path to session directory (unused for mock)
            max_frames: Maximum frames to use (for caption)
            max_facts: Maximum facts to generate (unused for mock)
            detail_level: "L0" for basic, "L1" for enhanced fields

        Returns:
            AnalysisResult with placeholder data
        """
        frame_count = min(len(segment.frames), max_frames)
        facts = [f"共{frame_count}帧画面", f"segment_id={segment.id}"][:max_facts]
        caption = f"【占位】{segment.id}：已抽取{frame_count}帧，等待视觉/字幕解析"

        result = AnalysisResult(
            segment_id=segment.id,
            scene_type="unknown",
            ocr_text=[],
            facts=facts,
            caption=caption,
            model="mock",
        )

        # Add L1 fields if detail_level is L1
        if detail_level == "L1":
            result.scene_label = "Unknown"
            result.what_changed = "mock数据，等待实际分析"
            result.ui_key_text = []
            result.player_action_guess = ""
            result.hook_detail = ""

        return result


class ClaudeAnalyzer:
    """Analyzer using Claude Vision API."""

    def __init__(self, client=None):
        """Initialize Claude analyzer.

        Args:
            client: Optional ClaudeClient instance. If None, creates one.
        """
        self._client = client

    def _get_client(self):
        """Lazy-load the Claude client."""
        if self._client is None:
            from yanhu.claude_client import ClaudeClient
            self._client = ClaudeClient()
        return self._client

    def analyze_segment(
        self,
        segment: SegmentInfo,
        session_dir: Path,
        max_frames: int = 3,
        max_facts: int = 3,
        detail_level: str = "L1",
    ) -> AnalysisResult:
        """Analyze a segment using Claude Vision.

        Args:
            segment: Segment info from manifest
            session_dir: Path to session directory
            max_frames: Maximum frames to analyze
            max_facts: Maximum facts to return
            detail_level: "L0" for basic, "L1" for enhanced fields

        Returns:
            AnalysisResult with Claude's analysis
        """
        # Get frame paths, limited to max_frames
        frame_paths = [session_dir / f for f in segment.frames[:max_frames]]

        if not frame_paths:
            return AnalysisResult(
                segment_id=segment.id,
                scene_type="unknown",
                ocr_text=[],
                caption="",
                error="No frames available for analysis",
            )

        # Check frames exist
        missing = [p for p in frame_paths if not p.exists()]
        if missing:
            return AnalysisResult(
                segment_id=segment.id,
                scene_type="unknown",
                ocr_text=[],
                caption="",
                error=f"Missing frames: {[str(p) for p in missing]}",
            )

        try:
            client = self._get_client()
            response = client.analyze_frames(
                frame_paths, max_facts=max_facts, detail_level=detail_level
            )

            # Convert ocr_items from Claude format to AnalysisResult format
            # Calculate t_rel based on segment start time and frame index
            # NOTE: Text is kept verbatim - no normalization/correction applied
            ocr_items = []
            if response.ocr_items:
                segment_duration = segment.end_time - segment.start_time
                num_frames = len(frame_paths)
                for item in response.ocr_items:
                    # Parse frame index from source_frame (e.g., "frame_0003.jpg" -> 3)
                    try:
                        frame_idx = int(item.source_frame[6:10])
                    except (ValueError, IndexError):
                        frame_idx = 1
                    # Estimate t_rel: segment_start + (frame_idx - 1) / num_frames * duration
                    if num_frames > 1:
                        frame_ratio = (frame_idx - 1) / (num_frames - 1)
                        t_rel = segment.start_time + frame_ratio * segment_duration
                    else:
                        t_rel = segment.start_time
                    ocr_items.append(OcrItem(
                        text=item.text,  # Verbatim - no normalization
                        t_rel=round(t_rel, 2),
                        source_frame=item.source_frame,
                    ))

            return AnalysisResult(
                segment_id=segment.id,
                scene_type=response.scene_type,
                ocr_text=response.ocr_text,  # Verbatim - no normalization
                facts=response.facts,
                caption=response.caption,
                confidence=response.confidence,
                model=response.model,
                error=response.error,
                raw_text=response.raw_text,
                # L1 fields
                scene_label=response.scene_label,
                what_changed=response.what_changed,
                ui_key_text=response.ui_key_text or [],  # Verbatim - no normalization
                ui_symbols=response.ui_symbols or [],
                player_action_guess=response.player_action_guess,
                hook_detail=response.hook_detail,
                ocr_items=ocr_items,
            )
        except Exception as e:
            return AnalysisResult(
                segment_id=segment.id,
                scene_type="unknown",
                ocr_text=[],
                caption="",
                error=str(e),
            )


def get_analyzer(backend: str = "mock", client=None) -> Analyzer:
    """Get analyzer instance by backend name.

    Args:
        backend: Backend name ("mock" or "claude")
        client: Optional client instance (for testing)

    Returns:
        Analyzer instance

    Raises:
        ValueError: If backend is not supported
    """
    if backend == "mock":
        return MockAnalyzer()
    elif backend == "claude":
        return ClaudeAnalyzer(client=client)
    raise ValueError(f"Unknown analyzer backend: {backend}")


def check_cache(
    segment: SegmentInfo,
    session_dir: Path,
    backend: str,
) -> AnalysisResult | None:
    """Check if valid cached analysis exists for a specific backend.

    Args:
        segment: Segment info
        session_dir: Session directory
        backend: Backend name ("mock" or "claude")

    Returns:
        Cached AnalysisResult if valid for this backend, None otherwise
    """
    if not segment.analysis_path:
        return None

    analysis_file = session_dir / segment.analysis_path
    if not analysis_file.exists():
        return None

    try:
        result = AnalysisResult.load(analysis_file)
        if result.is_cache_valid_for(backend):
            return result
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    return None


@dataclass
class AnalyzeOptions:
    """Options for analyze_session."""

    backend: str = "mock"
    max_frames: int = 3
    force: bool = False
    dry_run: bool = False
    limit: int | None = None
    segments: list[str] | None = None


@dataclass
class AnalyzeStats:
    """Statistics from analyze_session."""

    total_segments: int = 0
    processed: int = 0
    skipped_cache: int = 0
    skipped_filter: int = 0
    errors: int = 0
    api_calls: int = 0
    max_frames: int = 3
    # Dynamic frames tracking
    upgraded_segments: int = 0  # Segments that got more frames due to subtitles

    # Segment ID lists for dry-run reporting
    will_process: list[str] = field(default_factory=list)
    cached_skip: list[str] = field(default_factory=list)
    filtered_skip: list[str] = field(default_factory=list)

    @property
    def total_images(self) -> int:
        """Estimated total images (api_calls * max_frames)."""
        return self.api_calls * self.max_frames


def _has_subtitle_content(result: AnalysisResult) -> bool:
    """Check if analysis result has subtitle/dialogue content.

    Used to determine if a segment should get more frames for better OCR.
    """
    return bool(result.ocr_text) or bool(result.ui_key_text)


def analyze_session(
    manifest: Manifest,
    session_dir: Path,
    backend: str = "mock",
    *,
    max_frames: int = 3,
    max_frames_dialogue: int = 6,
    max_facts: int = 3,
    detail_level: str = "L1",
    force: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    segments: list[str] | None = None,
    client=None,
    on_progress=None,
) -> AnalyzeStats:
    """Analyze segments in a session.

    Args:
        manifest: Session manifest (will be modified in place)
        session_dir: Path to session directory
        backend: Analyzer backend to use
        max_frames: Initial max frames per segment (for first pass)
        max_frames_dialogue: Max frames for segments with subtitles detected (for recall)
        max_facts: Maximum facts per segment to generate
        detail_level: "L0" for basic, "L1" for enhanced fields
        force: Re-analyze even if cache exists
        dry_run: Only calculate stats, don't run analysis
        limit: Only process first N segments
        segments: Only process these segment IDs
        client: Optional analyzer client (for testing)
        on_progress: Optional callback(segment_id, status, result)

    Returns:
        AnalyzeStats with processing statistics

    Notes:
        Dynamic frame allocation: If initial analysis detects subtitles (ocr_text
        or ui_key_text non-empty) and max_frames < max_frames_dialogue, a second
        pass is done with more frames to improve OCR recall.
    """
    stats = AnalyzeStats(total_segments=len(manifest.segments), max_frames=max_frames)

    # Step 1: Apply filters (--segments, --limit) to get "final set"
    filtered_segments = []
    for seg in manifest.segments:
        # Check segment filter (--segments)
        if segments and seg.id not in segments:
            stats.skipped_filter += 1
            stats.filtered_skip.append(seg.id)
            continue

        # Check limit (--limit)
        if limit is not None and len(filtered_segments) >= limit:
            stats.skipped_filter += 1
            stats.filtered_skip.append(seg.id)
            continue

        filtered_segments.append(seg)

    # Step 2: Check cache for each segment in "final set"
    segments_to_process = []
    for seg in filtered_segments:
        if not force:
            cached = check_cache(seg, session_dir, backend)
            if cached:
                stats.skipped_cache += 1
                stats.cached_skip.append(seg.id)
                if on_progress:
                    on_progress(seg.id, "cached", cached)
                continue

        segments_to_process.append(seg)
        stats.will_process.append(seg.id)

    stats.api_calls = len(segments_to_process)

    # Dry run - just return stats
    if dry_run:
        return stats

    # Create analyzer
    analyzer = get_analyzer(backend, client=client)
    analysis_dir = session_dir / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    # Process segments with dynamic frame allocation
    for segment in segments_to_process:
        try:
            # First pass: analyze with initial max_frames
            result = analyzer.analyze_segment(
                segment, session_dir, max_frames, max_facts, detail_level
            )

            # Dynamic frame upgrade: if subtitles detected and can benefit from more frames
            if (
                not result.error
                and _has_subtitle_content(result)
                and max_frames < max_frames_dialogue
                and len(segment.frames) > max_frames
            ):
                # Second pass with more frames for better OCR recall
                result = analyzer.analyze_segment(
                    segment, session_dir, max_frames_dialogue, max_facts, detail_level
                )
                stats.upgraded_segments += 1
                stats.api_calls += 1  # Count the extra API call

            if result.error:
                stats.errors += 1
            else:
                stats.processed += 1

            # Save analysis file
            relative_path = generate_analysis_path(segment.id)
            output_path = session_dir / relative_path
            result.save(output_path)

            # Update manifest
            segment.analysis_path = relative_path

            if on_progress:
                on_progress(segment.id, "done", result)

        except Exception as e:
            stats.errors += 1
            # Save error result
            result = AnalysisResult(
                segment_id=segment.id,
                scene_type="unknown",
                ocr_text=[],
                caption="",
                error=str(e),
            )
            relative_path = generate_analysis_path(segment.id)
            output_path = session_dir / relative_path
            result.save(output_path)
            segment.analysis_path = relative_path

            if on_progress:
                on_progress(segment.id, "error", result)

    return stats
