"""Progress tracking for long-running pipeline stages.

Provides real-time progress updates written to progress.json for monitoring.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ProgressSnapshot:
    """A snapshot of pipeline progress at a point in time."""

    session_id: str
    stage: str  # "download_model", "transcribe", "compose", "done"
    done: int  # Number of items completed in current stage
    total: int  # Total items in current stage
    elapsed_sec: float  # Elapsed time since stage started
    eta_sec: float | None  # Estimated time to completion (None if unknown)
    updated_at: str  # ISO timestamp (UTC)
    coverage: dict[str, int] | None = None  # Optional coverage info if limited
    message: str | None = None  # Optional status message (e.g., "Downloading model...")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "session_id": self.session_id,
            "stage": self.stage,
            "done": self.done,
            "total": self.total,
            "elapsed_sec": round(self.elapsed_sec, 2),
            "updated_at": self.updated_at,
        }
        if self.eta_sec is not None:
            result["eta_sec"] = round(self.eta_sec, 2)
        if self.coverage is not None:
            result["coverage"] = self.coverage
        if self.message is not None:
            result["message"] = self.message
        return result


class ProgressTracker:
    """Tracks and persists progress for long-running pipeline stages.

    Progress is written atomically to <session_dir>/outputs/progress.json.
    Suitable for real-time monitoring by external processes.

    All timestamps are in UTC for consistency.
    """

    def __init__(
        self,
        session_id: str,
        session_dir: Path,
        stage: str,
        total: int,
        coverage: dict[str, int] | None = None,
        message: str | None = None,
    ):
        """Initialize progress tracker.

        Args:
            session_id: Session identifier
            session_dir: Path to session directory
            stage: Current stage name (e.g., "transcribe", "download_model")
            total: Total number of items to process in this stage
            coverage: Optional coverage metadata if processing is limited
            message: Optional status message
        """
        self.session_id = session_id
        self.session_dir = session_dir
        self.stage = stage
        self.total = total
        self.coverage = coverage
        self.message = message
        self.done = 0
        self.start_time = time.time()
        self.progress_file = session_dir / "outputs" / "progress.json"
        self._terminal_locked = False  # Step 32.14: Prevent stage overwrite after terminal

        # Ensure outputs directory exists
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)

        # Write initial progress
        self._write_progress()

    def update(self, done: int, message: str | None = None) -> None:
        """Update progress with current completion count.

        Args:
            done: Number of items completed so far
            message: Optional status message to update
        """
        # Step 32.14: Terminal lock - don't update after terminal state
        if self._terminal_locked:
            return

        self.done = done
        if message is not None:
            self.message = message
        self._write_progress()

    def finalize(self, stage: str = "done") -> None:
        """Mark current stage as complete and optionally transition to next stage.

        Args:
            stage: Stage name to transition to (default: "done")
        """
        # Step 32.14: Terminal lock - don't finalize after already in terminal state
        if self._terminal_locked:
            return

        self.stage = stage
        self.done = self.total
        self._write_progress()

        # Step 32.14: Lock terminal states to prevent overwrites
        if stage in ("done", "failed", "cancelled"):
            self._terminal_locked = True

    def _write_progress(self) -> None:
        """Write progress snapshot to progress.json atomically."""
        elapsed = time.time() - self.start_time

        # Calculate ETA (best-effort)
        eta = None
        if self.done > 0 and self.done < self.total:
            avg_time_per_item = elapsed / self.done
            remaining = self.total - self.done
            eta = avg_time_per_item * remaining

        snapshot = ProgressSnapshot(
            session_id=self.session_id,
            stage=self.stage,
            done=self.done,
            total=self.total,
            elapsed_sec=elapsed,
            eta_sec=eta,
            updated_at=datetime.now(timezone.utc).isoformat(),
            coverage=self.coverage,
            message=self.message,
        )

        # Write atomically (temp file + rename)
        fd, temp_path = tempfile.mkstemp(
            dir=self.progress_file.parent,
            prefix=".progress_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
            # Atomic rename
            os.replace(temp_path, self.progress_file)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def format_console_line(self) -> str:
        """Format a concise progress line for console output.

        Returns:
            Formatted progress string
            (e.g., "Transcribe: 12/50 segments, 45.2s elapsed, ETA 3m 22s")
        """
        elapsed = time.time() - self.start_time
        parts = [
            f"{self.stage.capitalize()}: {self.done}/{self.total} segments",
            f"{elapsed:.1f}s elapsed",
        ]

        if self.done > 0 and self.done < self.total:
            avg_time_per_item = elapsed / self.done
            remaining = self.total - self.done
            eta = avg_time_per_item * remaining
            parts.append(f"ETA {_format_duration(eta)}")

        return ", ".join(parts)


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "3m 22s", "1h 5m", "45s")
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m"


def write_stage_heartbeat(
    session_id: str,
    session_dir: Path,
    stage: str,
    message: str,
    done: int = 0,
    total: int = 0,
) -> None:
    """Write a quick stage heartbeat to progress.json for non-segment pipeline steps.

    This is a simplified alternative to ProgressTracker for stages that don't
    have iterative progress (e.g., ingest, segment, extract, analyze, compose).

    Args:
        session_id: Session identifier
        session_dir: Path to session directory
        stage: Stage name (e.g., "ingest", "segment", "extract", "analyze", "compose")
        message: Human-readable status message
        done: Items completed (default 0)
        total: Total items (default 0, can be 1 for single-step stages)
    """
    progress_file = session_dir / "outputs" / "progress.json"

    # Ensure outputs directory exists
    progress_file.parent.mkdir(parents=True, exist_ok=True)

    snapshot = ProgressSnapshot(
        session_id=session_id,
        stage=stage,
        done=done,
        total=total,
        elapsed_sec=0.0,  # Heartbeats don't track elapsed time
        eta_sec=None,
        updated_at=datetime.now(timezone.utc).isoformat(),
        message=message,
    )

    # Write atomically (temp file + rename)
    fd, temp_path = tempfile.mkstemp(
        dir=progress_file.parent,
        prefix=".progress_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
        # Atomic rename
        os.replace(temp_path, progress_file)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
