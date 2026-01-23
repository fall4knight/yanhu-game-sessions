"""Yanhu CLI - Main entry point."""

from pathlib import Path

import click

from yanhu import __version__
from yanhu.aligner import align_segment, merge_aligned_quotes_to_analysis
from yanhu.analyzer import analyze_session
from yanhu.composer import (
    has_valid_claude_analysis,
    write_highlights,
    write_overview,
    write_timeline,
)
from yanhu.extractor import extract_frames
from yanhu.ffmpeg_utils import FFmpegError, FFmpegNotFoundError, check_ffmpeg_available
from yanhu.manifest import Manifest, create_manifest
from yanhu.segmenter import segment_video
from yanhu.session import (
    copy_source_video,
    create_session_directory,
    generate_session_id,
)
from yanhu.transcriber import transcribe_session


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
@click.option("--output-dir", "-o", default="sessions", help="Output directory")
@click.option("--backend", "-b", default="mock", type=click.Choice(["mock", "claude"]))
@click.option("--max-frames", "-n", default=3, help="Max frames per segment (default: 3)")
@click.option("--max-facts", default=3, help="Max facts per segment (default: 3)")
@click.option(
    "--detail-level",
    default="L1",
    type=click.Choice(["L0", "L1"]),
    help="L0=basic, L1=enhanced with scene_label/what_changed (default: L1)",
)
@click.option("--force", "-f", is_flag=True, help="Re-analyze even if analysis exists")
@click.option("--dry-run", is_flag=True, help="Show stats without running analysis")
@click.option("--limit", "-l", type=int, help="Only process first N segments")
@click.option("--segments", help="Comma-separated segment IDs to process")
def analyze(
    session: str,
    output_dir: str,
    backend: str,
    max_frames: int,
    max_facts: int,
    detail_level: str,
    force: bool,
    dry_run: bool,
    limit: int | None,
    segments: str | None,
):
    """Analyze segments using vision/ASR models.

    Generates analysis JSON files for each segment with scene classification and captions.

    Examples:

      yanhu analyze -s demo --backend mock

      yanhu analyze -s demo --backend claude --dry-run

      yanhu analyze -s demo --backend claude --limit 1

      yanhu analyze -s demo --backend claude --segments part_0001,part_0002
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

    # Parse segment filter
    segment_list = None
    if segments:
        segment_list = [s.strip() for s in segments.split(",")]

    click.echo(f"Analyzing session: {manifest.session_id}")
    click.echo(f"  Backend: {backend}")
    click.echo(f"  Max frames: {max_frames}")
    click.echo(f"  Max facts: {max_facts}")
    click.echo(f"  Detail level: {detail_level}")
    click.echo(f"  Total segments: {len(manifest.segments)}")
    if force:
        click.echo("  Force: enabled (ignoring cache)")
    if limit:
        click.echo(f"  Limit: {limit} segments")
    if segment_list:
        click.echo(f"  Filter: {segment_list}")

    # Progress callback
    def on_progress(segment_id: str, status: str, result):
        if status == "cached":
            click.echo(f"  {segment_id}: cached (skipped)")
        elif status == "done":
            if result.error:
                click.echo(f"  {segment_id}: error - {result.error}")
            else:
                click.echo(f"  {segment_id}: {result.scene_type}")
        elif status == "error":
            click.echo(f"  {segment_id}: error - {result.error}")

    # Run analysis
    try:
        stats = analyze_session(
            manifest,
            session_dir,
            backend,
            max_frames=max_frames,
            max_facts=max_facts,
            detail_level=detail_level,
            force=force,
            dry_run=dry_run,
            limit=limit,
            segments=segment_list,
            on_progress=on_progress,
        )
    except ValueError as e:
        raise click.ClickException(str(e))

    # Save updated manifest (skip if dry-run)
    if not dry_run:
        manifest.save(session_dir)

    # Summary
    click.echo("")
    if dry_run:
        click.echo("Dry-run summary:")
        click.echo("")

        # Segment lists
        if stats.will_process:
            click.echo(f"  Will process:   [{', '.join(stats.will_process)}]")
        else:
            click.echo("  Will process:   []")

        if stats.cached_skip:
            click.echo(f"  Cached skip:    [{', '.join(stats.cached_skip)}]")
        else:
            click.echo("  Cached skip:    []")

        if stats.filtered_skip:
            click.echo(f"  Filtered skip:  [{', '.join(stats.filtered_skip)}]")
        else:
            click.echo("  Filtered skip:  []")

        click.echo("")

        # Cost estimation
        click.echo("Cost estimation:")
        click.echo(f"  API calls:      {stats.api_calls}")
        click.echo(f"  Images/call:    {stats.max_frames}")
        click.echo(f"  Total images:   {stats.total_images}")
    else:
        click.echo("Analysis complete!")
        click.echo(f"  Processed: {stats.processed}")
        click.echo(f"  Skipped (cached): {stats.skipped_cache}")
        click.echo(f"  Skipped (filtered): {stats.skipped_filter}")
        if stats.errors:
            click.echo(f"  Errors: {stats.errors}")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--output-dir", "-o", default="sessions", help="Output directory")
@click.option("--backend", "-b", default="mock", type=click.Choice(["mock", "whisper_local"]))
@click.option("--max-seconds", type=int, help="Max audio seconds per segment")
@click.option("--force", "-f", is_flag=True, help="Re-transcribe even if ASR exists")
@click.option("--limit", "-l", type=int, help="Only process first N segments")
@click.option("--segments", help="Comma-separated segment IDs to process")
@click.option("--model-size", default="base", help="Whisper model (tiny/base/small/medium/large)")
@click.option("--language", default=None, help="Language code (zh/en/yue), default=auto")
@click.option("--vad-filter/--no-vad-filter", default=True, help="Enable VAD filter")
@click.option("--device", default="cpu", help="Device (cpu/cuda/auto)")
@click.option(
    "--compute-type",
    default="int8",
    type=click.Choice(["int8", "float16", "float32"]),
    help="Quantization type (default: int8)",
)
@click.option("--beam-size", default=5, type=int, help="Beam size for decoding (default: 5)")
def transcribe(
    session: str,
    output_dir: str,
    backend: str,
    max_seconds: int | None,
    force: bool,
    limit: int | None,
    segments: str | None,
    model_size: str,
    language: str | None,
    vad_filter: bool,
    device: str,
    compute_type: str,
    beam_size: int,
):
    """Transcribe audio from video segments using ASR.

    Generates ASR transcription and writes to analysis/<segment>.json.

    Examples:

      yanhu transcribe -s demo --backend mock

      yanhu transcribe -s demo --backend whisper_local --model-size small --language zh

      yanhu transcribe -s demo --backend whisper_local --segments part_0001 --force

      yanhu transcribe -s demo --backend whisper_local --compute-type float32 --beam-size 5
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

    # Parse segment filter
    segment_list = None
    if segments:
        segment_list = [s.strip() for s in segments.split(",")]

    click.echo(f"Transcribing session: {manifest.session_id}")
    click.echo(f"  Backend: {backend}")
    click.echo(f"  Total segments: {len(manifest.segments)}")
    if backend == "whisper_local":
        click.echo(f"  Model: {model_size}")
        click.echo(f"  Language: {language or 'auto'}")
        click.echo(f"  Device: {device}")
        click.echo(f"  Compute type: {compute_type}")
        click.echo(f"  Beam size: {beam_size}")
        click.echo(f"  VAD filter: {'enabled' if vad_filter else 'disabled'}")
    if max_seconds:
        click.echo(f"  Max seconds: {max_seconds}")
    if force:
        click.echo("  Force: enabled (ignoring cache)")
    if limit:
        click.echo(f"  Limit: {limit} segments")
    if segment_list:
        click.echo(f"  Filter: {segment_list}")

    # Progress callback
    def on_progress(segment_id: str, status: str, result):
        if status == "cached":
            click.echo(f"  {segment_id}: cached (skipped)")
        elif status == "done":
            num_items = len(result.asr_items) if result else 0
            click.echo(f"  {segment_id}: {num_items} items")
        elif status == "error":
            error_msg = result.asr_error if result else "unknown error"
            click.echo(f"  {segment_id}: error - {error_msg}")

    # Run transcription
    try:
        stats = transcribe_session(
            manifest,
            session_dir,
            backend=backend,
            max_seconds=max_seconds,
            force=force,
            limit=limit,
            segments=segment_list,
            on_progress=on_progress,
            model_size=model_size,
            language=language,
            vad_filter=vad_filter,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
        )
    except ValueError as e:
        raise click.ClickException(str(e))

    # Summary
    click.echo("")
    click.echo("Transcription complete!")
    click.echo(f"  Processed: {stats.processed}")
    click.echo(f"  Skipped (cached): {stats.skipped_cache}")
    click.echo(f"  Skipped (filtered): {stats.skipped_filter}")
    if stats.errors:
        click.echo(f"  Errors: {stats.errors}")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--output-dir", "-o", default="sessions", help="Output directory (default: sessions)")
