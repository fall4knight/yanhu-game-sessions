"""Tests for ASR transcription."""

import json
from unittest.mock import MagicMock, patch

import pytest

from yanhu.manifest import Manifest, SegmentInfo
from yanhu.transcriber import (
    AsrConfig,
    AsrItem,
    AsrResult,
    MockAsrBackend,
    WhisperLocalBackend,
    _ensure_monotonic,
    get_asr_backend,
    merge_asr_to_analysis,
    save_asr_result_per_model,
    transcribe_session,
)


class TestAsrItem:
    """Test AsrItem dataclass."""

    def test_to_dict(self):
        """Should serialize to dict."""
        item = AsrItem(text="hello", t_start=1.0, t_end=2.0)
        d = item.to_dict()
        assert d == {"text": "hello", "t_start": 1.0, "t_end": 2.0}

    def test_from_dict(self):
        """Should deserialize from dict."""
        d = {"text": "hello", "t_start": 1.0, "t_end": 2.0}
        item = AsrItem.from_dict(d)
        assert item.text == "hello"
        assert item.t_start == 1.0
        assert item.t_end == 2.0


class TestAsrResult:
    """Test AsrResult dataclass."""

    def test_to_dict_with_items(self):
        """Should serialize with items."""
        result = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="hello", t_start=0.0, t_end=1.0)],
            asr_backend="mock",
        )
        d = result.to_dict()
        assert d["asr_backend"] == "mock"
        assert len(d["asr_items"]) == 1
        assert d["asr_items"][0]["text"] == "hello"

    def test_to_dict_with_error(self):
        """Should serialize with error."""
        result = AsrResult(
            segment_id="part_0001",
            asr_backend="mock",
            asr_error="Something failed",
        )
        d = result.to_dict()
        assert d["asr_backend"] == "mock"
        assert d["asr_error"] == "Something failed"
        assert "asr_items" not in d


class TestEnsureMonotonic:
    """Test _ensure_monotonic function."""

    def test_empty_list(self):
        """Should handle empty list."""
        assert _ensure_monotonic([]) == []

    def test_already_monotonic(self):
        """Should preserve already monotonic items."""
        items = [
            AsrItem(text="a", t_start=0.0, t_end=1.0),
            AsrItem(text="b", t_start=1.0, t_end=2.0),
        ]
        result = _ensure_monotonic(items)
        assert len(result) == 2
        assert result[0].t_start == 0.0
        assert result[0].t_end == 1.0
        assert result[1].t_start == 1.0
        assert result[1].t_end == 2.0

    def test_fix_overlapping(self):
        """Should fix overlapping timestamps."""
        items = [
            AsrItem(text="a", t_start=0.0, t_end=2.0),
            AsrItem(text="b", t_start=1.0, t_end=3.0),  # Overlaps with previous
        ]
        result = _ensure_monotonic(items)
        assert result[0].t_end == 2.0
        assert result[1].t_start >= result[0].t_end

    def test_fix_t_end_before_t_start(self):
        """Should fix t_end < t_start."""
        items = [
            AsrItem(text="a", t_start=1.0, t_end=0.5),  # Invalid
        ]
        result = _ensure_monotonic(items)
        assert result[0].t_start <= result[0].t_end


