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
  - [x] Fallback highlight when no content passes threshold (Step 21)
    - [x] `_create_fallback_highlight()` ALWAYS returns fallback (never None)
    - [x] Uses first segment with analysis if available, else first segment with generic text
    - [x] Fallback quote: aligned_quotes > "Fallback highlight (analysis unavailable)"
    - [x] Relaxed validation: accepts canonical "- [HH:MM:SS]" OR fallback with score=0
    - [x] 9 new tests for fallback creation, missing analysis, and validation
  - [x] Prevent symbols-only highlights (Step 18c)
    - [x] `has_readable_content()` method validates highlight has readable text (not just emoji/punctuation)
    - [x] Filter symbols-only entries before taking top-k in `compose_highlights()`
    - [x] Symbols can contribute to scoring and appear as metadata, but not as standalone highlights
    - [x] 9 new tests for symbols-only prevention and validation
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

### Milestone 9.0: Desktop Distribution MVP (macOS/Windows) — Done

**Scope**: Ship a **standalone desktop distribution** for the existing local Web App (viewer + trigger + upload + progress + sessions).  
No pipeline rewrite, no native GUI redesign—focus on **one-click launch** for non-programmers.

**Definition of Done**: A user can download a zip from GitHub Releases, double‑click a macOS `.app` / Windows `.exe`, the browser opens automatically to `http://127.0.0.1:8787`, and they can drag & drop a video to process and view session outputs—without installing Python or using a terminal.

**Checklist (MVP)**:
- [x] Desktop launcher entrypoint (`yanhu.launcher`) that:
  - [x] Checks `ffmpeg/ffprobe` availability and shows clear install guidance if missing
  - [x] Creates default data dirs on first run: `~/yanhu-sessions/{raw,sessions}`
  - [x] Starts the local server and auto-opens the default browser
- [x] UI safety signals:
  - [x] Visible “Local processing only” banner/header
  - [x] Warning banner when ffmpeg is missing
- [x] Packaging (distribution-first):
  - [x] PyInstaller spec (`yanhu.spec`) builds macOS `.app` and Windows `.exe`
  - [x] Local build scripts (`scripts/build_desktop.sh`, `scripts/build_desktop.bat`)
  - [x] Build docs (`docs/BUILD.md`, `scripts/README.md`)
- [x] Release automation:
  - [x] GitHub Actions workflow builds artifacts on tag push and uploads to GitHub Releases
- [x] Non-programmer docs:
  - [x] README "Non‑Programmer Quickstart" (Chinese + English)
- [x] Desktop UX verification gate:
  - [x] `yanhu verify --desktop-ux` command enforces critical contracts
  - [x] Checks ffprobe discovery (shutil.which + fallback paths)
  - [x] Checks Quit Server hard-stop (os._exit fallback)
  - [x] Checks launcher compatibility (create_app/run_app kwargs)
  - [x] CI integration: runs automatically in GitHub Actions
  - [x] RUNBOOK: "Release Smoke Test" section with manual checklist
- [ ] Code signing / notarization (defer to M9.1)
- [ ] Installer packages (.dmg/.msi) + auto-updater (defer to M9.1)
- [ ] Bundle ffmpeg binaries (license/compliance review; defer to M9.1)
- [ ] Hide console window / tray integration (defer to M9.1)

**Technology Decision (MVP)**:
- Committed to **Distribution-first**: reuse the local Web UI + PyInstaller launcher.
- Optional follow-up: embed the Web UI into a native shell (QtWebEngine/Tauri/Electron) under M9.1+ if needed.

**Security & Privacy (MVP)**:
- Local processing by default; no server upload path.
- Any API keys remain local to the user machine and must never be stored in-repo.


### Milestone 9.1: Desktop App Polish (Post-MVP)

**Scope**: Production-grade enhancements after M9.0 validation. Focus on security, UX polish, and advanced features.

**Checklist (Future)**:
- [ ] **Secure Credential Storage**
  - [ ] macOS: Keychain Access integration
  - [ ] Windows: Credential Manager integration
  - [ ] Migrate from plaintext `api_keys.json` to OS-native secure storage
- [ ] **Advanced Watcher Features**
  - [ ] Add `--once` mode button (scan once and exit)
  - [ ] Add watchdog mode (real-time file events, if library available)
  - [ ] Real-time queue updates (file watcher on `pending.jsonl`)
- [ ] **Cost Estimation**
  - [ ] Pre-run cost estimator: "Estimated API cost: X frames × Y segments = $Z"
  - [ ] Display cost breakdown by preset (fast vs quality)
  - [ ] Historical cost tracking per session
- [ ] **System Integration**
  - [ ] Tray icon with Start/Stop watcher shortcuts
  - [ ] Auto-start on login (optional, user-configurable)
  - [ ] Desktop notifications for job completion/failure
- [ ] **Packaging & Distribution**
  - [ ] macOS: Code signing and notarization
  - [ ] Windows: MSI installer with Add/Remove Programs support
  - [ ] Auto-update mechanism (check for new releases)
  - [ ] Bundle ffmpeg binary (optional, with license compliance)
- [ ] **Configuration Management (Advanced)**
  - [ ] Preset editor: customize fast/quality parameters
  - [ ] "Reset to Defaults" button for all settings
  - [ ] Import/Export config for team sharing
  - [ ] Preset preview: show expected max-frames, model-size, etc.
