#!/usr/bin/env python3
"""Tests for runtime self-check tooling (scripts/runtime_selfcheck.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).parent.parent


class TestRuntimeSelfcheck:
    """High-signal tests for runtime self-check script."""

    def test_selfcheck_supports_all_profiles_with_correct_exit_codes(self):
        """Verify script supports all profiles and returns correct exit codes."""
        # Core profile should pass (we have click, ffmpeg-python, etc.)
        result_core = subprocess.run(
            [sys.executable, "scripts/runtime_selfcheck.py", "--profile", "core"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result_core.returncode == 0, f"Core profile should pass: {result_core.stderr}"

        # App profile should pass (we have flask, markdown, etc.)
        result_app = subprocess.run(
            [sys.executable, "scripts/runtime_selfcheck.py", "--profile", "app"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result_app.returncode == 0, f"App profile should pass: {result_app.stderr}"

        # Desktop profile should pass (we have yanhu.launcher, etc.)
        result_desktop = subprocess.run(
            [sys.executable, "scripts/runtime_selfcheck.py", "--profile", "desktop"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert (
            result_desktop.returncode == 0
        ), f"Desktop profile should pass: {result_desktop.stderr}"

        # All profile returns exit code (may pass or fail depending on ASR deps)
        result_all = subprocess.run(
            [sys.executable, "scripts/runtime_selfcheck.py", "--profile", "all"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result_all.returncode in [0, 1], "All profile should return 0 or 1"

    def test_selfcheck_output_format_includes_success_and_failure_counts(self):
        """Verify output format contains 'Successful imports' and 'Failed imports'."""
        result = subprocess.run(
            [sys.executable, "scripts/runtime_selfcheck.py", "--profile", "core"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        output = result.stdout
        assert "Successful imports:" in output, "Should show successful imports count"
        assert "Failed imports:" in output, "Should show failed imports count"
        assert (
            "SELF-CHECK PASSED" in output or "SELF-CHECK FAILED" in output
        ), "Should show clear pass/fail status"

    def test_selfcheck_invalid_profile_fails(self):
        """Verify invalid profile name is rejected."""
        result = subprocess.run(
            [sys.executable, "scripts/runtime_selfcheck.py", "--profile", "invalid"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "Invalid profile should fail"
        assert "invalid choice" in result.stderr.lower() or "ERROR" in result.stdout


class TestDependencyMatrixDocumentation:
    """High-signal tests for dependency matrix documentation."""

    def test_dependency_matrix_exists_and_contains_required_profiles(self):
        """Verify dependency matrix exists and contains all required profile headings."""
        doc = REPO_ROOT / "docs" / "DEPENDENCY_MATRIX.md"
        assert doc.exists(), "docs/DEPENDENCY_MATRIX.md should exist"

        content = doc.read_text()

        # Check all required profiles are documented
        required_profiles = ["core", "app", "asr", "desktop", "all"]
        for profile in required_profiles:
            assert (
                profile.lower() in content.lower()
            ), f"Profile '{profile}' should be documented"

        # Check key documentation elements
        assert "Python Packages" in content or "python packages" in content.lower()
        assert "pip install" in content.lower(), "Should include installation commands"
        assert (
            "runtime selfcheck" in content.lower() or "selfcheck" in content.lower()
        ), "Should reference selfcheck script"


class TestCIRehearsalScript:
    """High-signal tests for CI rehearsal script."""

    def test_ci_rehearsal_script_exists_and_contains_required_steps(self):
        """Verify CI rehearsal script exists and includes all required CI steps."""
        script = REPO_ROOT / "scripts" / "ci_rehearsal_desktop.sh"
        assert script.exists(), "ci_rehearsal_desktop.sh should exist"
        assert script.stat().st_mode & 0o100, "Should be executable"

        content = script.read_text()

        # Check shebang
        first_line = content.split("\n")[0]
        assert first_line.startswith("#!") and "bash" in first_line.lower()

        # Check all key CI steps are present
        required_steps = [
            "ruff check",
            "pytest",
            "runtime_selfcheck.py",
            "pyinstaller",
        ]
        for step in required_steps:
            assert step.lower() in content.lower(), f"Should include step: {step}"

        # Check it installs runtime deps for desktop-full build
        assert "tiktoken" in content, "Should install tiktoken for ASR"
        assert "regex" in content, "Should install regex for ASR"
        assert "safetensors" in content, "Should install safetensors for ASR"

        # Check it creates clean venv
        assert "venv" in content.lower(), "Should create venv"
        assert "ci-rehearsal" in content or "CI" in content, "Should be CI-specific venv"
