#!/usr/bin/env python3
"""Runtime self-check for packaged desktop app.

Verifies that all required runtime dependencies are present and importable.
This should be run:
1. Before packaging (to catch missing deps in dev)
2. After packaging (to verify bundled deps)

Exit codes:
- 0: All dependencies present
- 1: One or more dependencies missing
"""

from __future__ import annotations

import sys


def check_imports() -> tuple[list[str], list[str]]:
    """Check all required runtime imports.

    Returns:
        Tuple of (successful_imports, failed_imports)
    """
    # Core dependencies (always required)
    core_modules = [
        "click",
        "ffmpeg",  # ffmpeg-python
        "yaml",  # pyyaml
        "anthropic",
        "emoji",
    ]

    # App dependencies (Flask ecosystem)
    app_modules = [
        "flask",
        "markdown",
        "jinja2",
        "werkzeug",
    ]

    # ASR dependencies (faster-whisper and transitive deps)
    asr_modules = [
        "faster_whisper",
        "av",
        "ctranslate2",
        "tokenizers",
        "huggingface_hub",
        "onnxruntime",
        "tqdm",
    ]

    # Additional submodules that may be dynamically imported
    additional_modules = [
        "tiktoken",
        "regex",
        "safetensors",
    ]

    # Yanhu internal modules
    yanhu_modules = [
        "yanhu.app",
        "yanhu.cli",
        "yanhu.session",
        "yanhu.manifest",
        "yanhu.segmenter",
        "yanhu.extractor",
        "yanhu.analyzer",
        "yanhu.transcriber",
        "yanhu.aligner",
        "yanhu.composer",
        "yanhu.watcher",
        "yanhu.progress",
        "yanhu.verify",
        "yanhu.metrics",
        "yanhu.asr_registry",
        "yanhu.ffmpeg_utils",
    ]

    all_modules = (
        core_modules + app_modules + asr_modules + additional_modules + yanhu_modules
    )

    successful = []
    failed = []

    for module_name in all_modules:
        try:
            __import__(module_name)
            successful.append(module_name)
        except ImportError as e:
            failed.append(f"{module_name}: {e}")

    return successful, failed


def main() -> int:
    """Run self-check and report results.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("=" * 60)
    print("Yanhu Desktop App - Runtime Self-Check")
    print("=" * 60)
    print()

    successful, failed = check_imports()

    print(f"✓ Successful imports: {len(successful)}")
    print(f"✗ Failed imports: {len(failed)}")
    print()

    if failed:
        print("FAILED IMPORTS:")
        print("-" * 60)
        for failure in failed:
            print(f"  ✗ {failure}")
        print()
        print("=" * 60)
        print("SELF-CHECK FAILED: Missing runtime dependencies")
        print("=" * 60)
        return 1

    print("=" * 60)
    print("SELF-CHECK PASSED: All runtime dependencies present")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
