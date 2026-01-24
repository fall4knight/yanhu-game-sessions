# Yanhu Game Sessions v0.1.0 Release Notes

**Release Date**: 2026-01-23
**Type**: Initial MVP Release

---

## What is Yanhu Game Sessions?

Yanhu Game Sessions is a **local-only** desktop application for post-game video analysis. It helps you:

- **Segment** game session recordings into manageable chunks
- **Analyze** each segment with AI vision (Claude) or mock backend
- **Transcribe** audio with local Whisper or mock ASR
- **Generate** timelines, highlights, and summaries automatically

**All processing happens on your local machine. No data is uploaded to the cloud.**

---

## Download & Install

### Prerequisites

**Required**: ffmpeg (for video processing)
- **macOS**: `brew install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- **Linux**: `sudo apt-get install ffmpeg` (Debian/Ubuntu)

**Optional** (for Claude Vision analysis):
- Set environment variable: `ANTHROPIC_API_KEY=your_key_here`

### Download

Get the latest release from GitHub Releases:
- **macOS**: Download `Yanhu-Sessions-macOS.zip`
- **Windows**: Download `Yanhu-Sessions-Windows.zip`

### Installation

**macOS**:
1. Extract `Yanhu-Sessions-macOS.zip`
2. Right-click `Yanhu Sessions.app` → **Open** (first time only)
3. Click **Open** in security dialog
4. Browser opens automatically at http://127.0.0.1:8787

**Windows**:
1. Extract `Yanhu-Sessions-Windows.zip`
2. Double-click `yanhu.exe` inside the `yanhu` folder
3. Click **More info** → **Run anyway** in Windows Defender warning (first time only)
4. Browser opens automatically at http://127.0.0.1:8787

---

## Quick Start

1. **Launch the app** (see Installation above)
2. **Browser opens** automatically to the web interface
3. **Drag and drop** a video file into the upload area, or
4. **Select existing file** by entering the file path
5. **Wait** for processing (progress shown in real-time)
6. **View results**:
   - **Timeline**: Chronological breakdown with timestamps
   - **Highlights**: Key moments and memorable quotes
   - **Overview**: Session summary
   - **Transcripts**: Side-by-side ASR model comparisons (if multi-model enabled)

### Example: Processing a 5-minute gameplay video

```
1. Drop video.mp4 into upload area
2. Select preset: "Fast" (default)
3. Click "Upload & Start Job"
4. Processing time: ~2-3 minutes
5. View session outputs in Timeline tab
```

---

## Features (v0.1.0)

### Core Pipeline
- ✅ **Video Ingestion**: Link/copy videos with metadata tracking
- ✅ **Adaptive Segmentation**: Auto-adjusts segment duration (5s/15s/30s) based on video length
- ✅ **Frame Extraction**: Extract keyframes from each segment
- ✅ **Vision Analysis**: Claude Vision or mock backend
- ✅ **ASR Transcription**: Whisper (local) or mock backend
- ✅ **Multi-model ASR**: Run multiple ASR models side-by-side
- ✅ **Timeline Generation**: Markdown timeline with timestamps and evidence
- ✅ **Highlights & Overview**: Automatic summary generation

### Web Interface
- ✅ **Session Viewer**: Browse all sessions with tabbed interface
- ✅ **Job Queue**: Upload videos and track processing progress
- ✅ **Real-time Progress**: Live updates with calibrated ETA
- ✅ **Drag & Drop Upload**: Easy file upload with 5GB limit
- ✅ **Job Control**: Cancel pending/processing jobs
- ✅ **Transcripts Viewer**: Compare multiple ASR model outputs

### Developer Tools
- ✅ **CLI**: Full command-line interface for automation
- ✅ **Presets**: Fast (base model, int8) and Quality (small model, float32)
- ✅ **Transcribe Limits**: Process first N segments for quick previews
- ✅ **Metrics Tracking**: Persistent throughput metrics improve ETA accuracy
- ✅ **Verify Tool**: Validate session outputs meet quality standards

### Distribution
- ✅ **Desktop Launcher**: One-click start with browser auto-open
- ✅ **ffmpeg Detection**: Clear warnings and install instructions
- ✅ **Default Directories**: Auto-creates `~/yanhu-sessions/{sessions,raw}`
- ✅ **Local-only Notice**: Visible privacy indicator in UI

---

## Known Limitations (MVP)

### Security & Trust
- ❌ **No code signing**: First run shows security warnings (expected)
  - macOS: Right-click → Open to bypass Gatekeeper
  - Windows: "More info" → "Run anyway" to bypass Defender
- ❌ **No installer packages**: Manual zip extraction required
- ❌ **No auto-updater**: Check GitHub Releases for new versions

### Dependencies
- ❌ **ffmpeg not bundled**: Users must install separately
- ❌ **Console window visible**: Terminal window stays open (Windows)

### Features
- ❌ **Single worker**: Processes one job at a time
- ❌ **No cloud sync**: Sessions stored locally only
- ❌ **No video playback**: View timeline/highlights as text/markdown

**These limitations will be addressed in future releases (M9.1+).**

---

## Troubleshooting

### "Port 8787 already in use"

**Problem**: Another app is using port 8787

**Solution**:
1. Find and stop the conflicting app, or
2. Edit `launcher.py` to use a different port (requires rebuild)

### "ffmpeg not found" warning banner

**Problem**: ffmpeg/ffprobe not installed or not in PATH

**Solution**:
- **macOS**: `brew install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- **Verify**: Run `ffmpeg -version` in terminal

