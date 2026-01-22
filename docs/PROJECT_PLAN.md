# Yanhu Game Sessions - Project Plan

## Executive Summary

**Yanhu Game Sessions** is a post-game replay companion system that processes game recordings through a multi-stage pipeline: ingest raw video, segment into clips, extract frames, run multimodal AI (vision + ASR), and compose session summaries. MVP v0.1 targets offline batch processing with manual trigger, outputting structured Markdown timelines and highlights. Key risks include ffmpeg dependency management, API costs for vision/ASR models, and privacy of gameplay data.

---

## Requirements Map

| ID | Hard Requirement (from README) | Module | Acceptance Test |
|----|-------------------------------|--------|-----------------|
| R1 | Watcher script detects new videos in raw directory | `watcher` | Given a new `.mp4` in `raw/`, it is renamed and moved to `processed/<game>/` within 30s |
| R2 | Rename videos to format `YYYY-MM-DD_HH-MM-SS_<game>_<run>.mp4` | `watcher` | Filename matches regex, metadata preserved |
| R3 | Segment video into 30s-60s chunks using ffmpeg | `segmenter` | Output files `*_part_NNNN.mp4` exist, each <= 60s duration |
| R4 | Extract key frames (middle frame + scene-change frames) | `extractor` | At least 1 frame per segment; scene-change frames detected when delta > threshold |
| R5 | Call multimodal vision model to classify scene type and OCR text | `vision_analyzer` | Returns JSON with `scene_type`, `ocr_text` fields; mocked model passes |
| R6 | Call ASR model to transcribe audio | `asr` | Returns timestamped transcript; handles silence gracefully |
| R7 | LLM post-processing of ASR (optional) | `asr_postprocess` | Corrects known error patterns; toggle-able via config |
| R8 | Generate per-segment natural language description | `segment_summarizer` | Each segment has a 2-4 sentence Chinese description |
| R9 | Merge all segments into session timeline + highlights | `composer` | Outputs `timeline.md`, `highlights.md`, `overview.md` |
| R10 | Manifest file tracks all artifacts | `manifest` | `manifest.json` lists all paths, hashes, timestamps |

---

## MVP v0.1 Spec

### Inputs

- **Video file**: Single `.mp4` or `.mkv` file (manual path input for MVP)
- **Config**: `config.yaml` specifying API keys, segment duration, model endpoints

### Outputs

```
sessions/<session_id>/
  manifest.json          # artifact registry
  overview.md            # game, duration, outcome summary
  timeline.md            # HH:MM:SS event log
  highlights.md          # notable moments with timestamps
  segments/
    part_0001/
      video.mp4
      frames/
        frame_001.jpg
        frame_002.jpg
      analysis.json      # vision + ASR results
      summary.txt
    part_0002/
      ...
```

### Repository Folder Layout

```
yanhu-game-sessions/
  README.md
  pyproject.toml         # Python packaging
  config.example.yaml
  src/
    yanhu/
      __init__.py
      cli.py             # main entry point
      watcher.py         # R1, R2
      segmenter.py       # R3
      extractor.py       # R4
      vision_analyzer.py # R5
      asr.py             # R6
      asr_postprocess.py # R7
      segment_summarizer.py # R8
      composer.py        # R9
      manifest.py        # R10
      models/            # model client abstractions
        base.py
        claude_vision.py
        openai_vision.py
        whisper_asr.py
  tests/
    fixtures/
      sample_10s.mp4
    test_segmenter.py
    test_extractor.py
    test_composer.py
  sessions/              # output directory (gitignored)
  .claude/
    skills/
```

### Data Formats

#### manifest.json

```json
{
  "session_id": "2026-01-19_21-45-00_gnosia_run01",
  "created_at": "2026-01-19T21:45:00Z",
  "source_video": "/path/to/original.mp4",
  "segments": [
    {
      "id": "part_0001",
      "start_time": 0,
      "end_time": 30,
      "video_path": "segments/part_0001/video.mp4",
      "frames": ["segments/part_0001/frames/frame_001.jpg"],
      "analysis_path": "segments/part_0001/analysis.json",
      "summary_path": "segments/part_0001/summary.txt"
    }
  ],
  "outputs": {
    "overview": "overview.md",
    "timeline": "timeline.md",
    "highlights": "highlights.md"
  }
}
```

#### analysis.json (per segment)

```json
{
  "segment_id": "part_0001",
  "scene_type": "dialogue",
  "ocr_text": ["角色A: 你好", "系统提示: 请选择"],
  "asr_transcript": [
    {"start": 0.0, "end": 2.5, "text": "欢迎来到古诺希亚"}
  ],
  "characters_detected": ["角色A", "角色B"],
  "is_highlight": false
}
```

