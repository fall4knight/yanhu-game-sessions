# Smoke Test Checklist - v0.1.0

**Purpose**: Verify the v0.1.0 release works for non-programmers on macOS and Windows.

**Tester Profile**: Non-technical user, no command-line experience, first-time installation.

---

## Pre-Test Setup

- [ ] **Clean machine** (or VM) with no prior Yanhu installation
- [ ] **ffmpeg installed** (via Homebrew on macOS, or manual install on Windows)
- [ ] **Test video file** ready (~1-5 minutes, .mp4 format, <500MB)

---

## Test 1: Download & Extract (macOS)

### Steps
1. [ ] Download `Yanhu-Sessions-macOS.zip` from GitHub Releases
2. [ ] Double-click zip file to extract
3. [ ] Verify `Yanhu Sessions.app` appears in Finder

### Expected Results
- ✅ Zip extracts cleanly
- ✅ App bundle is visible in Finder
- ✅ File size: ~50-100MB

### Failure Modes
- ❌ "Archive damaged" error → Re-download zip
- ❌ No .app file appears → Check macOS version (requires 10.15+)

---

## Test 2: First Launch (macOS)

### Steps
1. [ ] Right-click `Yanhu Sessions.app` → **Open**
2. [ ] Click **Open** in security dialog
3. [ ] Wait for terminal window to appear
4. [ ] Browser should auto-open to http://127.0.0.1:8787

### Expected Results (Terminal)
```
============================================================
Yanhu Game Sessions - Desktop Launcher
============================================================

Sessions directory: /Users/yourname/yanhu-sessions/sessions
Raw videos directory: /Users/yourname/yanhu-sessions/raw

Starting web server at http://127.0.0.1:8787

Opening browser...

Press Ctrl+C to stop the server and exit.
============================================================
```

### Expected Results (Browser)
- ✅ Page loads at http://127.0.0.1:8787
- ✅ Header shows "Yanhu Sessions"
- ✅ Header shows "🔒 Local processing only"
- ✅ Upload area visible with drag-and-drop zone
- ✅ "Submit existing file" form visible below

**If ffmpeg NOT installed:**
- ✅ Yellow warning banner at top:
  ```
  ⚠️ ffmpeg not available: ffmpeg and ffprobe not found
  Install ffmpeg to process videos:
  macOS: brew install ffmpeg | Windows: Download from ffmpeg.org | Linux: sudo apt-get install ffmpeg
  ```

### Failure Modes
- ❌ "Unidentified developer" dialog appears → Use Right-click → Open (not double-click)
- ❌ Browser doesn't open → Manually navigate to http://127.0.0.1:8787
- ❌ "Port already in use" → Close other apps using port 8787, or kill existing yanhu process
- ❌ Terminal closes immediately → Check console output for errors

---

## Test 3: First Launch (Windows)

### Steps
1. [ ] Extract `Yanhu-Sessions-Windows.zip`
2. [ ] Open extracted `yanhu` folder
3. [ ] Double-click `yanhu.exe`
4. [ ] Click **More info** → **Run anyway** in Windows Defender dialog
5. [ ] Wait for console window to appear
6. [ ] Browser should auto-open to http://127.0.0.1:8787

### Expected Results (Console)
```
============================================================
Yanhu Game Sessions - Desktop Launcher
============================================================

Sessions directory: C:\Users\yourname\yanhu-sessions\sessions
Raw videos directory: C:\Users\yourname\yanhu-sessions\raw

Starting web server at http://127.0.0.1:8787

Opening browser...

Press Ctrl+C to stop the server and exit.
============================================================
```

### Expected Results (Browser)
- Same as macOS Test 2 above

### Failure Modes
- ❌ Windows Defender blocks → Click "More info" then "Run anyway"
- ❌ DLL missing errors → Ensure Windows 10+ with latest updates
- ❌ Console window closes immediately → Run from cmd.exe to see errors

---

## Test 4: Upload & Process Video

### Steps
1. [ ] **Drag and drop** test video file into upload area (or click to browse)
2. [ ] Verify file name appears
3. [ ] Leave default settings:
   - Preset: Fast
   - All optional fields empty
4. [ ] Click **"Upload & Start Job"**
5. [ ] Browser redirects to job detail page

### Expected Results (Upload)
- ✅ File uploads successfully (progress bar if large file)
- ✅ Redirects to `/jobs/job_YYYYMMDD_HHMMSS_hash8`

### Expected Results (Job Detail Page)
- ✅ Shows "Status: pending" initially
- ✅ Shows "Media Info" table with video details
- ✅ Shows "Estimates" table with segment count and runtime
- ✅ Status changes to "processing" within ~5 seconds

**Example Media Info:**
```
Duration: 1m 30s
File size: 45.2 MB
Container: mp4
Video codec: h264
Audio codec: aac
Resolution: 1920x1080
FPS: 30.00
Bitrate: 4000 kbps
```