### "Unidentified developer" warning (macOS)

**Problem**: App is not code-signed

**Solution**:
1. Right-click (Control+Click) on `Yanhu Sessions.app`
2. Select **Open** from context menu
3. Click **Open** in security dialog
4. App will remember this choice

### Windows Defender SmartScreen warning

**Problem**: Executable is not code-signed

**Solution**:
1. Click **More info** in warning dialog
2. Click **Run anyway** button
3. App will start normally

### Processing fails with "Video file not found"

**Problem**: File path is incorrect or file was moved

**Solution**:
- Use absolute paths (e.g., `/Users/name/Videos/game.mp4`)
- Ensure file still exists at specified location
- Check file permissions (readable by app)

### Browser doesn't open automatically

**Problem**: Default browser not set or permission issue

**Solution**:
- Manually open browser and navigate to http://127.0.0.1:8787
- Check console output for errors

### Job stuck in "processing" status

**Problem**: Pipeline crashed or worker stopped

**Solution**:
1. Restart the app
2. Cancel the stuck job
3. Re-submit if needed
4. Check console output for error messages

### "ANTHROPIC_API_KEY not set" when using Claude

**Problem**: Environment variable not configured

**Solution**:
- **macOS/Linux**: `export ANTHROPIC_API_KEY=your_key_here` before launching
- **Windows**: Set via System Properties → Environment Variables
- Or use `--backend mock` for testing without API key

---

## Data Privacy & Security

### What data is stored?
- **Sessions**: Processed videos, frames, analysis, transcripts
- **Location**: `~/yanhu-sessions/sessions/`
- **Jobs**: Metadata, status, configurations
- **Location**: `~/yanhu-sessions/_queue/jobs/`
- **Metrics**: Processing throughput statistics
- **Location**: `~/yanhu-sessions/_metrics.json`

### What data is sent to the cloud?
- **None**, unless you explicitly use Claude Vision backend with API key
- If using Claude: Only extracted frames are sent to Anthropic API
- Original videos never leave your machine

### How to delete data?
```bash
# Delete all sessions
rm -rf ~/yanhu-sessions/sessions/*

# Delete all jobs
rm -rf ~/yanhu-sessions/_queue/jobs/*

# Delete everything
rm -rf ~/yanhu-sessions/
```

---

## System Requirements

### Minimum
- **OS**: macOS 10.15+, Windows 10+, or Linux (x86_64)
- **RAM**: 4GB (8GB recommended for Whisper)
- **Disk**: 1GB for app, plus space for sessions (varies by video size)
- **CPU**: Any modern dual-core processor

### Recommended
- **OS**: macOS 12+, Windows 11
- **RAM**: 16GB (for smooth Whisper processing)
- **Disk**: SSD with 10GB+ free space
- **CPU**: Quad-core or better
- **GPU**: Not required (Whisper runs on CPU in this version)

---

## Getting Help

### Documentation
- **README**: General overview and 60s quickstart
- **RUNBOOK**: Detailed CLI usage and examples
- **BUILD.md**: Building from source
- **PROJECT_PLAN.md**: Development roadmap

### Support
- **Issues**: [GitHub Issues](https://github.com/anthropics/yanhu-game-sessions/issues)
- **Discussions**: [GitHub Discussions](https://github.com/anthropics/yanhu-game-sessions/discussions)

---

## Technical Details

### Built With
- **Python 3.10**: Core runtime
- **Flask**: Web framework
- **ffmpeg**: Video processing
- **faster-whisper**: Local ASR (optional)
- **Anthropic Claude**: Vision analysis (optional)
- **PyInstaller**: Desktop packaging

### Architecture
- **Pipeline**: Ingest → Segment → Extract → Analyze → Transcribe → Compose
- **Storage**: Local filesystem, JSON manifests
- **Web UI**: Server-rendered HTML + JavaScript for real-time updates
- **Worker**: Single-threaded background job processor

### File Structure
```
~/yanhu-sessions/
├── sessions/              # Processed sessions
│   └── YYYY-MM-DD_HH-MM-SS_game_tag/
│       ├── source/        # Original video (linked/copied)
│       ├── segments/      # Split video chunks
│       ├── frames/        # Extracted keyframes
│       ├── analysis/      # Vision analysis results
│       ├── audio/         # Extracted audio (if Whisper used)
│       ├── outputs/
│       │   ├── asr/       # Per-model ASR transcripts
│       │   └── progress.json
│       ├── timeline.md    # Generated timeline
│       ├── overview.md    # Session summary
│       ├── highlights.md  # Key moments
│       └── manifest.json  # Session metadata
├── raw/                   # Uploaded videos
└── _queue/
    └── jobs/              # Job metadata
```

---

## What's Next?

### Planned for v0.2 (M9.1 - Desktop Polish)
- Code signing for macOS and Windows
- Installer packages (.dmg, .msi)
- Auto-updater
- Hide console window (Windows)
- System tray integration
- Keychain integration for API keys

### Planned for Future Releases
- Multi-worker job processing
- Video playback in browser
- Side-by-side ASR diff viewer
- Qwen3 vision/ASR backend
- Export to video with burned-in captions

### Feedback Welcome!
We're actively developing Yanhu Game Sessions. Your feedback helps prioritize features.
Please file issues and suggestions on GitHub.

---

## License

MIT License - See LICENSE file for details

---

**Thank you for trying Yanhu Game Sessions v0.1.0!**

For the latest updates, visit: https://github.com/anthropics/yanhu-game-sessions
