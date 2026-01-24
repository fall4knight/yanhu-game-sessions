# Release Instructions - v0.1.0

This document contains step-by-step instructions for creating and publishing the v0.1.0 release.

## Prerequisites

- [ ] All tests passing: `pytest -q` (761 tests)
- [ ] All lint checks passing: `ruff check src/ tests/`
- [ ] PROJECT_PLAN.md Milestone 9.0 marked as Done
- [ ] Clean working directory: `git status` shows no uncommitted changes
- [ ] On main branch: `git branch` shows `* main`

## Release Checklist

### 1. Final Verification

```bash
# Run full test suite
pytest -q

# Expected: 761 passed

# Run linter
ruff check src/ tests/

# Expected: All checks passed!

# Verify launcher works in dev mode
python -m yanhu.launcher
# Should start server and open browser
# Press Ctrl+C to stop
```

### 2. Verify Release Artifacts Exist

Check that these files exist:
- [ ] `RELEASE_NOTES_v0.1.0.md` - Comprehensive release notes
- [ ] `SMOKE_TEST_CHECKLIST.md` - User testing checklist
- [ ] `docs/BUILD.md` - Build documentation
- [ ] `scripts/build_desktop.sh` - macOS/Linux build script
- [ ] `scripts/build_desktop.bat` - Windows build script
- [ ] `.github/workflows/build-desktop.yml` - CI/CD workflow
- [ ] `yanhu.spec` - PyInstaller spec file

### 3. Commit Release Artifacts

```bash
# Add new files
git add RELEASE_NOTES_v0.1.0.md
git add SMOKE_TEST_CHECKLIST.md
git add RELEASE_INSTRUCTIONS.md

# Commit
git commit -m "chore: add v0.1.0 release documentation

- Release notes with quickstart, limitations, troubleshooting
- Smoke test checklist for non-programmers
- Release instructions for maintainers"

# Push to main
git push origin main
```

### 4. Create and Push Tag

```bash
# Create annotated tag
git tag -a v0.1.0 -m "Release v0.1.0: Desktop Distribution MVP

First stable release of Yanhu Game Sessions with desktop packaging.

Features:
- Desktop launcher with one-click start
- macOS .app and Windows .exe packages
- Local-only web UI with upload, jobs, progress tracking
- Multi-model ASR transcription
- Timeline, highlights, and overview generation
- ffmpeg detection and warnings

See RELEASE_NOTES_v0.1.0.md for details."

# Verify tag created
git tag -l -n9 v0.1.0

# Push tag to trigger GitHub Actions
git push origin v0.1.0
```

### 5. Monitor GitHub Actions

1. Go to: https://github.com/anthropics/yanhu-game-sessions/actions
2. Wait for "Build Desktop Apps" workflow to complete (~10-15 minutes)
3. Verify both jobs succeed:
   - ✅ build-macos
   - ✅ build-windows

**If builds fail:**
- Check workflow logs
- Fix issues
- Delete tag: `git tag -d v0.1.0 && git push origin :refs/tags/v0.1.0`
- Repeat from step 4

### 6. Verify Release Created

1. Go to: https://github.com/anthropics/yanhu-game-sessions/releases
2. Verify release v0.1.0 exists
3. Verify artifacts attached:
   - [ ] `Yanhu-Sessions-macOS.zip` (~50-100MB)
   - [ ] `Yanhu-Sessions-Windows.zip` (~50-100MB)

### 7. Edit Release Notes on GitHub

1. Click "Edit" on the v0.1.0 release
2. Copy content from `RELEASE_NOTES_v0.1.0.md`
3. Paste into release description
4. Add at the top:

```markdown
## Download

- **macOS**: [Yanhu-Sessions-macOS.zip](link)
- **Windows**: [Yanhu-Sessions-Windows.zip](link)

**Prerequisites**: Install [ffmpeg](https://ffmpeg.org/download.html) before running.

See full release notes below.

---
```

5. Check "Set as the latest release"
6. Click "Update release"

### 8. Smoke Test Artifacts

**macOS:**
```bash
# Download artifact
# Extract Yanhu-Sessions-macOS.zip
# Right-click Yanhu Sessions.app → Open
# Verify browser opens and UI loads
```

**Windows:**
```cmd
REM Download artifact
REM Extract Yanhu-Sessions-Windows.zip
REM Double-click yanhu.exe
REM Verify browser opens and UI loads
```

Follow `SMOKE_TEST_CHECKLIST.md` for comprehensive testing.

### 9. Update README (Optional)

Add a "Download" section to README.md:

```markdown
## Download Pre-built Desktop App

**Latest Release**: [v0.1.0](https://github.com/anthropics/yanhu-game-sessions/releases/tag/v0.1.0)

- **macOS**: Download `Yanhu-Sessions-macOS.zip`, extract, right-click → Open
- **Windows**: Download `Yanhu-Sessions-Windows.zip`, extract, double-click `yanhu.exe`

See [RELEASE_NOTES_v0.1.0.md](RELEASE_NOTES_v0.1.0.md) for details.
```

Commit and push if updated.

### 10. Announce Release (Optional)

Post announcement with:
- Link to release page
- Key features
- Installation instructions
- Call for feedback

## Post-Release

### Monitor Issues

Watch for user-reported issues:
- GitHub Issues
- GitHub Discussions

### Prepare for v0.2

Create milestone for next release:
- Bug fixes from v0.1 feedback
- M9.1 features (code signing, installers)
- Performance improvements

## Rollback Procedure (if needed)

If critical issues found:

```bash
# Mark release as pre-release
# (Edit release on GitHub, check "This is a pre-release")

# Delete tag
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0

# Fix issues
# Create new tag (e.g., v0.1.1)
```

## Common Issues

### "Release already exists"
- Delete existing draft release on GitHub
- Re-push tag

### Build artifacts missing
- Check GitHub Actions logs
- Ensure workflow has proper permissions
- Verify GITHUB_TOKEN secret exists

### Tag push doesn't trigger workflow
- Check `.github/workflows/build-desktop.yml` triggers config
- Ensure tag matches pattern: `v*`
- Check GitHub Actions is enabled for repository

## Verification Summary

Before announcing release, verify:
- ✅ GitHub release exists with v0.1.0 tag
- ✅ Both macOS and Windows artifacts attached
- ✅ Release notes published on GitHub
- ✅ Smoke tests pass on both platforms
- ✅ No P0/P1 issues found
- ✅ README links to release

---

**Release Manager**: [Your Name]
**Release Date**: 2026-01-23
**Version**: v0.1.0
