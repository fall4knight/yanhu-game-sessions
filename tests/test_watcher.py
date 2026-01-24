"""Tests for watcher module."""

import json
from pathlib import Path

from yanhu.watcher import (
    QueueJob,
    RunQueueConfig,
    RunQueueResult,
    ScanResult,
    VideoHandler,
    WatcherConfig,
    WatcherState,
    append_job_to_queue,
    compute_file_key,
    create_job_from_path,
    get_pending_jobs,
    guess_game_from_filename,
    is_video_file,
    load_state,
    read_queue,
    run_queue,
    save_state,
    scan_once,
    update_job_status,
    write_queue,
)


class TestIsVideoFile:
    """Test is_video_file function."""

    def test_mp4_is_video(self):
        assert is_video_file(Path("video.mp4")) is True

    def test_mkv_is_video(self):
        assert is_video_file(Path("video.mkv")) is True

    def test_mov_is_video(self):
        assert is_video_file(Path("video.mov")) is True

    def test_uppercase_extension(self):
        assert is_video_file(Path("video.MP4")) is True
        assert is_video_file(Path("video.MKV")) is True

    def test_txt_not_video(self):
        assert is_video_file(Path("file.txt")) is False

    def test_jpg_not_video(self):
        assert is_video_file(Path("image.jpg")) is False

    def test_no_extension(self):
        assert is_video_file(Path("noextension")) is False


class TestGuessGameFromFilename:
    """Test guess_game_from_filename function."""

    def test_date_prefix(self):
        """Should extract game name after date prefix."""
        assert guess_game_from_filename("2026-01-20_gnosia_run01.mp4") == "gnosia"

    def test_date_suffix(self):
        """Should extract game name before date suffix."""
        assert guess_game_from_filename("genshin_2026-01-20.mp4") == "genshin"

    def test_underscore_separator(self):
        """Should handle underscore separators."""
        assert guess_game_from_filename("zelda_botw_session.mp4") == "zelda"

    def test_dash_separator(self):
        """Should handle dash separators."""
        assert guess_game_from_filename("mario-kart-race.mp4") == "mario"

    def test_simple_name(self):
        """Should handle simple filename."""
        assert guess_game_from_filename("gameplay.mp4") == "gameplay"

    def test_returns_lowercase(self):
        """Should return lowercase game name."""
        assert guess_game_from_filename("GNOSIA_run01.mp4") == "gnosia"