def compose(session: str, output_dir: str):
    """Compose timeline, overview, and highlights from session data.

    Generates timeline.md, overview.md, and highlights.md using analysis if available.
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

    # Write highlights
    highlights_path = write_highlights(manifest, session_dir)
    click.echo(f"  Written: {highlights_path.name}")

    # Check if valid Claude analysis exists and show appropriate message
    if has_valid_claude_analysis(manifest, session_dir):
        click.echo("\nComposition complete! Using analysis results.")
        click.echo("  Use `yanhu analyze ... --force` to refresh.")
    else:
        click.echo("\nComposition complete!")
        click.echo("  Note: Descriptions are placeholders. Run Vision/ASR analysis to fill them.")


@main.command()
@click.option("--session", "-s", required=True, help="Session ID")
@click.option("--output-dir", "-o", default="sessions", help="Output directory")
@click.option("--window", "-w", default=1.5, type=float, help="Time window for alignment (seconds)")
@click.option("--max-quotes", "-m", default=6, type=int, help="Max quotes per segment")
@click.option("--force", "-f", is_flag=True, help="Re-align even if aligned_quotes exists")
@click.option("--segments", help="Comma-separated segment IDs to process")
def align(
    session: str,
    output_dir: str,
    window: float,
    max_quotes: int,
    force: bool,
    segments: str | None,
):
    """Align OCR and ASR text to create unified quotes.

    Generates aligned_quotes in analysis/<segment>.json by matching
    OCR text (as anchor) with ASR transcription within a time window.

    Examples:

      yanhu align -s demo

      yanhu align -s demo --window 2.0 --max-quotes 8

      yanhu align -s demo --segments part_0001,part_0004 --force
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

    # Parse segment filter
    segment_list = None
    if segments:
        segment_list = [s.strip() for s in segments.split(",")]

    click.echo(f"Aligning session: {manifest.session_id}")
    click.echo(f"  Window: {window}s")
    click.echo(f"  Max quotes: {max_quotes}")
    click.echo(f"  Total segments: {len(manifest.segments)}")
    if force:
        click.echo("  Force: enabled (ignoring cache)")
    if segment_list:
        click.echo(f"  Filter: {segment_list}")

    # Process each segment
    processed = 0
    skipped_cache = 0
    skipped_filter = 0
    skipped_no_data = 0

    for segment in manifest.segments:
        # Apply filter
        if segment_list and segment.id not in segment_list:
            skipped_filter += 1
            continue

        analysis_path = session_dir / "analysis" / f"{segment.id}.json"

        # Check if analysis exists
        if not analysis_path.exists():
            skipped_no_data += 1
            click.echo(f"  {segment.id}: no analysis (skipped)")
            continue

        # Check cache
        if not force:
            import json

            try:
                with open(analysis_path, encoding="utf-8") as f:
                    data = json.load(f)
                if "aligned_quotes" in data:
                    skipped_cache += 1
                    click.echo(f"  {segment.id}: cached (skipped)")
                    continue
            except (json.JSONDecodeError, OSError):
                pass

        # Run alignment
        aligned_quotes = align_segment(analysis_path, window, max_quotes)

        if aligned_quotes:
            merge_aligned_quotes_to_analysis(aligned_quotes, analysis_path)
            click.echo(f"  {segment.id}: {len(aligned_quotes)} quotes")
            processed += 1
        else:
            click.echo(f"  {segment.id}: no quotes (no OCR/ASR)")
            skipped_no_data += 1

    # Summary
    click.echo("")
    click.echo("Alignment complete!")
    click.echo(f"  Processed: {processed}")
    click.echo(f"  Skipped (cached): {skipped_cache}")
    click.echo(f"  Skipped (filtered): {skipped_filter}")
    click.echo(f"  Skipped (no data): {skipped_no_data}")


