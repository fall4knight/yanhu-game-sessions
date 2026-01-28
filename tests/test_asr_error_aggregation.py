import json


def test_aggregate_asr_errors_sets_dependency_error_for_asr_dependency_missing(tmp_path):
    """If all segments fail with ASR dependency missing, surface as dependency_error."""
    from yanhu.watcher import aggregate_asr_errors

    session_dir = tmp_path / "session"
    transcript_path = session_dir / "outputs" / "asr" / "mock" / "transcript.json"
    transcript_path.parent.mkdir(parents=True)

    msg = (
        "ASR dependency missing: neither faster-whisper nor openai-whisper found. "
        "This is a packaging error in desktop builds. "
        "Download the latest release from the official website."
    )

    transcript_path.write_text(
        json.dumps(
            [
                {"segment_id": "part_0001", "asr_error": msg},
                {"segment_id": "part_0002", "asr_error": msg},
            ]
        ),
        encoding="utf-8",
    )

    summary = aggregate_asr_errors(session_dir, ["mock"])
    assert summary is not None
    assert summary.failed_segments == 2
    assert summary.total_segments == 2
    assert summary.dependency_error is not None
    assert "asr dependency missing" in summary.dependency_error.lower()
    # Should not accidentally show ffmpeg instructions for this case
    assert "ffmpeg" not in summary.dependency_error.lower()
