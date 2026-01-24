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
from zoneinfo import ZoneInfo

# Supported video extensions
VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov"})


def compute_file_key(path: Path) -> str:
    """Compute a deterministic dedup key for a file.

    Uses path + mtime + size + content fingerprint to create a unique hash.
    This ensures files are re-queued if they are replaced with different content,
    even when mtime granularity is coarse.

    Content fingerprint:
    - Files <= 256KB: hash full content
    - Files > 256KB: hash first 64KB + last 64KB

    Args:
        path: Path to the file

    Returns:
        16-character hex string (blake2b digest_size=8)
    """
    resolved = path.resolve()
    stat = resolved.stat()

    # Compute content fingerprint
    size = stat.st_size
    content_hash = hashlib.blake2b(digest_size=8)

    with open(resolved, "rb") as f:
        if size <= 256 * 1024:  # 256KB
            # Hash full content
            content_hash.update(f.read())
        else:
            # Hash first 64KB + last 64KB
            first_chunk = f.read(64 * 1024)
            content_hash.update(first_chunk)

            # Seek to last 64KB
            f.seek(-64 * 1024, 2)  # Seek from end
            last_chunk = f.read(64 * 1024)
            content_hash.update(last_chunk)

    # Combine metadata + content fingerprint
    key_data = f"{resolved}:{stat.st_mtime}:{stat.st_size}:{content_hash.hexdigest()}"
    final_hash = hashlib.blake2b(key_data.encode(), digest_size=8)
    return final_hash.hexdigest()


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
    suggested_game: str | None = None  # Optional game name hint (P3: from --default-game)
    raw_dir: str | None = None  # Source directory (for multi-dir debugging)
    # P3: Naming strategy fields
    raw_filename: str | None = None  # Filename with extension (backward compat)
    raw_stem: str | None = None  # Filename without extension (backward compat)
    suggested_tag: str | None = None  # Auto-generated tag with hash (backward compat)
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
        if self.raw_filename is not None:
            result["raw_filename"] = self.raw_filename
        if self.raw_stem is not None:
            result["raw_stem"] = self.raw_stem
        if self.suggested_tag is not None:
            result["suggested_tag"] = self.suggested_tag
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
            raw_filename=data.get("raw_filename"),
            raw_stem=data.get("raw_stem"),
            suggested_tag=data.get("suggested_tag"),
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
        """Get tag, with fallback to suggested_tag or 'run01'."""
        return self.tag or self.suggested_tag or "run01"


def is_video_file(path: Path) -> bool:
    """Check if a path is a supported video file.

    Args:
        path: Path to check

    Returns:
        True if the file has a supported video extension
    """
    return path.suffix.lower() in VIDEO_EXTENSIONS


def generate_tag_from_filename(filename: str) -> str:
    """Generate a unique tag from filename using stem + short hash.

    P3: Avoids hardcoded actor/game names and prevents confusion from
    files with same prefix.

    Args:
        filename: Full filename with extension

    Returns:
        Tag in format: <stem>__<hash8>
        Example: "actor_clip_副本.MP4" -> "actor_clip_副本__a1b2c3d4"
    """
    import hashlib

    # Get stem (filename without extension)
    stem = Path(filename).stem

    # Generate deterministic 8-char hash from full filename
    # Use MD5 for speed (not security-critical)
    hash_obj = hashlib.md5(filename.encode("utf-8"))
    short_hash = hash_obj.hexdigest()[:8]

    # Combine stem with hash
    return f"{stem}__{short_hash}"


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