**Example Estimates:**
```
Segments: 18 (auto-medium, 5s each)
Estimated runtime: ~1m 5s
```

### Failure Modes
- ❌ "Invalid file type" → Use .mp4/.mov/.mkv/.webm only
- ❌ Upload hangs → Check file size (<5GB limit)
- ❌ "ffmpeg not found" → Install ffmpeg (see warning banner)

---

## Test 5: Monitor Progress

### Steps
1. [ ] Stay on job detail page
2. [ ] Observe progress bar updates every 1-2 seconds
3. [ ] Wait for processing to complete

### Expected Results (During Processing)
- ✅ Progress bar shows:
  ```
  Stage: transcribe | Progress: 5/18 segments | Elapsed: 15s, ETA ~45s
  Observed rate: 0.333 seg/s | Calibrated ETA: ~39s | Est. finish: 10:15
  ```
- ✅ Progress bar is yellow (in-progress state)
- ✅ ETA updates in real-time and becomes more accurate
- ✅ Can click "← All Sessions" to go back

### Expected Results (When Complete)
- ✅ Progress bar turns green:
  ```
  Stage: done | Progress: 18/18 segments | Elapsed: 1m 5s
  ```
- ✅ Status changes to "done"
- ✅ "Session ID" link appears (e.g., `2026-01-23_10-00-00_unknown_run01`)

### Failure Modes
- ❌ Stuck at "Stage: segment" → ffmpeg issue (check console)
- ❌ Stuck at "Stage: transcribe" → Check disk space
- ❌ Progress stops updating → Refresh page

---

## Test 6: View Session Outputs

### Steps
1. [ ] Click session ID link from job detail page
2. [ ] Explore all tabs: Overview, Highlights, Timeline, Transcripts, Manifest

### Expected Results (Overview Tab - Default Active)
- ✅ Shows session summary in markdown format
- ✅ Contains:
  - Session metadata (game, tag, date)
  - Processing settings (preset, segment strategy)
  - Scene summary
  - Key moments
  - Character/dialogue highlights

**Example Overview Content:**
```markdown
# Session Overview: 2026-01-23_10-00-00_unknown_run01

**Game**: unknown
**Tag**: run01
**Created**: 2026-01-23T10:00:00
**Duration**: 90.0 seconds
**Segments**: 18 (5s each, auto-medium strategy)

## Processing Settings
- Preset: fast
- Analyze: mock backend
- Transcribe: mock backend
- Frames per segment: 3

## Scene Summary
[Content generated by mock backend]
...
```

### Expected Results (Highlights Tab)
- ✅ Shows memorable moments
- ✅ Contains quotes with timestamps
- ✅ References segment evidence

### Expected Results (Timeline Tab)
- ✅ Shows chronological breakdown
- ✅ Each entry has:
  - Timestamp (HH:MM:SS format)
  - Scene description
  - Dialogue/transcription
  - Evidence (segment/frame references)

**Example Timeline Entry:**
```markdown
## 00:00:05 - 00:00:10 | segment part_0001

**Scene**: [Mock scene description]

**Dialogue**:
- [无字幕]

**Evidence**: segment part_0001, frame 0001.jpg
```

### Expected Results (Transcripts Tab)
- ✅ Shows "Loading transcripts..." initially
- ✅ Shows model selector: `[mock]` button
- ✅ Clicking mock button displays transcripts
- ✅ Each segment shows:
  - Segment ID (e.g., part_0001)
  - Backend (mock)
  - Transcription items with timestamps

**Example Transcript:**
```
part_0001 (mock)
[0.00s - 10.00s]: [无字幕]

part_0002 (mock)
[10.00s - 15.00s]: [无字幕]
```

### Expected Results (Manifest Tab)
- ✅ Shows raw JSON manifest
- ✅ Contains:
  - session_id
  - created_at
  - source_video path
  - segments list
  - asr_models (if used)

### Failure Modes
- ❌ Tabs don't switch → JavaScript error (check browser console)
- ❌ Markdown not rendered → Flask not serving correctly
- ❌ Transcripts tab empty → Check outputs/asr/ directory exists

---

## Test 7: Process Second Video (Existing File)

### Steps
1. [ ] Click "← All Sessions" to return to home page
2. [ ] Scroll to "Submit existing file" form
3. [ ] Enter path to test video (e.g., `/Users/name/Videos/test.mp4`)
4. [ ] Optional: Enter "Game" name (e.g., "genshin")
5. [ ] Click **"Submit Job"**
6. [ ] Verify job processes successfully

### Expected Results
- ✅ Job created and processes
- ✅ Session ID includes game name (e.g., `2026-01-23_10-05-00_genshin_run01`)
- ✅ All tabs work as in Test 6

