#!/bin/bash
# CI Rehearsal Script for Desktop Builds
# Simulates the build-desktop.yml workflow locally to catch issues before pushing tags.
#
# Usage: ./scripts/ci_rehearsal_desktop.sh
#
# This script:
# 1. Creates a clean venv
# 2. Installs dependencies (matching build-desktop.yml)
# 3. Runs linting and tests
# 4. Runs runtime self-check
# 5. Builds with PyInstaller
# 6. Validates macOS bundle structure (on macOS)
#
# Exit code: 0 on success, non-zero on failure

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv-ci-rehearsal"

echo "============================================================"
echo "Yanhu Desktop Build - CI Rehearsal"
echo "============================================================"
echo ""
echo "Repo: $REPO_ROOT"
echo "Venv: $VENV_DIR"
echo ""

# Clean up previous venv if exists
if [ -d "$VENV_DIR" ]; then
    echo "[1/7] Cleaning previous CI venv..."
    rm -rf "$VENV_DIR"
fi

# Create fresh venv
echo "[2/7] Creating clean venv..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "[3/7] Upgrading pip..."
python -m pip install --upgrade pip --quiet

# Install dependencies (matching build-desktop.yml)
echo "[4/7] Installing dependencies..."
pip install -e "$REPO_ROOT[app,build,asr]" --quiet
pip install tiktoken regex safetensors --quiet

# Debug: Show installed ASR packages
echo ""
echo "=== Installed ASR-related packages ==="
pip freeze | grep -E "tiktoken|regex|safetensors|faster-whisper|ctranslate2|tokenizers|huggingface-hub|onnxruntime|av|tqdm" || echo "(No matching packages - this is a problem!)"
echo ""

# Run ruff check
echo "[5/7] Running ruff check..."
cd "$REPO_ROOT"
ruff check src/ tests/ scripts/ || {
    echo ""
    echo "✗ FAILED: ruff check"
    exit 1
}
echo "✓ ruff check passed"
echo ""

# Run pytest
echo "[6/7] Running pytest..."
pytest -q || {
    echo ""
    echo "✗ FAILED: pytest"
    exit 1
}
echo "✓ pytest passed"
echo ""

# Run runtime self-check (all profiles)
echo "[7/7] Running runtime self-check (--profile all)..."
python "$REPO_ROOT/scripts/runtime_selfcheck.py" --profile all || {
    echo ""
    echo "✗ FAILED: runtime self-check"
    exit 1
}
echo "✓ Runtime self-check passed"
echo ""

# Build with PyInstaller
echo "[8/7] Building with PyInstaller..."
cd "$REPO_ROOT"
pyinstaller yanhu.spec --clean --noconfirm || {
    echo ""
    echo "✗ FAILED: PyInstaller build"
    exit 1
}
echo "✓ PyInstaller build completed"
echo ""

# Validate macOS bundle structure (only on macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "[9/7] Validating macOS bundle structure..."

    APP_BUNDLE="$REPO_ROOT/dist/Yanhu Sessions.app"

    if [ ! -d "$APP_BUNDLE" ]; then
        echo "✗ FAILED: Bundle not found at: $APP_BUNDLE"
        exit 1
    fi
    echo "  ✓ Found: $APP_BUNDLE"

    if [ ! -f "$APP_BUNDLE/Contents/Info.plist" ]; then
        echo "✗ FAILED: Info.plist missing"
        exit 1
    fi
    echo "  ✓ Found: Info.plist"

    if [ ! -d "$APP_BUNDLE/Contents/MacOS" ]; then
        echo "✗ FAILED: MacOS directory missing"
        exit 1
    fi
    echo "  ✓ Found: MacOS directory"

    if [ ! -f "$APP_BUNDLE/Contents/MacOS/yanhu" ]; then
        echo "✗ FAILED: yanhu executable missing"
        exit 1
    fi
    echo "  ✓ Found: yanhu executable"

    echo "✓ macOS bundle structure validated"
    echo ""
else
    echo "[9/7] Skipping macOS bundle validation (not on macOS)"
    echo ""
fi

# Success summary
echo "============================================================"
echo "CI REHEARSAL PASSED"
echo "============================================================"
echo ""
echo "All checks completed successfully:"
echo "  ✓ ruff check"
echo "  ✓ pytest"
echo "  ✓ runtime self-check (--profile all)"
echo "  ✓ PyInstaller build"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  ✓ macOS bundle structure"
fi
echo ""
echo "Build artifacts:"
echo "  dist/Yanhu Sessions.app (macOS)"
echo "  dist/yanhu/ (Windows)"
echo ""
echo "Ready for release tagging!"
echo "============================================================"

# Cleanup: deactivate venv
deactivate
exit 0