---

## Milestones

### Milestone 0: Project Scaffolding

**Scope**: Set up the Python package structure, CI pipeline, and configuration templates.

**Definition of Done**: Repository has working Python package structure, CI runs, and sample config.

**Checklist**:
- [x] Initialize `pyproject.toml` with dependencies (ffmpeg-python, anthropic, openai, etc.)
- [x] Create `src/yanhu/__init__.py` and `cli.py` skeleton
- [x] Add `config.example.yaml` with all required fields documented
- [x] Set up `.gitignore` (sessions/, *.mp4, .env)
- [x] Add GitHub Actions workflow for linting (ruff) and tests (pytest)
- [x] Write `tests/test_placeholder.py` that passes

---

### Milestone 1: Video Ingestion & Segmentation

**Scope**: Implement video segmentation using ffmpeg, create manifest tracking system.

**Definition of Done**: CLI can take a video path and produce numbered segment files in `sessions/<id>/segments/`.

**Checklist**:
- [x] Implement `segmenter.py` using subprocess ffmpeg
  - [x] Function `segment_video(manifest, session_dir) -> List[SegmentInfo]`
  - [x] Handle edge case: last segment < duration
- [x] Implement `manifest.py` with `Manifest` dataclass and JSON serialization
- [x] Add CLI command `yanhu ingest --video <path> --game <name> --tag <tag>`
  - [x] Auto-generate session_id from timestamp + game + tag
  - [x] Create session folder structure (source/, segments/)
- [x] Add CLI command `yanhu segment --session <id>` to run segmentation
- [x] Write unit tests (session_id format, segment naming, manifest, ffmpeg commands)
- [x] Verify ffmpeg error handling (missing binary check)

---

### Milestone 2: Frame Extraction

**Scope**: Extract key frames from each video segment for vision analysis.

**Definition of Done**: Each segment has a `frames/` folder with key frames extracted.

**Checklist**:
- [x] Implement `extractor.py`
  - [x] Function `extract_frames(manifest, session_dir, frames_per_segment)`
  - [x] Calculate evenly distributed sample timestamps including middle frame
  - [x] JPEG output via ffmpeg subprocess
  - [ ] (Stretch) Scene-change detection using frame diff threshold
- [x] Update manifest to track frame paths (SegmentInfo.frames field)
- [x] Add CLI command `yanhu extract --session <id> --frames-per-segment N`
- [x] Write unit tests (sampling logic, path naming, command building, manifest integration)

---

### Milestone 3: Vision Analysis

**Scope**: Integrate multimodal vision models for scene classification and OCR.

**Definition of Done**: Each segment has `analysis.json` with scene classification and OCR.

**Checklist**:
- [ ] Define `models/base.py` abstract interface for vision models
- [ ] Implement `models/claude_vision.py` using Anthropic API
  - [ ] Prompt template for scene classification + OCR
  - [ ] Handle rate limits and retries
- [x] Implement `analyzer.py` with AnalysisResult dataclass
  - [x] Mock backend: generates placeholder captions
  - [x] Output: `analysis/<segment_id>.json`
- [x] Add CLI command `yanhu analyze --session <id> --backend mock`
- [x] Update manifest with `analysis_path` field
- [x] Update composer to use analysis captions (replaces TODO)
- [x] Write unit tests for mock analyzer and analysis integration

---

### Milestone 4: ASR Transcription

**Scope**: Implement audio transcription with optional LLM post-processing.

**Definition of Done**: Each segment has timestamped transcript in `analysis.json`.

**Checklist**:
- [ ] Implement `models/whisper_asr.py` using OpenAI Whisper API (or local whisper.cpp)
- [ ] Implement `asr.py`
  - [ ] Function `transcribe_segment(video_path) -> List[TranscriptEntry]`
  - [ ] Handle segments with no speech (return empty list)
- [ ] (Optional) Implement `asr_postprocess.py` for LLM-based correction
- [ ] Merge ASR results into `analysis.json`
- [ ] Add CLI command `yanhu transcribe <session_id>`
- [ ] Write unit test with known audio sample

---

### Milestone 5: Segment Summarization

**Scope**: Generate natural language descriptions for each segment combining vision and ASR data.

**Definition of Done**: Each segment has `summary.txt` with natural language description.

**Checklist**:
- [ ] Implement `segment_summarizer.py`
  - [ ] Function `summarize_segment(analysis: AnalysisResult) -> str`
  - [ ] Prompt template combining vision + ASR data
