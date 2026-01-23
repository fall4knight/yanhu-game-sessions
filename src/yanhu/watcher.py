"""File watcher for automatic video detection and queue management.

Watches a directory for new video files and adds them to a processing queue.
Does NOT trigger the full pipeline - only detects and queues.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Supported video extensions
VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov"})


def compute_file_key(path: Path) -> str:
    """Compute a deterministic dedup key for a file.

    Uses path + mtime + size to create a unique hash.
    This ensures files are re-queued if they are replaced with different content.

    Args:
        path: Path to the file

    Returns:
        SHA256 hash of the key components
    """
    resolved = path.resolve()
    stat = resolved.stat()
    key_data = f"{resolved}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


@dataclass
class WatcherState:
    """Persistent state for the watcher.

    Tracks seen files to prevent duplicate queueing across restarts.
    """

    last_scan_time: str | None = None  # ISO format timestamp
    seen_hashes: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "last_scan_time": self.last_scan_time,
            "seen_hashes": list(self.seen_hashes),
            "seen_count": len(self.seen_hashes),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WatcherState":
        """Create from dictionary."""
        return cls(
            last_scan_time=data.get("last_scan_time"),
            seen_hashes=set(data.get("seen_hashes", [])),
        )

    def has_seen(self, file_hash: str) -> bool:
        """Check if a file hash has been seen."""
        return file_hash in self.seen_hashes

    def mark_seen(self, file_hash: str) -> None:
        """Mark a file hash as seen."""
        self.seen_hashes.add(file_hash)

    def update_scan_time(self) -> None:
        """Update last scan time to now."""
        self.last_scan_time = datetime.now().isoformat()


def load_state(state_file: Path) -> WatcherState:
    """Load watcher state from file.

    Args:
        state_file: Path to state.json

    Returns:
        WatcherState instance (empty if file doesn't exist)
    """
    if not state_file.exists():
        return WatcherState()

    try:
        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)
        return WatcherState.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return WatcherState()


def save_state(state: WatcherState, state_file: Path) -> None:
    """Save watcher state to file atomically.

    Uses temp file + rename for atomic write.

    Args:
        state: WatcherState to save
        state_file: Path to state.json
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first
    fd, temp_path = tempfile.mkstemp(
        dir=state_file.parent,
        prefix=".state_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        # Atomic rename
        os.replace(temp_path, state_file)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


@dataclass
class QueueJob:
    """A job in the processing queue.

    Represents a video file waiting to be processed.
    """

    created_at: str  # ISO format timestamp
    raw_path: str  # Absolute path to the video file
    status: str = "pending"  # pending, processing, done, failed
    suggested_game: str | None = None  # Optional game name hint
    raw_dir: str | None = None  # Source directory (for multi-dir debugging)
    # Additional fields for run-queue
    game: str | None = None  # Explicit game name (overrides suggested_game)
    tag: str | None = None  # Run tag (e.g., "run01")
    session_id: str | None = None  # Generated session ID after processing
    error: str | None = None  # Error message if failed
    outputs: dict | None = None  # Output paths after successful processing

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "created_at": self.created_at,
            "raw_path": self.raw_path,
            "status": self.status,
        }
        if self.suggested_game is not None:
            result["suggested_game"] = self.suggested_game
        if self.raw_dir is not None:
            result["raw_dir"] = self.raw_dir
        if self.game is not None:
            result["game"] = self.game
        if self.tag is not None:
            result["tag"] = self.tag
        if self.session_id is not None:
            result["session_id"] = self.session_id
        if self.error is not None:
            result["error"] = self.error
        if self.outputs is not None:
            result["outputs"] = self.outputs
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "QueueJob":
        """Create from dictionary."""
        return cls(
            created_at=data["created_at"],
            raw_path=data["raw_path"],
            status=data.get("status", "pending"),
            suggested_game=data.get("suggested_game"),
            raw_dir=data.get("raw_dir"),
            game=data.get("game"),
            tag=data.get("tag"),
            session_id=data.get("session_id"),
            error=data.get("error"),
            outputs=data.get("outputs"),
        )

    def to_json_line(self) -> str:
        """Convert to JSON line for JSONL file."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> "QueueJob":
        """Create from JSON line."""
        return cls.from_dict(json.loads(line))

    def get_game(self) -> str:
        """Get game name, with fallback to suggested_game or 'unknown'."""
        return self.game or self.suggested_game or "unknown"

    def get_tag(self) -> str:
        """Get tag, with fallback to 'run01'."""
        return self.tag or "run01"


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
        remainder = name[date_prefix.end() :]
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


def create_job_from_path(video_path: Path, raw_dir: Path | None = None) -> QueueJob:
    """Create a queue job from a video file path.

    Args:
        video_path: Path to the video file
        raw_dir: Optional source directory (for multi-dir debugging)

    Returns:
        QueueJob instance
    """
    return QueueJob(
        created_at=datetime.now().isoformat(),
        raw_path=str(video_path.resolve()),
        status="pending",
        suggested_game=guess_game_from_filename(video_path.name),
        raw_dir=str(raw_dir.resolve()) if raw_dir else None,
    )


def append_job_to_queue(job: QueueJob, queue_file: Path) -> None:
    """Append a job to the queue file (JSONL format).

    Creates the queue file and parent directories if they don't exist.
    Uses append + flush for durability.

    Args:
        job: The job to append
        queue_file: Path to the JSONL queue file
    """
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    with open(queue_file, "a", encoding="utf-8") as f:
        f.write(job.to_json_line() + "\n")
        f.flush()
        os.fsync(f.fileno())


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
    """Configuration for the file watcher.

    Supports multiple raw directories. Files moved between directories
    will be re-queued (dedup key includes full resolved path).
    """

    raw_dirs: list[Path]  # Directories to watch for new videos
    queue_dir: Path  # Directory for queue files
    queue_filename: str = "pending.jsonl"
    state_filename: str = "state.json"

    @property
    def queue_file(self) -> Path:
        """Full path to the queue file."""
        return self.queue_dir / self.queue_filename

    @property
    def state_file(self) -> Path:
        """Full path to the state file."""
        return self.queue_dir / self.state_filename

    @classmethod
    def from_single_dir(cls, raw_dir: Path, queue_dir: Path, **kwargs) -> "WatcherConfig":
        """Create config from a single raw directory (backwards compatibility)."""
        return cls(raw_dirs=[raw_dir], queue_dir=queue_dir, **kwargs)


class VideoHandler:
    """Handler for video file events.

    This is a simple class that can be used with watchdog's Observer,
    or called directly for testing without threads.

    Uses persistent state for deduplication across restarts.
    """

    def __init__(self, config: WatcherConfig, state: WatcherState | None = None):
        """Initialize the handler.

        Args:
            config: Watcher configuration
            state: Optional pre-loaded state (loads from file if not provided)
        """
        self.config = config
        self._state = state if state is not None else load_state(config.state_file)

    @property
    def state(self) -> WatcherState:
        """Get the current watcher state."""
        return self._state

    def on_created(self, path: Path, raw_dir: Path | None = None) -> QueueJob | None:
        """Handle a new file being created.

        Uses file hash (path + mtime + size) for deduplication.
        The dedup key includes the full resolved path, so moving a file
        to a different directory will allow it to be re-queued.

        Args:
            path: Path to the new file
            raw_dir: Source directory (for multi-dir tracking)

        Returns:
            QueueJob if a video was queued, None otherwise
        """
        if not is_video_file(path):
            return None

        # Compute dedup key (includes full resolved path)
        try:
            file_hash = compute_file_key(path)
        except OSError:
            # File might have been deleted
            return None

        # Check if already seen
        if self._state.has_seen(file_hash):
            return None

        # Mark as seen and save state
        self._state.mark_seen(file_hash)
        save_state(self._state, self.config.state_file)

        # Create and queue the job
        job = create_job_from_path(path, raw_dir=raw_dir)
        append_job_to_queue(job, self.config.queue_file)
        return job

    def save_state(self) -> None:
        """Save current state to file."""
        save_state(self._state, self.config.state_file)


@dataclass
class ScanResult:
    """Result of a directory scan."""

    found: int = 0
    queued: int = 0
    skipped: int = 0


def scan_directory(config: WatcherConfig, handler: VideoHandler) -> ScanResult:
    """Scan all configured directories for video files and enqueue new ones.

    Args:
        config: Watcher configuration
        handler: VideoHandler instance with state

    Returns:
        ScanResult with counts
    """
    result = ScanResult()

    for raw_dir in config.raw_dirs:
        if not raw_dir.exists():
            continue
        for path in raw_dir.iterdir():
            if not path.is_file():
                continue
            if not is_video_file(path):
                continue

            result.found += 1
            job = handler.on_created(path, raw_dir=raw_dir)
            if job:
                result.queued += 1
            else:
                result.skipped += 1

    # Update scan time
    handler.state.update_scan_time()
    handler.save_state()

    return result


def scan_once(
    config: WatcherConfig,
    on_queued: callable | None = None,
) -> ScanResult:
    """Scan all directories once and enqueue new videos, then exit.

    Args:
        config: Watcher configuration
        on_queued: Optional callback(job) called for each queued job

    Returns:
        ScanResult with counts
    """
    handler = VideoHandler(config)
    result = ScanResult()

    for raw_dir in config.raw_dirs:
        if not raw_dir.exists():
            continue
        for path in raw_dir.iterdir():
            if not path.is_file():
                continue
            if not is_video_file(path):
                continue

            result.found += 1
            job = handler.on_created(path, raw_dir=raw_dir)
            if job:
                result.queued += 1
                if on_queued:
                    on_queued(job)
            else:
                result.skipped += 1

    # Update scan time
    handler.state.update_scan_time()
    handler.save_state()

    return result


def start_polling(
    config: WatcherConfig,
    interval: int,
    on_queued: callable | None = None,
    on_scan_complete: callable | None = None,
) -> None:
    """Poll directories at regular intervals for new video files.

    This function blocks and runs until interrupted.
    Does not require watchdog.

    Args:
        config: Watcher configuration
        interval: Seconds between scans
        on_queued: Optional callback(job) called for each queued job
        on_scan_complete: Optional callback(queued_count) called after each scan
    """
    import time

    handler = VideoHandler(config)

    dirs_str = ", ".join(str(d) for d in config.raw_dirs)
    print(f"Polling [{dirs_str}] every {interval}s for new videos...")
    print(f"Queue file: {config.queue_file}")
    print(f"State file: {config.state_file}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            result = scan_directory(config, handler)
            if result.queued > 0:
                print(
                    f"Scan: found={result.found}, queued={result.queued}, skipped={result.skipped}"
                )
            # Call on_scan_complete callback with queued count
            if on_scan_complete:
                try:
                    on_scan_complete(result.queued)
                except Exception as e:
                    print(f"Warning: on_scan_complete callback failed: {e}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped polling.")


def start_watcher(
    config: WatcherConfig,
    on_queued: callable | None = None,
    on_batch_queued: callable | None = None,
) -> None:
    """Start watching directories for new video files using watchdog.

    This function blocks and runs until interrupted.
    Requires watchdog to be installed.

    Args:
        config: Watcher configuration
        on_queued: Optional callback(job) called for each queued job
        on_batch_queued: Optional callback(count) called after file(s) queued

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

    # Build a map from directory path to raw_dir for proper tracking
    dir_to_raw_dir = {str(d.resolve()): d for d in config.raw_dirs}

    class WatchdogHandler(FileSystemEventHandler):
        def __init__(self, video_handler: VideoHandler):
            self.video_handler = video_handler

        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            # Find which raw_dir this file belongs to
            raw_dir = None
            parent_str = str(path.parent.resolve())
            if parent_str in dir_to_raw_dir:
                raw_dir = dir_to_raw_dir[parent_str]
            job = self.video_handler.on_created(path, raw_dir=raw_dir)
            if job:
                print(f"Queued: {path.name} (game={job.suggested_game or 'unknown'})")
                if on_queued:
                    on_queued(job)
                # Trigger batch callback for each queued file
                if on_batch_queued:
                    try:
                        on_batch_queued(1)
                    except Exception as e:
                        print(f"Warning: on_batch_queued callback failed: {e}")

    handler = VideoHandler(config)
    watchdog_handler = WatchdogHandler(handler)

    observer = Observer()
    for raw_dir in config.raw_dirs:
        observer.schedule(watchdog_handler, str(raw_dir), recursive=False)
    observer.start()

    dirs_str = ", ".join(str(d) for d in config.raw_dirs)
    print(f"Watching [{dirs_str}] for new videos...")
    print(f"Queue file: {config.queue_file}")
    print(f"State file: {config.state_file}")
    print("Press Ctrl+C to stop.")

    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped watching.")

    observer.join()


def write_queue(jobs: list[QueueJob], queue_file: Path) -> None:
    """Write all jobs to the queue file (overwrites existing).

    Args:
        jobs: List of jobs to write
        queue_file: Path to the JSONL queue file
    """
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    with open(queue_file, "w", encoding="utf-8") as f:
        for job in jobs:
            f.write(job.to_json_line() + "\n")


def update_job_status(
    queue_file: Path,
    raw_path: str,
    new_status: str,
    session_id: str | None = None,
    error: str | None = None,
    outputs: dict | None = None,
) -> None:
    """Update a job's status in the queue file.

    Finds the job by raw_path and updates its status.
    Rewrites the entire queue file to maintain atomicity.

    Args:
        queue_file: Path to the JSONL queue file
        raw_path: The raw_path to identify the job
        new_status: New status to set
        session_id: Session ID if processing succeeded
        error: Error message if failed
        outputs: Output paths if succeeded
    """
    jobs = read_queue(queue_file)
    for job in jobs:
        if job.raw_path == raw_path:
            job.status = new_status
            if session_id is not None:
                job.session_id = session_id
            if error is not None:
                job.error = error
            if outputs is not None:
                job.outputs = outputs
            break
    write_queue(jobs, queue_file)


@dataclass
class JobResult:
    """Result of processing a job."""

    success: bool
    session_id: str | None = None
    error: str | None = None
    outputs: dict | None = None


def process_job(
    job: QueueJob,
    output_dir: Path,
    force: bool = False,
) -> JobResult:
    """Process a single job through the pipeline.

    Pipeline steps:
    1. ingest: copy video, create manifest
    2. segment: split into segments
    3. extract: extract frames
    4. analyze: run Claude vision (conservative params)
    5. transcribe: run whisper_local (conservative params)
    6. compose: generate timeline/overview/highlights

    Args:
        job: The job to process
        output_dir: Output directory for sessions
        force: Force reprocessing even if cached

    Returns:
        JobResult with success/failure and details
    """
    from yanhu.analyzer import analyze_session
    from yanhu.composer import write_highlights, write_overview, write_timeline
    from yanhu.extractor import extract_frames
    from yanhu.manifest import create_manifest
    from yanhu.segmenter import segment_video
    from yanhu.session import (
        copy_source_video,
        create_session_directory,
        generate_session_id,
    )
    from yanhu.transcriber import transcribe_session

    raw_path = Path(job.raw_path)

    # Check if raw file exists
    if not raw_path.exists():
        return JobResult(
            success=False,
            error=f"Raw video not found: {job.raw_path}",
        )

    try:
        # Step 1: Ingest
        game = job.get_game()
        tag = job.get_tag()
        session_id = generate_session_id(game, tag)
        session_dir = create_session_directory(output_dir, session_id)
        source_local = copy_source_video(raw_path, session_dir)
        manifest = create_manifest(
            session_id=session_id,
            source_video=str(raw_path),
            source_video_local=str(source_local.relative_to(session_dir)),
            segment_duration=60,
        )
        manifest.save(session_dir / "manifest.json")

        # Step 2: Segment
        segment_video(manifest, session_dir)
        manifest.save(session_dir / "manifest.json")

        # Step 3: Extract frames
        extract_frames(manifest, session_dir, frames_per_segment=6)
        manifest.save(session_dir / "manifest.json")

        # Step 4: Analyze (conservative params)
        analyze_session(
            manifest=manifest,
            session_dir=session_dir,
            backend="claude",
            max_frames=3,
            detail_level="L1",
            max_facts=3,
            force=force,
        )

        # Step 5: Transcribe (conservative params)
        transcribe_session(
            manifest=manifest,
            session_dir=session_dir,
            backend="whisper_local",
            model_size="base",
            compute_type="int8",
            force=force,
        )

        # Step 6: Compose
        write_timeline(manifest, session_dir)
        write_overview(manifest, session_dir)
        write_highlights(manifest, session_dir)

        return JobResult(
            success=True,
            session_id=session_id,
            outputs={
                "session_dir": str(session_dir),
                "timeline": str(session_dir / "timeline.md"),
                "overview": str(session_dir / "overview.md"),
                "highlights": str(session_dir / "highlights.md"),
            },
        )

    except Exception as e:
        return JobResult(
            success=False,
            error=str(e),
        )


@dataclass
class RunQueueConfig:
    """Configuration for queue consumer."""

    queue_dir: Path
    output_dir: Path
    limit: int = 1
    dry_run: bool = False
    force: bool = False
    queue_filename: str = "pending.jsonl"

    @property
    def queue_file(self) -> Path:
        """Full path to the queue file."""
        return self.queue_dir / self.queue_filename


@dataclass
class RunQueueResult:
    """Result of running the queue consumer."""

    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


def run_queue(
    config: RunQueueConfig,
    on_job_start: callable | None = None,
    on_job_complete: callable | None = None,
) -> RunQueueResult:
    """Run the queue consumer.

    Reads pending jobs from the queue file and processes them.

    Args:
        config: Consumer configuration
        on_job_start: Callback(job) called before processing each job
        on_job_complete: Callback(job, result) called after each job

    Returns:
        RunQueueResult with counts
    """
    result = RunQueueResult()

    # Read pending jobs
    pending = get_pending_jobs(config.queue_file)
    if not pending:
        return result

    # Limit to N jobs
    jobs_to_process = pending[: config.limit]

    for job in jobs_to_process:
        if on_job_start:
            on_job_start(job)

        if config.dry_run:
            # Dry-run: don't execute, don't update status
            result.skipped += 1
            if on_job_complete:
                on_job_complete(job, None)
            continue

        # Update status to processing
        update_job_status(config.queue_file, job.raw_path, "processing")

        # Process the job
        job_result = process_job(job, config.output_dir, config.force)
        result.processed += 1

        if job_result.success:
            result.succeeded += 1
            update_job_status(
                config.queue_file,
                job.raw_path,
                "done",
                session_id=job_result.session_id,
                outputs=job_result.outputs,
            )
        else:
            result.failed += 1
            update_job_status(
                config.queue_file,
                job.raw_path,
                "failed",
                error=job_result.error,
            )

        if on_job_complete:
            on_job_complete(job, job_result)

    return result
