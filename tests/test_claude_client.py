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


class TestClaudeClientHardFactsRules:
    """Test that prompts enforce hard facts rules and prohibit inferences."""

    def test_l1_prompt_defines_hard_facts(self):
        """L1 prompt should define what hard facts are allowed."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention allowed hard facts categories
        assert "镜头类型" in prompt
        assert "特写" in prompt or "中景" in prompt or "远景" in prompt
        assert "字幕存在" in prompt or "是否有字幕" in prompt

    def test_l1_prompt_allows_visual_character_features(self):
        """L1 prompt should allow visible character features but not identities."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention allowed visual features
        assert "眼镜" in prompt
        assert "盔甲" in prompt or "武器" in prompt
        # Should prohibit naming character identities
        assert "身份" in prompt and "禁止" in prompt

    def test_l1_prompt_prohibits_character_names_in_facts(self):
        """L1 prompt should prohibit character names in facts."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should show example of prohibited character names
        assert "嫦娥" in prompt or "夏侯惇" in prompt
        # Should indicate these are prohibited in facts
        assert "禁止写入 facts" in prompt or "禁止写入】" in prompt

    def test_l1_prompt_prohibits_plot_inference_in_facts(self):
        """L1 prompt should prohibit plot inferences in facts."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should prohibit plot-related inferences
        assert "剧情推断" in prompt
        # Should show examples of prohibited inferences
        assert "仰望星空" in prompt or "决战" in prompt or "回忆" in prompt

    def test_l1_prompt_requires_uncertainty_prefix(self):
        """L1 prompt should require '疑似' prefix for uncertain elements."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention using 疑似 for uncertainty
        assert "疑似" in prompt
        # Should be in the facts section context
        assert "不确定" in prompt

    def test_l1_prompt_redirects_inference_to_player_action_guess(self):
        """L1 prompt should redirect inferences to player_action_guess."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # player_action_guess section should mention it's for inferences
        assert "推断放这里" in prompt or "身份判断" in prompt

    def test_l1_prompt_what_changed_uses_observable_changes(self):
        """L1 prompt should require what_changed to use observable changes."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention observable changes
        assert "可观测" in prompt or "字幕" in prompt
        assert "镜头切换" in prompt or "特效出现" in prompt

    def test_l1_prompt_shows_correct_and_incorrect_examples(self):
        """L1 prompt should show examples of correct and incorrect facts."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should have example markers
        assert "正确" in prompt
        assert "错误" in prompt

    def test_l0_prompt_also_has_hard_facts_rules(self):
        """L0 prompt should also have hard facts rules."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L0")

        # L0 should also restrict facts
        assert "硬事实" in prompt
        assert "禁止" in prompt or "不要命名身份" in prompt

    def test_l1_prompt_prohibits_battle_scene_without_evidence(self):
        """L1 prompt should prohibit '战斗场面' without observable evidence."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should explicitly prohibit 战斗场面/战斗中/战斗画面
        assert "战斗场面" in prompt
        assert "禁止" in prompt
        # Should require evidence for using 战斗
        assert "血条" in prompt
        assert "技能栏" in prompt

    def test_l1_prompt_requires_evidence_for_battle_word(self):
        """L1 prompt should require evidence (血条/技能栏/伤害数值) for '战斗' word."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention the evidence required
        assert "伤害数值" in prompt or "武器挥砍特效" in prompt
        # Should provide alternative descriptions
        assert "黑白色调" in prompt or "动作画面" in prompt

    def test_l1_prompt_prohibits_posture_emotion_words_in_what_changed(self):
        """L1 prompt should prohibit posture/emotion words in what_changed."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should prohibit these words
        assert "仰望" in prompt
        assert "悲伤" in prompt
        # Should be in prohibition context
        assert "禁止使用主观" in prompt or "禁止：" in prompt

    def test_l1_prompt_provides_replacements_for_posture_words(self):
        """L1 prompt should provide observable replacements for posture words."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should provide replacement suggestions
        assert "抬头特写" in prompt or "视线方向向上" in prompt
        # Should mention redirecting to player_action_guess
        assert "player_action_guess" in prompt


class TestClaudeClientJsonFormatRules:
    """Test that prompts contain strict JSON format rules."""

    def test_l1_prompt_requires_json_loads_compatible(self):
        """L1 prompt should require json.loads compatible output."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        assert "json.loads" in prompt

    def test_l1_prompt_prohibits_unescaped_double_quotes(self):
        """L1 prompt should prohibit unescaped double quotes in text fields."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should mention prohibition of double quotes
        assert "禁止" in prompt and "双引号" in prompt

    def test_l1_prompt_suggests_chinese_brackets(self):
        """L1 prompt should suggest Chinese book title marks or parentheses."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L1")

        # Should suggest alternatives
        assert "「」" in prompt or "书名号" in prompt
        assert "（）" in prompt or "括号" in prompt

    def test_l0_prompt_also_has_json_format_rules(self):
        """L0 prompt should also have JSON format rules."""
        client = ClaudeClient.__new__(ClaudeClient)
        prompt = client._get_prompt_text(detail_level="L0")

        assert "json.loads" in prompt
        assert "双引号" in prompt
        assert "「」" in prompt or "书名号" in prompt


class TestClaudeClientParseResponse:
    """Test Claude client response parsing and error handling."""

    def test_parse_response_truncates_raw_text_to_500_chars(self):
        """raw_text should be truncated to 500 chars on JSON parse error."""
        client = ClaudeClient.__new__(ClaudeClient)
        long_text = "x" * 1000  # 1000 chars

        response = client._parse_response(long_text, "claude-test-model")

        assert response.error is not None
        assert "JSON parse error" in response.error
        assert response.raw_text is not None
        assert len(response.raw_text) == 500

    def test_parse_response_keeps_short_raw_text(self):
        """raw_text shorter than 500 should not be truncated."""
        client = ClaudeClient.__new__(ClaudeClient)
        short_text = "invalid json but short"

        response = client._parse_response(short_text, "claude-test-model")

        assert response.error is not None
        assert response.raw_text == short_text

    def test_parse_response_handles_empty_text(self):
        """Empty text should result in None raw_text."""
        client = ClaudeClient.__new__(ClaudeClient)

        response = client._parse_response("", "claude-test-model")

        assert response.error is not None
        assert response.raw_text is None

    def test_parse_response_valid_json_no_error(self):
        """Valid JSON should parse without error."""
        client = ClaudeClient.__new__(ClaudeClient)
        valid_json = (
            '{"scene_type": "dialogue", "ocr_text": [], '
            '"facts": ["test"], "caption": "test caption"}'
        )

        response = client._parse_response(valid_json, "claude-test-model")

        assert response.error is None
        assert response.raw_text is None
        assert response.scene_type == "dialogue"
        assert response.caption == "test caption"
