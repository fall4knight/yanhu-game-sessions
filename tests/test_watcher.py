"""Tests for watcher module."""

import json
from pathlib import Path

from yanhu.watcher import (
    QueueJob,
    VideoHandler,
    WatcherConfig,
    append_job_to_queue,
    create_job_from_path,
    get_pending_jobs,
    guess_game_from_filename,
    is_video_file,
    read_queue,
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
            '{"created_at": "2026-01-20T12:00:00", '
            '"raw_path": "/video.mp4", '
            '"status": "pending"}'
        )
        job = QueueJob.from_json_line(line)
        assert job.raw_path == "/video.mp4"


class TestCreateJobFromPath:
    """Test create_job_from_path function."""

    def test_creates_job_with_path(self, tmp_path):
        """Should create job with absolute path."""
        video = tmp_path / "gnosia_run01.mp4"
        video.touch()

        job = create_job_from_path(video)

        assert job.raw_path == str(video.resolve())
        assert job.status == "pending"
        assert job.suggested_game == "gnosia"
        assert job.created_at is not None

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

        config = WatcherConfig(raw_dir=raw_dir, queue_dir=queue_dir)
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

        config = WatcherConfig(raw_dir=raw_dir, queue_dir=queue_dir)
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

        config = WatcherConfig(raw_dir=raw_dir, queue_dir=queue_dir)
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
            raw_dir=tmp_path / "raw",
            queue_dir=tmp_path / "queue",
        )
        assert config.queue_file == tmp_path / "queue" / "pending.jsonl"

    def test_custom_queue_filename(self, tmp_path):
        """Should support custom queue filename."""
        config = WatcherConfig(
            raw_dir=tmp_path / "raw",
            queue_dir=tmp_path / "queue",
            queue_filename="jobs.jsonl",
        )
        assert config.queue_file == tmp_path / "queue" / "jobs.jsonl"
