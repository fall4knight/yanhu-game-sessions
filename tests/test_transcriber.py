"""Tests for ASR transcription."""

import json

import pytest

from yanhu.manifest import Manifest, SegmentInfo
from yanhu.transcriber import (
    AsrItem,
    AsrResult,
    MockAsrBackend,
    _ensure_monotonic,
    get_asr_backend,
    merge_asr_to_analysis,
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
        analysis_file.write_text(json.dumps({
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "ocr_items": [
                {"text": "Hello", "t_rel": 0.0, "source_frame": "frame_0001.jpg"},
                {"text": "World", "t_rel": 2.0, "source_frame": "frame_0002.jpg"},
            ],
        }))

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
        analysis_file.write_text(json.dumps({
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "ui_key_text": ["Key text 1", "Key text 2"],
        }))

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
        analysis_file.write_text(json.dumps({
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "ocr_items": [
                {"text": "A", "t_rel": 0.0, "source_frame": "f1.jpg"},
                {"text": "B", "t_rel": 1.0, "source_frame": "f2.jpg"},
                {"text": "C", "t_rel": 2.0, "source_frame": "f3.jpg"},
            ],
        }))

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
        analysis_file.write_text(json.dumps({
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "caption": "Existing caption",
        }))

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

            manifest.segments.append(SegmentInfo(
                id=seg_id,
                start_time=i * 10.0,
                end_time=(i + 1) * 10.0,
                video_path=f"segments/{seg_id}.mp4",
                frames=[f"frames/{seg_id}/frame_0001.jpg"],
            ))

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
        (analysis_dir / "part_0001.json").write_text(json.dumps({
            "segment_id": "part_0001",
            "asr_items": [{"text": "existing", "t_start": 0, "t_end": 1}],
            "asr_backend": "mock",
        }))

        stats = transcribe_session(manifest, tmp_path, backend="mock")

        assert stats.processed == 1
        assert stats.skipped_cache == 1

    def test_force_reprocess(self, tmp_path):
        """Should reprocess with force=True."""
        manifest = self._create_test_manifest(tmp_path, num_segments=1)

        # Pre-create ASR data
        analysis_dir = tmp_path / "analysis"
        analysis_dir.mkdir()
        (analysis_dir / "part_0001.json").write_text(json.dumps({
            "segment_id": "part_0001",
            "asr_items": [{"text": "old", "t_start": 0, "t_end": 1}],
            "asr_backend": "mock",
        }))

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

        stats = transcribe_session(
            manifest, tmp_path, backend="mock", segments=["part_0002"]
        )

        assert stats.processed == 1
        assert stats.skipped_filter == 2

    def test_progress_callback(self, tmp_path):
        """Should call progress callback."""
        manifest = self._create_test_manifest(tmp_path, num_segments=1)
        progress_calls = []

        def on_progress(segment_id, status, result):
            progress_calls.append((segment_id, status))

        transcribe_session(
            manifest, tmp_path, backend="mock", on_progress=on_progress
        )

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
        (analysis_dir / "part_0001.json").write_text(json.dumps({
            "segment_id": "part_0001",
            "scene_type": "dialogue",
            "ocr_items": [
                {"text": "A", "t_rel": 0.0, "source_frame": "f1.jpg"},
                {"text": "B", "t_rel": 1.0, "source_frame": "f2.jpg"},
                {"text": "C", "t_rel": 2.0, "source_frame": "f3.jpg"},
            ],
        }))

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
