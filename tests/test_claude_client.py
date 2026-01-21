"""Tests for Claude client."""

from yanhu.claude_client import ClaudeClient


class TestClaudeClientPrompt:
    """Test Claude client prompt construction."""

    def test_prompt_contains_scene_type_enum(self):
        """Prompt should list all scene_type enum values."""
        client = ClaudeClient.__new__(ClaudeClient)  # Skip __init__
        prompt = client._get_prompt_text()

        assert "dialogue" in prompt
        assert "choice" in prompt
        assert "combat" in prompt
        assert "menu" in prompt
        assert "cutscene" in prompt
        assert "unknown" in prompt

    def test_prompt_requires_json_only(self):
        """Prompt should require JSON-only output."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text()

        assert "JSON" in prompt
        assert "markdown" in prompt.lower()

    def test_prompt_specifies_required_fields(self):
        """Prompt should specify all required fields."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text()

        assert "scene_type" in prompt
        assert "ocr_text" in prompt
        assert "caption" in prompt

    def test_prompt_emphasizes_objective_facts(self):
        """Prompt should emphasize objective facts, not subjective descriptions."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text()

        # Should mention objective facts
        assert "客观" in prompt
        assert "facts" in prompt

        # Should have confidence field
        assert "confidence" in prompt

    def test_prompt_handles_non_game_content(self):
        """Prompt should handle test images/non-game content."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text()

        assert "测试" in prompt or "非游戏" in prompt

    def test_prompt_limits_ocr_text(self):
        """Prompt should limit ocr_text count."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text()

        assert "8" in prompt  # max 8 items


class TestClaudeClientDetailLevel:
    """Test Claude client detail level switching."""

    def test_l0_prompt_does_not_include_l1_fields(self):
        """L0 prompt should not include L1-specific fields."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L0")

        # L0 should not have scene_label, what_changed, etc.
        assert "scene_label" not in prompt
        assert "what_changed" not in prompt
        assert "ui_key_text" not in prompt
        assert "player_action_guess" not in prompt
        assert "hook_detail" not in prompt

    def test_l1_prompt_includes_l1_fields(self):
        """L1 prompt should include L1-specific fields."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # L1 should have all L1 fields
        assert "scene_label" in prompt
        assert "what_changed" in prompt
        assert "ui_key_text" in prompt
        assert "player_action_guess" in prompt
        assert "hook_detail" in prompt

    def test_l1_prompt_has_scene_label_enum(self):
        """L1 prompt should have scene_label enum values."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        assert "Loading" in prompt
        assert "Menu" in prompt
        assert "Cutscene" in prompt
        assert "Combat" in prompt
        assert "Dialogue" in prompt
        assert "TVTest" in prompt

    def test_l1_prompt_requires_uncertainty_for_guess(self):
        """L1 prompt should require uncertainty markers for player_action_guess."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        assert "可能" in prompt or "疑似" in prompt

    def test_default_detail_level_is_l1(self):
        """Default detail level should be L1."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text()

        # Should have L1 fields
        assert "scene_label" in prompt
        assert "what_changed" in prompt