### Failure Modes
- ❌ "File not found" → Use absolute path, not relative
- ❌ "Path must be under raw_dir" → Use upload instead (or enable --allow-any-path in CLI mode)

---

## Test 8: Home Page Session List

### Steps
1. [ ] Return to home page (http://127.0.0.1:8787)
2. [ ] Verify sessions list shows both processed jobs

### Expected Results
- ✅ Sessions sorted newest-first
- ✅ Each session shows:
  - Session ID (clickable link)
  - Status: done
  - Created timestamp
  - "Details" link
- ✅ Upload form still visible at top

### Failure Modes
- ❌ Empty list → Sessions not saved correctly
- ❌ Wrong order → Sorting logic broken

---

## Test 9: Cancel Job (Optional)

### Steps
1. [ ] Upload a large video (>5 minutes)
2. [ ] Wait for processing to start
3. [ ] Click **"Cancel Job"** button on job detail page
4. [ ] Verify job cancellation

### Expected Results
- ✅ Status changes to "cancel_requested"
- ✅ Processing stops after current segment completes
- ✅ Final status: "cancelled"

### Failure Modes
- ❌ Job continues processing → Worker didn't detect cancel signal

---

## Test 10: Restart & Persistence

### Steps
1. [ ] Close browser
2. [ ] Close terminal window (or press Ctrl+C)
3. [ ] Wait 5 seconds
4. [ ] Relaunch app (same as Test 2 or Test 3)
5. [ ] Browser opens again
6. [ ] Check home page

### Expected Results
- ✅ App starts cleanly
- ✅ Previous sessions still visible in list
- ✅ Can view previous session outputs
- ✅ All data persisted in `~/yanhu-sessions/`

### Failure Modes
- ❌ App won't start → Port still in use (kill previous process)
- ❌ Sessions disappeared → Check ~/yanhu-sessions/sessions/ exists

---

## Test 11: Multi-Model ASR (Advanced)

### Steps
1. [ ] Upload new video
2. [ ] In "ASR Models" field, enter: `mock,mock`
3. [ ] Submit job
4. [ ] Wait for completion
5. [ ] View Transcripts tab

### Expected Results
- ✅ Model selector shows: `[mock]` button (only one because both are same model)
- ✅ Transcripts display correctly
- ✅ Manifest shows `"asr_models": ["mock", "mock"]`

### Failure Modes
- ❌ "Unknown ASR model" error → Invalid model name
- ❌ Only one transcript saved → Check outputs/asr/ directory

---

## Test 12: Error Handling

### Steps (Missing ffmpeg)
1. [ ] Temporarily rename ffmpeg (macOS: `mv /opt/homebrew/bin/ffmpeg /opt/homebrew/bin/ffmpeg.bak`)
2. [ ] Restart app
3. [ ] Try to upload and process video

### Expected Results
- ✅ App starts with warning:
  ```
  WARNING: ffmpeg and ffprobe not found
  The app will start, but video processing will fail.
  ```
- ✅ Yellow warning banner visible in browser
- ✅ Job starts but fails at segment stage
- ✅ Status: "failed"
- ✅ Error message shows ffmpeg-related issue

### Cleanup
1. [ ] Restore ffmpeg (macOS: `mv /opt/homebrew/bin/ffmpeg.bak /opt/homebrew/bin/ffmpeg`)

---

## Success Criteria

### All Tests Pass (✅)
- macOS: Tests 1, 2, 4-11 pass
- Windows: Tests 3, 4-11 pass
- Error handling: Test 12 shows expected behavior

### Release Approved If:
- ✅ Non-technical tester completes Tests 1-8 without assistance
- ✅ All tabs load and display content correctly
- ✅ No crashes or data loss
- ✅ Security warnings are expected and documented
- ✅ ffmpeg detection works correctly

### Block Release If:
- ❌ App crashes during normal operation
- ❌ Data corruption (sessions/jobs lost)
- ❌ Browser doesn't open on any platform
- ❌ Upload fails silently
- ❌ Progress never updates

---

## Testing Notes

**Time Required**: ~30-45 minutes for full checklist

**Recommended Test Videos**:
- Short test: 30 seconds (quick smoke test)
- Medium test: 2-5 minutes (typical session)
- Large test: 10+ minutes (stress test, optional)

**Test Platforms**:
- macOS 12+ (Monterey or newer recommended)
- Windows 10/11
- Linux (Ubuntu 22.04 LTS recommended)

**Browser Compatibility**:
- Chrome/Edge (recommended)
- Firefox
- Safari (macOS)

---

## Post-Test Cleanup

```bash
# Remove test data
rm -rf ~/yanhu-sessions/

# Uninstall app
# macOS: Delete "Yanhu Sessions.app"
# Windows: Delete yanhu folder
```

---

**Last Updated**: 2026-01-23 for v0.1.0
