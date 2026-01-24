# Building Desktop Applications

This guide covers building desktop packages for Yanhu Sessions using PyInstaller.

## Prerequisites

1. **Python 3.10+** installed
2. **Dependencies installed**:
   ```bash
   pip install -e ".[app,build]"
   ```

3. **Platform-specific tools**:
   - macOS: Xcode Command Line Tools
   - Windows: Visual Studio Build Tools (optional, for better compatibility)

## Quick Build

### macOS

```bash
# Build .app bundle
./scripts/build_desktop.sh

# Output: dist/Yanhu Sessions.app
```

### Windows

```cmd
REM Build .exe
scripts\build_desktop.bat

REM Output: dist\yanhu\yanhu.exe
```

### Linux

```bash
# Build executable
./scripts/build_desktop.sh

# Output: dist/yanhu/yanhu
```

## Manual Build (Advanced)

If you need more control, run PyInstaller directly:

```bash
# Clean previous builds
rm -rf build/ dist/

# Build using spec file
pyinstaller yanhu.spec

# macOS: dist/Yanhu Sessions.app
# Windows: dist/yanhu/yanhu.exe
# Linux: dist/yanhu/yanhu
```

## Customizing the Build

Edit `yanhu.spec` to customize:

- **Icon**: Add `icon='path/to/icon.icns'` (macOS) or `icon='path/to/icon.ico'` (Windows)
- **Console**: Set `console=False` to hide console window (Windows)
- **Bundle identifier**: Change `bundle_identifier` (macOS)
- **Hidden imports**: Add missing imports to `hiddenimports` list

## Testing the Build

### Test in dev mode (without building)

```bash
# Run launcher directly
python -m yanhu.launcher

# Or use the test script
./scripts/test_launcher_dev.sh
```

### Test the built package

**macOS:**
```bash
open "dist/Yanhu Sessions.app"
```

**Windows:**
```cmd
dist\yanhu\yanhu.exe
```

**Linux:**
```bash
./dist/yanhu/yanhu
```

The app should:
1. Print startup messages to console
2. Create `~/yanhu-sessions/` directory
3. Auto-open browser to http://127.0.0.1:8787
4. Show ffmpeg warning if ffmpeg not installed

## Distributing the Build

### macOS

Create a zip archive:
```bash
cd dist
zip -r "Yanhu-Sessions-macOS.zip" "Yanhu Sessions.app"
```

Users extract and double-click `Yanhu Sessions.app`.

**Note**: First run will show "unidentified developer" warning. Users must right-click → Open to bypass (no code signing in MVP).

### Windows

Create a zip archive:
```powershell
cd dist
Compress-Archive -Path yanhu -DestinationPath Yanhu-Sessions-Windows.zip
```

Users extract and double-click `yanhu.exe`.

**Note**: Windows Defender may show warning for unsigned executables. Users must click "More info" → "Run anyway".

### Linux

Create a tarball:
```bash
cd dist
tar -czf yanhu-sessions-linux.tar.gz yanhu/
```

Users extract and run `./yanhu/yanhu`.

## CI/CD Builds

GitHub Actions automatically builds packages on tag push:

```bash
# Create and push tag
git tag v0.1.0
git push origin v0.1.0
```

Artifacts are uploaded to GitHub Releases:
- `Yanhu-Sessions-macOS.zip`
- `Yanhu-Sessions-Windows.zip`

## Troubleshooting

### "Module not found" errors

Add missing modules to `hiddenimports` in `yanhu.spec`:
```python
hiddenimports=[
    'your.missing.module',
    ...
]
```

### Large bundle size

Exclude unnecessary packages in `yanhu.spec`:
```python
excludes=[
    'tkinter',
    'matplotlib',
    ...
]
```

### macOS Gatekeeper issues

For distribution, code signing is required:
```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name" \
  "dist/Yanhu Sessions.app"
```

(Not included in MVP)

### Windows antivirus false positives

Submit the built executable to antivirus vendors for whitelisting, or use code signing certificate.

(Not included in MVP)

## Known Limitations (MVP)

- No code signing (users see security warnings)
- No auto-updater
- No installer packages (.dmg, .msi)
- Does NOT bundle ffmpeg (users must install separately)
- Console window shows on Windows (can be hidden by setting `console=False`)

These will be addressed in M9.1: Desktop Polish.
