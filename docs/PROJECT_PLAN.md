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

**Definition of Done**: Each segment has `analysis/<segment_id>.json` with scene classification, OCR, and L1 fields.

**Checklist** (actual implementation path):
- [x] Implement `analyzer.py` with AnalysisResult dataclass
  - [x] Schema: segment_id, scene_type, ocr_text, facts, caption, confidence, model, error
  - [x] L1 fields: scene_label, what_changed, ui_key_text, ui_symbols, ocr_items, hook_detail
  - [x] Mock backend: generates placeholder captions
  - [x] Output: `analysis/<segment_id>.json`
- [x] Implement `claude_client.py` for Claude Vision API
  - [x] Multi-frame analysis (--max-frames configurable)
  - [x] L1 prompt template: scene classification + OCR + facts + what_changed
  - [x] OCR text deduplication and watermark filtering
  - [x] Quote fidelity: preserve verbatim OCR in ocr_items with t_rel and source_frame
  - [x] JSON parse with retry/repair fallback (raw_text field on failure)
  - [x] Backend-aware caching (mock vs claude-* model prefix)
- [x] Add CLI command `yanhu analyze --session <id> --backend mock|claude`
  - [x] Options: --limit, --segments, --dry-run, --force, --max-frames, --detail-level
- [x] Update manifest with `analysis_path` field
- [x] Update composer to use analysis (facts, what_changed, ui_key_text, quote)
- [x] Write unit tests for analyzer, claude_client, and integration
- [x] Verify gate coverage: cache behavior, JSON pollution check, highlights assertions
- [ ] (Refactor optional) Extract `models/base.py` abstract interface for vision backends
- [ ] (Stretch) OpenAI Vision backend

---

### Milestone 4: ASR Transcription

**Scope**: Implement audio transcription with optional LLM post-processing.

**Definition of Done**: Each segment has timestamped transcript (`asr_items`) in `analysis.json`.

**Checklist** (actual implementation path):
- [x] Implement `transcriber.py` with AsrItem dataclass and backend abstraction
  - [x] AsrItem schema: text, t_start, t_end (session-relative timestamps)
  - [x] AsrConfig: device, compute_type, model_size, language, beam_size, vad_filter
  - [x] Mock backend: generates placeholder transcripts
  - [x] WhisperLocalBackend using faster-whisper library
- [x] Add CLI command `yanhu transcribe --session <id> --backend mock|whisper_local`
  - [x] Options: --segments, --force, --model-size, --compute-type, --beam-size, --vad-filter/--no-vad-filter, --language
  - [x] Write asr_items + asr_config + asr_backend to analysis.json
- [x] Timeline shows ASR: `- asr: <first transcript>` or `[无字幕]`
- [x] Write unit tests for transcriber backends and CLI
- [x] Verify gate: asr_items presence assertions
- [ ] (Stretch) OpenAI Whisper API backend
- [ ] (Stretch) Implement `asr_postprocess.py` for LLM-based correction

---

### Milestone 5: Segment Summarization (Quote + Summary Dual-Layer)

**Scope**: Generate structured quote + summary for each segment combining OCR, ASR, and vision analysis.

**Definition of Done**: Each highlight has quote (verbatim original) + summary (objective description) dual-layer output.

**Checklist** (target implementation path):
- [x] OCR/ASR alignment fusion (`aligner.py`)
  - [x] AlignedQuote schema: t, source (ocr/asr/both), ocr, asr fields
  - [x] Time-window matching (default 1.5s) with OCR as anchor
  - [x] Preserve both OCR and ASR text verbatim when source="both"
  - [x] CLI command `yanhu align --session <id> --segments --window --max-quotes`
- [x] Quote selection logic in highlights
  - [x] Priority: aligned_quotes (source=both → "ocr (asr)") > ocr > asr > ui_key_text > ocr_text > facts
  - [x] Heart emoji binding from ui_symbols
- [x] Summary generation in highlights
  - [x] Format: `facts[0] / truncated what_changed` (sentence boundary truncation, max 40 chars)
  - [x] Fallback to caption if no facts
- [x] Highlights output format: `- [HH:MM:SS] <QUOTE> (segment=..., score=...)` + `  - summary: ...`
- [x] Write unit tests for aligner, quote selection, summary truncation
- [x] Verify gate: aligned_quotes assertions, timeline quote line with ASR annotation
- [ ] (Optional) Standalone `yanhu summarize` CLI for batch summary generation
  - Note: Not required for MVP; highlights already provide quote+summary dual-layer output

---

### Milestone 6: Session Composition

**Scope**: Merge all segment analysis into final session documents with AI-generated content.