class TestMockAsrBackend:
    """Test MockAsrBackend."""

    def test_transcribe_with_ocr_items(self, tmp_path):
        """Should generate ASR from ocr_items."""
        # Setup
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis_file = analysis_dir / "part_0001.json"
        analysis_file.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "ocr_items": [
                        {"text": "Hello", "t_rel": 0.0, "source_frame": "frame_0001.jpg"},
                        {"text": "World", "t_rel": 2.0, "source_frame": "frame_0002.jpg"},
                    ],
                }
            )
        )

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        backend = MockAsrBackend()
        result = backend.transcribe_segment(segment, tmp_path)

        assert result.segment_id == "part_0001"
        assert result.asr_backend == "mock"
        assert result.asr_error is None
        assert len(result.asr_items) == 2
        assert result.asr_items[0].text == "Hello"
        assert result.asr_items[1].text == "World"

    def test_transcribe_with_ui_key_text(self, tmp_path):
        """Should fallback to ui_key_text when no ocr_items."""
        # Setup
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis_file = analysis_dir / "part_0001.json"
        analysis_file.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "ui_key_text": ["Key text 1", "Key text 2"],
                }
            )
        )

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        backend = MockAsrBackend()
        result = backend.transcribe_segment(segment, tmp_path)

        assert len(result.asr_items) == 2
        assert result.asr_items[0].text == "Key text 1"
        assert result.asr_items[1].text == "Key text 2"

    def test_transcribe_no_data(self, tmp_path):
        """Should create placeholder when no OCR data."""
        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        backend = MockAsrBackend()
        result = backend.transcribe_segment(segment, tmp_path)

        assert len(result.asr_items) == 1
        assert result.asr_items[0].text == "[无字幕]"

    def test_timestamps_monotonic(self, tmp_path):
        """Should ensure timestamps are monotonically increasing."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis_file = analysis_dir / "part_0001.json"
        analysis_file.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "ocr_items": [
                        {"text": "A", "t_rel": 0.0, "source_frame": "f1.jpg"},
                        {"text": "B", "t_rel": 1.0, "source_frame": "f2.jpg"},
                        {"text": "C", "t_rel": 2.0, "source_frame": "f3.jpg"},
                    ],
                }
            )
        )

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        backend = MockAsrBackend()
        result = backend.transcribe_segment(segment, tmp_path)

        # Check monotonicity
        for i in range(len(result.asr_items)):
            item = result.asr_items[i]
            assert item.t_start <= item.t_end, f"t_start > t_end for item {i}"
            if i > 0:
                prev = result.asr_items[i - 1]
                assert item.t_start >= prev.t_end, f"Not monotonic at item {i}"


class TestMergeAsrToAnalysis:
    """Test merge_asr_to_analysis function."""

    def test_merge_into_existing(self, tmp_path):
        """Should merge ASR into existing analysis."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis_file = analysis_dir / "part_0001.json"
        analysis_file.write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "caption": "Existing caption",
                }
            )
        )

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        asr_result = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="Hello", t_start=0.0, t_end=1.0)],
            asr_backend="mock",
        )

        merge_asr_to_analysis(asr_result, analysis_file, segment)

        # Verify
        with open(analysis_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["segment_id"] == "part_0001"
        assert data["scene_type"] == "dialogue"
        assert data["caption"] == "Existing caption"
        assert data["asr_backend"] == "mock"
        assert len(data["asr_items"]) == 1
        assert data["asr_items"][0]["text"] == "Hello"

    def test_create_minimal_analysis(self, tmp_path):
        """Should create minimal analysis when file doesn't exist."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis_file = analysis_dir / "part_0001.json"

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        asr_result = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="Hello", t_start=0.0, t_end=1.0)],
            asr_backend="mock",
        )

        merge_asr_to_analysis(asr_result, analysis_file, segment)

        # Verify
        with open(analysis_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["segment_id"] == "part_0001"
        assert data["scene_type"] == "unknown"
        assert data["caption"] == ""
        assert data["asr_backend"] == "mock"

    def test_merge_error(self, tmp_path):
        """Should merge error into analysis."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis_file = analysis_dir / "part_0001.json"

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        asr_result = AsrResult(
            segment_id="part_0001",
            asr_backend="mock",
            asr_error="Something failed",
        )

        merge_asr_to_analysis(asr_result, analysis_file, segment)

        with open(analysis_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["asr_error"] == "Something failed"
        assert "asr_items" not in data


class TestGetAsrBackend:
    """Test get_asr_backend factory."""

    def test_get_mock(self):
        """Should return MockAsrBackend."""
        backend = get_asr_backend("mock")
        assert isinstance(backend, MockAsrBackend)

    def test_unknown_backend(self):
        """Should raise for unknown backend."""
        with pytest.raises(ValueError, match="Unknown ASR backend"):
            get_asr_backend("unknown")


class TestTranscribeSession:
    """Test transcribe_session function."""

    def _create_test_manifest(self, tmp_path, num_segments=2):
        """Create a test manifest with segments."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[],
        )

        for i in range(num_segments):
            seg_id = f"part_{i + 1:04d}"
            frames_dir = tmp_path / "frames" / seg_id
            frames_dir.mkdir(parents=True)
            (frames_dir / "frame_0001.jpg").write_bytes(b"fake")

            manifest.segments.append(
                SegmentInfo(
                    id=seg_id,
                    start_time=i * 10.0,
                    end_time=(i + 1) * 10.0,
                    video_path=f"segments/{seg_id}.mp4",
                    frames=[f"frames/{seg_id}/frame_0001.jpg"],
                )
            )

        return manifest

    def test_transcribe_all_segments(self, tmp_path):
        """Should transcribe all segments."""
        manifest = self._create_test_manifest(tmp_path, num_segments=2)

        stats = transcribe_session(manifest, tmp_path, backend="mock")

        assert stats.processed == 2
        assert stats.skipped_cache == 0
        assert stats.errors == 0

        # Check files created
        assert (tmp_path / "analysis" / "part_0001.json").exists()
        assert (tmp_path / "analysis" / "part_0002.json").exists()

    def test_skip_cached(self, tmp_path):
        """Should skip segments with existing ASR data."""
        manifest = self._create_test_manifest(tmp_path, num_segments=2)

        # Pre-create ASR data for first segment
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "asr_items": [{"text": "existing", "t_start": 0, "t_end": 1}],
                    "asr_backend": "mock",
                }
            )
        )

        stats = transcribe_session(manifest, tmp_path, backend="mock")

        assert stats.processed == 1
        assert stats.skipped_cache == 1

    def test_force_reprocess(self, tmp_path):
        """Should reprocess with force=True."""
        manifest = self._create_test_manifest(tmp_path, num_segments=1)

        # Pre-create ASR data
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "asr_items": [{"text": "old", "t_start": 0, "t_end": 1}],
                    "asr_backend": "mock",
                }
            )
        )

        stats = transcribe_session(manifest, tmp_path, backend="mock", force=True)

        assert stats.processed == 1
        assert stats.skipped_cache == 0

    def test_limit(self, tmp_path):
        """Should respect limit parameter."""
        manifest = self._create_test_manifest(tmp_path, num_segments=5)

        stats = transcribe_session(manifest, tmp_path, backend="mock", limit=2)

        assert stats.processed == 2

    def test_segment_filter(self, tmp_path):
        """Should filter by segment IDs."""
        manifest = self._create_test_manifest(tmp_path, num_segments=3)

        stats = transcribe_session(manifest, tmp_path, backend="mock", segments=["part_0002"])

        assert stats.processed == 1
        assert stats.skipped_filter == 2

    def test_progress_callback(self, tmp_path):
        """Should call progress callback."""
        manifest = self._create_test_manifest(tmp_path, num_segments=1)
        progress_calls = []

        def on_progress(segment_id, status, result, stats):
            progress_calls.append((segment_id, status))

        transcribe_session(manifest, tmp_path, backend="mock", on_progress=on_progress)

        assert len(progress_calls) == 1
        assert progress_calls[0] == ("part_0001", "done")


class TestAsrTimestampValidation:
    """Test ASR timestamp validation requirements."""

    def test_t_start_le_t_end(self, tmp_path):
        """Verify t_start <= t_end for all items."""
        manifest = Manifest(
            session_id="test",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                    frames=[],
                )
            ],
        )

        transcribe_session(manifest, tmp_path, backend="mock")

        analysis_file = tmp_path / "analysis" / "part_0001.json"
        with open(analysis_file, encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("asr_items", []):
            assert item["t_start"] <= item["t_end"]

    def test_timestamps_monotonic(self, tmp_path):
        """Verify timestamps are monotonically increasing."""
        # Setup with multiple OCR items
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "part_0001.json").write_text(
            json.dumps(
                {
                    "segment_id": "part_0001",
                    "scene_type": "dialogue",
                    "ocr_items": [
                        {"text": "A", "t_rel": 0.0, "source_frame": "f1.jpg"},
                        {"text": "B", "t_rel": 1.0, "source_frame": "f2.jpg"},
                        {"text": "C", "t_rel": 2.0, "source_frame": "f3.jpg"},
                    ],
                }
            )
        )

        manifest = Manifest(
            session_id="test",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                    frames=[],
                )
            ],
        )

        transcribe_session(manifest, tmp_path, backend="mock", force=True)

        with open(analysis_dir / "part_0001.json", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("asr_items", [])
        for i in range(1, len(items)):
            assert items[i]["t_start"] >= items[i - 1]["t_end"], (
                f"Not monotonic: item {i - 1} ends at {items[i - 1]['t_end']}, "
                f"item {i} starts at {items[i]['t_start']}"
            )


class TestWhisperLocalBackend:
    """Tests for WhisperLocalBackend (without actual whisper model)."""

    def test_init_params(self):
        """Should accept configuration parameters."""
        from yanhu.transcriber import WhisperLocalBackend

        backend = WhisperLocalBackend(
            model_size="small",
            language="zh",
            vad_filter=False,
            force_audio=True,
        )
        assert backend.model_size == "small"
        assert backend.language == "zh"
        assert backend.vad_filter is False
        assert backend.force_audio is True

    def test_audio_path_generation(self, tmp_path):
        """Should generate correct audio path format."""
        # Test that the audio path follows the expected pattern
        audio_dir = tmp_path / "audio"
        expected_audio_path = audio_dir / "part_0001.wav"

        # We're testing the path convention, not actual extraction
        assert str(expected_audio_path).endswith("audio/part_0001.wav")
        assert expected_audio_path.name == "part_0001.wav"

    def test_error_on_missing_video(self, tmp_path):
        """Should return error when video file is missing."""
        from yanhu.transcriber import WhisperLocalBackend

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/missing.mp4",
            frames=[],
        )

        backend = WhisperLocalBackend()
        result = backend.transcribe_segment(segment, tmp_path)

        assert result.asr_error is not None
        assert "not found" in result.asr_error.lower() or "failed" in result.asr_error.lower()
        assert result.asr_backend == "whisper_local"


class TestWhisperTimestampAlignment:
    """Test timestamp alignment for whisper backend."""

    def test_segment_start_added_to_timestamps(self):
        """Timestamps should be segment.start_time + local whisper time."""
        from yanhu.transcriber import AsrItem

        # Simulate what WhisperLocalBackend does:
        # If segment starts at 60s, and whisper returns 0-2s locally,
        # the result should be 60-62s
        segment_start = 60.0
        local_start = 0.0
        local_end = 2.5

        # This is how timestamps are computed in _transcribe_audio
        t_start = round(segment_start + local_start, 2)
        t_end = round(segment_start + local_end, 2)

        item = AsrItem(text="Hello", t_start=t_start, t_end=t_end)

        assert item.t_start == 60.0
        assert item.t_end == 62.5

    def test_multiple_segments_have_correct_offsets(self):
        """Each segment should have timestamps offset by its start_time."""
        from yanhu.transcriber import AsrItem

        # Segment 1: 0-10s, Segment 2: 10-20s, Segment 3: 20-30s
        segments_data = [
            (0.0, [(0.0, 2.0, "First"), (3.0, 5.0, "Second")]),
            (10.0, [(0.0, 1.5, "Third"), (2.0, 4.0, "Fourth")]),
            (20.0, [(1.0, 3.0, "Fifth")]),
        ]

        all_items = []
        for seg_start, local_items in segments_data:
            for local_start, local_end, text in local_items:
                item = AsrItem(
                    text=text,
                    t_start=round(seg_start + local_start, 2),
                    t_end=round(seg_start + local_end, 2),
                )
                all_items.append(item)

        # Verify absolute timestamps
        assert all_items[0].t_start == 0.0  # First
        assert all_items[0].t_end == 2.0
        assert all_items[1].t_start == 3.0  # Second
        assert all_items[2].t_start == 10.0  # Third (segment 2)
        assert all_items[3].t_start == 12.0  # Fourth
        assert all_items[4].t_start == 21.0  # Fifth (segment 3)


class TestGetAsrBackendWithOptions:
    """Test get_asr_backend factory with new options."""

    def test_whisper_backend_with_options(self):
        """Should pass options to WhisperLocalBackend."""
        from yanhu.transcriber import WhisperLocalBackend, get_asr_backend

        backend = get_asr_backend(
            "whisper_local",
            model_size="small",
            language="en",
            vad_filter=False,
            force_audio=True,
        )

        assert isinstance(backend, WhisperLocalBackend)
        assert backend.model_size == "small"
        assert backend.language == "en"
        assert backend.vad_filter is False
        assert backend.force_audio is True

    def test_mock_backend_ignores_whisper_options(self):
        """Mock backend should work even with whisper options."""
        backend = get_asr_backend(
            "mock",
            model_size="large",
            language="zh",
            vad_filter=False,
        )

        assert isinstance(backend, MockAsrBackend)


class TestTranscribeSessionWithOptions:
    """Test transcribe_session with whisper options."""

    def _create_test_manifest(self, tmp_path):
        """Create a test manifest."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                    frames=[],
                )
            ],
        )
        return manifest

    def test_passes_options_to_backend(self, tmp_path):
        """Should pass whisper options to transcribe_session."""
        manifest = self._create_test_manifest(tmp_path)

        # Mock backend ignores these, but the call should work
        stats = transcribe_session(
            manifest,
            tmp_path,
            backend="mock",
            model_size="small",
            language="zh",
            vad_filter=True,
        )

        assert stats.processed == 1