- [ ] **Error Handling (Enhanced)**
  - [ ] Link to full error log file (open in editor)
  - [ ] Error grouping by type (JSON errors, file not found, API errors)
  - [ ] Bulk retry failed jobs
- [ ] **UI Migration (Optional)**
  - [ ] Migrate to **Option B: Tauri/Electron** for modern UI
  - [ ] React/Vue/Svelte frontend with Python worker backend
  - [ ] Reuse all business logic from M9.0 (only UI layer replaced)

**Migration Path**: M9.0 validates user demand with minimal effort. M9.1 polishes UX and security. Option B (Tauri/Electron) migration is optional and only pursued if M9.0 sees adoption.

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

### Multimodal Backend Options: Gemini 3 Pro + Qwen3 (Cost-Effective Alternatives)

**Motivation**:
- **Gemini 3 Pro** shows strong native multimodal capabilities (ASR + OCR + summary + highlights in one shot) with competitive pricing
- **Claude Vision** is costly (~$3/1000 images) and engineering-heavy (separate ASR, multiple API calls per segment)
- **Qwen3** offers open-source, local-first option for privacy-sensitive deployments
- Goal: Reduce per-session cost by 50-80% while maintaining quality, enable users to choose backend based on budget/privacy needs

**Scope (Future Work)**:

1. **Analyze Backend Registry**
   - Add `analyze_backend` registry similar to ASR registry: `{claude, gemini_3pro, qwen3, mock}`
   - Each backend implements unified interface: `analyze_segment(frames, prompts) -> AnalysisResult`
   - Backend-specific configuration: API keys, model versions, regional endpoints
   - Graceful degradation: fallback to mock if backend unavailable

2. **Unified Multimodal Output Schema**
   - Define L1 fields (facts, what_changed, scene_label, ui_key_text, caption) as contract
   - Add `ui_symbol_items` (OCR with coordinates) for UI text extraction
   - Add `aligned_quotes` (quote + summary) for highlights generation
   - Schema validation: ensure all backends return compatible JSON structure
   - Version schema to support future extensions without breaking changes

3. **CLI + UI Wiring**
   - CLI: `--analyze-backend {claude|gemini_3pro|qwen3|mock}` flag (default: current behavior = claude)
   - App UI: Dropdown selector in job creation form (same as ASR model dropdown)
   - Store `analyze_backend` in `QueueJob` and `manifest.json` for reproducibility
   - Display backend used in session overview and job detail pages

4. **Cost Guardrails**
   - **Per-run budget cap**: `--max-cost-dollars N` flag to abort if estimate exceeds N
   - **Max calls/frames**: `--analyze-max-segments N` to limit API calls (similar to transcribe limits)
   - **Dry-run estimate**: `yanhu estimate --session <id>` shows cost breakdown before processing
   - **Response caching**: Cache API responses by `hash(frames_content + prompt)` to avoid redundant calls on re-runs
   - Cost tracking: Add `cost_estimate` and `actual_cost` fields to manifest and job JSON

5. **Evaluation & Quality Comparison**
   - **Side-by-side comparison tool**: Run same session through multiple backends, diff outputs
   - **Quality metrics**: Precision/recall on known test fixtures (e.g., ❤️ emoji binding cases, Cantonese ASR accuracy)
   - **Benchmark suite**: 5-10 representative sessions (game clips, actor clips, tutorial videos) with ground truth labels
   - **Cost vs Quality matrix**: Document tradeoffs (e.g., "Gemini 3 Pro: 60% cost, 90% quality vs Claude")
   - Add regression tests: ensure emoji binding, watermark filtering, quote alignment work across all backends

**Checklist (Unchecked)**:
- [ ] **Backend Registry**
  - [ ] Define `AnalyzeBackend` abstract interface with `analyze_segment()` method
  - [ ] Implement `GeminiProBackend` with Gemini 3 Pro API integration
  - [ ] Implement `Qwen3Backend` with local/API options (TBD: Qwen3 API endpoint or local model)
  - [ ] Update `analyze_session()` to accept `backend` parameter and dispatch to registry
  - [ ] Add backend validation and error handling (API key missing, rate limits, timeouts)
- [ ] **Unified Schema**
  - [ ] Document output schema v2 with all required L1 fields + ui_symbol_items + aligned_quotes
  - [ ] Add schema validation function: `validate_analysis_result(result, backend_name)`
  - [ ] Write converter functions for backend-specific responses → unified schema
  - [ ] Add tests: parse real API responses from each backend, assert schema compliance
- [ ] **CLI + UI Integration**
  - [ ] Add `--analyze-backend` flag to `yanhu analyze` command
  - [ ] Add backend dropdown to job creation form in app UI (default: claude)
  - [ ] Store `analyze_backend` in QueueJob dataclass and manifest.json
  - [ ] Display "Analyzed with: Gemini 3 Pro" in session overview metadata
  - [ ] Update app UI to show backend-specific warnings (e.g., "Gemini: beta quality")
