"""Session output verification and validation.

Validates that all required outputs exist and meet quality/consistency constraints.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def validate_progress_json(session_dir: Path) -> tuple[bool, str]:
    """Validate that progress.json exists and is valid.

    Args:
        session_dir: Path to session directory

    Returns:
        Tuple of (success, error_message). error_message is empty if success.
    """
    progress_file = session_dir / "outputs" / "progress.json"

    # Check file exists
    if not progress_file.exists():
        return False, "Missing required file: outputs/progress.json"

    # Load and parse JSON
    try:
        with open(progress_file, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"progress.json is not valid JSON: {e}"
    except OSError as e:
        return False, f"Failed to read progress.json: {e}"

    # Validate required fields
    required_fields = ["session_id", "stage", "done", "total", "elapsed_sec", "updated_at"]
    for field in required_fields:
        if field not in data:
            return False, f"progress.json missing required field: {field}"

    # Validate stage enum
    allowed_stages = {"transcribe", "compose", "done"}
    if data["stage"] not in allowed_stages:
        return (
            False,
            f"progress.json stage must be one of {allowed_stages}, got: {data['stage']}",
        )

    # Validate done/total are integers >= 0
    try:
        done = int(data["done"])
        total = int(data["total"])
    except (ValueError, TypeError):
        return False, "progress.json done/total must be integers"

    if done < 0:
        return False, f"progress.json done must be >= 0, got: {done}"
    if total < 0:
        return False, f"progress.json total must be >= 0, got: {total}"
    if done > total:
        return False, f"progress.json done ({done}) cannot exceed total ({total})"

    # Validate elapsed_sec >= 0
    try:
        elapsed = float(data["elapsed_sec"])
    except (ValueError, TypeError):
        return False, "progress.json elapsed_sec must be a number"

    if elapsed < 0:
        return False, f"progress.json elapsed_sec must be >= 0, got: {elapsed}"

    # Validate updated_at is ISO-8601 parseable
    try:
        datetime.fromisoformat(data["updated_at"])
    except (ValueError, TypeError) as e:
        return False, f"progress.json updated_at must be ISO-8601 format: {e}"

    # Validate done == total when stage is "done"
    if data["stage"] == "done" and done != total:
        return (
            False,
            f"progress.json stage is 'done' but done ({done}) != total ({total})",
        )

    return True, ""


def validate_partial_consistency(session_dir: Path) -> tuple[bool, str]:
    """Validate partial-by-limit consistency across manifest and overview.

    If manifest indicates transcribe_coverage (limits were applied),
    then overview must include PARTIAL marker and coverage stats.

    Args:
        session_dir: Path to session directory

    Returns:
        Tuple of (success, error_message). error_message is empty if success.
    """
    manifest_file = session_dir / "manifest.json"
    overview_file = session_dir / "overview.md"

    # Load manifest
    if not manifest_file.exists():
        return False, "Missing manifest.json"

    try:
        with open(manifest_file, encoding="utf-8") as f:
            manifest_data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"manifest.json is not valid JSON: {e}"
    except OSError as e:
        return False, f"Failed to read manifest.json: {e}"

    # Check if transcribe_coverage is present
    transcribe_coverage = manifest_data.get("transcribe_coverage")
    if transcribe_coverage is None:
        # No coverage metadata - this is a full session, no further checks needed
        return True, ""

    # Coverage is present - verify overview has PARTIAL marker and stats
    if not overview_file.exists():
        return False, "Missing overview.md"

    try:
        overview_content = overview_file.read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Failed to read overview.md: {e}"

    # Check for PARTIAL marker
    if "PARTIAL SESSION" not in overview_content:
        return (
            False,
            "manifest has transcribe_coverage but overview.md lacks PARTIAL SESSION marker",
        )

    # Check for coverage stats section
    if "Transcription Coverage" not in overview_content:
        return (
            False,
            "manifest has transcribe_coverage but overview.md lacks Transcription Coverage section",
        )

    # Verify coverage stats are present in overview
    processed = transcribe_coverage["processed"]
    total = transcribe_coverage["total"]
    skipped = transcribe_coverage["skipped_limit"]
    expected_stats = [
        f"Transcribed**: {processed}/{total} segments",
        f"Skipped**: {skipped} segments",
    ]
    for stat in expected_stats:
        if stat not in overview_content:
            return (
                False,
                f"overview.md missing expected coverage stat: {stat}",
            )

    # Optionally verify progress.json also has coverage (if present)
    progress_file = session_dir / "outputs" / "progress.json"
    if progress_file.exists():
        try:
            with open(progress_file, encoding="utf-8") as f:
                progress_data = json.load(f)

            # If progress has coverage, verify it matches manifest
            if "coverage" in progress_data:
                progress_coverage = progress_data["coverage"]
                if progress_coverage != transcribe_coverage:
                    return (
                        False,
                        f"progress.json coverage {progress_coverage} "
                        f"does not match manifest {transcribe_coverage}",
                    )
        except (json.JSONDecodeError, OSError):
            # progress.json issues will be caught by validate_progress_json
            pass

    return True, ""


def validate_outputs(session_dir: Path) -> tuple[bool, str]:
    """Validate that session outputs exist and meet all requirements.

    This is the main entry point for output validation, combining all checks:
    - Required markdown files exist and are non-empty
    - progress.json exists and is valid
    - partial-by-limit consistency (if applicable)

    Args:
        session_dir: Path to session directory

    Returns:
        Tuple of (success, error_message). error_message is empty if success.
    """
    # Check required files exist
    required_files = ["overview.md", "timeline.md", "highlights.md"]
    for filename in required_files:
        filepath = session_dir / filename
        if not filepath.exists():
            return False, f"Missing required output: {filename}"

    # Validate highlights.md has at least one highlight entry
    highlights_path = session_dir / "highlights.md"
    try:
        highlights_content = highlights_path.read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Failed to read highlights.md: {e}"

    if "- [" not in highlights_content:
        return False, "highlights.md contains no highlight entries (no '- [' line found)"

    # Validate timeline.md has content (segments or quotes)
    timeline_path = session_dir / "timeline.md"
    try:
        timeline_content = timeline_path.read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Failed to read timeline.md: {e}"

    if "### part_" not in timeline_content and "- quote:" not in timeline_content:
        return (
            False,
            "timeline.md contains no segment or quote content (no '### part_' or '- quote:' found)",
        )

    # NEW: Validate progress.json
    valid, error_msg = validate_progress_json(session_dir)
    if not valid:
        return False, error_msg

    # NEW: Validate partial-by-limit consistency
    valid, error_msg = validate_partial_consistency(session_dir)
    if not valid:
        return False, error_msg

    return True, ""