class TestQueueJob:
    """Test QueueJob dataclass."""

    def test_to_dict_basic(self):
        """Should serialize to dict."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
        )
        d = job.to_dict()
        assert d["created_at"] == "2026-01-20T12:00:00"
        assert d["raw_path"] == "/path/to/video.mp4"
        assert d["status"] == "pending"
        assert "suggested_game" not in d

    def test_to_dict_with_game(self):
        """Should include suggested_game when present."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
            suggested_game="gnosia",
        )
        d = job.to_dict()
        assert d["suggested_game"] == "gnosia"

    def test_from_dict(self):
        """Should deserialize from dict."""
        d = {
            "created_at": "2026-01-20T12:00:00",
            "raw_path": "/path/to/video.mp4",
            "status": "processing",
            "suggested_game": "zelda",
        }
        job = QueueJob.from_dict(d)
        assert job.created_at == "2026-01-20T12:00:00"
        assert job.raw_path == "/path/to/video.mp4"
        assert job.status == "processing"
        assert job.suggested_game == "zelda"

    def test_from_dict_default_status(self):
        """Should default to pending status."""
        d = {
            "created_at": "2026-01-20T12:00:00",
            "raw_path": "/path/to/video.mp4",
        }
        job = QueueJob.from_dict(d)
        assert job.status == "pending"

    def test_to_json_line(self):
        """Should serialize to JSON line."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
        )
        line = job.to_json_line()
        parsed = json.loads(line)
        assert parsed["created_at"] == "2026-01-20T12:00:00"

    def test_from_json_line(self):
        """Should deserialize from JSON line."""
        line = (
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/video.mp4", "status": "pending"}'
        )
        job = QueueJob.from_json_line(line)
        assert job.raw_path == "/video.mp4"


class TestCreateJobFromPath:
    """Test create_job_from_path function."""

    def test_creates_job_with_path(self, tmp_path):
        """Should create job with absolute path (P3: default game, no guessing)."""
        video = tmp_path / "gnosia_run01.mp4"
        video.touch()

        job = create_job_from_path(video)

        assert job.raw_path == str(video.resolve())
        assert job.status == "pending"
        # P3: Should use default "unknown", not guess "gnosia"
        assert job.suggested_game == "unknown"
        assert job.created_at is not None
        # P3: Should have new fields
        assert job.raw_filename == "gnosia_run01.mp4"
        assert job.raw_stem == "gnosia_run01"
        assert job.suggested_tag is not None
        assert "__" in job.suggested_tag

    def test_created_at_is_iso_format(self, tmp_path):
        """Should use ISO format for created_at."""
        video = tmp_path / "video.mp4"
        video.touch()

        job = create_job_from_path(video)

        # Should be parseable as ISO datetime
        from datetime import datetime

        datetime.fromisoformat(job.created_at)


class TestQueuePersistence:
    """Test queue file operations."""

    def test_append_job_creates_file(self, tmp_path):
        """Should create queue file and directories."""
        queue_file = tmp_path / "subdir" / "pending.jsonl"
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
            status="pending",
        )

        append_job_to_queue(job, queue_file)

        assert queue_file.exists()

    def test_append_job_writes_jsonl(self, tmp_path):
        """Should write job as JSON line."""
        queue_file = tmp_path / "pending.jsonl"
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
            status="pending",
        )

        append_job_to_queue(job, queue_file)

        content = queue_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["raw_path"] == "/video.mp4"

    def test_append_multiple_jobs(self, tmp_path):
        """Should append multiple jobs as separate lines."""
        queue_file = tmp_path / "pending.jsonl"

        for i in range(3):
            job = QueueJob(
                created_at=f"2026-01-20T12:0{i}:00",
                raw_path=f"/video{i}.mp4",
                status="pending",
            )
            append_job_to_queue(job, queue_file)

        content = queue_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3

    def test_read_queue_empty(self, tmp_path):
        """Should return empty list for nonexistent file."""
        queue_file = tmp_path / "missing.jsonl"
        jobs = read_queue(queue_file)
        assert jobs == []

    def test_read_queue_returns_jobs(self, tmp_path):
        """Should read all jobs from queue file."""
        queue_file = tmp_path / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "pending"}\n'
            '{"created_at": "2026-01-20T12:01:00", "raw_path": "/v2.mp4", "status": "done"}\n'
        )

        jobs = read_queue(queue_file)

        assert len(jobs) == 2
        assert jobs[0].raw_path == "/v1.mp4"
        assert jobs[1].raw_path == "/v2.mp4"

    def test_get_pending_jobs_filters(self, tmp_path):
        """Should only return pending jobs."""
        queue_file = tmp_path / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "pending"}\n'
            '{"created_at": "2026-01-20T12:01:00", "raw_path": "/v2.mp4", "status": "done"}\n'
            '{"created_at": "2026-01-20T12:02:00", "raw_path": "/v3.mp4", "status": "pending"}\n'
        )

        pending = get_pending_jobs(queue_file)

        assert len(pending) == 2
        assert pending[0].raw_path == "/v1.mp4"
        assert pending[1].raw_path == "/v3.mp4"


class TestVideoHandler:
    """Test VideoHandler class (without real watchdog)."""

    def test_on_created_queues_video(self, tmp_path):
        """Should queue video file on creation."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)
        handler = VideoHandler(config)

        video = raw_dir / "game_run01.mp4"
        video.touch()

        job = handler.on_created(video)

        assert job is not None
        assert job.status == "pending"
        assert config.queue_file.exists()

    def test_on_created_ignores_non_video(self, tmp_path):
        """Should ignore non-video files."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)
        handler = VideoHandler(config)

        text_file = raw_dir / "notes.txt"
        text_file.touch()

        job = handler.on_created(text_file)

        assert job is None
        assert not config.queue_file.exists()

    def test_on_created_deduplicates(self, tmp_path):
        """Should not queue same file twice."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)
        handler = VideoHandler(config)

        video = raw_dir / "video.mp4"
        video.touch()

        # First call
        job1 = handler.on_created(video)
        # Second call (same file)
        job2 = handler.on_created(video)

        assert job1 is not None
        assert job2 is None  # Deduplicated

        # Only one job in queue
        jobs = read_queue(config.queue_file)
        assert len(jobs) == 1


class TestWatcherConfig:
    """Test WatcherConfig dataclass."""

    def test_queue_file_property(self, tmp_path):
        """Should compute queue file path."""
        config = WatcherConfig(
            raw_dirs=[tmp_path / "raw"],
            queue_dir=tmp_path / "queue",
        )
        assert config.queue_file == tmp_path / "queue" / "pending.jsonl"

    def test_custom_queue_filename(self, tmp_path):
        """Should support custom queue filename."""
        config = WatcherConfig(
            raw_dirs=[tmp_path / "raw"],
            queue_dir=tmp_path / "queue",
            queue_filename="jobs.jsonl",
        )
        assert config.queue_file == tmp_path / "queue" / "jobs.jsonl"

    def test_multiple_raw_dirs(self, tmp_path):
        """Should support multiple raw directories."""
        dir1 = tmp_path / "raw1"
        dir2 = tmp_path / "raw2"
        config = WatcherConfig(
            raw_dirs=[dir1, dir2],
            queue_dir=tmp_path / "queue",
        )
        assert len(config.raw_dirs) == 2
        assert dir1 in config.raw_dirs
        assert dir2 in config.raw_dirs


