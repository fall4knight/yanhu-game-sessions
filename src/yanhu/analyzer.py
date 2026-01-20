"""Vision analysis for video segments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from yanhu.manifest import Manifest, SegmentInfo


@dataclass
class AnalysisResult:
    """Result of analyzing a video segment."""

    segment_id: str
    scene_type: str  # e.g., "dialogue", "combat", "menu", "unknown"
    ocr_text: list[str] = field(default_factory=list)
    caption: str = ""

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "scene_type": self.scene_type,
            "ocr_text": self.ocr_text,
            "caption": self.caption,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AnalysisResult:
        return cls(
            segment_id=data["segment_id"],
            scene_type=data["scene_type"],
            ocr_text=data.get("ocr_text", []),
            caption=data.get("caption", ""),
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


def generate_analysis_path(segment_id: str) -> str:
    """Generate relative path for analysis file.

    Args:
        segment_id: Segment ID (e.g., "part_0001")

    Returns:
        Relative path like "analysis/part_0001.json"
    """
    return f"analysis/{segment_id}.json"


class MockAnalyzer:
    """Mock analyzer that generates placeholder analysis results."""

    def analyze_segment(self, segment: SegmentInfo) -> AnalysisResult:
        """Generate mock analysis for a segment.

        Args:
            segment: Segment info from manifest

        Returns:
            AnalysisResult with placeholder data
        """
        frame_count = len(segment.frames)
        caption = f"【占位】{segment.id}：已抽取{frame_count}帧，等待视觉/字幕解析"

        return AnalysisResult(
            segment_id=segment.id,
            scene_type="unknown",
            ocr_text=[],
            caption=caption,
        )


def get_analyzer(backend: str = "mock") -> MockAnalyzer:
    """Get analyzer instance by backend name.

    Args:
        backend: Backend name ("mock" for now)

    Returns:
        Analyzer instance

    Raises:
        ValueError: If backend is not supported
    """
    if backend == "mock":
        return MockAnalyzer()
    raise ValueError(f"Unknown analyzer backend: {backend}")


def analyze_session(
    manifest: Manifest,
    session_dir: Path,
    backend: str = "mock",
) -> None:
    """Analyze all segments in a session.

    Args:
        manifest: Session manifest (will be modified in place)
        session_dir: Path to session directory
        backend: Analyzer backend to use
    """
    analyzer = get_analyzer(backend)
    analysis_dir = session_dir / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    for segment in manifest.segments:
        # Generate analysis
        result = analyzer.analyze_segment(segment)

        # Save analysis file
        relative_path = generate_analysis_path(segment.id)
        output_path = session_dir / relative_path
        result.save(output_path)

        # Update manifest
        segment.analysis_path = relative_path
