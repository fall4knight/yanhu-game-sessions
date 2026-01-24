"""Tests for P3 naming strategy.

Tests that:
- No hardcoded actor/game names
- Tags include hash to avoid same-prefix confusion
- Backward compatibility with old jobs
"""

from yanhu.watcher import QueueJob, create_job_from_path, generate_tag_from_filename


class TestGenerateTagFromFilename:
    """Test P3 tag generation with hash."""

    def test_basic_tag_generation(self):
        """Should generate tag with stem + hash."""
        tag = generate_tag_from_filename("video.mp4")
        assert tag.startswith("video__")
        assert len(tag) == len("video__") + 8  # stem + __ + 8-char hash

    def test_chinese_filename(self):
        """Should handle Chinese characters correctly."""
        tag = generate_tag_from_filename("演员_片段_副本.MP4")
        assert tag.startswith("演员_片段_副本__")
        assert len(tag) == len("演员_片段_副本__") + 8

    def test_same_stem_different_hash(self):
        """Files with same prefix should get different hashes."""
        tag1 = generate_tag_from_filename("actor_clip.mp4")
        tag2 = generate_tag_from_filename("actor_clip_副本.mp4")
        tag3 = generate_tag_from_filename("actor_clip_copy.mp4")

        # All should start with different stems
        assert tag1.startswith("actor_clip__")
        assert tag2.startswith("actor_clip_副本__")
        assert tag3.startswith("actor_clip_copy__")

        # All should have different hashes
        assert tag1 != tag2
        assert tag2 != tag3
        assert tag1 != tag3

    def test_deterministic_hash(self):
        """Same filename should always produce same tag."""
        tag1 = generate_tag_from_filename("test.mp4")
        tag2 = generate_tag_from_filename("test.mp4")
        assert tag1 == tag2

    def test_different_extensions_different_hash(self):
        """Same stem with different extensions should get different hashes."""
        tag1 = generate_tag_from_filename("video.mp4")
        tag2 = generate_tag_from_filename("video.mkv")
        assert tag1 != tag2  # Different filenames = different hashes

    def test_special_characters(self):
        """Should handle special characters in filename."""
        tag = generate_tag_from_filename("video-2026-01-23_part1.mp4")
        assert tag.startswith("video-2026-01-23_part1__")
        assert "__" in tag
        assert len(tag.split("__")[1]) == 8


class TestCreateJobFromPath:
    """Test P3 job creation with new fields."""

    def test_fills_new_p3_fields(self, tmp_path):
        """Should populate raw_filename, raw_stem, suggested_tag."""
        video = tmp_path / "test_video.mp4"
        video.write_text("test")

        job = create_job_from_path(video, default_game="testgame")

        assert job.raw_filename == "test_video.mp4"
        assert job.raw_stem == "test_video"
        assert job.suggested_tag is not None
        assert job.suggested_tag.startswith("test_video__")
        assert len(job.suggested_tag) == len("test_video__") + 8

    def test_uses_default_game_not_guessing(self, tmp_path):
        """Should use default_game, not guess from filename."""
        # Filename that old guess_game_from_filename would parse
        video = tmp_path / "gnosia_2026-01-20.mp4"
        video.write_text("test")

        job = create_job_from_path(video, default_game="mygame")

        # Should NOT guess "gnosia", should use explicit default
        assert job.suggested_game == "mygame"
        assert job.suggested_game != "gnosia"

    def test_default_game_defaults_to_unknown(self, tmp_path):
        """Should default to 'unknown' when default_game not specified."""
        video = tmp_path / "video.mp4"
        video.write_text("test")

        job = create_job_from_path(video)

        assert job.suggested_game == "unknown"

    def test_chinese_filename_support(self, tmp_path):
        """Should handle Chinese filenames correctly."""
        video = tmp_path / "演员_片段.mp4"
        video.write_text("test")

        job = create_job_from_path(video, default_game="unknown")

        assert job.raw_filename == "演员_片段.mp4"
        assert job.raw_stem == "演员_片段"
        assert job.suggested_tag.startswith("演员_片段__")


