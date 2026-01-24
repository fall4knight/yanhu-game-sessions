#!/bin/bash
# Build desktop application packages using PyInstaller

set -e

echo "Building Yanhu Sessions desktop app..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "ERROR: PyInstaller not found. Install with: pip install pyinstaller"
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/

# Build using spec file
echo "Running PyInstaller..."
pyinstaller yanhu.spec

# Show results
echo ""
echo "Build complete!"
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS app created at: dist/Yanhu Sessions.app"
    echo "You can run it by double-clicking, or from terminal:"
    echo "  open 'dist/Yanhu Sessions.app'"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    echo "Windows executable created at: dist/yanhu/yanhu.exe"
    echo "You can run it by double-clicking yanhu.exe"
else
    echo "Linux build created at: dist/yanhu/"
    echo "You can run it with: ./dist/yanhu/yanhu"
fi

echo ""
echo "NOTE: The built app does NOT include ffmpeg."
echo "Users must install ffmpeg separately for video processing."
