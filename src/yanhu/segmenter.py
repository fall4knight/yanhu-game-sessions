"""Video segmentation using ffmpeg."""

from pathlib import Path

from yanhu.ffmpeg_utils import get_video_duration, run_ffmpeg
from yanhu.manifest import Manifest, SegmentInfo


def generate_segment_id(index: int) -> str:
    """Generate segment ID with 4-digit zero-padded index.

    Args:
        index: 1-based segment index

    Returns:
        Segment ID like "part_0001"
    """
    return f"part_{index:04d}"


def generate_segment_filename(session_id: str, index: int) -> str:
    """Generate segment filename.

    Args:
        session_id: The session identifier
        index: 1-based segment index

    Returns:
        Filename like "<session_id>_part_0001.mp4"
    """
    segment_id = generate_segment_id(index)
    return f"{session_id}_{segment_id}.mp4"


def calculate_segments(
    total_duration: float,
    segment_duration: int,
) -> list[tuple[float, float]]:
    """Calculate segment start/end times.

    Args:
        total_duration: Total video duration in seconds
        segment_duration: Target segment duration in seconds

    Returns:
        List of (start_time, end_time) tuples
    """
    segments = []
    start = 0.0
    while start < total_duration:
        end = min(start + segment_duration, total_duration)
        segments.append((start, end))
        start = end
    return segments


def build_segment_command(
    input_path: Path,
    output_path: Path,
    start_time: float,
    duration: float,
) -> list[str]:
    """Build ffmpeg command for extracting a segment.

    Args:
        input_path: Source video path
        output_path: Output segment path
        start_time: Start time in seconds
        duration: Segment duration in seconds

    Returns:
        List of ffmpeg arguments (excluding 'ffmpeg' itself)
    """
    return [
        "-y",  # overwrite output
        "-ss", str(start_time),
        "-i", str(input_path),
        "-t", str(duration),
        "-c", "copy",  # copy streams without re-encoding
        "-avoid_negative_ts", "make_zero",
        str(output_path),
    ]


def segment_video(
    manifest: Manifest,
    session_dir: Path,
) -> list[SegmentInfo]:
    """Segment video according to manifest settings.

    Args:
        manifest: Session manifest with source video info
        session_dir: Path to session directory

    Returns:
        List of SegmentInfo for each created segment
    """
    source_path = session_dir / manifest.source_video_local
    segments_dir = session_dir / "segments"
    segment_duration = manifest.segment_duration_seconds

    # Get video duration
    total_duration = get_video_duration(source_path)

    # Calculate segment boundaries
    time_ranges = calculate_segments(total_duration, segment_duration)

    segment_infos = []
    for index, (start_time, end_time) in enumerate(time_ranges, start=1):
        segment_id = generate_segment_id(index)
        filename = generate_segment_filename(manifest.session_id, index)
        output_path = segments_dir / filename

        # Build and run ffmpeg command
        duration = end_time - start_time
        cmd_args = build_segment_command(source_path, output_path, start_time, duration)
        run_ffmpeg(cmd_args)

        # Create segment info with relative path
        segment_info = SegmentInfo(
            id=segment_id,
            start_time=start_time,
            end_time=end_time,
            video_path=f"segments/{filename}",
        )
        segment_infos.append(segment_info)

    return segment_infos
