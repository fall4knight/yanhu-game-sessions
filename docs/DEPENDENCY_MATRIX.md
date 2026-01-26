# Yanhu Game Sessions - Dependency Matrix

This document defines the single source of truth for runtime dependencies by feature profile.

## Profiles

### Core Profile (Pipeline/Compose/Verify)

**Description**: Minimal dependencies for offline pipeline processing (segment, extract, analyze, compose, verify).

**Python Packages**:
- `click >= 8.0` - CLI framework
- `ffmpeg-python >= 0.2` - FFmpeg bindings
- `pyyaml >= 6.0` - YAML parsing
- `anthropic >= 0.18` - Claude API client
- `emoji >= 2.0` - Emoji utilities

**System Dependencies**:
- `ffmpeg` - Video processing (install: `brew install ffmpeg` on macOS, `sudo apt install ffmpeg` on Ubuntu)
- `ffprobe` - Media probing (included with ffmpeg)

**Runtime Selfcheck Modules**:
```python
import click
import ffmpeg  # ffmpeg-python
import yaml  # pyyaml
import anthropic
import emoji
import yanhu.session
import yanhu.manifest
import yanhu.segmenter
import yanhu.extractor
import yanhu.analyzer
import yanhu.composer
import yanhu.verify
```

---

### App Profile (Web UI)

**Description**: Flask-based web interface for session viewing and job management.

**Python Packages**:
- `flask >= 3.0` - Web framework
- `markdown >= 3.5` - Markdown rendering

**System Dependencies**:
- None (beyond core)

**Runtime Selfcheck Modules**:
```python
import flask
import markdown
import jinja2  # transitive via flask
import werkzeug  # transitive via flask
import yanhu.app
```

---

### ASR Profile (Whisper Local)

**Description**: Local ASR transcription using faster-whisper or openai-whisper.

**Python Packages**:
- `faster-whisper >= 1.0` - Fast Whisper inference engine
  - Transitive: `av` (PyAV, audio extraction with bundled FFmpeg)
  - Transitive: `ctranslate2` (fast inference)
  - Transitive: `tokenizers` (Hugging Face tokenizers)
  - Transitive: `huggingface-hub` (model downloads)
  - Transitive: `onnxruntime` (ONNX runtime)
  - Transitive: `tqdm` (progress bars)
- `tiktoken` - Tokenizer utilities (optional, for future multimodal work)
- `regex` - Enhanced regex (used by tokenizers)
- `safetensors` - Safe tensor format (used by Hugging Face models)

**System Dependencies**:
- None (PyAV bundles FFmpeg libraries for audio extraction)
- GPU (optional): NVIDIA GPU with CUDA for accelerated inference

**Runtime Selfcheck Modules**:
```python
import faster_whisper
import av
import ctranslate2
import tokenizers
import huggingface_hub
import onnxruntime
import tqdm
import tiktoken
import regex
import safetensors
import yanhu.transcriber
import yanhu.asr_registry
```

---

### Dev/Test Profile (E2E Tests)

**Description**: End-to-end browser tests for UI/progress verification using Playwright.

**Python Packages**:
- `playwright >= 1.40` - Browser automation framework
- `pytest >= 7.0` - Test framework (already in dev dependencies)

**System Dependencies**:
- Playwright browsers (Chromium) - **one-time setup required**:
  ```bash
  python -m playwright install --with-deps chromium
  ```

**Runtime Selfcheck**: Not applicable (E2E tests have their own verification via `pytest -m e2e`)

**When to run**:
- Changes to `src/yanhu/app.py` (Flask routes, templates, JS)
- Changes to progress polling logic in `src/yanhu/watcher.py`
- Changes to any Jinja2 templates
- User requests E2E tests or mentions UI/progress changes

**Test Command**:
```bash
pytest -m e2e -v
```

**What E2E tests cover**:
- Progress polling behavior (when to poll, when to stop)
- Job state machine (pending → processing → done)
- Terminal lock enforcement (UI never regresses after done)
- Session link visibility
- Console error prevention (no 404 spam)

See `tests/e2e/README.md` and `E2E_SETUP.md` for detailed documentation.

---

### Desktop Profile (Packaged App)

**Description**: PyInstaller packaging for standalone macOS/Windows apps.

**Python Packages**:
- `pyinstaller >= 6.0` - Application packaging

**System Dependencies**:
- None (for packaging)
- At runtime: same as core profile (ffmpeg/ffprobe)

**Runtime Selfcheck Modules**:
```python
import yanhu.launcher
import yanhu.ffmpeg_utils
```

---

### All Profile (Complete)

**Description**: Union of all profiles (core + app + asr + desktop).

**Python Packages**: All packages from above profiles

**System Dependencies**: All system dependencies from above profiles

**Runtime Selfcheck Modules**: All modules from above profiles

**Install Command**:
```bash
pip install -e ".[app,build,asr]"
pip install tiktoken regex safetensors  # Additional deps not pulled transitively
```

---

## Profile Usage

### Development
```bash
# Core only
pip install -e .

# With web UI
pip install -e ".[app]"

# With ASR
pip install -e ".[asr]"
pip install tiktoken regex safetensors

# Full stack (all features)
pip install -e ".[app,asr]"
pip install tiktoken regex safetensors
```

### Desktop Packaging
```bash
# Install all runtime deps
pip install -e ".[app,build,asr]"
pip install tiktoken regex safetensors

# Verify runtime deps
python scripts/runtime_selfcheck.py --profile all

# Build
pyinstaller yanhu.spec
```

### CI/CD
```bash
# Build workflow
pip install -e ".[app,build,asr]"
pip install tiktoken regex safetensors
python scripts/runtime_selfcheck.py --profile all
pyinstaller yanhu.spec
```

---

## Version Policy

- **Minimum versions** are specified where stability/compatibility is critical
- **Exact versions** are NOT pinned (allow pip to resolve compatible sets)
- **Transitive dependencies** are documented but not explicitly installed (let pip resolve)
- **Desktop builds** must bundle all runtime deps (no pip install instructions to users)

---

## Maintenance

When adding new features:
1. Update this matrix with new packages/modules
2. Update `scripts/runtime_selfcheck.py` module lists
3. Update `yanhu.spec` hiddenimports if needed
4. Update `.github/workflows/build-desktop.yml` if new explicit installs needed
5. Run `python scripts/runtime_selfcheck.py --profile all` to verify
