"""Yanhu CLI - Main entry point."""

import click

from yanhu import __version__


@click.group()
@click.version_option(version=__version__, prog_name="yanhu")
def main():
    """Yanhu Game Sessions - Post-game replay companion.

    Process game recordings into structured timelines and highlights.
    """
    pass


@main.command()
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--game", "-g", required=True, help="Game name (e.g., gnosia, genshin)")
@click.option("--run-tag", "-r", default="run01", help="Run identifier (default: run01)")
def ingest(video_path: str, game: str, run_tag: str):
    """Ingest a video file and create a new session."""
    click.echo(f"[ingest] Not implemented yet. video={video_path}, game={game}, run={run_tag}")


@main.command()
@click.argument("session_id")
@click.option("--duration", "-d", default=30, help="Segment duration in seconds (default: 30)")
def segment(session_id: str, duration: int):
    """Segment a session's video into chunks."""
    click.echo(f"[segment] Not implemented yet. session={session_id}, duration={duration}s")


@main.command()
@click.argument("session_id")
def extract(session_id: str):
    """Extract key frames from each segment."""
    click.echo(f"[extract] Not implemented yet. session={session_id}")


@main.command()
@click.argument("session_id")
def compose(session_id: str):
    """Compose final timeline and highlights from session data."""
    click.echo(f"[compose] Not implemented yet. session={session_id}")


if __name__ == "__main__":
    main()