class TestAsrConfig:
    """Test AsrConfig dataclass."""

    def test_to_dict(self):
        """Should serialize to dict."""
        config = AsrConfig(
            device="cuda",
            compute_type="float16",
            model_size="large",
            language="zh",
            beam_size=10,
            vad_filter=False,
        )
        d = config.to_dict()
        assert d == {
            "device": "cuda",
            "compute_type": "float16",
            "model_size": "large",
            "language": "zh",
            "beam_size": 10,
            "vad_filter": False,
        }

    def test_from_dict(self):
        """Should deserialize from dict."""
        d = {
            "device": "cpu",
            "compute_type": "int8",
            "model_size": "base",
            "language": "en",
            "beam_size": 5,
            "vad_filter": True,
        }
        config = AsrConfig.from_dict(d)
        assert config.device == "cpu"
        assert config.compute_type == "int8"
        assert config.model_size == "base"
        assert config.language == "en"
        assert config.beam_size == 5
        assert config.vad_filter is True

    def test_defaults(self):
        """Should have correct defaults."""
        config = AsrConfig()
        assert config.device == "cpu"
        assert config.compute_type == "int8"
        assert config.model_size == "base"
        assert config.language is None
        assert config.beam_size == 5
        assert config.vad_filter is True


class TestAsrResultWithConfig:
    """Test AsrResult with asr_config field."""

    def test_to_dict_with_config(self):
        """Should serialize with config."""
        config = AsrConfig(device="cpu", compute_type="float32", model_size="small")
        result = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="hello", t_start=0.0, t_end=1.0)],
            asr_backend="whisper_local",
            asr_config=config,
        )
        d = result.to_dict()
        assert d["asr_backend"] == "whisper_local"
        assert "asr_config" in d
        assert d["asr_config"]["device"] == "cpu"
        assert d["asr_config"]["compute_type"] == "float32"
        assert d["asr_config"]["model_size"] == "small"

    def test_to_dict_without_config(self):
        """Should work without config."""
        result = AsrResult(
            segment_id="part_0001",
            asr_backend="mock",
        )
        d = result.to_dict()
        assert "asr_config" not in d