- [ ] Add CLI command `yanhu summarize <session_id>`
- [ ] Write test verifying summary is non-empty and in Chinese

---

### Milestone 6: Session Composition

**Scope**: Merge all segment summaries into final session documents.

**Definition of Done**: Session folder contains `overview.md`, `timeline.md`, `highlights.md`.

**Checklist**:
- [x] Implement `composer.py` (skeleton without AI descriptions)
  - [x] Function `compose_overview(manifest) -> str`
  - [x] Function `compose_timeline(manifest) -> str`
  - [x] Function `format_timestamp(seconds) -> HH:MM:SS`
  - [x] Function `compose_highlights(manifest, session_dir, top_k) -> str`
- [x] Add CLI command `yanhu compose --session <id>`
- [x] Generate timeline.md with segment time ranges and frame links
- [x] Generate overview.md with session metadata
- [x] Generate highlights.md with top-k scored segments
- [ ] Fill in AI-generated descriptions (requires M3-M5)
- [x] Write unit tests for timestamp formatting and timeline structure

---

### Milestone 7: Watcher (Optional for MVP)

**Scope**: Automatic file detection and pipeline triggering.

**Definition of Done**: New videos in `raw/` are automatically processed.

**Checklist**:
- [ ] Implement `watcher.py` using watchdog library
- [ ] Filename parser for game detection (pattern matching or user prompt)
- [ ] Trigger full pipeline on new file detection
- [ ] Add systemd/launchd service config for background running
- [ ] Write integration test with temp directory

---

### Milestone 8: Documentation & Polish

**Scope**: Complete user-facing documentation and developer guides.

**Definition of Done**: README updated with usage instructions, demo GIF, and troubleshooting.

**Checklist**:
- [ ] Write installation guide (ffmpeg, Python, API keys)
- [ ] Add usage examples for each CLI command
- [ ] Create sample output files for documentation
- [ ] Add CONTRIBUTING.md with development setup

---

## Risks & Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **ffmpeg not installed** | High | Medium | Check on startup, provide install instructions per OS; bundle static binary option |
| **ffmpeg version incompatibility** | Medium | Low | Pin minimum version (5.0+), test on CI with multiple versions |
| **API rate limits (Claude/OpenAI)** | High | High | Implement exponential backoff; add `--dry-run` mode; support local model fallback |
| **API costs exceed budget** | High | Medium | Add cost estimator before run; support local Whisper; cache results by segment hash |
| **Large video files (>1GB)** | Medium | High | Stream processing; segment early; warn user on large files |
| **Privacy: gameplay may contain personal info** | Medium | Medium | All processing local by default; warn before any cloud API call; add `--local-only` flag |
| **Non-standard video codecs** | Medium | Low | Normalize with ffmpeg transcoding step; support common formats only |
| **Long processing time (>10 min)** | Medium | High | Show progress bar; support resume from failed step; parallel segment processing |
| **Disk space exhaustion** | Low | Low | Warn if <10GB free; add cleanup command for old sessions |
| **Model hallucinations in OCR/ASR** | Medium | Medium | Human review mode; confidence scores in analysis.json; highlight low-confidence segments |

---

## Progress Log

| Date | Milestone | Status | Notes |
|------|-----------|--------|-------|
| 2026-01-20 | M0: Project Scaffolding | Done | CI added; all 6 checklist items complete |
| 2026-01-20 | M1: Video Ingestion & Segmentation | Done | ingest + segment CLI, manifest, 30 unit tests |
| 2026-01-20 | M2: Frame Extraction | Done | extract CLI, 54 unit tests total |
| 2026-01-20 | M6: Compose Skeleton | Done | timeline.md + overview.md (no AI), 78 tests |
| 2026-01-20 | M3: Mock Vision Analysis | Done | analyze CLI, mock backend, 109 tests |
| 2026-01-21 | M6: Highlights | Done | highlights.md with score-based selection |
| - | M3: Vision Analysis | Partial | Mock done; Claude/OpenAI backends pending |
| - | M4: ASR Transcription | Not Started | - |
| - | M5: Segment Summarization | Not Started | - |
| - | M6: Session Composition | Partial | Skeleton done; AI descriptions pending M3-M5 |
| - | M7: Watcher (Optional) | Not Started | Deferred to v0.2 |
| - | M8: Documentation & Polish | Not Started | - |

---

> **Note**: Milestones 0-6 are required for MVP v0.1. Milestone 7 (watcher) can be deferred to v0.2. Each milestone is independently testable and delivers incremental value.
