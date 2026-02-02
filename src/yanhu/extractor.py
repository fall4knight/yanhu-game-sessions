"""Frame extraction from video segments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from yanhu.ffmpeg_utils import get_video_duration, run_ffmpeg
from yanhu.manifest import Manifest

if TYPE_CHECKING:
    from yanhu.transcriber import AsrItem


@dataclass
class SubtitleFocusedSample:
    """Result of subtitle-focused frame sampling."""

    timestamps: list[float]  # Timestamps to sample (segment-relative)
    asr_midpoints: list[float]  # ASR segment midpoints included
    boundary_offsets: list[float]  # Speech boundary samples included


def calculate_sample_timestamps(
    duration: float,
    num_frames: int,
) -> list[float]:
    """Calculate timestamps for frame sampling.

    Strategy:
    - Always include middle frame (50%)
    - Evenly distribute remaining frames across duration
    - Avoid duplicate timestamps

    Args:
        duration: Video duration in seconds
        num_frames: Number of frames to extract

    Returns:
        Sorted list of timestamps in seconds (no duplicates)
    """
    if duration <= 0 or num_frames <= 0:
        return []

    if num_frames == 1:
        return [duration / 2]

    # Generate evenly spaced timestamps including middle
    timestamps = set()

    # Always add middle frame
    middle = duration / 2
    timestamps.add(middle)

    # Add evenly distributed frames
    # Use num_frames + 1 divisions to avoid edge frames at exactly 0 or duration
    step = duration / (num_frames + 1)
    for i in range(1, num_frames + 1):
        t = step * i
        timestamps.add(t)

    # Sort and limit to num_frames
    sorted_timestamps = sorted(timestamps)[:num_frames]
    return sorted_timestamps


def calculate_subtitle_focused_timestamps(
    duration: float,
    segment_start: float,
    asr_items: list[AsrItem],
    base_frames: int = 8,
    boundary_offsets: tuple[float, ...] = (0.3, 0.8),
    min_spacing: float = 0.2,
) -> SubtitleFocusedSample:
    """Calculate timestamps optimized for subtitle capture.

    Strategy:
    1. Always include ASR segment midpoints (where subtitles are most stable)
    2. Add frames around speech boundaries (+/- offsets) to catch transition subtitles
    3. Fill remaining budget with evenly distributed samples
    4. Deduplicate and respect minimum spacing

    Args:
        duration: Segment duration in seconds
        segment_start: Segment start time (absolute, for converting ASR times)
        asr_items: ASR items with t_start/t_end (absolute times)
        base_frames: Minimum number of frames to sample
        boundary_offsets: Offsets from speech start/end (seconds)
        min_spacing: Minimum spacing between samples (seconds)

    Returns:
        SubtitleFocusedSample with timestamps and tracking info
    """
    if duration <= 0:
        return SubtitleFocusedSample(timestamps=[], asr_midpoints=[], boundary_offsets=[])

    timestamps: set[float] = set()
    asr_midpoints: list[float] = []
    boundary_samples: list[float] = []

    # Convert ASR items to segment-relative times and extract key points
    for asr_item in asr_items:
        # ASR times are absolute; convert to segment-relative
        rel_start = asr_item.t_start - segment_start
        rel_end = asr_item.t_end - segment_start

        # Skip if ASR item is outside this segment
        if rel_end < 0 or rel_start > duration:
            continue

        # Clamp to segment bounds
        rel_start = max(0, rel_start)
        rel_end = min(duration, rel_end)

        # Add t_start and t_end directly (key ASR boundaries)
        if 0 < rel_start < duration:
            timestamps.add(round(rel_start, 2))
            boundary_samples.append(round(rel_start, 2))
        if 0 < rel_end < duration:
            timestamps.add(round(rel_end, 2))
            boundary_samples.append(round(rel_end, 2))

        # Add midpoint of ASR segment (best chance for stable subtitle)
        midpoint = (rel_start + rel_end) / 2
        if 0 < midpoint < duration:
            timestamps.add(round(midpoint, 2))
            asr_midpoints.append(round(midpoint, 2))

        # Add boundary samples for subtitle transitions (+/- offsets)
        for offset in boundary_offsets:
            # Just after speech starts
            t_after_start = rel_start + offset
            if 0 < t_after_start < duration:
                timestamps.add(round(t_after_start, 2))
                boundary_samples.append(round(t_after_start, 2))

            # Just before speech ends
            t_before_end = rel_end - offset
            if 0 < t_before_end < duration:
                timestamps.add(round(t_before_end, 2))
                boundary_samples.append(round(t_before_end, 2))

    # Always include middle frame
    middle = duration / 2
    timestamps.add(round(middle, 2))

    # First pass: apply min_spacing to ASR-derived timestamps
    sorted_ts = sorted(timestamps)
    spaced_timestamps: list[float] = []
    last_t = -min_spacing  # Allow first sample

    for t in sorted_ts:
        if t - last_t >= min_spacing:
            spaced_timestamps.append(t)
            last_t = t

    # Second pass: fill remaining slots with evenly distributed samples
    if len(spaced_timestamps) < base_frames:
        fill_needed = base_frames - len(spaced_timestamps)
        # Generate more candidates than needed to account for conflicts
        num_candidates = max(fill_needed * 3, base_frames * 2)
        step = duration / (num_candidates + 1)

        added = 0
        for i in range(1, num_candidates + 1):
            if added >= fill_needed:
                break
            candidate = round(step * i, 2)
            # Check if candidate is far enough from all existing timestamps
            too_close = any(abs(candidate - t) < min_spacing for t in spaced_timestamps)
            if not too_close and 0 < candidate < duration:
                spaced_timestamps.append(candidate)
                added += 1

        # Re-sort after adding fills
        spaced_timestamps.sort()

    return SubtitleFocusedSample(
        timestamps=spaced_timestamps,
        asr_midpoints=asr_midpoints,
        boundary_offsets=boundary_samples,
    )


def generate_frame_filename(index: int) -> str:
    """Generate frame filename with 4-digit zero-padding.

    Args:
        index: 1-based frame index

    Returns:
        Filename like "frame_0001.jpg"
    """
    return f"frame_{index:04d}.jpg"


def generate_frame_path(segment_id: str, index: int) -> str:
    """Generate relative path for a frame.

    Args:
        segment_id: Segment ID (e.g., "part_0001")
        index: 1-based frame index

    Returns:
        Relative path like "frames/part_0001/frame_0001.jpg"
    """
    filename = generate_frame_filename(index)
    return f"frames/{segment_id}/{filename}"


def build_extract_frame_command(
    input_path: Path,
    output_path: Path,
    timestamp: float,
) -> list[str]:
    """Build ffmpeg command to extract a single frame.

    Args:
        input_path: Source video path
        output_path: Output frame path (JPEG)
        timestamp: Time in seconds to extract frame

    Returns:
        List of ffmpeg arguments (excluding 'ffmpeg' itself)
    """
    return [
        "-y",  # overwrite output
        "-ss",
        f"{timestamp:.3f}",  # seek to timestamp
        "-i",
        str(input_path),
        "-frames:v",
        "1",  # extract 1 frame
        "-q:v",
        "2",  # high quality JPEG
        str(output_path),
    ]


def extract_frames_from_segment(
    segment_video_path: Path,
    output_dir: Path,
    segment_id: str,
    num_frames: int,
    *,
    asr_items: list[AsrItem] | None = None,
    segment_start: float = 0.0,
) -> list[str]:
    """Extract frames from a single segment.

    Args:
        segment_video_path: Path to segment video
        output_dir: Session directory (frames will be in output_dir/frames/<segment_id>/)
        segment_id: Segment ID for path naming
        num_frames: Number of frames to extract
        asr_items: Optional ASR items for subtitle-focused sampling
        segment_start: Segment start time (absolute) for ASR time conversion

    Returns:
        List of relative paths to extracted frames
    """
    # Get segment duration
    duration = get_video_duration(segment_video_path)

    # Calculate sampling timestamps
    if asr_items:
        # Use subtitle-focused sampling when ASR data is available
        sample_result = calculate_subtitle_focused_timestamps(
            duration=duration,
            segment_start=segment_start,
            asr_items=asr_items,
            base_frames=num_frames,
        )
        timestamps = sample_result.timestamps
    else:
        # Fall back to uniform sampling
        timestamps = calculate_sample_timestamps(duration, num_frames)

    # Create output directory
    frames_dir = output_dir / "frames" / segment_id
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_paths = []
    for i, timestamp in enumerate(timestamps, start=1):
        filename = generate_frame_filename(i)
        output_path = frames_dir / filename
        relative_path = generate_frame_path(segment_id, i)

        # Build and run ffmpeg command
        cmd_args = build_extract_frame_command(segment_video_path, output_path, timestamp)
        run_ffmpeg(cmd_args)

        frame_paths.append(relative_path)

    return frame_paths


def extract_frames(
    manifest: Manifest,
    session_dir: Path,
    frames_per_segment: int = 8,
    *,
    asr_results: dict[str, list[AsrItem]] | None = None,
) -> None:
    """Extract frames from all segments and update manifest.

    Args:
        manifest: Session manifest (will be modified in place)
        session_dir: Path to session directory
        frames_per_segment: Number of frames to extract per segment
        asr_results: Optional dict mapping segment_id -> list of AsrItem
                     for subtitle-focused sampling
    """
    for segment in manifest.segments:
        segment_video_path = session_dir / segment.video_path

        if not segment_video_path.exists():
            raise FileNotFoundError(f"Segment video not found: {segment_video_path}")

        # Get ASR items for this segment if available
        segment_asr = asr_results.get(segment.id) if asr_results else None

        frame_paths = extract_frames_from_segment(
            segment_video_path=segment_video_path,
            output_dir=session_dir,
            segment_id=segment.id,
            num_frames=frames_per_segment,
            asr_items=segment_asr,
            segment_start=segment.start_time,
        )

        # Update segment with frame paths
        segment.frames = frame_paths