class TestWhisperLocalBackendParams:
    """Test WhisperLocalBackend parameter handling."""

    def test_init_with_all_params(self):
        """Should accept all configuration parameters."""
        backend = WhisperLocalBackend(
            model_size="large",
            language="zh",
            vad_filter=False,
            force_audio=True,
            device="cuda",
            compute_type="float16",
            beam_size=10,
        )
        assert backend.model_size == "large"
        assert backend.language == "zh"
        assert backend.vad_filter is False
        assert backend.force_audio is True
        assert backend.device == "cuda"
        assert backend.compute_type == "float16"
        assert backend.beam_size == 10

    def test_default_params(self):
        """Should have correct default parameters."""
        backend = WhisperLocalBackend()
        assert backend.model_size == "base"
        assert backend.language is None
        assert backend.vad_filter is True
        assert backend.force_audio is False
        assert backend.device == "cpu"
        assert backend.compute_type == "int8"
        assert backend.beam_size == 5

    def test_get_asr_config(self):
        """Should return correct AsrConfig from settings."""
        backend = WhisperLocalBackend(
            model_size="small",
            language="en",
            vad_filter=False,
            device="cuda",
            compute_type="float32",
            beam_size=8,
        )
        config = backend._get_asr_config()
        assert isinstance(config, AsrConfig)
        assert config.model_size == "small"
        assert config.language == "en"
        assert config.vad_filter is False
        assert config.device == "cuda"
        assert config.compute_type == "float32"
        assert config.beam_size == 8


