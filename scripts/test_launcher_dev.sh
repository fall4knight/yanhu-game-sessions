#!/bin/bash
# Smoke test for desktop launcher in dev mode

set -e

echo "Testing desktop launcher (dev mode)..."
echo ""
echo "This will:"
echo "  1. Check ffmpeg availability"
echo "  2. Create default directories"
echo "  3. Start the Flask app"
echo "  4. Open browser at http://127.0.0.1:8787"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the launcher
python -m yanhu.launcher
