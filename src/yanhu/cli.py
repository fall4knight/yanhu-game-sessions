"""Yanhu CLI - Main entry point."""

from pathlib import Path

import click

from yanhu import __version__
from yanhu.analyzer import analyze_session
from yanhu.composer import write_overview, write_timeline
from yanhu.extractor import extract_frames
from yanhu.ffmpeg_utils import FFmpegError, FFmpegNotFoundError, check_ffmpeg_available
from yanhu.manifest import Manifest, create_manifest
from yanhu.segmenter import segment_video
from yanhu.session import (
    copy_source_video,
    create_session_directory,
    generate_session_id,
)


@click.group()
@click.version_option(version=__version__, prog_name="yanhu")
def main():
    """Yanhu Game Sessions - Post-game replay companion.

    Process game recordings into structured timelines and highlights.
    """
    pass


@main.command()
@click.option("--video", "-v", required=True, type=click.Path(exists=True), help="Video file path")
@click.option("--game", "-g", required=True, help="Game name (e.g., gnosia, genshin)")
@click.option("--tag", "-t", required=True, help="Run tag (e.g., run01, session02)")
@click.option("--output-dir", "-o", default="sessions", help="Output directory (default: sessions)")
@click.option("--segment-duration", "-d", default=60, help="Segment duration in seconds")
def ingest(video: str, game: str, tag: str, output_dir: str, segment_duration: int):
    """Ingest a video file and create a new session.

    Creates session directory, copies source video, and writes manifest.
    """
    video_path = Path(video)
    output_path = Path(output_dir)

    # Generate session ID
    session_id = generate_session_id(game, tag)
    click.echo(f"Creating session: {session_id}")

    # Create session directory structure
    session_dir = create_session_directory(session_id, output_path)
    click.echo(f"Session directory: {session_dir}")

    # Copy source video
    click.echo(f"Copying source video: {video_path.name}")
    source_local = copy_source_video(video_path, session_dir)

    # Create and save manifest
    manifest = create_manifest(
        session_id=session_id,
        source_video=video_path,
        source_video_local=str(source_local),
        segment_duration=segment_duration,
    )
    manifest_path = manifest.save(session_dir)
    click.echo(f"Manifest saved: {manifest_path}")

    click.echo("\nSession created successfully!")
    click.echo(f"  Session ID: {session_id}")
    click.echo(f"  Next step:  yanhu segment --session {session_id} --output-dir {output_dir}")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID to segment")
@click.option("--output-dir", "-o", default="sessions", help="Output directory (default: sessions)")
@click.option("--segment-duration", "-d", type=int, help="Override segment duration (seconds)")
def segment(session: str, output_dir: str, segment_duration: int | None):
    """Segment a session's video into chunks.

    Reads manifest, runs ffmpeg to split video, and updates manifest.
    """
    session_dir = Path(output_dir) / session

    # Check session exists
    if not session_dir.exists():
        raise click.ClickException(f"Session not found: {session_dir}")

    # Check ffmpeg
    try:
        ffmpeg_path = check_ffmpeg_available()
        click.echo(f"Using ffmpeg: {ffmpeg_path}")
    except FFmpegNotFoundError as e:
        raise click.ClickException(str(e))

    # Load manifest
    try:
        manifest = Manifest.load(session_dir)
    except FileNotFoundError:
        raise click.ClickException(f"Manifest not found in {session_dir}")

    # Override segment duration if specified
    if segment_duration is not None:
        manifest.segment_duration_seconds = segment_duration
        click.echo(f"Segment duration: {segment_duration}s (overridden)")
    else:
        click.echo(f"Segment duration: {manifest.segment_duration_seconds}s")

    # Run segmentation
    click.echo(f"Segmenting: {manifest.source_video_local}")
    try:
        segment_infos = segment_video(manifest, session_dir)
    except FFmpegError as e:
        raise click.ClickException(f"Segmentation failed: {e}")

    # Update manifest with segments
    manifest.segments = segment_infos
    manifest.save(session_dir)

    click.echo("\nSegmentation complete!")
    click.echo(f"  Segments created: {len(segment_infos)}")
    for seg in segment_infos:
        click.echo(f"    {seg.id}: {seg.start_time:.1f}s - {seg.end_time:.1f}s -> {seg.video_path}")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--output-dir", "-o", default="sessions", help="Output directory (default: sessions)")