class TestQueueJobExtended:
    """Test extended QueueJob fields for run-queue."""

    def test_get_game_with_explicit_game(self):
        """Should return explicit game over suggested_game."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
            suggested_game="guessed",
            game="explicit",
        )
        assert job.get_game() == "explicit"

    def test_get_game_falls_back_to_suggested(self):
        """Should fall back to suggested_game when game is None."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
            suggested_game="guessed",
        )
        assert job.get_game() == "guessed"

    def test_get_game_returns_unknown(self):
        """Should return 'unknown' when no game info."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
        )
        assert job.get_game() == "unknown"

    def test_get_tag_with_explicit_tag(self):
        """Should return explicit tag."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
            tag="session05",
        )
        assert job.get_tag() == "session05"

    def test_get_tag_returns_default(self):
        """Should return 'run01' when no tag."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
        )
        assert job.get_tag() == "run01"

    def test_to_dict_with_all_fields(self):
        """Should serialize all extended fields."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
            status="done",
            suggested_game="guessed",
            game="explicit",
            tag="run02",
            session_id="explicit_run02_20260120",
            outputs={"timeline": "timeline.md"},
        )
        d = job.to_dict()
        assert d["game"] == "explicit"
        assert d["tag"] == "run02"
        assert d["session_id"] == "explicit_run02_20260120"
        assert d["outputs"] == {"timeline": "timeline.md"}

    def test_to_dict_with_error(self):
        """Should serialize error field."""
        job = QueueJob(
            created_at="2026-01-20T12:00:00",
            raw_path="/video.mp4",
            status="failed",
            error="Video not found",
        )
        d = job.to_dict()
        assert d["error"] == "Video not found"

    def test_from_dict_with_all_fields(self):
        """Should deserialize all extended fields."""
        d = {
            "created_at": "2026-01-20T12:00:00",
            "raw_path": "/video.mp4",
            "status": "done",
            "game": "zelda",
            "tag": "run03",
            "session_id": "zelda_run03_20260120",
            "error": None,
            "outputs": {"session_dir": "/sessions/zelda"},
        }
        job = QueueJob.from_dict(d)
        assert job.game == "zelda"
        assert job.tag == "run03"
        assert job.session_id == "zelda_run03_20260120"
        assert job.outputs == {"session_dir": "/sessions/zelda"}


class TestWriteQueue:
    """Test write_queue function."""

    def test_write_queue_creates_file(self, tmp_path):
        """Should create queue file with jobs."""
        queue_file = tmp_path / "queue" / "pending.jsonl"
        jobs = [
            QueueJob(
                created_at="2026-01-20T12:00:00",
                raw_path="/v1.mp4",
                status="pending",
            ),
            QueueJob(
                created_at="2026-01-20T12:01:00",
                raw_path="/v2.mp4",
                status="done",
            ),
        ]

        write_queue(jobs, queue_file)

        assert queue_file.exists()
        content = queue_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2

    def test_write_queue_overwrites(self, tmp_path):
        """Should overwrite existing file."""
        queue_file = tmp_path / "pending.jsonl"
        queue_file.write_text("old content\n")

        jobs = [
            QueueJob(
                created_at="2026-01-20T12:00:00",
                raw_path="/new.mp4",
                status="pending",
            ),
        ]

        write_queue(jobs, queue_file)

        content = queue_file.read_text()
        assert "old content" not in content
        assert "/new.mp4" in content


class TestUpdateJobStatus:
    """Test update_job_status function."""

    def test_updates_status(self, tmp_path):
        """Should update job status by raw_path."""
        queue_file = tmp_path / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "pending"}\n'
            '{"created_at": "2026-01-20T12:01:00", "raw_path": "/v2.mp4", "status": "pending"}\n'
        )

        update_job_status(queue_file, "/v1.mp4", "processing")

        jobs = read_queue(queue_file)
        assert jobs[0].status == "processing"
        assert jobs[1].status == "pending"

    def test_updates_with_session_id(self, tmp_path):
        """Should update session_id when provided."""
        queue_file = tmp_path / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "processing"}\n'
        )

        update_job_status(
            queue_file,
            "/v1.mp4",
            "done",
            session_id="game_run01_20260120",
        )

        jobs = read_queue(queue_file)
        assert jobs[0].status == "done"
        assert jobs[0].session_id == "game_run01_20260120"

    def test_updates_with_error(self, tmp_path):
        """Should update error when provided."""
        queue_file = tmp_path / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "processing"}\n'
        )

        update_job_status(queue_file, "/v1.mp4", "failed", error="File not found")

        jobs = read_queue(queue_file)
        assert jobs[0].status == "failed"
        assert jobs[0].error == "File not found"

    def test_updates_with_outputs(self, tmp_path):
        """Should update outputs when provided."""
        queue_file = tmp_path / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "processing"}\n'
        )

        update_job_status(
            queue_file,
            "/v1.mp4",
            "done",
            outputs={"timeline": "/sessions/game/timeline.md"},
        )

        jobs = read_queue(queue_file)
        assert jobs[0].outputs == {"timeline": "/sessions/game/timeline.md"}