@main.command()
@click.option(
    "--raw-dir",
    "-r",
    multiple=True,
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Directory to watch (can be specified multiple times)",
)
@click.option(
    "--queue-dir",
    "-q",
    default="sessions/_queue",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Directory for queue files (default: sessions/_queue)",
)
@click.option(
    "--once",
    is_flag=True,
    help="Scan directories once and exit (no continuous watching)",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=None,
    help="Poll interval in seconds (mutually exclusive with watchdog mode)",
)
@click.option(
    "--auto-run",
    is_flag=True,
    help="Auto-process queued jobs after detection (WARNING: may consume API tokens)",
)
@click.option(
    "--auto-run-limit",
    type=int,
    default=1,
    help="Max jobs to process per auto-run trigger (default: 1)",
)
@click.option(
    "--auto-run-dry-run",
    is_flag=True,
    help="Auto-run in dry-run mode (print jobs without processing)",
)
@click.option(
    "--output-dir",
    "-o",
    default="sessions",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Output directory for auto-run processing (default: sessions)",
)
def watch(
    raw_dir: tuple[str, ...],
    queue_dir: str,
    once: bool,
    interval: int | None,
    auto_run: bool,
    auto_run_limit: int,
    auto_run_dry_run: bool,
    output_dir: str,
):
    """Watch directories for new video files and queue them.

    Monitors raw_dirs for new .mp4/.mkv/.mov files and adds them to
    a processing queue (pending.jsonl).

    With --auto-run: Automatically processes queued jobs through the full
    pipeline after detection. WARNING: This will consume API tokens!

    Multiple directories: Use --raw-dir multiple times. Moving a file
    from one dir to another will re-queue it (dedup key includes path).

    Modes:
      --once: Scan existing files once and exit
      --interval N: Poll every N seconds (no watchdog dependency)
      Default: Use watchdog for real-time monitoring (requires watchdog)

    Examples:

      yanhu watch -r ~/Videos/raw --once

      yanhu watch -r ~/Videos/raw --once --auto-run

      yanhu watch -r ~/Videos/raw --interval 30 --auto-run --auto-run-limit 2

      yanhu watch -r ~/Videos/raw --auto-run --auto-run-dry-run
    """
    from yanhu.watcher import (
        RunQueueConfig,
        WatcherConfig,
        run_queue,
        scan_once,
        start_polling,
        start_watcher,
    )

    raw_dirs = [Path(d) for d in raw_dir]
    config = WatcherConfig(
        raw_dirs=raw_dirs,
        queue_dir=Path(queue_dir),
    )

    dirs_str = ", ".join(str(d) for d in config.raw_dirs)
    click.echo(f"Raw directories: [{dirs_str}]")
    click.echo(f"Queue file: {config.queue_file}")
    click.echo(f"State file: {config.state_file}")
    if auto_run:
        mode_str = "dry-run" if auto_run_dry_run else "enabled"
        click.echo(f"Auto-run: {mode_str} (limit={auto_run_limit})")
        if not auto_run_dry_run:
            click.echo("  WARNING: Auto-run will consume API tokens!")
    click.echo("")

    def on_queued(job):
        click.echo(f"Queued: {Path(job.raw_path).name} (game={job.suggested_game or 'unknown'})")

    def trigger_auto_run(queued_jobs: list):
        """Trigger auto-run if enabled and jobs were queued.

        Args:
            queued_jobs: List of QueueJob objects queued in this scan
        """
        if not auto_run or not queued_jobs:
            return

        click.echo("")
        click.echo(f"Auto-run triggered ({len(queued_jobs)} new jobs queued)...")

        # Extract raw_paths from queued jobs (CRITICAL: only process these jobs)
        raw_path_filter = {job.raw_path for job in queued_jobs}

        run_config = RunQueueConfig(
            queue_dir=Path(queue_dir),
            output_dir=Path(output_dir),
            limit=auto_run_limit,
            dry_run=auto_run_dry_run,
            force=False,
            raw_path_filter=raw_path_filter,
        )

        try:
            result = run_queue(
                run_config,
                on_job_start=lambda job: click.echo(f"  Processing: {Path(job.raw_path).name}"),
                on_job_complete=lambda job, res: (
                    click.echo(f"    ✓ Success: {res.session_id}")
                    if res and res.success
                    else click.echo(f"    ✗ Failed: {res.error if res else 'unknown'}")
                    if res
                    else click.echo("    - Dry-run")
                ),
            )

            click.echo("")
            click.echo("Auto-run complete!")
            click.echo(f"  Processed: {result.processed}")
            click.echo(f"  Succeeded: {result.succeeded}")
            click.echo(f"  Failed: {result.failed}")
            if auto_run_dry_run:
                click.echo(f"  Skipped (dry-run): {result.skipped}")
        except Exception as e:
            click.echo(f"  ✗ Auto-run failed: {e}")
            click.echo("  Watcher will continue running...")

    if once:
        # Scan once and exit
        click.echo("Scanning directories (once mode)...")
        result = scan_once(config, on_queued=on_queued)
        click.echo("")
        click.echo(
            f"Scan complete: found={result.found}, queued={result.queued}, skipped={result.skipped}"
        )
        # Trigger auto-run after scan completes (pass queued_jobs list)
        trigger_auto_run(result.queued_jobs)
    elif interval is not None:
        # Poll mode
        click.echo(f"Starting watcher (polling mode, interval={interval}s)...")
        start_polling(
            config,
            interval,
            on_queued=on_queued,
            on_scan_complete=trigger_auto_run,
        )
    else:
        # Watchdog mode (default)
        click.echo("Starting watcher (watchdog mode)...")
        start_watcher(
            config,
            on_queued=on_queued,
            on_batch_queued=trigger_auto_run,
        )