@click.option("--frames-per-segment", "-n", default=8, help="Frames to extract per segment")
def extract(session: str, output_dir: str, frames_per_segment: int):
    """Extract key frames from each segment.

    Extracts frames from segment videos and updates manifest with frame paths.
    """
    session_dir = Path(output_dir) / session

    # Check session exists
    if not session_dir.exists():
        raise click.ClickException(f"Session not found: {session_dir}")

    # Check ffmpeg
    try:
        ffmpeg_path = check_ffmpeg_available()
        click.echo(f"Using ffmpeg: {ffmpeg_path}")
    except FFmpegNotFoundError as e:
        raise click.ClickException(str(e))

    # Load manifest
    try:
        manifest = Manifest.load(session_dir)
    except FileNotFoundError:
        raise click.ClickException(f"Manifest not found in {session_dir}")

    # Check segments exist
    if not manifest.segments:
        raise click.ClickException("No segments found. Run 'yanhu segment' first.")

    click.echo(f"Extracting {frames_per_segment} frames per segment...")
    click.echo(f"  Segments to process: {len(manifest.segments)}")

    # Run extraction
    try:
        extract_frames(manifest, session_dir, frames_per_segment)
    except FFmpegError as e:
        raise click.ClickException(f"Frame extraction failed: {e}")
    except FileNotFoundError as e:
        raise click.ClickException(str(e))

    # Save updated manifest
    manifest.save(session_dir)

    # Summary
    total_frames = sum(len(seg.frames) for seg in manifest.segments)
    click.echo("\nExtraction complete!")
    click.echo(f"  Total frames extracted: {total_frames}")
    for seg in manifest.segments:
        click.echo(f"    {seg.id}: {len(seg.frames)} frames")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--output-dir", "-o", default="sessions", help="Output directory (default: sessions)")
@click.option("--backend", "-b", default="mock", help="Analysis backend (default: mock)")
def analyze(session: str, output_dir: str, backend: str):
    """Analyze segments using vision/ASR models.

    Generates analysis JSON files for each segment with scene classification and captions.
    """
    session_dir = Path(output_dir) / session

    # Check session exists
    if not session_dir.exists():
        raise click.ClickException(f"Session not found: {session_dir}")

    # Load manifest
    try:
        manifest = Manifest.load(session_dir)
    except FileNotFoundError:
        raise click.ClickException(f"Manifest not found in {session_dir}")

    # Check segments exist
    if not manifest.segments:
        raise click.ClickException("No segments found. Run 'yanhu segment' first.")

    click.echo(f"Analyzing session: {manifest.session_id}")
    click.echo(f"  Backend: {backend}")
    click.echo(f"  Segments: {len(manifest.segments)}")

    # Run analysis
    try:
        analyze_session(manifest, session_dir, backend)
    except ValueError as e:
        raise click.ClickException(str(e))

    # Save updated manifest
    manifest.save(session_dir)

    click.echo("\nAnalysis complete!")
    for seg in manifest.segments:
        click.echo(f"  {seg.id}: {seg.analysis_path}")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--output-dir", "-o", default="sessions", help="Output directory (default: sessions)")
def compose(session: str, output_dir: str):
    """Compose timeline and overview from session data.

    Generates timeline.md and overview.md, using analysis captions if available.
    """
    session_dir = Path(output_dir) / session

    # Check session exists
    if not session_dir.exists():
        raise click.ClickException(f"Session not found: {session_dir}")

    # Load manifest
    try:
        manifest = Manifest.load(session_dir)
    except FileNotFoundError:
        raise click.ClickException(f"Manifest not found in {session_dir}")

    # Check segments exist
    if not manifest.segments:
        raise click.ClickException("No segments found. Run 'yanhu segment' first.")

    click.echo(f"Composing session: {manifest.session_id}")
    click.echo(f"  Segments: {len(manifest.segments)}")

    # Write timeline
    timeline_path = write_timeline(manifest, session_dir)
    click.echo(f"  Written: {timeline_path.name}")

    # Write overview
    overview_path = write_overview(manifest, session_dir)
    click.echo(f"  Written: {overview_path.name}")

    click.echo("\nComposition complete!")
    click.echo("  Note: Descriptions are placeholders. Run Vision/ASR analysis to fill them.")


if __name__ == "__main__":
    main()