def create_job_from_path(
    video_path: Path,
    raw_dir: Path | None = None,
    default_game: str = "unknown",
) -> QueueJob:
    """Create a queue job from a video file path.

    P3: Uses default_game instead of guessing, generates tag with hash
    to avoid confusion from files with same prefix.

    Args:
        video_path: Path to the video file
        raw_dir: Optional source directory (for multi-dir debugging)
        default_game: Default game name (P3: avoids hardcoded guessing)

    Returns:
        QueueJob instance
    """
    filename = video_path.name
    return QueueJob(
        created_at=datetime.now().isoformat(),
        raw_path=str(video_path.resolve()),
        status="pending",
        suggested_game=default_game,  # P3: use explicit default, no guessing
        raw_dir=str(raw_dir.resolve()) if raw_dir else None,
        raw_filename=filename,  # P3: store for reference
        raw_stem=video_path.stem,  # P3: stem for tag generation
        suggested_tag=generate_tag_from_filename(filename),  # P3: stem + hash
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
    default_game: str = "unknown"  # P3: default game name (avoids guessing)

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

        # Create and queue the job (P3: pass default_game from config)
        job = create_job_from_path(path, raw_dir=raw_dir, default_game=self.config.default_game)
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
    queued_jobs: list[QueueJob] = field(default_factory=list)  # Jobs queued this scan


def scan_directory(config: WatcherConfig, handler: VideoHandler) -> ScanResult:
    """Scan all configured directories for video files and enqueue new ones.

    Args:
        config: Watcher configuration
        handler: VideoHandler instance with state

    Returns:
        ScanResult with counts and list of queued jobs
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
                result.queued_jobs.append(job)
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
        ScanResult with counts and list of queued jobs
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
                result.queued_jobs.append(job)
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
        on_scan_complete: Optional callback(queued_jobs: list) called after each scan

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
            # Call on_scan_complete callback with queued jobs list
            if on_scan_complete:
                try:
                    on_scan_complete(result.queued_jobs)
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
        on_batch_queued: Optional callback(queued_jobs: list) called after file(s) queued

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
            # Debounce: track recently processed paths with timestamps
            # Format: {str(path): timestamp}
            self._recent_events: dict[str, float] = {}
            self._debounce_window = 1.0  # seconds

        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)

            # Debounce: skip if same path was processed within window
            import time

            path_str = str(path.resolve())
            now = time.time()
            if path_str in self._recent_events:
                last_time = self._recent_events[path_str]
                if now - last_time < self._debounce_window:
                    return  # Skip duplicate event within debounce window
            self._recent_events[path_str] = now

            # Clean up old entries (keep last 100)
            if len(self._recent_events) > 100:
                cutoff = now - self._debounce_window * 2
                self._recent_events = {
                    p: t for p, t in self._recent_events.items() if t > cutoff
                }

            # Find which raw_dir this file belongs to
            raw_dir = None
            parent_str = str(path.parent.resolve())
            if parent_str in dir_to_raw_dir:
                raw_dir = dir_to_raw_dir[parent_str]

            # Only print and trigger callbacks if actually queued
            job = self.video_handler.on_created(path, raw_dir=raw_dir)
            if job:
                print(f"Queued: {path.name} (game={job.suggested_game or 'unknown'})")
                if on_queued:
                    on_queued(job)
                # Trigger batch callback with single-element list
                if on_batch_queued:
                    try:
                        on_batch_queued([job])
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


def validate_outputs(session_dir: Path) -> tuple[bool, str]:
    """Validate that session outputs exist and are non-empty.

    Args:
        session_dir: Path to session directory

    Returns:
        Tuple of (success, error_message). error_message is empty if success.
    """
    # Check required files exist
    required_files = ["overview.md", "timeline.md", "highlights.md"]
    for filename in required_files:
        filepath = session_dir / filename
        if not filepath.exists():
            return False, f"Missing required output: {filename}"

    # Validate highlights.md has at least one highlight entry
    highlights_path = session_dir / "highlights.md"
    highlights_content = highlights_path.read_text(encoding="utf-8")
    if "- [" not in highlights_content:
        return False, "highlights.md contains no highlight entries (no '- [' line found)"

    # Validate timeline.md has content (segments or quotes)
    timeline_path = session_dir / "timeline.md"
    timeline_content = timeline_path.read_text(encoding="utf-8")
    if "### part_" not in timeline_content and "- quote:" not in timeline_content:
        return (
            False,
            "timeline.md contains no segment or quote content (no '### part_' or '- quote:' found)",
        )

    return True, ""


def process_job(
    job: QueueJob,
    output_dir: Path,
    force: bool = False,
    source_mode: str = "link",
    run_config: dict | None = None,
) -> JobResult:
    """Process a single job through the pipeline.

    Pipeline steps:
    1. ingest: link/copy video, create manifest
    2. segment: split into segments
    3. extract: extract frames
    4. analyze: run Claude vision (params from run_config)
    5. transcribe: run whisper_local (params from run_config)
    6. compose: generate timeline/overview/highlights
    7. validate: verify outputs exist and are non-empty

    Args:
        job: The job to process
        output_dir: Output directory for sessions
        force: Force reprocessing even if cached
        source_mode: "link" (hardlink/symlink, default) or "copy"
        run_config: Configuration dict with processing parameters (from preset)
                   If None, uses default fast preset

    Returns:
        JobResult with success/failure and details
    """
    # Use default fast preset if no config provided
    if run_config is None:
        run_config = get_preset_config("fast")
        run_config["preset"] = "fast"
        run_config["source_mode"] = source_mode
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

    # Determine segment duration based on strategy
    segment_duration = determine_segment_duration(
        video_path=raw_path,
        strategy=run_config.get("segment_strategy", "auto"),
        explicit_duration=run_config.get("segment_duration"),
    )
    strategy_name = run_config.get("segment_strategy", "auto")
    print(f"  Segment duration: {segment_duration}s (strategy: {strategy_name})")

    # Initialize transcribe_stats in case of early error
    from yanhu.transcriber import TranscribeStats
    transcribe_stats = TranscribeStats()

    try:
        # Step 1: Ingest
        game = job.get_game()
        tag = job.get_tag()

        # Parse job.created_at and convert to America/Los_Angeles timezone
        job_timestamp = datetime.fromisoformat(job.created_at)
        la_tz = ZoneInfo("America/Los_Angeles")

        if job_timestamp.tzinfo is None:
            # Naive datetime - assume America/Los_Angeles
            job_timestamp = job_timestamp.replace(tzinfo=la_tz)
        else:
            # Aware datetime - convert to America/Los_Angeles
            job_timestamp = job_timestamp.astimezone(la_tz)

        session_id = generate_session_id(game, tag, timestamp=job_timestamp)
        # CRITICAL: create_session_directory args are (session_id, output_dir)
        session_dir = create_session_directory(session_id, output_dir)
        source_local, source_metadata = copy_source_video(raw_path, session_dir, mode=source_mode)
        print(f"  Source mode: {source_metadata.source_mode}")
        if source_metadata.source_fallback_error:
            print(f"  {source_metadata.source_fallback_error}")
        manifest = create_manifest(
            session_id=session_id,
            source_video=raw_path,
            source_video_local=str(source_local),  # Already relative from copy_source_video
            segment_duration=segment_duration,  # Use adaptive duration
            source_metadata=source_metadata,
        )
        manifest.save(session_dir)

        # Step 2: Segment
        segment_infos = segment_video(manifest, session_dir)
        manifest.segments = segment_infos
        manifest.save(session_dir)

        # Step 3: Extract frames
        extract_frames(manifest, session_dir, frames_per_segment=6)
        manifest.save(session_dir)

        # Step 4: Analyze (params from run_config)
        analyze_session(
            manifest=manifest,
            session_dir=session_dir,
            backend="claude",
            max_frames=run_config.get("max_frames", 3),
            detail_level=run_config.get("detail_level", "L1"),
            max_facts=run_config.get("max_facts", 3),
            force=force,
        )

        # Step 5: Transcribe (params from run_config)
        # Progress callback for transcribe
        import time

        transcribe_start_time = time.time()
        last_progress_log = [0]  # Mutable to track in closure

        def transcribe_progress_callback(
            seg_id: str, status: str, result, stats
        ) -> None:
            """Log transcribe progress."""
            if status == "done" and result:
                item_count = len(result.asr_items) if result.asr_items else 0
                if item_count > 0:
                    print(f"    {seg_id}: {item_count} items")
                else:
                    print(f"    {seg_id}: empty")
            elif status == "cached":
                print(f"    {seg_id}: cached")
            elif status == "error":
                print(f"    {seg_id}: error")
            elif status in ("limit_reached", "duration_limit_reached"):
                msg = (
                    f"  Transcribe limit reached: {stats.processed}/{stats.total} "
                    f"segments processed"
                )
                print(msg)
            # Log progress summary every 5 segments
            if stats and stats.processed > 0 and stats.processed % 5 == 0:
                if stats.processed != last_progress_log[0]:
                    elapsed = time.time() - transcribe_start_time
                    progress_msg = (
                        f"  Progress: {stats.processed}/{stats.total} segments, "
                        f"elapsed {elapsed:.1f}s"
                    )
                    print(progress_msg)
                    last_progress_log[0] = stats.processed

        transcribe_limit = run_config.get("transcribe_limit")
        # Convert 0 to None (0 means no limit)
        if transcribe_limit == 0:
            transcribe_limit = None

        transcribe_stats = transcribe_session(
            manifest=manifest,
            session_dir=session_dir,
            backend=run_config.get("transcribe_backend", "whisper_local"),
            model_size=run_config.get("transcribe_model", "base"),
            compute_type=run_config.get("transcribe_compute", "int8"),
            beam_size=run_config.get("transcribe_beam_size", 1),
            vad_filter=run_config.get("transcribe_vad_filter", True),
            limit=transcribe_limit,
            max_total_seconds=run_config.get("transcribe_max_seconds"),
            on_progress=transcribe_progress_callback,
            force=force,
        )

        # Step 6: Compose
        write_timeline(manifest, session_dir)
        write_overview(manifest, session_dir)
        write_highlights(manifest, session_dir)

        # Step 7: Validate outputs
        valid, error_msg = validate_outputs(session_dir)

        # Prepare outputs with transcribe stats
        outputs = {
            "session_dir": str(session_dir),
            "timeline": str(session_dir / "timeline.md"),
            "overview": str(session_dir / "overview.md"),
            "highlights": str(session_dir / "highlights.md"),
            "run_config": run_config,  # Record parameters used
            "transcribe_processed": transcribe_stats.processed,
            "transcribe_total": transcribe_stats.total,
            "transcribe_limited": transcribe_stats.skipped_limit > 0,
        }

        if not valid:
            return JobResult(
                success=False,
                session_id=session_id,
                error=f"Output validation failed: {error_msg}",
                outputs=outputs,
            )

        return JobResult(
            success=True,
            session_id=session_id,
            outputs=outputs,
        )

    except Exception as e:
        return JobResult(
            success=False,
            error=str(e),
        )


# Preset configurations for processing quality vs speed tradeoffs
PRESETS = {
    "fast": {
        # Analysis parameters
        "max_frames": 3,
        "max_facts": 3,
        "detail_level": "L1",
        # Transcribe parameters
        "transcribe_backend": "whisper_local",
        "transcribe_model": "base",
        "transcribe_compute": "int8",
        "transcribe_beam_size": 1,
        "transcribe_vad_filter": True,
        "transcribe_limit": None,  # No limit by default
        "transcribe_max_seconds": None,  # No duration limit by default
    },
    "quality": {
        # Analysis parameters
        "max_frames": 6,
        "max_facts": 5,
        "detail_level": "L1",
        # Transcribe parameters
        "transcribe_backend": "whisper_local",
        "transcribe_model": "small",
        "transcribe_compute": "float32",
        "transcribe_beam_size": 5,
        "transcribe_vad_filter": True,
        "transcribe_limit": None,  # No limit by default
        "transcribe_max_seconds": None,  # No duration limit by default
    },
}

# Segment duration strategies (seconds)
SEGMENT_STRATEGIES = {
    "short": 5,  # High information density, good for short clips
    "medium": 15,  # Balanced, good for medium-length videos
    "long": 30,  # Traditional, good for long sessions
}


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Duration in seconds, or 0 if cannot determine
    """
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return 0


def determine_segment_duration(
    video_path: Path,
    strategy: str = "auto",
    explicit_duration: int | None = None,
) -> int:
    """Determine segment duration based on strategy and video length.

    Auto strategy (adaptive based on video duration):
    - <= 3 min (180s): 5s segments (high density for short clips)
    - <= 15 min (900s): 15s segments (balanced)
    - > 15 min: 30s segments (efficient for long sessions)

    Args:
        video_path: Path to video file
        strategy: "auto", "short", "medium", or "long"
        explicit_duration: If provided, overrides strategy

    Returns:
        Segment duration in seconds
    """
    # Explicit duration takes precedence
    if explicit_duration is not None:
        return explicit_duration

    # Named strategies
    if strategy in SEGMENT_STRATEGIES:
        return SEGMENT_STRATEGIES[strategy]

    # Auto strategy: adapt to video length
    if strategy == "auto":
        duration = get_video_duration(video_path)
        if duration == 0:
            # Fallback to medium if can't determine
            return 15

        # Adaptive thresholds
        if duration <= 180:  # <= 3 minutes
            return 5
        elif duration <= 900:  # <= 15 minutes
            return 15
        else:  # > 15 minutes
            return 30

    # Unknown strategy: default to medium
    return 15


def get_preset_config(preset_name: str) -> dict:
    """Get configuration for a preset.

    Args:
        preset_name: Name of preset ("fast" or "quality")

    Returns:
        Dict of configuration parameters

    Raises:
        ValueError: If preset_name is not recognized
    """
    if preset_name not in PRESETS:
        raise ValueError(
            f"Unknown preset: {preset_name}. Must be one of: {list(PRESETS.keys())}"
        )
    return PRESETS[preset_name].copy()


@dataclass
class RunQueueConfig:
    """Configuration for queue consumer."""

    queue_dir: Path
    output_dir: Path
    limit: int = 1
    dry_run: bool = False
    force: bool = False
    queue_filename: str = "pending.jsonl"
    raw_path_filter: set[str] | None = None  # Only process jobs with these raw_paths
    source_mode: str = "link"  # "link" (default: hardlink/symlink) or "copy"
    # Preset and override parameters
    preset: str = "fast"  # Preset name: "fast" or "quality"
    # Analysis overrides (None means use preset value)
    max_frames: int | None = None
    max_facts: int | None = None
    detail_level: str | None = None
    # Transcribe overrides (None means use preset value)
    transcribe_backend: str | None = None
    transcribe_model: str | None = None
    transcribe_compute: str | None = None
    transcribe_beam_size: int | None = None
    transcribe_vad_filter: bool | None = None
    transcribe_limit: int | None = None  # Max segments to transcribe (0 = no limit)
    transcribe_max_seconds: float | None = None  # Max total duration to transcribe
    # Segment strategy (adaptive duration)
    segment_duration: int | None = None  # Explicit duration in seconds
    segment_strategy: str = "auto"  # "auto", "short", "medium", "long"

    @property
    def queue_file(self) -> Path:
        """Full path to the queue file."""
        return self.queue_dir / self.queue_filename

    def resolve_config(self) -> dict:
        """Resolve final configuration by merging preset with overrides.

        Returns:
            Dict of all parameters to use for processing
        """
        # Start with preset
        preset_config = get_preset_config(self.preset)

        # Override with explicit parameters if provided
        if self.max_frames is not None:
            preset_config["max_frames"] = self.max_frames
        if self.max_facts is not None:
            preset_config["max_facts"] = self.max_facts
        if self.detail_level is not None:
            preset_config["detail_level"] = self.detail_level
        if self.transcribe_backend is not None:
            preset_config["transcribe_backend"] = self.transcribe_backend
        if self.transcribe_model is not None:
            preset_config["transcribe_model"] = self.transcribe_model
        if self.transcribe_compute is not None:
            preset_config["transcribe_compute"] = self.transcribe_compute
        if self.transcribe_beam_size is not None:
            preset_config["transcribe_beam_size"] = self.transcribe_beam_size
        if self.transcribe_vad_filter is not None:
            preset_config["transcribe_vad_filter"] = self.transcribe_vad_filter
        if self.transcribe_limit is not None:
            preset_config["transcribe_limit"] = self.transcribe_limit
        if self.transcribe_max_seconds is not None:
            preset_config["transcribe_max_seconds"] = self.transcribe_max_seconds

        # Add metadata
        preset_config["preset"] = self.preset
        preset_config["source_mode"] = self.source_mode
        preset_config["segment_duration"] = self.segment_duration
        preset_config["segment_strategy"] = self.segment_strategy

        return preset_config


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

    # Resolve configuration (preset + overrides)
    run_config = config.resolve_config()

    # Read pending jobs
    pending = get_pending_jobs(config.queue_file)
    if not pending:
        return result

    # Filter by raw_path if specified (CRITICAL: only process specified jobs)
    if config.raw_path_filter:
        pending = [job for job in pending if job.raw_path in config.raw_path_filter]
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
        job_result = process_job(
            job,
            config.output_dir,
            force=config.force,
            source_mode=config.source_mode,
            run_config=run_config,
        )
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
