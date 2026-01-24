"""Tests for yanhu-verify helper script."""

import subprocess
from pathlib import Path


class TestVerifyHelper:
    """Test verify helper script doesn't use bash -lc."""

    def test_helper_script_exists(self):
        """Verify helper script exists and is executable."""
        helper = Path(".claude/skills/yanhu-verify/run_with_env.py")
        assert helper.exists(), "Helper script should exist"
        assert helper.stat().st_mode & 0o111, "Helper script should be executable"

    def test_helper_loads_dotenv(self):
        """Verify helper uses python-dotenv, not bash -lc."""
        helper = Path(".claude/skills/yanhu-verify/run_with_env.py")
        content = helper.read_text()

        # Should use python-dotenv
        assert "from dotenv import load_dotenv" in content or "dotenv_values" in content, (
            "Helper should use python-dotenv for env loading"
        )

        # Should NOT use bash -lc
        assert "bash -lc" not in content, "Helper should not use 'bash -lc' pattern"
        assert "subprocess.run" in content, "Helper should use subprocess.run"

    def test_helper_filters_shell_noise(self):
        """Verify helper filters gvm and shell noise."""
        helper = Path(".claude/skills/yanhu-verify/run_with_env.py")
        content = helper.read_text()

        # Should filter noise keywords
        noise_keywords = ["__gvm", "_encode", "_decode", "cd:"]
        for keyword in noise_keywords:
            assert keyword in content, f"Helper should filter '{keyword}' noise"

    def test_skill_md_uses_helper(self):
        """Verify skill.md uses helper script, not bash -lc."""
        skill = Path(".claude/skills/yanhu-verify/skill.md")
        content = skill.read_text()

        # Should use helper script
        assert "run_with_env.py" in content, "Skill should use run_with_env.py helper"

        # Should NOT use bash -lc anymore
        bash_lc_count = content.count("bash -lc")
        assert bash_lc_count == 0, f"Skill should not use 'bash -lc' (found {bash_lc_count})"

    def test_helper_runs_without_bash_lc(self, tmp_path):
        """Verify helper can run commands without invoking bash -lc."""
        helper = Path(".claude/skills/yanhu-verify/run_with_env.py")

        # Run a simple command through helper
        result = subprocess.run(
            [str(helper), "echo", "test"],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )

        # Should succeed
        assert result.returncode == 0, "Helper should run commands successfully"
        assert "test" in result.stdout, "Helper should pass through command output"

        # The helper script itself should not invoke bash -lc internally
        # (We already checked this in test_helper_loads_dotenv)

    def test_skill_md_env_check_uses_python(self):
        """Verify skill.md env check uses Python, not bash -lc."""
        skill = Path(".claude/skills/yanhu-verify/skill.md")
        content = skill.read_text()

        # Find the env check section
        env_check_section = content.split("## Prerequisites for Claude Backend")[1].split("##")[0]

        # Should use python3 -c with dotenv
        assert "python3 -c" in env_check_section or "run_with_env.py" in env_check_section, (
            "Env check should use Python, not bash"
        )

        # Should use dotenv
        assert (
            "dotenv" in env_check_section or "run_with_env.py" in env_check_section
        ), "Env check should use dotenv"


class TestVerifySemantics:
    """Test that verification semantics haven't changed."""

    def test_verify_tasks_unchanged(self):
        """Verify all verification tasks are still present."""
        skill = Path(".claude/skills/yanhu-verify/skill.md")
        content = skill.read_text()

        # All original tasks should still be present
        required_tasks = [
            "Source video observability",
            "L1 Claude Vision analysis",
            "Timeline pollution check",
            "Highlights check",
            "ASR transcription check",
            "ASR timestamp validation",
            "ASR whisper_local backend",
        ]

        for task in required_tasks:
            assert task in content, f"Verification task '{task}' should still be present"

    def test_verify_checks_unchanged(self):
        """Verify critical checks are still present."""
        skill = Path(".claude/skills/yanhu-verify/skill.md")
        content = skill.read_text()

        # Critical checks should still be present
        critical_checks = [
            "source_metadata",
            "source_mode",
            'model starts with "claude-"',
            "facts length",
            "scene_label",
            "JSON fragments",
            "highlights.md",
            "asr_items",
            "t_start <= t_end",
            "faster-whisper",
        ]

        for check in critical_checks:
            assert check in content, f"Critical check '{check}' should still be present"
