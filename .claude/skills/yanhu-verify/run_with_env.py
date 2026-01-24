#!/usr/bin/env python3
"""Helper script to run yanhu commands with .env loaded, without shell noise."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Load .env and run command, filtering shell noise."""
    # Load .env file
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            # Fallback: manual parsing
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            os.environ[key.strip()] = value.strip()

    # Run command
    if len(sys.argv) < 2:
        print("Usage: run_with_env.py <command> [args...]", file=sys.stderr)
        sys.exit(1)

    try:
        result = subprocess.run(
            sys.argv[1:],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Filter out gvm/cd noise from stderr
        stderr_lines = result.stderr.split("\n")
        clean_stderr = "\n".join(
            line
            for line in stderr_lines
            if not (
                line.startswith("cd:")
                or "__gvm" in line
                or "_encode" in line
                or "_decode" in line
                or "setValueForKeyFakeAssocArray" in line
                or "valueForKeyFakeAssocArray" in line
            )
        )

        # Output
        print(result.stdout, end="")
        if clean_stderr.strip():
            print(clean_stderr, file=sys.stderr, end="")

        sys.exit(result.returncode)

    except FileNotFoundError:
        print(f"Command not found: {sys.argv[1]}", file=sys.stderr)
        sys.exit(127)


if __name__ == "__main__":
    main()