- [ ] **Cost Guardrails**
  - [ ] Implement `estimate_cost(backend, num_segments, frames_per_segment) -> dollars`
  - [ ] Add `--max-cost-dollars` flag with pre-run check and abort if exceeded
  - [ ] Add `--analyze-max-segments` limit (similar to `--transcribe-limit`)
  - [ ] Implement response caching: `cache/<backend>/<hash>.json` for API responses
  - [ ] Add cost tracking fields to manifest: `estimated_cost`, `actual_cost`, `cost_breakdown`
  - [ ] Display cost summary in job detail page and session overview
- [ ] **Evaluation Suite**
  - [ ] Create benchmark fixture: 5 sessions with ground truth labels (facts, ui_text, quotes)
  - [ ] Implement `yanhu compare --session <id> --backends claude,gemini_3pro,qwen3`
  - [ ] Generate diff report: show side-by-side outputs, highlight mismatches
  - [ ] Add quality metrics: emoji binding accuracy, watermark filtering recall, quote alignment F1
  - [ ] Document cost vs quality tradeoffs in `docs/BACKEND_COMPARISON.md`
  - [ ] Add regression tests: run benchmark suite on CI, assert no quality degradation

**Acceptance Criteria (Definition of Done)**:
- User can run `yanhu analyze --analyze-backend gemini_3pro <session>` and get valid outputs
- App UI shows backend dropdown, stores choice in manifest, displays in overview
- Cost estimator shows accurate breakdown: "Estimated: $0.50 (Gemini 3 Pro, 10 segments × 6 frames)"
- Side-by-side comparison report shows Gemini 3 Pro matches Claude on ❤️ emoji binding test case
- Benchmark suite passes with ≥85% accuracy on all backends (facts extraction, ui_text, quotes)
- Cost guardrails prevent runaway spending: `--max-cost-dollars 5` aborts if estimate exceeds $5
- Caching reduces repeat API calls: re-running same session with same backend uses cached responses
- Documentation includes migration guide: "How to switch from Claude to Gemini 3 Pro"

**Does NOT Include (Out of Scope)**:
- Multi-backend ensemble (running multiple backends and merging outputs)
- Real-time streaming analysis (still batch-only per segment)
- Custom prompt templates per backend (uses same prompts for now)
- Automatic backend selection based on content type (user must choose explicitly)

---

### OCR Decoupling + Vibe Layer (Gemini/Qwen-Friendly Architecture)

**Motivation**:
- **Current architecture is expensive and unreliable**: Claude Vision performs both OCR extraction and narrative analysis in one call, making it costly (~$3/1000 images) without guaranteeing better OCR accuracy than specialized tools
- **Evidence stability critical**: ASR and OCR should be verbatim, timestamped, and immutable; current mixing of extraction + interpretation risks evidence contamination
- **Gemini/Qwen inference characteristics**: Gemini 3 Pro provides strong narrative summaries and "vibe" capture but may infer/hallucinate details; these should NOT overwrite evidence-layer OCR
- **Cost control requires separation**: Cannot optimize costs while OCR and analysis are bundled; need to choose cheap OCR + optional expensive analysis
- **Verification gate depends on evidence**: Current verify gate checks evidence fields (ocr_items, asr_items), which should remain deterministic regardless of analysis backend

**Proposed Architecture**:

**Two-Layer Pipeline**:

