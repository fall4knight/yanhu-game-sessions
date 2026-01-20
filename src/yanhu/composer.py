"""Session composition: generate timeline and overview documents."""

from pathlib import Path

from yanhu.manifest import Manifest


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "00:01:30" for 90 seconds
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_time_range(start: float, end: float) -> str:
    """Format a time range as HH:MM:SS - HH:MM:SS.

    Args:
        start: Start time in seconds
        end: End time in seconds

    Returns:
        Formatted string like "00:00:00 - 00:01:00"
    """
    return f"{format_timestamp(start)} - {format_timestamp(end)}"


def format_frames_list(frames: list[str], max_display: int = 3) -> str:
    """Format frames list as markdown links.

    Args:
        frames: List of relative frame paths
        max_display: Maximum frames to show before truncating

    Returns:
        Markdown formatted string with frame links
    """
    if not frames:
        return "_No frames extracted_"

    displayed = frames[:max_display]
    links = [f"[{Path(f).name}]({f})" for f in displayed]

    result = ", ".join(links)
    remaining = len(frames) - max_display
    if remaining > 0:
        result += f" ... ({remaining} more)"

    return result


def compose_timeline(manifest: Manifest) -> str:
    """Generate timeline markdown from manifest.

    Args:
        manifest: Session manifest with segments

    Returns:
        Markdown content for timeline.md
    """
    lines = [
        f"# Timeline: {manifest.session_id}",
        "",
        f"**Session**: {manifest.session_id}",
        f"**Segments**: {len(manifest.segments)}",
        "",
        "---",
        "",
        "## Timeline",
        "",
    ]

    for seg in manifest.segments:
        time_range = format_time_range(seg.start_time, seg.end_time)
        frames_str = format_frames_list(seg.frames)

        lines.extend([
            f"### {seg.id} ({time_range})",
            "",
            f"**Frames**: {frames_str}",
            "",
            "> TODO: describe what happened",
            "",
        ])

    return "\n".join(lines)


def compose_overview(manifest: Manifest) -> str:
    """Generate overview markdown from manifest.

    Args:
        manifest: Session manifest

    Returns:
        Markdown content for overview.md
    """
    # Parse session_id to extract game name
    parts = manifest.session_id.split("_")
    game_name = parts[2] if len(parts) >= 3 else "Unknown"
    run_tag = parts[3] if len(parts) >= 4 else "Unknown"

    # Calculate total duration from segments
    if manifest.segments:
        total_duration = max(seg.end_time for seg in manifest.segments)
    else:
        total_duration = 0.0

    total_frames = sum(len(seg.frames) for seg in manifest.segments)

    lines = [
        f"# Overview: {manifest.session_id}",
        "",
        "## Session Info",
        "",
        f"- **Game**: {game_name}",
        f"- **Run Tag**: {run_tag}",
        f"- **Duration**: {format_timestamp(total_duration)}",
        f"- **Segments**: {len(manifest.segments)}",
        f"- **Total Frames**: {total_frames}",
        f"- **Created**: {manifest.created_at}",
        "",
        "## Summary",
        "",
        "> TODO: AI-generated summary will appear here after Vision/ASR analysis.",
        "",
        "## Outcome",
        "",
        "> TODO: Session outcome (win/loss/progress) to be determined.",
        "",
    ]

    return "\n".join(lines)


def write_timeline(manifest: Manifest, session_dir: Path) -> Path:
    """Write timeline.md to session directory.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory

    Returns:
        Path to written timeline.md
    """
    content = compose_timeline(manifest)
    output_path = session_dir / "timeline.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def write_overview(manifest: Manifest, session_dir: Path) -> Path:
    """Write overview.md to session directory.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory

    Returns:
        Path to written overview.md
    """
    content = compose_overview(manifest)
    output_path = session_dir / "overview.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path