**Definition of Done**: Session folder contains `overview.md`, `timeline.md`, `highlights.md` with full AI content.

**Checklist** (actual implementation path):
- [x] Implement `composer.py`
  - [x] Function `compose_overview(manifest) -> str`
  - [x] Function `compose_timeline(manifest) -> str` with facts, change, ui, asr, quote lines
  - [x] Function `format_timestamp(seconds) -> HH:MM:SS`
  - [x] Function `compose_highlights(manifest, session_dir, top_k) -> str`
- [x] Add CLI command `yanhu compose --session <id>`
- [x] Generate timeline.md with segment time ranges, frame links, and analysis content
  - [x] Show: facts[0] blockquote, change line, ui line, asr line, quote line
- [x] Generate overview.md with session metadata
- [x] Generate highlights.md with scored segments
  - [x] Scoring algorithm: ui_key_text (+100 base +10/item), facts (+50 base +10/item), caption (+20), ocr_text (+10/item +1/10chars), scene_label weights, change keywords (+5/kw), watermark penalty (-50)
  - [x] Quote-first priority with aligned_quotes support
  - [x] Heart emoji binding from ui_symbols (inserts before "都做过" keyword)
  - [x] Adjacent segment merging (max 2 quotes when merged)
  - [x] Watermark filtering (小红书, @username, etc.)
  - [x] Score-based deduplication by ui_key_text
  - [x] Summary line: `facts[0] / truncated what_changed`
- [x] Write unit tests for timestamp, timeline, highlights, quote selection, heart prefix
- [x] AI-generated descriptions integration
  - [x] Vision analysis: facts, what_changed, ui_key_text, scene_label (M3)
  - [x] ASR transcription: asr_items with timestamps (M4)
  - [x] Quote + Summary dual-layer in highlights (M5)

---

### Milestone 7: Watcher (v0.2 Skeleton)

**Scope**: Automatic file detection and queue management. Pipeline triggering deferred to v0.3.

**Definition of Done**: New videos in `raw/` are detected and queued for later processing. Queue consumer processes jobs sequentially.

**Checklist** (v0.2 skeleton):
- [x] Implement `watcher.py` using watchdog library (optional dependency)
  - [x] VideoHandler: detect new .mp4/.mkv/.mov files
  - [x] QueueJob dataclass: created_at, raw_path, suggested_game, status
  - [x] Queue persistence: append to `sessions/_queue/pending.jsonl`
- [x] Filename parser for game detection (guess_game_from_filename)
- [x] Add CLI command `yanhu watch --raw-dir <path> --queue-dir <path>`
- [x] Queue consumer `run_queue()`
  - [x] Extended QueueJob: game, tag, session_id, error, outputs fields
  - [x] Status transitions: pending → processing → done/failed
  - [x] process_job(): full pipeline (ingest → segment → extract → analyze → transcribe → compose)
  - [x] Conservative params: max-frames=3, max-facts=3, whisper_local base/int8
  - [x] Graceful failure: missing raw_path → status=failed + error message
- [x] Add CLI command `yanhu run-queue --queue-dir --output-dir --limit --dry-run --force`
- [x] Watcher reliability enhancements (M7.2)
  - [x] Dedup: compute_file_key() using path+mtime+size hash
  - [x] WatcherState: persist seen_hashes to state.json
  - [x] Atomic write: state.json via temp file + rename
  - [x] Append + flush for pending.jsonl durability
  - [x] `--once` mode: scan directory once and exit
  - [x] `--interval N` mode: poll every N seconds (no watchdog dependency)
- [x] Multi raw-dir support (M7.3)
  - [x] CLI: `--raw-dir` can be specified multiple times
  - [x] Dedup key includes resolved path (different dirs = different keys)
  - [x] QueueJob.raw_dir field tracks source directory
  - [x] Same file moved to different dir can be re-queued
- [x] Write unit tests (84 watcher tests, 515 total)
- [x] (v0.3) Trigger full pipeline on new file detection (auto-run)
  - [x] CLI params: --auto-run, --auto-run-limit, --auto-run-dry-run, --output-dir
  - [x] scan_once: trigger run_queue after scan if queued > 0
  - [x] start_polling: on_scan_complete callback for batch trigger
  - [x] start_watcher: on_batch_queued callback for per-file trigger
  - [x] Safety: auto-run failures don't stop watcher; errors logged to job
  - [x] Tests: 8 auto-run tests (monkeypatch run_queue, verify limit/dry-run)
  - [x] Docs: RUNBOOK auto-run examples with safety warnings
- [ ] (v0.3) Add systemd/launchd service config for background running
- [ ] (v0.3) Integration test with temp directory and real Observer

---