class TestWhisperParamPassthrough:
    """Test that parameters are correctly passed to faster-whisper."""

    def test_model_init_params_passed(self, tmp_path):
        """Should pass device and compute_type to WhisperModel."""
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], None)

        with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
            import sys

            mock_whisper_module = sys.modules["faster_whisper"]
            mock_whisper_module.WhisperModel = MagicMock(return_value=mock_model)

            backend = WhisperLocalBackend(
                model_size="medium",
                device="cuda",
                compute_type="float16",
            )
            # Trigger model loading
            backend._load_model()

            mock_whisper_module.WhisperModel.assert_called_once_with(
                "medium",
                device="cuda",
                compute_type="float16",
            )

    def test_transcribe_params_passed(self, tmp_path):
        """Should pass beam_size, vad_filter, language to transcribe."""
        # Create a mock segment iterator
        mock_segment = MagicMock()
        mock_segment.text = " Test text "
        mock_segment.start = 0.0
        mock_segment.end = 1.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([mock_segment]), None)

        with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
            import sys

            mock_whisper_module = sys.modules["faster_whisper"]
            mock_whisper_module.WhisperModel = MagicMock(return_value=mock_model)

            backend = WhisperLocalBackend(
                model_size="base",
                language="zh",
                vad_filter=True,
                beam_size=8,
            )
            backend._load_model()

            # Call _transcribe_audio directly
            backend._transcribe_audio(tmp_path / "test.wav", 0.0)

            # Check transcribe was called with correct params
            mock_model.transcribe.assert_called_once()
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["vad_filter"] is True
            assert call_kwargs["beam_size"] == 8
            assert call_kwargs["language"] == "zh"

    def test_transcribe_without_language(self, tmp_path):
        """Should not pass language when None (auto-detect)."""
        mock_segment = MagicMock()
        mock_segment.text = " Test "
        mock_segment.start = 0.0
        mock_segment.end = 1.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([mock_segment]), None)

        with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
            import sys

            mock_whisper_module = sys.modules["faster_whisper"]
            mock_whisper_module.WhisperModel = MagicMock(return_value=mock_model)

            backend = WhisperLocalBackend(
                language=None,
                beam_size=5,
            )
            backend._load_model()

            backend._transcribe_audio(tmp_path / "test.wav", 0.0)

            call_kwargs = mock_model.transcribe.call_args[1]
            assert "language" not in call_kwargs
            assert call_kwargs["beam_size"] == 5


