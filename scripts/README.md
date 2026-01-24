# Scripts

This directory contains utility scripts for building and testing Yanhu Sessions.

## Build Scripts

### `build_desktop.sh` (macOS/Linux)

Builds desktop application using PyInstaller.

```bash
./scripts/build_desktop.sh
```

**Output:**
- macOS: `dist/Yanhu Sessions.app`
- Linux: `dist/yanhu/yanhu`

### `build_desktop.bat` (Windows)

Builds desktop application using PyInstaller on Windows.

```cmd
scripts\build_desktop.bat
```

**Output:**
- Windows: `dist\yanhu\yanhu.exe`

## Development/Testing Scripts

### `test_launcher_dev.sh`

Tests the desktop launcher in development mode (without building).

```bash
./scripts/test_launcher_dev.sh
```

This runs the launcher directly via Python and auto-opens the browser.
Press Ctrl+C to stop.

## Requirements

All scripts require:
- Python 3.10+
- Dependencies installed: `pip install -e ".[app,build]"`

Build scripts additionally require:
- PyInstaller installed (included in `[build]` extras)
