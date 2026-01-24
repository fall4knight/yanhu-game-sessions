"""Manifest data structure and JSON serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class SourceMetadata:
    """Observability metadata for source video link/copy behavior."""

    source_mode: str  # "hardlink" | "symlink" | "copy"
    source_inode_raw: int  # inode of original file
    source_inode_session: int  # inode of file in session/source/
    source_link_count: int  # link count of session file
    source_fallback_error: str | None = None  # error if fallback occurred
    source_symlink_target: str | None = None  # target if symlink

    def to_dict(self) -> dict:
        result = {
            "source_mode": self.source_mode,
            "source_inode_raw": self.source_inode_raw,
            "source_inode_session": self.source_inode_session,
            "source_link_count": self.source_link_count,
        }
        if self.source_fallback_error:
            result["source_fallback_error"] = self.source_fallback_error
        if self.source_symlink_target:
            result["source_symlink_target"] = self.source_symlink_target
        return result

    @classmethod
    def from_dict(cls, data: dict) -> SourceMetadata:
        return cls(
            source_mode=data["source_mode"],
            source_inode_raw=data["source_inode_raw"],
            source_inode_session=data["source_inode_session"],
            source_link_count=data["source_link_count"],
            source_fallback_error=data.get("source_fallback_error"),
            source_symlink_target=data.get("source_symlink_target"),
        )


@dataclass
class SegmentInfo:
    """Information about a single video segment."""

    id: str  # e.g., "part_0001"
    start_time: float  # seconds from video start
    end_time: float  # seconds from video start
    video_path: str  # relative to session directory
    frames: list[str] = field(default_factory=list)  # relative paths to extracted frames
    analysis_path: str | None = None  # relative path to analysis JSON

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "video_path": self.video_path,
        }
        if self.frames:
            result["frames"] = self.frames
        if self.analysis_path:
            result["analysis_path"] = self.analysis_path
        return result

    @classmethod
    def from_dict(cls, data: dict) -> SegmentInfo:
        return cls(
            id=data["id"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            video_path=data["video_path"],
            frames=data.get("frames", []),
            analysis_path=data.get("analysis_path"),
        )


@dataclass
class Manifest:
    """Session manifest tracking all artifacts."""

    session_id: str
    created_at: str  # ISO format
    source_video: str  # original path
    source_video_local: str  # path within session (relative)
    segment_duration_seconds: int
    segments: list[SegmentInfo] = field(default_factory=list)
    source_metadata: SourceMetadata | None = None  # observability for source link/copy
    transcribe_coverage: dict[str, int] | None = None  # {processed, total, skipped_limit}

    def to_dict(self) -> dict:
        result = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "source_video": self.source_video,
            "source_video_local": self.source_video_local,
            "segment_duration_seconds": self.segment_duration_seconds,
            "segments": [s.to_dict() for s in self.segments],
        }
        if self.source_metadata:
            result["source_metadata"] = self.source_metadata.to_dict()
        if self.transcribe_coverage:
            result["transcribe_coverage"] = self.transcribe_coverage
        return result

    @classmethod
    def from_dict(cls, data: dict) -> Manifest:
        source_metadata = None
        if "source_metadata" in data:
            source_metadata = SourceMetadata.from_dict(data["source_metadata"])
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            source_video=data["source_video"],
            source_video_local=data["source_video_local"],
            segment_duration_seconds=data["segment_duration_seconds"],
            segments=[SegmentInfo.from_dict(s) for s in data.get("segments", [])],
            source_metadata=source_metadata,
            transcribe_coverage=data.get("transcribe_coverage"),
        )

    def save(self, session_dir: Path) -> Path:
        """Save manifest to session directory.

        Returns:
            Path to the saved manifest.json
        """
        manifest_path = session_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return manifest_path

    @classmethod
    def load(cls, session_dir: Path) -> Manifest:
        """Load manifest from session directory."""
        manifest_path = session_dir / "manifest.json"
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def create_manifest(
    session_id: str,
    source_video: Path,
    source_video_local: str,
    segment_duration: int,
    source_metadata: SourceMetadata | None = None,
) -> Manifest:
    """Create a new manifest for a session.

    Args:
        session_id: The session identifier
        source_video: Original video path (absolute)
        source_video_local: Path within session directory (relative)
        segment_duration: Target segment duration in seconds
        source_metadata: Observability metadata for source link/copy

    Returns:
        New Manifest instance
    """
    return Manifest(
        session_id=session_id,
        created_at=datetime.now().isoformat(),
        source_video=str(source_video.resolve()),
        source_video_local=source_video_local,
        segment_duration_seconds=segment_duration,
        segments=[],
        source_metadata=source_metadata,
    )
