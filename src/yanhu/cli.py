"""Yanhu CLI - Main entry point."""

from pathlib import Path

import click

from yanhu import __version__
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
def extract(session: str, output_dir: str):
    """Extract key frames from each segment."""
    click.echo(f"[extract] Not implemented yet. session={session}")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--output-dir", "-o", default="sessions", help="Output directory (default: sessions)")
def compose(session: str, output_dir: str):
    """Compose final timeline and highlights from session data."""
    click.echo(f"[compose] Not implemented yet. session={session}")


if __name__ == "__main__":
    main()