class TestRunQueueConfig:
    """Test RunQueueConfig dataclass."""

    def test_queue_file_property(self, tmp_path):
        """Should compute queue file path."""
        config = RunQueueConfig(
            queue_dir=tmp_path / "queue",
            output_dir=tmp_path / "sessions",
        )
        assert config.queue_file == tmp_path / "queue" / "pending.jsonl"

    def test_default_values(self, tmp_path):
        """Should have sensible defaults."""
        config = RunQueueConfig(
            queue_dir=tmp_path / "queue",
            output_dir=tmp_path / "sessions",
        )
        assert config.limit == 1
        assert config.dry_run is False
        assert config.force is False


class TestRunQueue:
    """Test run_queue function."""

    def test_empty_queue_returns_zero(self, tmp_path):
        """Should return empty result for empty queue."""
        config = RunQueueConfig(
            queue_dir=tmp_path / "queue",
            output_dir=tmp_path / "sessions",
        )

        result = run_queue(config)

        assert result.processed == 0
        assert result.succeeded == 0
        assert result.failed == 0

    def test_dry_run_skips_processing(self, tmp_path):
        """Should not process in dry-run mode."""
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir(parents=True)
        queue_file = queue_dir / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "pending"}\n'
        )

        config = RunQueueConfig(
            queue_dir=queue_dir,
            output_dir=tmp_path / "sessions",
            dry_run=True,
        )

        result = run_queue(config)

        assert result.processed == 0
        assert result.skipped == 1

        # Status should NOT be updated in dry-run
        jobs = read_queue(queue_file)
        assert jobs[0].status == "pending"

    def test_dry_run_calls_callbacks(self, tmp_path):
        """Should call callbacks in dry-run mode."""
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir(parents=True)
        queue_file = queue_dir / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "pending"}\n'
        )

        config = RunQueueConfig(
            queue_dir=queue_dir,
            output_dir=tmp_path / "sessions",
            dry_run=True,
        )

        started = []
        completed = []

        def on_start(job):
            started.append(job.raw_path)

        def on_complete(job, result):
            completed.append((job.raw_path, result))

        run_queue(config, on_job_start=on_start, on_job_complete=on_complete)

        assert started == ["/v1.mp4"]
        assert len(completed) == 1
        assert completed[0][0] == "/v1.mp4"
        assert completed[0][1] is None  # No result in dry-run

    def test_respects_limit(self, tmp_path):
        """Should only process up to limit jobs."""
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir(parents=True)
        queue_file = queue_dir / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", "raw_path": "/v1.mp4", "status": "pending"}\n'
            '{"created_at": "2026-01-20T12:01:00", "raw_path": "/v2.mp4", "status": "pending"}\n'
            '{"created_at": "2026-01-20T12:02:00", "raw_path": "/v3.mp4", "status": "pending"}\n'
        )

        config = RunQueueConfig(
            queue_dir=queue_dir,
            output_dir=tmp_path / "sessions",
            limit=2,
            dry_run=True,
        )

        result = run_queue(config)

        assert result.skipped == 2  # Only 2 processed (dry-run)

    def test_handles_missing_raw_file(self, tmp_path):
        """Should fail gracefully when raw file is missing."""
        queue_dir = tmp_path / "queue"
        queue_dir.mkdir(parents=True)
        output_dir = tmp_path / "sessions"
        output_dir.mkdir(parents=True)
        queue_file = queue_dir / "pending.jsonl"
        queue_file.write_text(
            '{"created_at": "2026-01-20T12:00:00", '
            '"raw_path": "/nonexistent.mp4", "status": "pending"}\n'
        )

        config = RunQueueConfig(
            queue_dir=queue_dir,
            output_dir=output_dir,
            limit=1,
        )

        result = run_queue(config)

        assert result.processed == 1
        assert result.failed == 1
        assert result.succeeded == 0

        # Check status was updated to failed
        jobs = read_queue(queue_file)
        assert jobs[0].status == "failed"
        assert "not found" in jobs[0].error.lower()


class TestRunQueueResult:
    """Test RunQueueResult dataclass."""

    def test_default_values(self):
        """Should have zero defaults."""
        result = RunQueueResult()
        assert result.processed == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.skipped == 0


