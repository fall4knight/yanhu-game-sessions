#!/usr/bin/env python3
"""Runtime self-check for Yanhu dependencies.

Verifies that required runtime dependencies are present and importable.
Supports profile-based checking (core, app, desktop, asr, all).

Exit codes:
- 0: All dependencies present
- 1: One or more dependencies missing
"""

from __future__ import annotations

import argparse
import sys

# Profile definitions (aligned with docs/DEPENDENCY_MATRIX.md)
PROFILES = {
    "core": {
        "description": "Core pipeline (segment, extract, analyze, compose, verify)",
        "modules": [
            "click",
            "ffmpeg",  # ffmpeg-python
            "yaml",  # pyyaml
            "anthropic",
            "emoji",
            "yanhu.session",
            "yanhu.manifest",
            "yanhu.segmenter",
            "yanhu.extractor",
            "yanhu.analyzer",
            "yanhu.composer",
            "yanhu.verify",
            "yanhu.metrics",
            "yanhu.ffmpeg_utils",
        ],
    },
    "app": {
        "description": "Web UI (Flask)",
        "modules": [
            "flask",
            "markdown",
            "jinja2",
            "werkzeug",
            "yanhu.app",
            "yanhu.cli",
        ],
    },
    "asr": {
        "description": "ASR transcription (Whisper local)",
        "modules": [
            "faster_whisper",
            "av",
            "ctranslate2",
            "tokenizers",
            "huggingface_hub",
            "onnxruntime",
            "tqdm",
            "tiktoken",
            "regex",
            "safetensors",
            "yanhu.transcriber",
            "yanhu.asr_registry",
        ],
    },
    "desktop": {
        "description": "Desktop packaging (PyInstaller launcher)",
        "modules": [
            "yanhu.launcher",
            "yanhu.watcher",
            "yanhu.progress",
            "yanhu.aligner",
        ],
    },
}


def get_modules_for_profile(profile: str) -> list[str]:
    """Get list of modules to check for a given profile.

    Args:
        profile: Profile name (core, app, desktop, asr, all)

    Returns:
        List of module names to import
    """
    if profile == "all":
        # Union of all profiles
        all_modules = set()
        for p in PROFILES.values():
            all_modules.update(p["modules"])
        return sorted(all_modules)
    elif profile in PROFILES:
        return PROFILES[profile]["modules"]
    else:
        raise ValueError(f"Unknown profile: {profile}. Valid: {', '.join(PROFILES.keys())}, all")


def check_imports(modules: list[str]) -> tuple[list[str], list[str]]:
    """Check if modules can be imported.

    Args:
        modules: List of module names to check

    Returns:
        Tuple of (successful_imports, failed_imports)
    """
    successful = []
    failed = []

    for module_name in modules:
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
    # Attempt to set UTF-8 encoding for Windows compatibility
    # (but we still use ASCII symbols for maximum robustness)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass  # Silently continue with default encoding

    parser = argparse.ArgumentParser(
        description="Runtime dependency self-check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Profiles:
  core     - Core pipeline (segment, extract, analyze, compose, verify)
  app      - Web UI (Flask)
  asr      - ASR transcription (Whisper local)
  desktop  - Desktop packaging (PyInstaller launcher)
  all      - All profiles (union)

Examples:
  python scripts/runtime_selfcheck.py --profile core
  python scripts/runtime_selfcheck.py --profile all
        """,
    )
    parser.add_argument(
        "--profile",
        default="all",
        choices=list(PROFILES.keys()) + ["all"],
        help="Dependency profile to check (default: all)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(f"Yanhu Runtime Self-Check - Profile: {args.profile}")
    print("=" * 60)

    if args.profile in PROFILES:
        print(f"Description: {PROFILES[args.profile]['description']}")
    elif args.profile == "all":
        print("Description: All profiles (complete dependency set)")
    print()

    try:
        modules = get_modules_for_profile(args.profile)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    successful, failed = check_imports(modules)

    print(f"[OK] Successful imports: {len(successful)}/{len(modules)}")
    print(f"[FAIL] Failed imports: {len(failed)}")
    print()

    if failed:
        print("FAILED IMPORTS:")
        print("-" * 60)
        for failure in failed:
            print(f"  [FAIL] {failure}")
        print()
        print("=" * 60)
        print(f"SELF-CHECK FAILED: Missing dependencies for profile '{args.profile}'")
        print("=" * 60)
        print()
        print("See docs/DEPENDENCY_MATRIX.md for installation instructions.")
        return 1

    print("=" * 60)
    print(f"SELF-CHECK PASSED: All dependencies present for profile '{args.profile}'")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
