"""Frame extraction from video segments."""

from pathlib import Path

from yanhu.ffmpeg_utils import get_video_duration, run_ffmpeg
from yanhu.manifest import Manifest


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
) -> list[str]:
    """Extract frames from a single segment.

    Args:
        segment_video_path: Path to segment video
        output_dir: Session directory (frames will be in output_dir/frames/<segment_id>/)
        segment_id: Segment ID for path naming
        num_frames: Number of frames to extract

    Returns:
        List of relative paths to extracted frames
    """
    # Get segment duration
    duration = get_video_duration(segment_video_path)

    # Calculate sampling timestamps
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
) -> None:
    """Extract frames from all segments and update manifest.

    Args:
        manifest: Session manifest (will be modified in place)
        session_dir: Path to session directory
        frames_per_segment: Number of frames to extract per segment
    """
    for segment in manifest.segments:
        segment_video_path = session_dir / segment.video_path

        if not segment_video_path.exists():
            raise FileNotFoundError(f"Segment video not found: {segment_video_path}")

        frame_paths = extract_frames_from_segment(
            segment_video_path=segment_video_path,
            output_dir=session_dir,
            segment_id=segment.id,
            num_frames=frames_per_segment,
        )

        # Update segment with frame paths
        segment.frames = frame_paths