### Milestone 8: Documentation & Polish

**Scope**: Minimal documentation closure for internal use.

**Definition of Done**: README has quickstart, RUNBOOK has full workflow.

**Checklist** (minimal closure):
- [x] README: 60 秒 Quickstart（依赖 + 6 条命令）
- [x] RUNBOOK: End-to-End Quickstart（ffmpeg testsrc + mock 全流程）
- [x] RUNBOOK: Claude + whisper_local 实战流程（.env、dry-run、参数说明）
- [x] RUNBOOK: Verify gate 常见 FAIL 及修复
- [x] 强调 sessions/ 和 .env 不入 git
- [ ] (Stretch) 创建 CONTRIBUTING.md
- [ ] (Stretch) Demo GIF

---

## Polish Backlog (Stretch)

### OCR Variant Denoise for Highlights (Stretch)

**Goal**: Reduce obvious OCR noise in consumer layer (ui_key_text / aligned_quotes / highlights) WITHOUT modifying evidence.

**Non-negotiables**:
- **Preserve evidence**: `ocr_items` must remain verbatim and unchanged (no deletion, no rewrite)
- **Denoise affects only display fields**: ui_key_text / aligned_quotes / highlights
- **Must be behind a feature flag** (default OFF)

**Verification**:
- Add verify assertions when flag ON:
  - `ocr_items` count unchanged
  - highlights/timeline do not contain raw JSON pollution
  - denoise never alters `ocr_items` text
- Add 3 regression fixtures:
  - Cantonese clip
  - Mandarin clip
  - Game analysis subtitle clip

**Acceptance criteria**:
- Actor clip no longer surfaces "真束条了?" in highlights when flag ON, while `ocr_items` still contains the original noisy variants.

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
| 2026-01-20 | M3: Mock Vision Analysis | Done | analyze CLI, mock backend, 109 tests |
| 2026-01-21 | M3: Claude Vision | Done | claude_client.py, L1 fields, OCR排噪, JSON兜底, verify gate |
| 2026-01-21 | M4: ASR Transcription | Done | transcriber.py, whisper_local backend, asr_items写回, timeline展示 |
| 2026-01-22 | M5: Quote+Summary | Done | aligner.py, aligned_quotes双字段, highlights quote+summary格式 |
| 2026-01-22 | M6: Session Composition | Done | timeline/overview/highlights完整; quote优先, emoji绑定, 合并段限2条, watermark过滤, 431 tests |
| 2026-01-22 | M7: Watcher (v0.2) | Done | M7.1: run-queue; M7.2: dedup+state; M7.3: multi raw-dir; 84 watcher tests, 515 total |
| 2026-01-22 | M8: Documentation | Done | README quickstart, RUNBOOK 全流程+实战+verify gate; 内部使用闭环 |
| 2026-01-22 | Highlights Scoring Fix | Done | Fixed score_segment() to reward facts (+50 base +10/item) and caption (+20); verified all 6 tasks pass including whisper_local |
| 2026-01-22 | M7: Watcher (v0.3) | Done | Auto-run: --auto-run + limit + dry-run; on_scan_complete/on_batch_queued callbacks; 8 auto-run tests; RUNBOOK safety warnings |
| 2026-01-23 | P2.1: Source Observability | Done | SourceMetadata dataclass: source_mode, inodes, link_count, fallback_error; copy_source_video验证hardlink/symlink/copy; yanhu-verify task A; 14 new tests, 550 total |
| 2026-01-23 | P3: Naming Strategy | Done | No hardcoded actor/game guessing; tag = stem__hash8 (避免同前缀混淆); --default-game CLI flag (默认unknown); QueueJob增raw_filename/raw_stem/suggested_tag; 18 P3 tests, 568 total |
| 2026-01-23 | Presets (fast/quality) | Done | PRESETS dict (fast: 3frames/3facts/base/int8, quality: 6frames/5facts/small/float32); RunQueueConfig.resolve_config() 支持覆盖; job.outputs.run_config 记录实际参数; --preset CLI 选项; 15 preset tests, 583 total |
| 2026-01-23 | Adaptive Segment Duration | Done | SEGMENT_STRATEGIES dict (short:5s, medium:15s, long:30s); get_video_duration() via ffprobe; determine_segment_duration() with auto strategy (≤3min→5s, ≤15min→15s, >15min→30s); --segment-strategy/--segment-duration CLI options; process_job() calls determine_segment_duration(); 28 segment tests, 611 total; RUNBOOK section 4d |

---

> **Note**: Milestones 0-6 are required for MVP v0.1. Milestone 7 (watcher) can be deferred to v0.2. Each milestone is independently testable and delivers incremental value.