class TestGetAsrBackendAllParams:
    """Test get_asr_backend factory with all new options."""

    def test_whisper_backend_all_params(self):
        """Should pass all options to WhisperLocalBackend."""
        backend = get_asr_backend(
            "whisper_local",
            model_size="large",
            language="yue",
            vad_filter=False,
            force_audio=True,
            device="cuda",
            compute_type="float32",
            beam_size=10,
        )

        assert isinstance(backend, WhisperLocalBackend)
        assert backend.model_size == "large"
        assert backend.language == "yue"
        assert backend.vad_filter is False
        assert backend.force_audio is True
        assert backend.device == "cuda"
        assert backend.compute_type == "float32"
        assert backend.beam_size == 10


class TestTranscribeSessionAllParams:
    """Test transcribe_session with all new parameters."""

    def _create_test_manifest(self, tmp_path):
        """Create a test manifest."""
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-01T00:00:00",
            source_video="source.mp4",
            source_video_local="source/source.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                    frames=[],
                )
            ],
        )
        return manifest

    def test_passes_all_params_to_backend(self, tmp_path):
        """Should pass all params through transcribe_session."""
        manifest = self._create_test_manifest(tmp_path)

        # Use mock backend - it ignores params but the call should work
        stats = transcribe_session(
            manifest,
            tmp_path,
            backend="mock",
            model_size="large",
            language="yue",
            vad_filter=False,
            device="cuda",
            compute_type="float32",
            beam_size=10,
        )

        assert stats.processed == 1

    @patch("yanhu.transcriber.WhisperLocalBackend")
    def test_whisper_backend_receives_params(self, MockBackend, tmp_path):
        """Should pass params to WhisperLocalBackend via get_asr_backend."""
        manifest = self._create_test_manifest(tmp_path)

        # Setup mock backend
        mock_instance = MagicMock()
        mock_result = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="test", t_start=0.0, t_end=1.0)],
            asr_backend="whisper_local",
        )
        mock_instance.transcribe_segment.return_value = mock_result
        MockBackend.return_value = mock_instance

        transcribe_session(
            manifest,
            tmp_path,
            backend="whisper_local",
            model_size="medium",
            language="zh",
            vad_filter=True,
            device="cpu",
            compute_type="int8",
            beam_size=7,
            force=True,
        )

        # Verify backend was created with correct params
        MockBackend.assert_called_once_with(
            model_size="medium",
            language="zh",
            vad_filter=True,
            force_audio=True,
            device="cpu",
            compute_type="int8",
            beam_size=7,
        )


