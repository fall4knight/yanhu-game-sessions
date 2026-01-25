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
    status: str = "pending"  # pending, processing, done, failed, cancelled, cancel_requested
    job_id: str | None = None  # Unique job identifier (auto-generated if None)
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
    preset: str | None = None  # Processing preset (fast/quality)
    media: dict | None = None  # Media metadata from ffprobe (MediaInfo.to_dict())
    estimated_segments: int | None = None  # Estimated number of segments
    estimated_runtime_sec: int | None = None  # Estimated processing time in seconds
    asr_models: list[str] | None = None  # ASR models to run (e.g., ["whisper_local", "mock"])
    whisper_device: str | None = None  # Whisper device mode ("cpu" or "cuda")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "created_at": self.created_at,
            "raw_path": self.raw_path,
            "status": self.status,
        }
        if self.job_id is not None:
            result["job_id"] = self.job_id
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
        if self.preset is not None:
            result["preset"] = self.preset
        if self.media is not None:
            result["media"] = self.media
        if self.estimated_segments is not None:
            result["estimated_segments"] = self.estimated_segments
        if self.estimated_runtime_sec is not None:
            result["estimated_runtime_sec"] = self.estimated_runtime_sec
        if self.asr_models is not None:
            result["asr_models"] = self.asr_models
        if self.whisper_device is not None:
            result["whisper_device"] = self.whisper_device
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "QueueJob":
        """Create from dictionary."""
        return cls(
            created_at=data["created_at"],
            raw_path=data["raw_path"],
            status=data.get("status", "pending"),
            job_id=data.get("job_id"),
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
            preset=data.get("preset"),
            media=data.get("media"),
            estimated_segments=data.get("estimated_segments"),
            estimated_runtime_sec=data.get("estimated_runtime_sec"),
            asr_models=data.get("asr_models"),
            whisper_device=data.get("whisper_device"),
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


def generate_job_id() -> str:
    """Generate a unique job ID.

    Uses timestamp + short hash for readability and uniqueness.
    Format: job_YYYYMMDD_HHMMSS_<hash8>

    Returns:
        Job ID string
    """
    import hashlib
    import uuid

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    # Generate short hash from UUID for uniqueness
    hash_obj = hashlib.md5(str(uuid.uuid4()).encode())
    short_hash = hash_obj.hexdigest()[:8]

    return f"job_{timestamp}_{short_hash}"


def save_job_to_file(job: QueueJob, jobs_dir: Path) -> None:
    """Save a job to a per-job JSON file.

    Uses atomic write (temp file + rename).

    Args:
        job: The job to save
        jobs_dir: Directory for job files
    """
    # Ensure job has an ID
    if not job.job_id:
        job.job_id = generate_job_id()

    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_file = jobs_dir / f"{job.job_id}.json"

    # Write to temp file first
    fd, temp_path = tempfile.mkstemp(
        dir=jobs_dir,
        prefix=".job_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(job.to_dict(), f, ensure_ascii=False, indent=2)
        # Atomic rename
        os.replace(temp_path, job_file)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def load_job_from_file(job_file: Path) -> QueueJob | None:
    """Load a job from a JSON file.

    Args:
        job_file: Path to job JSON file

    Returns:
        QueueJob instance, or None if file cannot be read
    """
    if not job_file.exists():
        return None

    try:
        with open(job_file, encoding="utf-8") as f:
            data = json.load(f)
        return QueueJob.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return None


def list_all_jobs(jobs_dir: Path) -> list[QueueJob]:
    """List all jobs from the jobs directory.

    Args:
        jobs_dir: Directory containing job JSON files

    Returns:
        List of QueueJob instances, sorted by created_at descending
    """
    if not jobs_dir.exists():
        return []

    jobs = []
    for job_file in jobs_dir.glob("job_*.json"):
        job = load_job_from_file(job_file)
        if job:
            jobs.append(job)

    # Sort by created_at descending (newest first)
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs


def get_job_by_id(job_id: str, jobs_dir: Path) -> QueueJob | None:
    """Get a job by its ID.

    Args:
        job_id: The job ID
        jobs_dir: Directory containing job JSON files

    Returns:
        QueueJob instance, or None if not found
    """
    job_file = jobs_dir / f"{job_id}.json"
    return load_job_from_file(job_file)


def update_job_by_id(
    job_id: str,
    jobs_dir: Path,
    status: str | None = None,
    session_id: str | None = None,
    error: str | None = None,
    outputs: dict | None = None,
) -> QueueJob | None:
    """Update a job by its ID.

    Args:
        job_id: The job ID
        jobs_dir: Directory containing job JSON files
        status: New status (if provided)
        session_id: Session ID (if provided)
        error: Error message (if provided)
        outputs: Output paths (if provided)

    Returns:
        Updated QueueJob, or None if not found
    """
    job = get_job_by_id(job_id, jobs_dir)
    if not job:
        return None

    # Update fields
    if status is not None:
        job.status = status
    if session_id is not None:
        job.session_id = session_id
    if error is not None:
        job.error = error
    if outputs is not None:
        job.outputs = outputs

    # Save back
    save_job_to_file(job, jobs_dir)
    return job


def cancel_job(job_id: str, jobs_dir: Path) -> QueueJob | None:
    """Cancel a job by its ID.

    Transitions:
    - pending → cancelled
    - processing → cancel_requested

    Args:
        job_id: The job ID
        jobs_dir: Directory containing job JSON files

    Returns:
        Updated QueueJob, or None if not found or already completed
    """
    job = get_job_by_id(job_id, jobs_dir)
    if not job:
        return None

    # Only cancel pending or processing jobs
    if job.status == "pending":
        job.status = "cancelled"
        save_job_to_file(job, jobs_dir)
        return job
    elif job.status == "processing":
        job.status = "cancel_requested"
        save_job_to_file(job, jobs_dir)
        return job
    else:
        # Already done/failed/cancelled - no change
        return job


def get_pending_jobs_v2(jobs_dir: Path) -> list[QueueJob]:
    """Get all pending jobs from the jobs directory.

    Args:
        jobs_dir: Directory containing job JSON files

    Returns:
        List of QueueJob with status="pending", sorted by created_at ascending
    """
    all_jobs = list_all_jobs(jobs_dir)
    pending = [job for job in all_jobs if job.status == "pending"]
    # Sort by created_at ascending (oldest first) for FIFO processing
    pending.sort(key=lambda j: j.created_at)
    return pending


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
            "This feature is not available in the desktop build. "
            "Use the CLI version for file watching capabilities."
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
class AsrErrorSummary:
    """Summary of ASR errors for a session."""

    total_segments: int = 0
    failed_segments: int = 0
    dependency_error: str | None = None  # ffmpeg missing, etc.
    error_samples: list[str] = field(default_factory=list)  # First few error messages


def aggregate_asr_errors(session_dir: Path, asr_models: list[str] | None) -> AsrErrorSummary | None:
    """Aggregate ASR errors from per-model transcript files.

    Checks for:
    - Dependency failures (ffmpeg missing) - affects all segments
    - Partial failures - some segments failed

    Args:
        session_dir: Path to session directory
        asr_models: List of ASR models that were run

    Returns:
        AsrErrorSummary if errors found, None otherwise
    """
    if not asr_models:
        return None

    # Check each model for errors
    for model_key in asr_models:
        transcript_path = session_dir / "outputs" / "asr" / model_key / "transcript.json"
        if not transcript_path.exists():
            continue

        try:
            with open(transcript_path, encoding="utf-8") as f:
                results = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if not results:
            continue

        # Collect error information
        total = len(results)
        failed = 0
        ffmpeg_missing_count = 0
        error_samples = []

        for entry in results:
            error_msg = entry.get("asr_error")
            if error_msg:
                failed += 1
                # Check for ffmpeg dependency error
                error_lower = error_msg.lower()
                is_ffmpeg_error = (
                    "ffmpeg" in error_lower
                    and ("not found" in error_lower or "no such file" in error_lower)
                )
                if is_ffmpeg_error:
                    ffmpeg_missing_count += 1
                # Collect first few error samples
                if len(error_samples) < 3:
                    error_samples.append(error_msg[:200])  # Truncate long errors

        if failed > 0:
            summary = AsrErrorSummary(
                total_segments=total,
                failed_segments=failed,
                error_samples=error_samples,
            )

            # Determine if this is a dependency failure
            # If all segments failed with ffmpeg missing, it's a dependency error
            if ffmpeg_missing_count == total:
                summary.dependency_error = (
                    "ffmpeg not found - whisper_local requires ffmpeg to extract audio. "
                    "Install ffmpeg and retry."
                )

            return summary

    return None


@dataclass
class JobResult:
    """Result of processing a job."""

    success: bool
    session_id: str | None = None
    error: str | None = None
    outputs: dict | None = None
    asr_errors: AsrErrorSummary | None = None  # ASR error aggregation




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
    from yanhu.verify import validate_outputs

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
        # Auto-detect analyze backend based on API key availability
        import os
        analyze_backend = "claude" if os.environ.get("ANTHROPIC_API_KEY") else "mock"
        analyze_session(
            manifest=manifest,
            session_dir=session_dir,
            backend=analyze_backend,
            max_frames=run_config.get("max_frames", 3),
            detail_level=run_config.get("detail_level", "L1"),
            max_facts=run_config.get("max_facts", 3),
            force=force,
        )

        # Step 5: Transcribe (params from run_config)
        # Initialize progress tracker for transcribe stage
        from yanhu.progress import ProgressTracker

        # Determine coverage for progress tracker
        transcribe_limit = run_config.get("transcribe_limit")
        if transcribe_limit == 0:
            transcribe_limit = None

        transcribe_coverage = None
        if transcribe_limit is not None:
            # If limit is set, prepare coverage metadata
            total_segments = len(manifest.segments)
            transcribe_coverage = {
                "processed": min(transcribe_limit, total_segments),
                "total": total_segments,
                "skipped_limit": max(0, total_segments - transcribe_limit),
            }

        progress_tracker = ProgressTracker(
            session_id=manifest.session_id,
            session_dir=session_dir,
            stage="transcribe",
            total=len(manifest.segments),
            coverage=transcribe_coverage,
        )

        # Progress callback for transcribe
        last_progress_log = [0]  # Mutable to track in closure

        def transcribe_progress_callback(
            seg_id: str, status: str, result, stats
        ) -> None:
            """Log transcribe progress and update progress tracker."""
            # Update progress tracker with current done count
            # stats.processed tracks successfully processed segments
            if stats:
                progress_tracker.update(stats.processed)

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
                    # Use progress tracker for formatted output
                    print(f"  {progress_tracker.format_console_line()}")
                    last_progress_log[0] = stats.processed

        # Determine which ASR models to run
        asr_models = job.asr_models
        if asr_models is None:
            # Backward compatibility: use default or backend from run_config
            backend = run_config.get("transcribe_backend", "whisper_local")
            asr_models = [backend]

        transcribe_stats = transcribe_session(
            manifest=manifest,
            session_dir=session_dir,
            backend=run_config.get("transcribe_backend", "whisper_local"),
            model_size=run_config.get("transcribe_model", "base"),
            compute_type=run_config.get("transcribe_compute", "int8"),
            device=run_config.get("whisper_device", "cpu"),
            beam_size=run_config.get("transcribe_beam_size", 1),
            vad_filter=run_config.get("transcribe_vad_filter", True),
            limit=transcribe_limit,
            max_total_seconds=run_config.get("transcribe_max_seconds"),
            on_progress=transcribe_progress_callback,
            force=force,
            asr_models=asr_models,
        )

        # Finalize progress tracker (transition to compose stage)
        progress_tracker.finalize(stage="compose")

        # Save transcribe coverage to manifest if limit was used
        if transcribe_stats.skipped_limit > 0:
            manifest.transcribe_coverage = {
                "processed": transcribe_stats.processed,
                "total": transcribe_stats.total,
                "skipped_limit": transcribe_stats.skipped_limit,
            }

        # Save ASR models to manifest
        if asr_models:
            manifest.asr_models = asr_models

        # Save manifest if updated
        if transcribe_stats.skipped_limit > 0 or asr_models:
            manifest.save(session_dir)

        # Step 6: Compose
        write_timeline(manifest, session_dir)
        write_overview(manifest, session_dir)
        write_highlights(manifest, session_dir)

        # Update progress to done
        progress_tracker.finalize(stage="done")

        # Step 7: Aggregate ASR errors
        asr_error_summary = aggregate_asr_errors(session_dir, asr_models)

        # Step 8: Validate outputs
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

        # Add ASR error info to outputs if present
        if asr_error_summary:
            outputs["asr_error_summary"] = {
                "total_segments": asr_error_summary.total_segments,
                "failed_segments": asr_error_summary.failed_segments,
                "dependency_error": asr_error_summary.dependency_error,
                "error_samples": asr_error_summary.error_samples,
            }

        if not valid:
            return JobResult(
                success=False,
                session_id=session_id,
                error=f"Output validation failed: {error_msg}",
                outputs=outputs,
                asr_errors=asr_error_summary,
            )

        # Check for dependency failures - these should fail the job
        if asr_error_summary and asr_error_summary.dependency_error:
            return JobResult(
                success=False,
                session_id=session_id,
                error=asr_error_summary.dependency_error,
                outputs=outputs,
                asr_errors=asr_error_summary,
            )

        # Check for partial failures - mark as success with warnings
        # (User can see errors in Transcripts tab)
        return JobResult(
            success=True,
            session_id=session_id,
            outputs=outputs,
            asr_errors=asr_error_summary,
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


@dataclass
class MediaInfo:
    """Media file metadata from ffprobe."""

    duration_sec: float | None = None
    file_size_bytes: int | None = None
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    bitrate_kbps: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {}
        if self.duration_sec is not None:
            result["duration_sec"] = self.duration_sec
        if self.file_size_bytes is not None:
            result["file_size_bytes"] = self.file_size_bytes
        if self.container is not None:
            result["container"] = self.container
        if self.video_codec is not None:
            result["video_codec"] = self.video_codec
        if self.audio_codec is not None:
            result["audio_codec"] = self.audio_codec
        if self.width is not None:
            result["width"] = self.width
        if self.height is not None:
            result["height"] = self.height
        if self.fps is not None:
            result["fps"] = self.fps
        if self.bitrate_kbps is not None:
            result["bitrate_kbps"] = self.bitrate_kbps
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "MediaInfo":
        """Create from dictionary."""
        return cls(
            duration_sec=data.get("duration_sec"),
            file_size_bytes=data.get("file_size_bytes"),
            container=data.get("container"),
            video_codec=data.get("video_codec"),
            audio_codec=data.get("audio_codec"),
            width=data.get("width"),
            height=data.get("height"),
            fps=data.get("fps"),
            bitrate_kbps=data.get("bitrate_kbps"),
        )


def probe_media(video_path: Path) -> MediaInfo:
    """Probe media file for metadata using ffprobe.

    Best-effort extraction of media info. Gracefully degrades if ffprobe
    is unavailable (returns file size only).

    Args:
        video_path: Path to video file

    Returns:
        MediaInfo with available metadata
    """
    import subprocess

    from yanhu.ffmpeg_utils import find_ffprobe

    info = MediaInfo()

    # Always get file size (no ffprobe needed)
    try:
        info.file_size_bytes = video_path.stat().st_size
    except OSError:
        pass

    # Find ffprobe (with fallback paths for packaged apps)
    ffprobe_path = find_ffprobe()
    if not ffprobe_path:
        # Graceful degradation: return file size only
        return info

    # Try ffprobe for detailed metadata
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # ffprobe failed, return basic info
            return info

        data = json.loads(result.stdout)

        # Extract format info
        if "format" in data:
            fmt = data["format"]
            if "duration" in fmt:
                try:
                    info.duration_sec = float(fmt["duration"])
                except (ValueError, TypeError):
                    pass
            if "format_name" in fmt:
                info.container = fmt["format_name"]
            if "bit_rate" in fmt:
                try:
                    info.bitrate_kbps = int(int(fmt["bit_rate"]) / 1000)
                except (ValueError, TypeError):
                    pass

        # Extract stream info
        if "streams" in data:
            for stream in data["streams"]:
                codec_type = stream.get("codec_type")

                if codec_type == "video" and info.video_codec is None:
                    # First video stream
                    info.video_codec = stream.get("codec_name")
                    if "width" in stream:
                        try:
                            info.width = int(stream["width"])
                        except (ValueError, TypeError):
                            pass
                    if "height" in stream:
                        try:
                            info.height = int(stream["height"])
                        except (ValueError, TypeError):
                            pass
                    # Calculate FPS from avg_frame_rate
                    if "avg_frame_rate" in stream:
                        try:
                            fps_str = stream["avg_frame_rate"]
                            if "/" in fps_str:
                                num, den = fps_str.split("/")
                                if int(den) != 0:
                                    info.fps = float(num) / float(den)
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass

                elif codec_type == "audio" and info.audio_codec is None:
                    # First audio stream
                    info.audio_codec = stream.get("codec_name")

    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
        # ffprobe unavailable or failed - return basic info
        pass

    return info


def calculate_job_estimates(
    media_info: MediaInfo,
    segment_strategy: str = "auto",
    preset: str = "fast",
    metrics_file: Path | None = None,
) -> tuple[int, int]:
    """Calculate estimated segments and runtime for a job.

    Uses persistent metrics if available to improve accuracy.

    Args:
        media_info: Media metadata from probe_media
        segment_strategy: Segmentation strategy (auto/short/medium/long)
        preset: Processing preset (fast/quality)
        metrics_file: Optional path to _metrics.json for improved estimates

    Returns:
        Tuple of (estimated_segments, estimated_runtime_sec)
    """
    import math

    # Default estimates if duration unavailable
    if media_info.duration_sec is None or media_info.duration_sec <= 0:
        return (0, 0)

    # Determine segment duration
    duration_sec = media_info.duration_sec

    if segment_strategy == "short":
        segment_duration = 5
    elif segment_strategy == "medium":
        segment_duration = 15
    elif segment_strategy == "long":
        segment_duration = 30
    else:  # auto
        if duration_sec <= 180:  # <= 3 minutes
            segment_duration = 5
        elif duration_sec <= 900:  # <= 15 minutes
            segment_duration = 15
        else:
            segment_duration = 30

    # Calculate estimated segments
    estimated_segments = math.ceil(duration_sec / segment_duration)

    # Try to use metrics for better estimate
    if metrics_file and metrics_file.exists():
        try:
            from yanhu.metrics import MetricsStore

            store = MetricsStore(metrics_file)
            metrics = store.get_metrics(preset, segment_duration)
            if metrics and metrics.samples > 0 and metrics.avg_rate_ema > 0:
                # Use observed rate from metrics
                # runtime = overhead + segments / rate
                base_overhead_sec = 10
                estimated_runtime_sec = base_overhead_sec + int(
                    estimated_segments / metrics.avg_rate_ema
                )
                return (estimated_segments, estimated_runtime_sec)
        except Exception:
            # Fallback to heuristic if metrics loading fails
            pass

    # Fallback to heuristic
    # Fast preset: ~3 sec/segment (segmentation + extraction + quick analysis + fast transcribe)
    # Quality preset: ~8 sec/segment (higher quality models take longer)
    if preset == "quality":
        sec_per_segment = 8
    else:  # fast
        sec_per_segment = 3

    # Add base overhead (ingest, compose, verify)
    base_overhead_sec = 10

    estimated_runtime_sec = (estimated_segments * sec_per_segment) + base_overhead_sec

    return (estimated_segments, estimated_runtime_sec)


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
