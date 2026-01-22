"""File watcher for automatic video detection and queue management.

Watches a directory for new video files and adds them to a processing queue.
Does NOT trigger the full pipeline - only detects and queues.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Supported video extensions
VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov"})


@dataclass
class QueueJob:
    """A job in the processing queue.

    Represents a video file waiting to be processed.
    """

    created_at: str  # ISO format timestamp
    raw_path: str  # Absolute path to the video file
    status: str = "pending"  # pending, processing, done, error
    suggested_game: str | None = None  # Optional game name hint

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "created_at": self.created_at,
            "raw_path": self.raw_path,
            "status": self.status,
        }
        if self.suggested_game is not None:
            result["suggested_game"] = self.suggested_game
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "QueueJob":
        """Create from dictionary."""
        return cls(
            created_at=data["created_at"],
            raw_path=data["raw_path"],
            status=data.get("status", "pending"),
            suggested_game=data.get("suggested_game"),
        )

    def to_json_line(self) -> str:
        """Convert to JSON line for JSONL file."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> "QueueJob":
        """Create from JSON line."""
        return cls.from_dict(json.loads(line))


def is_video_file(path: Path) -> bool:
    """Check if a path is a supported video file.

    Args:
        path: Path to check

    Returns:
        True if the file has a supported video extension
    """
    return path.suffix.lower() in VIDEO_EXTENSIONS


def guess_game_from_filename(filename: str) -> str | None:
    """Try to extract game name from filename.

    Looks for patterns like:
    - game_name_2026-01-20.mp4
    - 2026-01-20_game_name.mp4
    - game-name.mp4

    Args:
        filename: The filename (without directory)

    Returns:
        Guessed game name, or None if cannot determine
    """
    # Remove extension
    name = Path(filename).stem

    # Pattern: date prefix (YYYY-MM-DD or YYYYMMDD)
    date_prefix = re.match(r"^\d{4}[-_]?\d{2}[-_]?\d{2}[-_]?", name)
    if date_prefix:
        # Remove date prefix and extract game name
        remainder = name[date_prefix.end():]
        # Take first word/segment as game hint
        parts = re.split(r"[-_\s]+", remainder)
        if parts and parts[0]:
            return parts[0].lower()

    # Pattern: game name first, then date
    date_suffix = re.search(r"[-_]?\d{4}[-_]?\d{2}[-_]?\d{2}$", name)
    if date_suffix:
        game_part = name[: date_suffix.start()]
        parts = re.split(r"[-_\s]+", game_part)
        if parts and parts[0]:
            return parts[0].lower()

    # Fallback: use first word
    parts = re.split(r"[-_\s]+", name)
    if parts and parts[0]:
        return parts[0].lower()

    return None


def create_job_from_path(video_path: Path) -> QueueJob:
    """Create a queue job from a video file path.

    Args:
        video_path: Path to the video file

    Returns:
        QueueJob instance
    """
    return QueueJob(
        created_at=datetime.now().isoformat(),
        raw_path=str(video_path.resolve()),
        status="pending",
        suggested_game=guess_game_from_filename(video_path.name),
    )


def append_job_to_queue(job: QueueJob, queue_file: Path) -> None:
    """Append a job to the queue file (JSONL format).

    Creates the queue file and parent directories if they don't exist.

    Args:
        job: The job to append
        queue_file: Path to the JSONL queue file
    """
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    with open(queue_file, "a", encoding="utf-8") as f:
        f.write(job.to_json_line() + "\n")


def read_queue(queue_file: Path) -> list[QueueJob]:
    """Read all jobs from the queue file.

    Args:
        queue_file: Path to the JSONL queue file

    Returns:
        List of QueueJob instances
    """
    if not queue_file.exists():
        return []

    jobs = []
    with open(queue_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(QueueJob.from_json_line(line))
    return jobs


def get_pending_jobs(queue_file: Path) -> list[QueueJob]:
    """Get all pending jobs from the queue.

    Args:
        queue_file: Path to the JSONL queue file

    Returns:
        List of QueueJob with status="pending"
    """
    return [job for job in read_queue(queue_file) if job.status == "pending"]


@dataclass
class WatcherConfig:
    """Configuration for the file watcher."""

    raw_dir: Path  # Directory to watch for new videos
    queue_dir: Path  # Directory for queue files
    queue_filename: str = "pending.jsonl"

    @property
    def queue_file(self) -> Path:
        """Full path to the queue file."""
        return self.queue_dir / self.queue_filename


class VideoHandler:
    """Handler for video file events.

    This is a simple class that can be used with watchdog's Observer,
    or called directly for testing without threads.
    """

    def __init__(self, config: WatcherConfig):
        """Initialize the handler.

        Args:
            config: Watcher configuration
        """
        self.config = config
        self._processed_paths: set[str] = set()

    def on_created(self, path: Path) -> QueueJob | None:
        """Handle a new file being created.

        Args:
            path: Path to the new file

        Returns:
            QueueJob if a video was queued, None otherwise
        """
        if not is_video_file(path):
            return None

        # Avoid duplicate processing
        abs_path = str(path.resolve())
        if abs_path in self._processed_paths:
            return None
        self._processed_paths.add(abs_path)

        # Create and queue the job
        job = create_job_from_path(path)
        append_job_to_queue(job, self.config.queue_file)
        return job


def start_watcher(config: WatcherConfig) -> None:
    """Start watching a directory for new video files.

    This function blocks and runs until interrupted.
    Requires watchdog to be installed.

    Args:
        config: Watcher configuration

    Raises:
        ImportError: If watchdog is not installed
    """
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as e:
        raise ImportError(
            "watchdog is required for file watching. "
            "Install with: pip install yanhu-game-sessions[watcher]"
        ) from e

    class WatchdogHandler(FileSystemEventHandler):
        def __init__(self, video_handler: VideoHandler):
            self.video_handler = video_handler

        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            job = self.video_handler.on_created(path)
            if job:
                print(f"Queued: {path.name} (game={job.suggested_game or 'unknown'})")

    handler = VideoHandler(config)
    watchdog_handler = WatchdogHandler(handler)

    observer = Observer()
    observer.schedule(watchdog_handler, str(config.raw_dir), recursive=False)
    observer.start()

    print(f"Watching {config.raw_dir} for new videos...")
    print(f"Queue file: {config.queue_file}")
    print("Press Ctrl+C to stop.")

    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped watching.")

    observer.join()