class TestQueueJobBackwardCompatibility:
    """Test that old jobs without P3 fields still work."""

    def test_old_job_without_p3_fields(self):
        """Should load old jobs that don't have P3 fields."""
        old_job_dict = {
            "created_at": "2026-01-23T00:00:00",
            "raw_path": "/path/to/video.mp4",
            "status": "pending",
            "suggested_game": "gnosia",  # Old style guessed game
        }

        job = QueueJob.from_dict(old_job_dict)

        assert job.raw_filename is None
        assert job.raw_stem is None
        assert job.suggested_tag is None
        # Should still work with fallbacks
        assert job.get_game() == "gnosia"
        assert job.get_tag() == "run01"  # Default fallback

    def test_get_tag_fallback_chain(self):
        """Should fallback: tag -> suggested_tag -> 'run01'."""
        # Case 1: explicit tag takes priority
        job1 = QueueJob(
            created_at="2026-01-23T00:00:00",
            raw_path="/path/to/video.mp4",
            tag="explicit_tag",
            suggested_tag="suggested_tag__12345678",
        )
        assert job1.get_tag() == "explicit_tag"

        # Case 2: suggested_tag used when no explicit tag
        job2 = QueueJob(
            created_at="2026-01-23T00:00:00",
            raw_path="/path/to/video.mp4",
            suggested_tag="suggested_tag__12345678",
        )
        assert job2.get_tag() == "suggested_tag__12345678"

        # Case 3: fallback to run01 when neither exists
        job3 = QueueJob(
            created_at="2026-01-23T00:00:00",
            raw_path="/path/to/video.mp4",
        )
        assert job3.get_tag() == "run01"

    def test_to_dict_omits_none_p3_fields(self):
        """Should not include P3 fields if they're None (old jobs)."""
        job = QueueJob(
            created_at="2026-01-23T00:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
            suggested_game="gnosia",
        )

        d = job.to_dict()

        # Should not have P3 fields
        assert "raw_filename" not in d
        assert "raw_stem" not in d
        assert "suggested_tag" not in d


class TestNoHardcodedNames:
    """Test that P3 removes hardcoded actor/game guessing."""

    def test_no_actor_in_suggested_game(self, tmp_path):
        """Should not extract 'actor' from filename."""
        video = tmp_path / "actor_clip_2026-01-20.mp4"
        video.write_text("test")

        job = create_job_from_path(video, default_game="unknown")

        # Should NOT guess "actor"
        assert job.suggested_game == "unknown"
        assert "actor" not in job.suggested_game.lower()

    def test_no_game_guessing_from_patterns(self, tmp_path):
        """Should not guess game names from common patterns."""
        test_cases = [
            "gnosia_recording.mp4",
            "2026-01-20_genshin.mp4",
            "star-rail_clip.mp4",
        ]

        for filename in test_cases:
            video = tmp_path / filename
            video.write_text("test")

            job = create_job_from_path(video, default_game="unknown")

            # All should use explicit default, not guessed names
            assert job.suggested_game == "unknown"

    def test_custom_default_game_respected(self, tmp_path):
        """Should use custom default_game if provided."""
        video = tmp_path / "any_video.mp4"
        video.write_text("test")

        job = create_job_from_path(video, default_game="mycustomgame")

        assert job.suggested_game == "mycustomgame"


class TestTagUniqueness:
    """Test that tags prevent same-prefix confusion."""

    def test_multiple_files_same_prefix_unique_tags(self, tmp_path):
        """Files with same prefix should get unique tags."""
        files = [
            "actor_clip.mp4",
            "actor_clip_副本.mp4",
            "actor_clip_copy.mp4",
            "actor_clip_final.mp4",
        ]

        jobs = []
        for filename in files:
            video = tmp_path / filename
            video.write_text("test")
            job = create_job_from_path(video)
            jobs.append(job)

        # All tags should be unique
        tags = [job.suggested_tag for job in jobs]
        assert len(tags) == len(set(tags)), "Tags should all be unique"

        # All should contain __ separator
        for tag in tags:
            assert "__" in tag

    def test_session_id_uniqueness(self, tmp_path):
        """Session IDs from same-prefix files should be distinguishable."""
        from yanhu.session import generate_session_id

        files = ["video.mp4", "video_副本.mp4", "video_copy.mp4"]

        session_ids = []
        for filename in files:
            video = tmp_path / filename
            video.write_text("test")
            job = create_job_from_path(video, default_game="game")

            # Generate session ID as process_job would
            session_id = generate_session_id(job.get_game(), job.get_tag())
            session_ids.append(session_id)

        # All session IDs should be unique (different tags)
        assert len(session_ids) == len(set(session_ids))

        # All should contain different tag portions
        tag_parts = [sid.split("_")[-1] for sid in session_ids]
        assert len(tag_parts) == len(set(tag_parts))