@main.command("run-queue")
@click.option(
    "--queue-dir",
    "-q",
    default="sessions/_queue",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Directory for queue files (default: sessions/_queue)",
)
@click.option(
    "--output-dir",
    "-o",
    default="sessions",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Output directory for sessions (default: sessions)",
)
@click.option(
    "--limit",
    "-l",
    default=1,
    type=int,
    help="Max jobs to process (default: 1)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show pending jobs without processing",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force reprocessing even if cached",
)
def run_queue_cmd(queue_dir: str, output_dir: str, limit: int, dry_run: bool, force: bool):
    """Process pending jobs from the queue.

    Reads pending jobs from pending.jsonl and runs them through the
    full pipeline (ingest → segment → extract → analyze → transcribe → compose).

    Uses conservative parameters:
      - max-frames=3, max-facts=3
      - whisper_local model-size=base, compute=int8

    Examples:

      yanhu run-queue --dry-run

      yanhu run-queue --limit 3

      yanhu run-queue --queue-dir sessions/_queue --limit 1 --force
    """
    from yanhu.watcher import RunQueueConfig, get_pending_jobs, run_queue

    config = RunQueueConfig(
        queue_dir=Path(queue_dir),
        output_dir=Path(output_dir),
        limit=limit,
        dry_run=dry_run,
        force=force,
    )

    click.echo(f"Queue file: {config.queue_file}")
    click.echo(f"Output dir: {config.output_dir}")
    click.echo(f"Limit: {limit}")
    if dry_run:
        click.echo("Mode: dry-run (no processing)")
    if force:
        click.echo("Force: enabled (ignoring cache)")
    click.echo("")

    # Check pending jobs
    pending = get_pending_jobs(config.queue_file)
    if not pending:
        click.echo("No pending jobs in queue.")
        return

    click.echo(f"Pending jobs: {len(pending)}")
    jobs_to_show = pending[: config.limit]
    for i, job in enumerate(jobs_to_show, 1):
        click.echo(f"  {i}. {job.raw_path}")
        click.echo(f"     game={job.get_game()} tag={job.get_tag()}")
    click.echo("")

    if dry_run:
        click.echo("Dry-run complete. No jobs processed.")
        return

    # Callbacks for progress
    def on_start(job):
        click.echo(f"Processing: {Path(job.raw_path).name}")
        click.echo(f"  game={job.get_game()} tag={job.get_tag()}")

    def on_complete(job, result):
        if result is None:
            return
        if result.success:
            click.echo(f"  Done: session_id={result.session_id}")
            if result.outputs:
                click.echo(f"  Outputs: {result.outputs.get('session_dir', '')}")
        else:
            click.echo(f"  Failed: {result.error}")
        click.echo("")

    # Run queue
    result = run_queue(config, on_job_start=on_start, on_job_complete=on_complete)

    # Summary
    click.echo("Queue processing complete!")
    click.echo(f"  Processed: {result.processed}")
    click.echo(f"  Succeeded: {result.succeeded}")
    click.echo(f"  Failed: {result.failed}")
    if result.skipped:
        click.echo(f"  Skipped (dry-run): {result.skipped}")


if __name__ == "__main__":
    main()