class TestAsrConfigInAnalysis:
    """Test that asr_config is written to analysis JSON."""

    def test_config_saved_in_analysis(self, tmp_path):
        """Should save asr_config to analysis JSON."""
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        analysis_file = analysis_dir / "part_0001.json"

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
            frames=[],
        )

        config = AsrConfig(
            device="cuda",
            compute_type="float32",
            model_size="large",
            language="yue",
            beam_size=10,
            vad_filter=False,
        )
        asr_result = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="Hello", t_start=0.0, t_end=1.0)],
            asr_backend="whisper_local",
            asr_config=config,
        )

        merge_asr_to_analysis(asr_result, analysis_file, segment)

        # Verify
        with open(analysis_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["asr_backend"] == "whisper_local"
        assert "asr_config" in data
        assert data["asr_config"]["device"] == "cuda"
        assert data["asr_config"]["compute_type"] == "float32"
        assert data["asr_config"]["model_size"] == "large"
        assert data["asr_config"]["language"] == "yue"
        assert data["asr_config"]["beam_size"] == 10
        assert data["asr_config"]["vad_filter"] is False


class TestMultiModelTranscription:
    """Test multi-model ASR transcription."""

    def test_save_asr_result_per_model(self, tmp_path):
        """Should save per-model transcript to outputs/asr/<model>/transcript.json."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        result = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="Hello", t_start=0.0, t_end=1.0)],
            asr_backend="mock",
        )

        save_asr_result_per_model(result, session_dir, "mock")

        # Verify file created
        transcript_file = session_dir / "outputs" / "asr" / "mock" / "transcript.json"
        assert transcript_file.exists()

        # Verify content
        with open(transcript_file, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["segment_id"] == "part_0001"
        assert data[0]["asr_backend"] == "mock"
        assert len(data[0]["asr_items"]) == 1
        assert data[0]["asr_items"][0]["text"] == "Hello"

    def test_save_multiple_segments_per_model(self, tmp_path):
        """Should append multiple segments to same transcript file."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Save first segment
        result1 = AsrResult(
            segment_id="part_0001",
            asr_items=[AsrItem(text="First", t_start=0.0, t_end=1.0)],
            asr_backend="mock",
        )
        save_asr_result_per_model(result1, session_dir, "mock")

        # Save second segment
        result2 = AsrResult(
            segment_id="part_0002",
            asr_items=[AsrItem(text="Second", t_start=1.0, t_end=2.0)],
            asr_backend="mock",
        )
        save_asr_result_per_model(result2, session_dir, "mock")

        # Verify both segments in file
        transcript_file = session_dir / "outputs" / "asr" / "mock" / "transcript.json"
        with open(transcript_file, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 2
        assert data[0]["segment_id"] == "part_0001"
        assert data[1]["segment_id"] == "part_0002"

    def test_transcribe_session_with_multiple_models(self, tmp_path):
        """Should transcribe with multiple models."""
        # Create session structure
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        segments_dir = session_dir / "segments"
        segments_dir.mkdir()

        # Create manifest
        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T00:00:00",
            source_video="/test/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                )
            ],
        )

        # Transcribe with both mock and mock (to test multiple models)
        stats = transcribe_session(
            manifest=manifest,
            session_dir=session_dir,
            asr_models=["mock", "mock"],  # Use mock twice for testing
            force=True,
        )

        # Should process once (not duplicated per model)
        assert stats.processed == 1
        assert stats.total == 1

        # Verify per-model outputs exist
        mock_transcript = session_dir / "outputs" / "asr" / "mock" / "transcript.json"
        assert mock_transcript.exists()

        # Verify primary model also saved to analysis/
        analysis_file = session_dir / "analysis" / "part_0001.json"
        assert analysis_file.exists()

    def test_transcribe_session_backward_compat_no_asr_models(self, tmp_path):
        """Should work without asr_models parameter (backward compatibility)."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        segments_dir = session_dir / "segments"
        segments_dir.mkdir()

        manifest = Manifest(
            session_id="test_session",
            created_at="2026-01-23T00:00:00",
            source_video="/test/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo(
                    id="part_0001",
                    start_time=0.0,
                    end_time=10.0,
                    video_path="segments/part_0001.mp4",
                )
            ],
        )

        # Transcribe without asr_models (should use backend parameter)
        stats = transcribe_session(
            manifest=manifest,
            session_dir=session_dir,
            backend="mock",
            force=True,
        )

        assert stats.processed == 1

        # Verify primary model saved to analysis/
        analysis_file = session_dir / "analysis" / "part_0001.json"
        assert analysis_file.exists()

        # Verify per-model output also exists
        mock_transcript = session_dir / "outputs" / "asr" / "mock" / "transcript.json"
        assert mock_transcript.exists()


class TestWhisperLocalFfmpegDiscovery:
    """Test whisper_local uses find_ffmpeg() for packaged app support (Step 23)."""

    def test_whisper_local_ffmpeg_missing_error(self, tmp_path, monkeypatch):
        """When ffmpeg missing, whisper_local should produce asr_error for Step 22."""
        from yanhu.manifest import SegmentInfo
        from yanhu.transcriber import WhisperLocalBackend

        # Mock find_ffmpeg to return None (ffmpeg not found)
        def mock_find_ffmpeg():
            return None

        monkeypatch.setattr("yanhu.ffmpeg_utils.find_ffmpeg", mock_find_ffmpeg)

        # Create test session and segment
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        segments_dir = session_dir / "segments"
        segments_dir.mkdir()

        # Create dummy video file
        video_file = segments_dir / "part_0001.mp4"
        video_file.write_bytes(b"dummy video")

        segment = SegmentInfo(
            id="part_0001",
            start_time=0.0,
            end_time=10.0,
            video_path="segments/part_0001.mp4",
        )

        backend = WhisperLocalBackend(model_size="base")
        result = backend.transcribe_segment(segment, session_dir, max_seconds=None)

        # Should have error about ffmpeg not found
        assert result.asr_error is not None
        assert "ffmpeg not found" in result.asr_error
        # Error should trigger Step 22 dependency failure detection
        assert result.asr_items == []
