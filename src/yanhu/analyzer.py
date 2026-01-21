"""Vision analysis for video segments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from yanhu.manifest import Manifest, SegmentInfo


@dataclass
class AnalysisResult:
    """Result of analyzing a video segment."""

    segment_id: str
    scene_type: str  # e.g., "dialogue", "combat", "menu", "unknown"
    ocr_text: list[str] = field(default_factory=list)
    caption: str = ""
    model: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        result = {
            "segment_id": self.segment_id,
            "scene_type": self.scene_type,
            "ocr_text": self.ocr_text,
            "caption": self.caption,
        }
        if self.model:
            result["model"] = self.model
        if self.error:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: dict) -> AnalysisResult:
        return cls(
            segment_id=data["segment_id"],
            scene_type=data["scene_type"],
            ocr_text=data.get("ocr_text", []),
            caption=data.get("caption", ""),
            model=data.get("model"),
            error=data.get("error"),
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

    def has_valid_caption(self) -> bool:
        """Check if this result has a valid caption (not error)."""
        return bool(self.caption) and not self.error

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
    ) -> AnalysisResult:
        """Generate mock analysis for a segment.

        Args:
            segment: Segment info from manifest
            session_dir: Path to session directory (unused for mock)
            max_frames: Maximum frames to use (for caption)

        Returns:
            AnalysisResult with placeholder data
        """
        frame_count = min(len(segment.frames), max_frames)
        caption = f"【占位】{segment.id}：已抽取{frame_count}帧，等待视觉/字幕解析"

        return AnalysisResult(
            segment_id=segment.id,
            scene_type="unknown",
            ocr_text=[],
            caption=caption,
            model="mock",
        )


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
    ) -> AnalysisResult:
        """Analyze a segment using Claude Vision.

        Args:
            segment: Segment info from manifest
            session_dir: Path to session directory
            max_frames: Maximum frames to analyze

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
            response = client.analyze_frames(frame_paths)

            return AnalysisResult(
                segment_id=segment.id,
                scene_type=response.scene_type,
                ocr_text=response.ocr_text,
                caption=response.caption,
                model=response.model,
                error=response.error,
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

    # Segment ID lists for dry-run reporting
    will_process: list[str] = field(default_factory=list)
    cached_skip: list[str] = field(default_factory=list)
    filtered_skip: list[str] = field(default_factory=list)

    @property
    def total_images(self) -> int:
        """Estimated total images (api_calls * max_frames)."""
        return self.api_calls * self.max_frames


def analyze_session(
    manifest: Manifest,
    session_dir: Path,
    backend: str = "mock",
    *,
    max_frames: int = 3,
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
        max_frames: Maximum frames per segment to analyze
        force: Re-analyze even if cache exists
        dry_run: Only calculate stats, don't run analysis
        limit: Only process first N segments
        segments: Only process these segment IDs
        client: Optional analyzer client (for testing)
        on_progress: Optional callback(segment_id, status, result)

    Returns:
        AnalyzeStats with processing statistics
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

    # Process segments
    for segment in segments_to_process:
        try:
            result = analyzer.analyze_segment(segment, session_dir, max_frames)

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