class TestComputeFileKey:
    """Test compute_file_key function."""

    def test_same_file_same_key(self, tmp_path):
        """Same file should produce same key."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"content")

        key1 = compute_file_key(video)
        key2 = compute_file_key(video)

        assert key1 == key2

    def test_different_content_different_key(self, tmp_path):
        """Different content (same path) should produce different key after rewrite."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"content1")
        key1 = compute_file_key(video)

        # Rewrite with different content
        video.write_bytes(b"content2")
        key2 = compute_file_key(video)

        # Keys should differ because mtime and/or size changed
        assert key1 != key2

    def test_key_is_deterministic(self, tmp_path):
        """Key should be deterministic (16 hex chars)."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"test content")

        key = compute_file_key(video)

        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)


class TestWatcherState:
    """Test WatcherState dataclass."""

    def test_default_state(self):
        """Should start with empty seen set."""
        state = WatcherState()
        assert state.last_scan_time is None
        assert len(state.seen_hashes) == 0

    def test_has_seen(self):
        """Should track seen hashes."""
        state = WatcherState()
        state.mark_seen("abc123")

        assert state.has_seen("abc123") is True
        assert state.has_seen("xyz789") is False

    def test_update_scan_time(self):
        """Should update scan time."""
        state = WatcherState()
        state.update_scan_time()

        assert state.last_scan_time is not None
        # Should be parseable as ISO datetime
        from datetime import datetime

        datetime.fromisoformat(state.last_scan_time)

    def test_to_dict(self):
        """Should serialize to dict."""
        state = WatcherState()
        state.mark_seen("hash1")
        state.mark_seen("hash2")
        state.update_scan_time()

        d = state.to_dict()

        assert d["seen_count"] == 2
        assert set(d["seen_hashes"]) == {"hash1", "hash2"}
        assert d["last_scan_time"] is not None

    def test_from_dict(self):
        """Should deserialize from dict."""
        d = {
            "last_scan_time": "2026-01-22T10:00:00",
            "seen_hashes": ["hash1", "hash2", "hash3"],
        }

        state = WatcherState.from_dict(d)

        assert state.last_scan_time == "2026-01-22T10:00:00"
        assert len(state.seen_hashes) == 3
        assert state.has_seen("hash2")


class TestStatePersistence:
    """Test state file load/save."""

    def test_load_nonexistent_returns_empty(self, tmp_path):
        """Should return empty state for nonexistent file."""
        state_file = tmp_path / "missing.json"

        state = load_state(state_file)

        assert len(state.seen_hashes) == 0

    def test_save_creates_file(self, tmp_path):
        """Should create state file."""
        state_file = tmp_path / "subdir" / "state.json"
        state = WatcherState()
        state.mark_seen("test_hash")

        save_state(state, state_file)

        assert state_file.exists()

    def test_save_load_roundtrip(self, tmp_path):
        """Should preserve state through save/load."""
        state_file = tmp_path / "state.json"
        original = WatcherState()
        original.mark_seen("hash1")
        original.mark_seen("hash2")
        original.update_scan_time()

        save_state(original, state_file)
        loaded = load_state(state_file)

        assert loaded.has_seen("hash1")
        assert loaded.has_seen("hash2")
        assert loaded.last_scan_time == original.last_scan_time

    def test_save_is_atomic(self, tmp_path):
        """Save should use atomic write (temp + rename)."""
        state_file = tmp_path / "state.json"
        state = WatcherState()
        state.mark_seen("test")

        save_state(state, state_file)

        # File should exist and be valid JSON
        content = state_file.read_text()
        data = json.loads(content)
        assert "seen_hashes" in data

    def test_state_persisted_includes_seen_count(self, tmp_path):
        """State file should include seen_count for easy inspection."""
        state_file = tmp_path / "state.json"
        state = WatcherState()
        state.mark_seen("a")
        state.mark_seen("b")
        state.mark_seen("c")

        save_state(state, state_file)

        content = json.loads(state_file.read_text())
        assert content["seen_count"] == 3


class TestScanOnce:
    """Test scan_once function (--once mode)."""

    def test_once_scan_enqueues_new_files(self, tmp_path):
        """Should enqueue all video files in directory."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        # Create 2 video files
        (raw_dir / "video1.mp4").write_bytes(b"video1")
        (raw_dir / "video2.mkv").write_bytes(b"video2")
        # And one non-video file
        (raw_dir / "notes.txt").write_text("notes")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        result = scan_once(config)

        assert result.found == 2
        assert result.queued == 2
        assert result.skipped == 0

        # Check queue file
        jobs = read_queue(config.queue_file)
        assert len(jobs) == 2

    def test_dedup_skips_seen(self, tmp_path):
        """Should skip files that were already seen."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        # Create video file
        video = raw_dir / "video.mp4"
        video.write_bytes(b"video content")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        # First scan
        result1 = scan_once(config)
        assert result1.queued == 1

        # Second scan (same files)
        result2 = scan_once(config)
        assert result2.found == 1
        assert result2.queued == 0
        assert result2.skipped == 1

        # Queue should still have only 1 job
        jobs = read_queue(config.queue_file)
        assert len(jobs) == 1

    def test_state_persisted(self, tmp_path):
        """Should persist state after scan."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        (raw_dir / "video.mp4").write_bytes(b"video")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        scan_once(config)

        # Check state file exists and has correct content
        assert config.state_file.exists()
        state = load_state(config.state_file)
        assert len(state.seen_hashes) == 1
        assert state.last_scan_time is not None

    def test_once_calls_callback(self, tmp_path):
        """Should call on_queued callback for each queued file."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        (raw_dir / "game1.mp4").write_bytes(b"g1")
        (raw_dir / "game2.mp4").write_bytes(b"g2")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        queued_jobs = []

        def on_queued(job):
            queued_jobs.append(job)

        scan_once(config, on_queued=on_queued)

        assert len(queued_jobs) == 2


class TestVideoHandlerDedup:
    """Test VideoHandler deduplication with state."""

    def test_handler_uses_state(self, tmp_path):
        """Handler should use provided state for dedup."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        video = raw_dir / "video.mp4"
        video.write_bytes(b"content")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        # Pre-populate state with this file's hash
        file_hash = compute_file_key(video)
        state = WatcherState()
        state.mark_seen(file_hash)

        handler = VideoHandler(config, state=state)
        job = handler.on_created(video)

        # Should be skipped because already in state
        assert job is None

    def test_handler_persists_state(self, tmp_path):
        """Handler should save state after processing."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        video = raw_dir / "video.mp4"
        video.write_bytes(b"content")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)
        handler = VideoHandler(config)

        handler.on_created(video)

        # State should be saved
        assert config.state_file.exists()
        loaded_state = load_state(config.state_file)
        assert len(loaded_state.seen_hashes) == 1


class TestWatcherConfigState:
    """Test WatcherConfig state_file property."""

    def test_state_file_property(self, tmp_path):
        """Should compute state file path."""
        config = WatcherConfig(
            raw_dirs=[tmp_path / "raw"],
            queue_dir=tmp_path / "queue",
        )
        assert config.state_file == tmp_path / "queue" / "state.json"

    def test_custom_state_filename(self, tmp_path):
        """Should support custom state filename."""
        config = WatcherConfig(
            raw_dirs=[tmp_path / "raw"],
            queue_dir=tmp_path / "queue",
            state_filename="watcher_state.json",
        )
        assert config.state_file == tmp_path / "queue" / "watcher_state.json"


class TestMultiRawDirs:
    """Test multi raw-dir support."""

    def test_multi_raw_dirs_once_scan_enqueues_all(self, tmp_path):
        """Should enqueue files from all raw directories."""
        dir1 = tmp_path / "raw1"
        dir2 = tmp_path / "raw2"
        dir1.mkdir()
        dir2.mkdir()
        queue_dir = tmp_path / "queue"

        # Create 1 video in each directory
        (dir1 / "video1.mp4").write_bytes(b"video1")
        (dir2 / "video2.mp4").write_bytes(b"video2")

        config = WatcherConfig(raw_dirs=[dir1, dir2], queue_dir=queue_dir)

        result = scan_once(config)

        assert result.found == 2
        assert result.queued == 2
        assert result.skipped == 0

        # Check queue has 2 jobs
        jobs = read_queue(config.queue_file)
        assert len(jobs) == 2

        # Check raw_dir is recorded
        raw_dirs_in_jobs = {job.raw_dir for job in jobs}
        assert str(dir1.resolve()) in raw_dirs_in_jobs
        assert str(dir2.resolve()) in raw_dirs_in_jobs

    def test_move_file_between_dirs_requeues(self, tmp_path):
        """Moving file to different dir should allow re-queue (path changes)."""
        dir1 = tmp_path / "raw1"
        dir2 = tmp_path / "raw2"
        dir1.mkdir()
        dir2.mkdir()
        queue_dir = tmp_path / "queue"

        # Create video in dir1
        video = dir1 / "video.mp4"
        video.write_bytes(b"video content")

        config = WatcherConfig(raw_dirs=[dir1, dir2], queue_dir=queue_dir)

        # First scan - queues video from dir1
        result1 = scan_once(config)
        assert result1.queued == 1

        # Move video from dir1 to dir2
        new_path = dir2 / "video.mp4"
        video.rename(new_path)

        # Second scan - should queue again (different resolved path)
        result2 = scan_once(config)
        assert result2.found == 1
        assert result2.queued == 1  # Re-queued because path changed
        assert result2.skipped == 0

        # Total 2 jobs in queue
        jobs = read_queue(config.queue_file)
        assert len(jobs) == 2

        # Verify different raw_dirs recorded
        raw_paths = [job.raw_path for job in jobs]
        assert str(dir1.resolve() / "video.mp4") in raw_paths
        assert str(dir2.resolve() / "video.mp4") in raw_paths

    def test_same_filename_different_dirs_not_deduped(self, tmp_path):
        """Same filename in different dirs should both be queued."""
        dir1 = tmp_path / "raw1"
        dir2 = tmp_path / "raw2"
        dir1.mkdir()
        dir2.mkdir()
        queue_dir = tmp_path / "queue"

        # Create same-named file in both directories
        (dir1 / "game.mp4").write_bytes(b"content1")
        (dir2 / "game.mp4").write_bytes(b"content2")

        config = WatcherConfig(raw_dirs=[dir1, dir2], queue_dir=queue_dir)

        result = scan_once(config)

        # Both should be queued (different resolved paths)
        assert result.found == 2
        assert result.queued == 2
        assert result.skipped == 0

    def test_nonexistent_raw_dir_skipped(self, tmp_path):
        """Should skip non-existent directories gracefully."""
        existing_dir = tmp_path / "raw1"
        missing_dir = tmp_path / "missing"
        existing_dir.mkdir()
        queue_dir = tmp_path / "queue"

        (existing_dir / "video.mp4").write_bytes(b"video")

        config = WatcherConfig(raw_dirs=[existing_dir, missing_dir], queue_dir=queue_dir)

        # Should not raise, just skip missing dir
        result = scan_once(config)

        assert result.found == 1
        assert result.queued == 1


class TestQueueJobRawDir:
    """Test QueueJob raw_dir field."""

    def test_raw_dir_in_to_dict(self):
        """Should include raw_dir in serialization."""
        job = QueueJob(
            created_at="2026-01-22T10:00:00",
            raw_path="/dir1/video.mp4",
            raw_dir="/dir1",
        )
        d = job.to_dict()
        assert d["raw_dir"] == "/dir1"

    def test_raw_dir_from_dict(self):
        """Should deserialize raw_dir."""
        d = {
            "created_at": "2026-01-22T10:00:00",
            "raw_path": "/dir1/video.mp4",
            "raw_dir": "/dir1",
        }
        job = QueueJob.from_dict(d)
        assert job.raw_dir == "/dir1"

    def test_raw_dir_optional(self):
        """raw_dir should be optional for backwards compatibility."""
        d = {
            "created_at": "2026-01-22T10:00:00",
            "raw_path": "/video.mp4",
        }
        job = QueueJob.from_dict(d)
        assert job.raw_dir is None


class TestScanResult:
    """Test ScanResult dataclass."""

    def test_default_values(self):
        """Should have zero defaults."""
        result = ScanResult()
        assert result.found == 0
        assert result.queued == 0
        assert result.skipped == 0


class TestProbeMedia:
    """Test probe_media function."""

    def test_probe_returns_file_size_even_without_ffprobe(self, tmp_path, monkeypatch):
        """probe_media returns file size even if ffprobe unavailable."""
        from yanhu.watcher import probe_media

        # Create a test file
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"x" * 1024 * 100)  # 100KB

        # Mock subprocess to fail (ffprobe unavailable)
        import subprocess

        def mock_run(*args, **kwargs):
            raise FileNotFoundError("ffprobe not found")

        monkeypatch.setattr(subprocess, "run", mock_run)

        info = probe_media(video_file)

        # Should still get file size
        assert info.file_size_bytes == 1024 * 100
        # Other fields should be None
        assert info.duration_sec is None
        assert info.video_codec is None

    def test_probe_gracefully_handles_missing_file(self):
        """probe_media handles missing file gracefully."""
        from yanhu.watcher import probe_media

        info = probe_media(Path("/nonexistent/video.mp4"))

        # Should return empty MediaInfo
        assert info.file_size_bytes is None
        assert info.duration_sec is None


class TestCalculateJobEstimates:
    """Test calculate_job_estimates function."""

    def test_estimate_short_video_auto_strategy(self):
        """Short video (90s) uses 5s segments with auto strategy."""
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        media = MediaInfo(duration_sec=90.0, file_size_bytes=1024 * 1024 * 50)

        segments, runtime = calculate_job_estimates(media, segment_strategy="auto", preset="fast")

        # 90s / 5s segments = 18 segments
        assert segments == 18
        # Fast: 18 * 3 + 10 = 64 seconds
        assert runtime == 64

    def test_estimate_medium_video_auto_strategy(self):
        """Medium video (10min) uses 15s segments with auto strategy."""
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        media = MediaInfo(duration_sec=600.0, file_size_bytes=1024 * 1024 * 200)

        segments, runtime = calculate_job_estimates(media, segment_strategy="auto", preset="fast")

        # 600s / 15s segments = 40 segments
        assert segments == 40
        # Fast: 40 * 3 + 10 = 130 seconds
        assert runtime == 130

    def test_estimate_long_video_auto_strategy(self):
        """Long video (20min) uses 30s segments with auto strategy."""
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        media = MediaInfo(duration_sec=1200.0, file_size_bytes=1024 * 1024 * 400)

        segments, runtime = calculate_job_estimates(media, segment_strategy="auto", preset="fast")

        # 1200s / 30s segments = 40 segments
        assert segments == 40
        # Fast: 40 * 3 + 10 = 130 seconds
        assert runtime == 130

    def test_estimate_quality_preset_slower(self):
        """Quality preset has higher runtime estimate."""
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        media = MediaInfo(duration_sec=90.0, file_size_bytes=1024 * 1024 * 50)

        segments_fast, runtime_fast = calculate_job_estimates(
            media, segment_strategy="auto", preset="fast"
        )
        segments_quality, runtime_quality = calculate_job_estimates(
            media, segment_strategy="auto", preset="quality"
        )

        # Same number of segments
        assert segments_fast == segments_quality == 18
        # Quality takes longer
        # Quality: 18 * 8 + 10 = 154 seconds
        assert runtime_quality == 154
        assert runtime_quality > runtime_fast

    def test_estimate_no_duration_returns_zeros(self):
        """No duration returns (0, 0)."""
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        media = MediaInfo(file_size_bytes=1024 * 1024)

        segments, runtime = calculate_job_estimates(media, segment_strategy="auto", preset="fast")

        assert segments == 0
        assert runtime == 0

    def test_estimate_explicit_strategy(self):
        """Explicit strategy (short/medium/long) uses fixed segment duration."""
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        media = MediaInfo(duration_sec=100.0, file_size_bytes=1024 * 1024)

        # Short strategy: 5s segments
        segments_short, _ = calculate_job_estimates(media, segment_strategy="short", preset="fast")
        assert segments_short == 20  # ceil(100 / 5)

        # Medium strategy: 15s segments
        segments_medium, _ = calculate_job_estimates(
            media, segment_strategy="medium", preset="fast"
        )
        assert segments_medium == 7  # ceil(100 / 15)

        # Long strategy: 30s segments
        segments_long, _ = calculate_job_estimates(media, segment_strategy="long", preset="fast")
        assert segments_long == 4  # ceil(100 / 30)

    def test_estimate_uses_metrics_when_available(self, tmp_path):
        """Estimate uses metrics for better accuracy when available."""
        from yanhu.metrics import MetricsStore
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        # Create metrics file with observed data
        metrics_file = tmp_path / "_metrics.json"
        store = MetricsStore(metrics_file)
        # Store observed rate of 0.4 seg/s for fast preset with 5s segments
        store.update_metrics(preset="fast", segment_duration=5, observed_rate=0.4)

        # Create media info for 90s video (will use 5s segments with auto strategy)
        media = MediaInfo(duration_sec=90.0, file_size_bytes=1024 * 1024)

        # Calculate with metrics
        segments, runtime = calculate_job_estimates(
            media, segment_strategy="auto", preset="fast", metrics_file=metrics_file
        )

        # 90s / 5s = 18 segments
        assert segments == 18
        # With metrics: 10 (overhead) + 18 / 0.4 = 10 + 45 = 55 seconds
        assert runtime == 55

    def test_estimate_fallback_when_no_metrics(self, tmp_path):
        """Estimate falls back to heuristic when metrics unavailable."""
        from yanhu.watcher import MediaInfo, calculate_job_estimates

        # Empty metrics file
        metrics_file = tmp_path / "_metrics.json"

        media = MediaInfo(duration_sec=90.0, file_size_bytes=1024 * 1024)

        segments, runtime = calculate_job_estimates(
            media, segment_strategy="auto", preset="fast", metrics_file=metrics_file
        )

        # 90s / 5s = 18 segments
        assert segments == 18
        # Without metrics: use heuristic (3 sec/segment)
        # 18 * 3 + 10 = 64 seconds
        assert runtime == 64

    def test_estimate_fallback_when_metrics_file_missing(self):
        """Estimate falls back when metrics file doesn't exist."""
        from pathlib import Path

        from yanhu.watcher import MediaInfo, calculate_job_estimates

        media = MediaInfo(duration_sec=90.0, file_size_bytes=1024 * 1024)

        segments, runtime = calculate_job_estimates(
            media,
            segment_strategy="auto",
            preset="fast",
            metrics_file=Path("/nonexistent/_metrics.json"),
        )

        # Should use heuristic fallback
        assert segments == 18
        assert runtime == 64
