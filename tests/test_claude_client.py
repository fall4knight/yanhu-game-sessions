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


class TestClaudeClientOcrExclusionRules:
    """Test that prompts contain OCR exclusion rules for watermarks/platform UI."""

    def test_l1_prompt_excludes_platform_watermarks(self):
        """L1 prompt should list platform watermarks to exclude."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention common Chinese video platforms
        assert "小红书" in prompt
        assert "抖音" in prompt
        assert "B站" in prompt

    def test_l1_prompt_excludes_user_related_text(self):
        """L1 prompt should exclude user-related text."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention user-related exclusions
        assert "用户名" in prompt
        assert "作者" in prompt or "账号" in prompt

    def test_l1_prompt_excludes_interaction_buttons(self):
        """L1 prompt should exclude social interaction buttons."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention interaction buttons to exclude
        assert "点赞" in prompt
        assert "收藏" in prompt
        assert "分享" in prompt

    def test_l1_prompt_prioritizes_subtitles_in_ui_key_text(self):
        """L1 prompt should prioritize subtitles/dialogue in ui_key_text."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # ui_key_text section should mention subtitle priority
        assert "字幕" in prompt
        assert "台词" in prompt

    def test_l1_prompt_has_precision_over_recall_principle(self):
        """L1 prompt should state precision > recall principle."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention precision > recall
        assert "precision" in prompt.lower() or "宁可不写" in prompt

    def test_l0_prompt_also_has_exclusion_rules(self):
        """L0 prompt should also have basic exclusion rules."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L0")

        # L0 should also exclude watermarks
        assert "排除" in prompt or "必须排除" in prompt
        assert "水印" in prompt or "小红书" in prompt

    def test_l1_prompt_excludes_logo_brand(self):
        """L1 prompt should exclude logo/brand names."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention Logo exclusion
        assert "Logo" in prompt or "品牌" in prompt

    def test_l1_prompt_has_subtitle_identification_tips(self):
        """L1 prompt should have tips for identifying subtitles."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention subtitle visual characteristics
        assert "描边" in prompt or "阴影" in prompt
        # Should NOT assume subtitle is only at bottom
        assert "位置不限" in prompt or "不限于底部" in prompt