1. **Evidence Layer (Strict, Deterministic)**:
   - **Purpose**: Extract verbatim text, timestamps, frame anchors
   - **Outputs**: `ocr_items` (text + confidence + source_frame), `asr_items` (text + t_start + t_end)
   - **Backends**:
     - `ocr_backend: {open_ocr, claude_vision, gemini_ocr, qwen_ocr}`
     - `asr_backend: {whisper_local, mock}` (already exists)
   - **Default**: `open_ocr` (PaddleOCR or Tesseract) for cost-free, deterministic extraction
   - **Schema**: Confidence scores mandatory; no inference allowed (e.g., cannot add punctuation OCR didn't see)
   - **Immutable**: Evidence layer outputs never modified by Vibe Layer

2. **Vibe Layer (Interpretation, Inference-Tagged)**:
   - **Purpose**: Narrative summary, highlights, sentiment, game state inference
   - **Outputs**: `vibe_summary`, `highlight_moments`, `inferred_context` (all marked as "interpretation")
   - **Backends**: `analyze_backend: {claude, gemini_3pro, qwen3, mock}`
   - **Evidence anchors**: Every vibe claim must reference source evidence (e.g., "inferred from OCR 'daddy也叫了' at t=10.0")
   - **Explicit inference tagging**: UI displays "🔮 Inferred" label for all Vibe Layer content
   - **Optional**: Users can skip Vibe Layer entirely for privacy/cost (`--evidence-only` mode)

**CLI + UI Wiring**:
- `--ocr-backend {open_ocr|claude_vision|gemini_ocr|qwen_ocr}` (default: `open_ocr`)
- `--analyze-backend {claude|gemini_3pro|qwen3|none}` (default: `none` for evidence-only)
- `--evidence-only` flag: skip Vibe Layer, only extract OCR + ASR
- UI: Separate tabs for "Evidence" (OCR/ASR verbatim) and "Vibe" (narrative summaries with inference labels)

**Checklist (Unchecked)**:
- [ ] **OCR Backend Registry**
  - [ ] Define `OcrBackend` abstract interface: `extract_ocr(frames) -> list[OcrItem]`
  - [ ] Implement `OpenOcrBackend` using PaddleOCR or Tesseract (default, local, free)
  - [ ] Add confidence field to OcrItem schema (required for all backends)
  - [ ] Migrate existing `claude_vision` to dual mode: can serve as `ocr_backend` OR `analyze_backend`
  - [ ] Add `--ocr-backend` CLI flag and job configuration storage
  - [ ] Write tests: parse OCR from each backend, assert schema compliance (text, confidence, source_frame)
- [ ] **Evidence Layer Schema**
  - [ ] Document Evidence Layer contract: ocr_items + asr_items (verbatim, no inference)
  - [ ] Add `evidence.json` output: stores only OCR + ASR, no analysis/vibe content
  - [ ] Enforce immutability: Vibe Layer cannot modify evidence.json
  - [ ] Update verify gate to check only Evidence Layer outputs (ignore Vibe Layer)
  - [ ] Add "strict mode" verification: assert no inference in ocr_items (e.g., no added punctuation)
- [ ] **Vibe Layer Architecture**
  - [ ] Define `vibe_summary.json` schema: narrative, highlights, inferred_context, evidence_anchors
  - [ ] Add inference tagging: every inferred claim links to source evidence (ocr_item id or asr_item timestamp)
  - [ ] Implement `--evidence-only` mode: skip Vibe Layer entirely, only extract OCR + ASR
  - [ ] Add `--analyze-backend none` support: same as evidence-only mode
  - [ ] Update composer to generate timeline/highlights from Evidence Layer OR Vibe Layer (user choice)
- [ ] **UI Updates**
  - [ ] Add "Evidence" tab: shows verbatim OCR + ASR with confidence scores and frame links
  - [ ] Add "Vibe" tab: shows narrative summaries with 🔮 inference labels and evidence anchors
  - [ ] Display OCR confidence scores in Evidence tab (e.g., "都做过 (confidence: 0.95)")
  - [ ] Show evidence anchors in Vibe tab (e.g., "Inferred game state: victory [from OCR 'WIN' at frame_0042]")
  - [ ] Add toggle: "Evidence Only" mode hides Vibe tab and shows warning if analyze_backend != none
- [ ] **Benchmark Suite**
  - [ ] Create test fixture: actor clip with "❤️都做过" moment (tests emoji + OCR binding)
  - [ ] Create test fixture: Cantonese game clip (tests ASR fidelity for non-Mandarin)
  - [ ] Create test fixture: low-confidence OCR scenario (blurry text, tests confidence scoring)
  - [ ] Implement benchmark script: `yanhu benchmark --backends open_ocr,claude_vision --sessions <fixture_ids>`
  - [ ] Generate cost matrix: compare cost per session across backend combinations (OCR × Analyze)
  - [ ] Quality metrics: OCR accuracy (precision/recall vs ground truth), ❤️ binding success rate, Cantonese ASR WER
  - [ ] Document tradeoffs: "open_ocr + gemini_3pro: $0.20/session, 85% quality vs claude_vision: $3.50/session, 90% quality"
- [ ] **Cost Guardrails**
  - [ ] Implement per-session budget cap: `--max-cost-dollars N` aborts if Evidence + Vibe estimate exceeds N
  - [ ] Add separate cost tracking: `evidence_cost` and `vibe_cost` in manifest.json
  - [ ] Implement response caching for both layers: `cache/ocr/<hash>.json` and `cache/vibe/<hash>.json`
  - [ ] Add `yanhu estimate --session <id> --breakdown` to show Evidence vs Vibe cost split
  - [ ] Display cost savings when using evidence-only mode: "Evidence-only: $0.00 (saved $3.50 on Vibe Layer)"

**Definition of Done**:
- User can run `yanhu analyze --ocr-backend open_ocr --analyze-backend none <video>` for free, local-only evidence extraction
- Verify gate passes on evidence-only sessions (no Vibe Layer required for validation)
- UI clearly separates Evidence tab (verbatim, no 🔮 labels) from Vibe tab (summaries with 🔮 inference markers)
- Every vibe claim in `vibe_summary.json` has `evidence_anchor` field linking to source ocr_item or asr_item
- Benchmark suite shows ≥50% cost reduction: "open_ocr + gemini_3pro" vs "claude_vision only" (measured on 5+ sessions)
- ❤️都做过 binding test passes with `open_ocr` backend (emoji detection works with non-Claude OCR)
- Cantonese ASR fixture shows no degradation when switching from Claude Vision to open_ocr (ASR quality independent of OCR backend)
- Strict mode verify gate asserts: no inference in ocr_items (e.g., `assert all(item.source == 'ocr_raw' for item in ocr_items)`)
- Evidence Layer outputs (`evidence.json`, `ocr_items`, `asr_items`) remain immutable across re-runs with different Vibe backends

**Does NOT Include (Out of Scope)**:
- Multi-OCR ensemble (running multiple OCR backends and merging results)
- Real-time OCR streaming (still batch-only per segment)
- Custom OCR training or fine-tuning (uses off-the-shelf models only)
- Automatic OCR backend selection based on image quality (user must choose explicitly)
- Vibe Layer A/B testing or automatic backend routing

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
| 2026-01-23 | Transcribe Limits (Partial-by-Limit) | Done | --transcribe-limit N / --transcribe-max-seconds S flags; transcribe first N segments (not skip all); manifest.transcribe_coverage stores {processed, total, skipped_limit}; overview.md shows "⚠️ PARTIAL SESSION" marker with coverage stats; compose succeeds with missing transcripts; 5 tests, 643 total |
| 2026-01-23 | Progress Heartbeat (Long-Video UX) | Done | progress.json at <session_dir>/outputs/progress.json; atomic writes; schema: {session_id, stage, done, total, elapsed_sec, eta_sec, updated_at (UTC), coverage?}; ProgressTracker class; updates during transcribe (per segment); console prints concise progress every 5 segments; finalized to "compose" then "done"; handles edge cases (total=0, limit); 10 tests, 653 total |
| 2026-01-23 | Verify Gate Strengthening | Done | yanhu.verify module with validate_outputs(); validates progress.json exists and is valid (required fields, type checks, done≤total, stage∈{transcribe,compose,done}, stage=done→done==total, ISO-8601 updated_at); validates partial-by-limit consistency (manifest.transcribe_coverage→overview PARTIAL marker+stats, progress.json coverage matches manifest); 22 tests, 675 total |
| 2026-01-23 | App v0 (Viewer) | Done | CLI: `yanhu app --sessions-dir <path> --host 127.0.0.1 --port 8787`; Routes: GET / (list sessions, newest first), GET /s/{id} (tabs: overview/highlights/timeline/manifest), GET /s/{id}/progress (JSON, 404 if missing), GET /s/{id}/manifest (JSON); UI polls /progress every 1s when stage≠done; markdown rendered safely; minimal Flask+markdown deps; Does NOT support: upload/trigger pipeline; 11 tests, 686 total |
| 2026-01-23 | App v1 (Trigger) | Done | Extended CLI: `yanhu app --raw-dir <path> --worker/--no-worker --allow-any-path --preset fast`; New Job form on home page (raw_path, game, transcribe_limit, transcribe_max_seconds); POST /api/jobs validates path & enqueues; BackgroundWorker processes jobs (single-threaded, polls queue every 2s, reuses process_job); job status: pending→processing→done/failed; sessions & jobs unified list; Does NOT support: cancel jobs, multi-worker, upload (user provides path); 7 tests, 693 total |
| 2026-01-23 | App v1.1 (Observability + Cancel) | Done | Per-job JSON files in _queue/jobs/<job_id>.json (atomic writes); job_id auto-generated (job_YYYYMMDD_HHMMSS_hash8); Routes: GET /jobs/<job_id> (HTML detail page with status/metadata/progress/cancel button), GET /api/jobs/<job_id> (JSON), POST /api/jobs/<job_id>/cancel (pending→cancelled, processing→cancel_requested); Worker skips cancelled jobs, checks cancel_requested before/after processing; job status state machine: pending→processing→done/failed/cancelled, cancel_requested→cancelled; home page links to job detail; Cancel semantics: best-effort (pending=immediate skip, processing=after current step completes); 7 new tests, 699 total |
| 2026-01-23 | App v1.2 (Upload/Drag&Drop) | Done | POST /api/uploads (multipart/form-data) accepts file + optional game/preset/transcribe_limit/transcribe_max_seconds; saves to --raw-dir with unique name (YYYYMMDD_HHMMSS_hash8_sanitized_filename); validates extension (.mp4/.mov/.mkv/.webm); atomic write (tmp + rename); creates job automatically; redirects to /jobs/<job_id>; UI: drag&drop area + file picker on home page; MAX_CONTENT_LENGTH=5GB (configurable); path traversal sanitized (os.path.basename); 413 error for oversized files; uploaded files deletable via cancel; 6 new tests, 705 total |
| 2026-01-23 | App v1.3 (Media Preflight) | Done | probe_media() via ffprobe JSON output extracts: duration_sec, file_size_bytes, container, video_codec, audio_codec, width, height, fps, bitrate_kbps; graceful degradation if ffprobe unavailable (file_size only); MediaInfo dataclass; calculate_job_estimates() computes estimated_segments (ceil(duration/segment_duration)) and estimated_runtime_sec (segments * sec_per_segment + overhead); job.media/estimated_segments/estimated_runtime_sec stored in per-job JSON; UI displays "Media Info" and "Estimates" tables on job detail page with formatted values; probing happens after upload and existing-file job creation; does NOT affect pipeline behavior; 12 new tests (4 app + 8 watcher), 717 total |
| 2026-01-23 | App v1.4 (ETA Calibration + Metrics) | Done | MetricsStore in _metrics.json persists observed throughput (seg/s) per preset+segment_duration_bucket (auto_short/medium/long); BackgroundWorker._update_metrics() updates after job done using transcribe_processed/elapsed_sec; EMA smoothing (alpha=0.2): avg_rate_ema = 0.2*observed + 0.8*old; calculate_job_estimates() uses metrics when available (runtime = overhead + segments/metrics_rate), falls back to heuristic; UI JavaScript computes calibrated ETA: rate_ema = 0.2*current_rate + 0.8*rate_ema, eta = (total-done)/rate_ema; displays "Observed rate", "Calibrated ETA", "Est. finish time"; metrics are local-only advisory data; does NOT change pipeline behavior; 19 new tests (2 app + 3 watcher + 14 metrics), 736 total |
| 2026-01-23 | Multi-model ASR v0 | Done | asr_registry.py defines ASR_MODELS (mock, whisper_local) with validate_asr_models(); job.asr_models (comma-separated) accepted in UI forms and validated; transcribe_session(asr_models=[...]) runs models sequentially per segment; per-model outputs saved to outputs/asr/<model_key>/transcript.json (list of segment results); primary model (first in list) also saved to analysis/ for backward compat; manifest.asr_models records models run; UI "Transcripts" tab: GET /s/<session_id>/transcripts endpoint, model selector buttons, per-segment display with text/timestamps; best-effort error handling (one model fails → continue others); compose uses primary model only (v0 limitation); 8 new tests (6 registry + 5 transcriber), 749 total; Does NOT: implement qwen3 ASR, add side-by-side diff view, run models in parallel |
| 2026-01-23 | M9.0: Desktop Distribution MVP | Done | launcher.py desktop entrypoint: starts Flask app, ensures ~/yanhu-sessions/{sessions,raw} dirs exist, auto-opens browser to http://127.0.0.1:8787, checks ffmpeg availability and shows warning banner if missing; PyInstaller packaging: yanhu.spec builds macOS .app and Windows .exe (no code signing/installer for MVP); UI footer shows "🔒 Local processing only"; ffmpeg warning banner with install instructions if not available; GitHub Actions workflow builds macOS/Windows artifacts on tag push; pyproject.toml adds [build] optional deps (pyinstaller), yanhu-desktop entry point; scripts/build_desktop.sh/.bat for local builds; docs/BUILD.md + RELEASE_NOTES_v0.1.0.md + SMOKE_TEST_CHECKLIST.md; 6 new launcher tests, 761 total; Does NOT: redesign UI, add code signing, create installer, bundle ffmpeg; Distribution-first approach: reuses existing Web UI rather than building native GUI |
| 2026-01-23 | Step 13.8: Launcher Compatibility | Done | run_app() accepts debug: bool \| None = None for backward compatibility; filter_kwargs_by_signature() defensive kwarg filtering in launcher prevents crashes from signature mismatches; logs warnings when dropping unexpected kwargs; applied to create_app() and run_app() calls; 5 new tests verify debug parameter acceptance, kwarg filtering, and full launcher pattern; 769 tests total; prevents packaged launcher crashes when calling app functions |
| 2026-01-23 | Step 14: ASR Dropdown + Device Selection | Done | Replaced checkbox multi-select with single-model dropdown for ASR model selection; defaults to whisper_local (not mock); added conditional Whisper Device dropdown (CPU/GPU) with JavaScript toggle; CPU mode uses int8 quantization, GPU/CUDA uses float16; QueueJob.whisper_device field stores device preference; BackgroundWorker applies device settings to run_config and transcribe_session; device parameter passed to WhisperLocalBackend constructor; 4 new tests verify dropdown selection, CPU/GPU device storage, and UI rendering; 773 tests total; Does NOT: implement watch integration, change backend registry logic |
| 2026-01-23 | Bugfix: Timeline Frame Links | Done | Fixed 404 errors when clicking frame links in timeline.md; added Flask route /s/<session_id>/frames/<part_id>/<filename> to serve frame images; modified format_frames_list() to generate web-accessible URLs with session_id; implemented path traversal protection (regex validation + resolve() check); 5 new tests verify frame serving, 404 handling, and security; 778 tests total; Does NOT: change frame extraction logic, affect other routes |
| 2026-01-23 | Feature: Analysis Tab | Done | Added Analysis tab to session view for browsing per-part analysis JSON files; GET /s/<session_id>/analysis returns list of parts with summary (scene_label, what_changed, ui_key_text, counts); GET /s/<session_id>/analysis/<part_id> returns raw JSON; UI displays parts with preview and collapsible Raw JSON toggle; implemented security: regex validation for part_id (^part_\\d{4}$), path traversal protection via resolve() check, graceful 404 handling; 6 new tests verify list endpoint, JSON endpoint, invalid part_id blocking, missing files, tab rendering; 784 tests total; Does NOT: change analysis generation, modify pipeline behavior |
| 2026-01-23 | Feature: Session Navigation UX | Done | Implemented URL hash persistence for active tab state using format #tab=<name>; tabs restore on page refresh/back/forward via hashchange listener; added patchFrameLinks() to set target="_blank" and rel="noopener noreferrer" on all frame image links for new-tab opening; getActiveTabFromHash() parses hash, activateTabFromHash() restores tab state on DOMContentLoaded; showTab() updated to accept skipHashUpdate parameter to prevent loops; 4 new tests verify JavaScript functions present and hash navigation behavior; fixed invalid escape sequence deprecation warning in regex (\\w); 784 tests total; Does NOT: change backend routes, affect frame serving logic |
| 2026-01-24 | Bugfix: Overview TODO Placeholders | Done | Replaced TODO placeholders in Overview with deterministic summaries from existing outputs (no LLM calls); _extract_highlights_summaries() parses highlights.md summary bullets (priority 1), _extract_timeline_snippets() falls back to timeline.md facts (priority 2), neutral "No summary available yet." if nothing exists; _generate_overview_outcome() returns "Partial session (limited transcription)." if transcribe_coverage exists, else "Session processed successfully."; compose_overview() now accepts optional session_dir parameter; 6 new tests verify: highlights extraction, timeline fallback, neutral message, partial outcome, success outcome, max_items limit; 794 tests total; Does NOT: call external LLMs, change pipeline logic, infer win/loss without explicit field |
| 2026-01-24 | Bugfix: Heart Emoji Detection (Unicode Variants) | Done | Enhanced _has_heart_symbol() to detect all heart emoji Unicode variants: ❤️/❤ (U+2764 with/without VS16), colored hearts (💛💙💚💜🖤🤍🤎), broken heart (💔), heart suit (♥️/♥); added codepoint-based detection for robustness across Unicode normalization; 1 new comprehensive test with 17 variant assertions; verified working in session 2026-01-23_05-28-49_unknown_actor_clip__b999e892/part_0002 (fast preset + whisper_local + CPU: ❤️ at t_rel=8.0, bound to "都做过" correctly); 795 tests total; Does NOT: change pipeline architecture, modify symbol binding logic |
| 2026-01-24 | Evidence: Extract All Emojis → ui_symbol_items | Done | Implemented evidence-layer emoji extraction using Python emoji>=2.0 library; added extract_emojis_from_ocr() in analyzer.py to scan OCR text and emit UiSymbolItem with type="emoji", name=canonical (e.g., "red_heart"), raw glyph preserved (including VS16), source_frame anchor, optional source_text snippet; deduplicates within same frame; extended UiSymbolItem schema with optional fields (type, name, source_text) maintaining backward compatibility; integrated into ClaudeAnalyzer.analyze_segment() after Claude response processing; 11 new comprehensive tests cover: VS16 variants, colored hearts, multiple emojis, deduplication, skin tone modifiers, flags, source text capture; fixes "❤️都做过" class regressions by construction; 806 tests total; Does NOT: implement meaning inference (Vibe layer deferred), change pipeline architecture; meaning interpretation explicitly deferred |
| 2026-01-24 | Binding: Emoji ui_symbol_items → Timeline/Highlights | Done | Implemented time/frame-aligned emoji binding in timeline.md and highlights.md output; added get_segment_symbols() in composer.py to extract ui_symbol_items for segment with frame URL generation (/s/<session_id>/frames/<part_id>/<filename>); timeline displays "**Symbols**: [emoji](frame_url)" line after Frames section; highlights displays "- symbols: [emoji](frame_url)" line after summary (indented); merged highlights combine symbols from both segments; deduplicates symbols by (emoji, source_frame) within segment; 7 new tests verify: timeline symbols line, highlights symbols line, no symbols when empty, multiple emojis, merged segment symbol combining, correct URL format; verified with session 2026-01-23_05-28-49_unknown_actor_clip__b999e892/part_0002 (❤️ at frame_0004.jpg bound correctly); 813 tests total; Does NOT: add meaning inference, change OCR/ASR/quote text (evidence verbatim), use keyword special-casing (time/frame alignment only) |
| 2026-01-24 | Precision: Emoji Binding with source_part_id + ASR Context (UPDATED: Fixed timebase bug) | Done | Fixed emoji binding precision by anchoring symbols to part_id and displaying nearest ASR text with correct time-based matching; extended UiSymbolItem with source_part_id field for unambiguous frame binding; modified extract_emojis_from_ocr() to accept part_id parameter and set source_part_id; updated ClaudeAnalyzer.analyze_segment() to pass segment.id; enhanced get_segment_symbols() to filter by source_part_id (with backward compat fallback); **FIXED timebase bug**: implemented proper time-based ASR matching in _find_nearest_asr_text() using segment-relative time base (symbol.t_rel is segment-relative 0..duration, ASR t_start/t_end are absolute/session-relative, converted by subtracting segment.start_time); matches by midpoint distance: mid=(t_start+t_end)/2, finds minimal |symbol_t_rel - mid|; timeline/highlights display format: "[emoji](frame_url) (near: 'ASR text')" with 30-char truncation; added 9 new tests: source_part_id set when provided, None when not provided, timeline filtering, highlights filtering, timeline/highlights ASR context, nearest binding by midpoint (t_rel=3.7→"愛都做了" mid=3.70), early symbol binding (t_rel=0.9→first ASR mid=0.82), realistic integration (t_rel=3.0→"愛都做了" not first sentence); 822 tests total; Does NOT: change evidence layer verbatim requirement |
| 2026-01-24 | Bugfix: ffprobe Discovery for Packaged Apps | Done | Fixed ffprobe discovery for packaged macOS .app (no shell PATH available); implemented find_ffprobe() and find_ffmpeg() in ffmpeg_utils.py with fallback to common absolute paths (/opt/homebrew/bin/ffprobe, /usr/local/bin/ffprobe, /usr/bin/ffprobe); updated get_video_duration(), probe_media(), and check_ffmpeg_availability() to use new functions; app.py initializes app.config["ffprobe_path"] at startup; UI shows warning banner when ffprobe not found; job submission (POST /api/jobs) and upload (POST /api/uploads) reject with 400 error when ffprobe unavailable; upload/job forms disabled in UI when ffprobe_available=False; 5 new tests for find_ffprobe() behavior (which() success, fallback paths, not found) + 3 launcher tests updated to mock Path.exists(); 832 tests total; Does NOT: bundle ffmpeg in packaged app, change Windows behavior (relies on PATH for now) |
| 2026-01-24 | Feature: Quit Server Button + Shutdown Endpoint | Done | Added non-programmer-friendly Quit Server control for desktop launcher; UI header includes red "Quit Server" button in top-right; implemented POST /api/shutdown endpoint with security: requires valid per-launch token (secrets.token_urlsafe(32) stored in app.config["shutdown_token"]), only allows requests from 127.0.0.1/localhost/::1, schedules termination via Timer(0.3, terminate) where terminate() tries werkzeug shutdown first then os._exit(0); captures werkzeug.server.shutdown from request context before Timer closure to avoid context errors; shutdown_token embedded in page HTML via Jinja2 template for JavaScript access; JavaScript quitServer() function shows "Server stopped. You can close this tab." message; 5 new tests: shutdown requires token, succeeds with valid token and schedules Timer, terminate() calls os._exit(0), rejects non-local requests, Quit button renders cleanly; 832 tests total; Does NOT: add multi-user session management, persist tokens across restarts |
| 2026-01-24 | Hotfix: Reliable Process Termination | Done | Fixed "Quit Server" to actually terminate process reliably in packaged/dev environments; terminate() function tries werkzeug shutdown (dev server) then os._exit(0) as final fallback after 300ms delay; captures werkzeug_shutdown from request.environ before creating Timer closure (avoids "Working outside of request context" errors); tests monkeypatch os._exit to prevent test suite exits; UX message updated to "Server stopped. You can close this tab."; removed redundant test that was breaking Flask context management; 5 tests passing (shutdown validation, termination function, non-local rejection, token requirement, clean rendering); 832 tests total; Process termination now reliable on both dev server and packaged builds |
| 2026-01-24 | Desktop UX Verification Gate | Done | Added `yanhu verify --desktop-ux` command to enforce critical non-programmer contracts before release; verifies: (A) ffprobe discovery robustness (shutil.which + /opt/homebrew/bin, /usr/local/bin fallback paths for packaged apps), (B) Quit Server endpoint with os._exit(0) hard-stop, (C) launcher compatibility (create_app accepts jobs_dir + str paths, run_app accepts debug kwarg); implemented verify_desktop_ux() in verify.py with source code inspection; 18 new tests in test_verify_desktop_ux.py covering all checks + monkeypatched negative cases; CI integration: added step to .github/workflows/ci.yml; RUNBOOK: added "Release Smoke Test" section with gate + manual checklist; PROJECT_PLAN: added M9.0 checklist items; 852 tests total; Any regression (ffprobe PATH, quit not exiting, kwargs mismatch) now fails CI before release |
| 2026-01-24 | Backlog: Multimodal Backend Options | TODO Added | Added TODO for Gemini 3 Pro + Qwen3 multimodal backends as cost-effective alternatives to Claude Vision; see detailed milestone below |
| 2026-01-24 | Backlog: OCR Decoupling + Vibe Layer | TODO Added | Added TODO for two-layer architecture separating Evidence Layer (strict OCR+ASR verbatim) from Vibe Layer (inference-tagged summaries); addresses Claude Vision cost/reliability issues and enables Gemini/Qwen-friendly pipelines; see detailed milestone below |
| 2026-01-24 | Step 21: Highlights Fallback + Validation | Done | Fixed job failure when no highlights pass threshold OR analysis missing; _create_fallback_highlight() ALWAYS returns fallback (never None): uses first segment with analysis if available, else first segment with generic text "Fallback highlight (analysis unavailable)"; fallback has score=0; relaxed validate_outputs() to accept either canonical "- [HH:MM:SS]" format OR fallback marker with score=0; removed "_No highlights available. Run analysis first._" placeholder (replaced with deterministic fallback); updated test_highlights_empty_when_no_analysis and test_process_job_validation_failure_marks_failed to expect success with fallback; 9 new tests in test_highlights_fallback.py verify: fallback creation, format matching, aligned quote usage, missing analysis handling, validation acceptance; 869 tests total; Does NOT: change scoring algorithm, pipeline stages beyond compose/verify |
| 2026-01-24 | Step 18c: Prevent Symbols-Only Highlights | Done | Prevent symbols-only highlights (e.g., "[00:00:13] ❤️" with no readable text); added has_readable_content() method to HighlightEntry class to validate readable text (strips emoji/punctuation/whitespace); modified compose_highlights() to filter symbols-only entries before taking top-k; symbols can still contribute to scoring and appear as metadata, but cannot create standalone highlights without readable evidence; updated test_per_ocr_symbol_binding.py to match new behavior (no standalone symbol expectations); 9 new tests in test_symbols_only_highlights.py verify: symbols-only segment not highlighted, symbols with text shown as metadata, standalone entries filtered, has_readable_content() validation; 890 tests total; Does NOT: change evidence extraction or binding, only highlight selection/rendering |
| TBD | M9.1: Desktop Polish | Not Started | Code signing (macOS/Windows); Installer packages (.dmg, .msi); Auto-updater; Keychain integration for API keys; Menu bar/system tray icon; Crash reporting |

---

> **Note**: Milestones 0-6 are required for MVP v0.1. Milestone 7 (watcher) can be deferred to v0.2. Each milestone is independently testable and delivers incremental value.
