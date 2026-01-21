"""Claude Vision API client for analyzing video frames."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClaudeResponse:
    """Response from Claude API."""

    scene_type: str
    ocr_text: list[str]
    facts: list[str]
    caption: str
    model: str
    confidence: str | None = None
    error: str | None = None
    # L1 fields (optional)
    scene_label: str | None = None
    what_changed: str | None = None
    ui_key_text: list[str] | None = None
    player_action_guess: str | None = None
    hook_detail: str | None = None


class ClaudeClientError(Exception):
    """Error from Claude API client."""

    pass


class ClaudeClient:
    """Client for Claude Vision API with retry logic."""

    SCENE_TYPES = ["dialogue", "choice", "combat", "menu", "cutscene", "unknown"]
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            model: Model to use. Defaults to claude-sonnet-4-20250514.

        Raises:
            ClaudeClientError: If API key is not provided and not in environment.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ClaudeClientError(
                "ANTHROPIC_API_KEY not found. Set it in your environment:\n"
                "  export ANTHROPIC_API_KEY=sk-ant-..."
            )
        self.model = model or self.DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ClaudeClientError(
                    "anthropic package not installed. Install with:\n"
                    "  pip install anthropic"
                )
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _encode_image(self, image_path: Path) -> tuple[str, str]:
        """Encode image to base64.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (base64_data, media_type)
        """
        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")

        suffix = image_path.suffix.lower()
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")

        return data, media_type

    def _build_prompt(self, max_facts: int = 3, detail_level: str = "L1") -> str:
        """Build the analysis prompt for objective facts output."""
        return self._get_prompt_text(max_facts, detail_level)

    def _get_prompt_text(self, max_facts: int = 3, detail_level: str = "L1") -> str:
        """Return the prompt text (separated for testing)."""
        if detail_level == "L0":
            return self._get_l0_prompt(max_facts)
        return self._get_l1_prompt(max_facts)

    def _get_l0_prompt(self, max_facts: int = 3) -> str:
        """Return L0 prompt (basic facts+caption+ocr_text)."""
        return f"""分析这些游戏画面截图，输出客观信息包。严格JSON格式，不要markdown，不要解释。

输出格式：
{{
  "scene_type": "枚举值",
  "ocr_text": ["文字1", "文字2"],
  "facts": ["客观事实1", "客观事实2"],
  "caption": "一句话客观总结",
  "confidence": "low|med|high"
}}

字段规则：

1. scene_type（必须是以下之一）：
   - "dialogue"：有对话框、角色名、字幕
   - "choice"：有选项列表、按钮高亮、分支选择
   - "combat"：有血条、技能栏、战斗特效、敌人
   - "menu"：背包、设置、地图、存档等系统UI
   - "cutscene"：无UI或电影式镜头、过场动画
   - "unknown"：无法判断或非游戏内容

2. ocr_text（最多8条，只收集剧情相关文本）：
   【只收集】字幕/对白/对话框文字/剧情台词/选项文本/系统提示
   【必须排除】平台水印/用户名/账号名/Logo/背景装饰字，包括但不限于：
     小红书、抖音、B站、关注、点赞、收藏、分享、评论、@用户名、
     作者、ID、头像、置顶、推荐、下载、进度条、播放量、时长显示
   【识别技巧】字幕通常为：成行文本、对话框区域、带描边/阴影、靠近人物，
     但位置不限于底部（可能在中间/上方/对话框内）
   【原则】precision > recall：不确定是否为字幕时，宁可不写入，也不要写水印
   - 每条文本尽量完整（不要断成单字/碎片）
   - 无法识别或全是水印则返回空数组 []

3. facts（1到{max_facts}条客观短句）：
   - 只写客观可观察的事实，不要判断/建议/总结措辞
   - dialogue：说话角色、对话轮次、是否有选项
   - choice：选项数量、当前高亮选项、选择结果
   - combat：血量状态、技能释放、击杀/倒地、阶段变化
   - menu：打开的界面名称、正在进行的操作
   - 测试画面/彩条：写具体内容如"彩条测试卡；无文字；无UI元素"
   - 不要只写标签如"非游戏内容"，要写客观细节

4. caption：一句话客观总结（作为 fallback）

5. confidence：对分析结果的置信度
   - "high"：画面清晰、信息明确
   - "med"：部分模糊或不确定
   - "low"：画面不清或无法判断

只输出JSON，不要任何其他内容。"""

    def _get_l1_prompt(self, max_facts: int = 3) -> str:
        """Return L1 prompt (enhanced with scene_label, what_changed, etc.)."""
        return f"""分析这些游戏画面截图，输出客观信息包。严格JSON格式，不要markdown，不要解释。
禁止拟人/情绪/复盘口吻，只写客观事实。

输出格式：
{{
  "scene_type": "枚举值",
  "scene_label": "Loading|Menu|Cutscene|Combat|Dialogue|Error|TVTest|Unknown",
  "ocr_text": ["文字1", "文字2"],
  "facts": ["客观事实1", "客观事实2"],
  "caption": "一句话客观总结",
  "confidence": "low|med|high",
  "what_changed": "描述变化或状态",
  "ui_key_text": ["关键UI文字1"],
  "player_action_guess": "可能...|疑似...",
  "hook_detail": "一条可咀嚼细节"
}}

【重要】文本提取规则——排除平台水印/用户名/Logo：
【必须排除的文本类型】（绝对不要写入 ocr_text 或 ui_key_text）：
  - 平台水印：小红书、抖音、B站、快手、YouTube、Twitch
  - 用户相关：@用户名、作者名、账号ID、头像旁文字、粉丝数
  - 交互按钮：关注、点赞、收藏、分享、评论、转发、下载
  - 播放信息：播放量、时长显示、进度条、倍速
  - 平台UI：置顶、推荐、热门、广告、直播中
  - 背景装饰：Logo、品牌名、频道名、背景水印
【只收集的文本类型】：
  - 字幕/对白/对话框文字/剧情台词
  - 选项文本/系统提示/游戏内UI文字
【原则】precision > recall：不确定是否为字幕/剧情文本时，宁可不写入

字段规则：

1. scene_type（必须是以下之一）：
   - "dialogue"：有对话框、角色名、字幕
   - "choice"：有选项列表、按钮高亮、分支选择
   - "combat"：有血条、技能栏、战斗特效、敌人
   - "menu"：背包、设置、地图、存档等系统UI
   - "cutscene"：无UI或电影式镜头、过场动画
   - "unknown"：无法判断或非游戏内容

2. scene_label（必须是以下之一）：
   - "Loading"：加载画面、进度条
   - "Menu"：主菜单、设置、存档等系统界面
   - "Cutscene"：过场动画、CG、电影镜头
   - "Combat"：战斗、技能释放、敌人交互
   - "Dialogue"：对话、选项、剧情推进
   - "Error"：错误提示、崩溃画面
   - "TVTest"：测试画面、彩条、非游戏内容
   - "Unknown"：无法判断

3. ocr_text（最多8条，只收集剧情相关文本）：
   【识别技巧】字幕/对白通常为：
     - 成行文本、对话框区域、带描边/阴影/半透明背景
     - 靠近人物或画面中央/下方，但位置不限（可能在中间/上方/对话框内）
     - 与画面内容相关的叙事性文字
   - 每条文本尽量完整（不要断成单字/碎片）
   - 若画面有多块文本：先判断哪块是剧情字幕/台词，只提取那部分
   - 无法识别或全是水印/平台UI则返回空数组 []

4. facts（1到{max_facts}条客观短句）：
   - 只写客观可观察的事实，不要判断/建议/总结措辞
   - dialogue：说话角色、对话轮次、是否有选项
   - choice：选项数量、当前高亮选项、选择结果
   - combat：血量状态、技能释放、击杀/倒地、阶段变化
   - menu：打开的界面名称、正在进行的操作
   - 测试画面/彩条：写具体内容如"彩条测试卡；无文字；无UI元素"

5. caption：一句话客观总结（作为 fallback）

6. confidence：对分析结果的置信度
   - "high"：画面清晰、信息明确
   - "med"：部分模糊或不确定
   - "low"：画面不清或无法判断

7. what_changed（必填）：
   - 描述这段画面相对上一段或本段内的变化/状态
   - 回答"发生了什么变化"或"当前处于什么状态"
   - 要具体，避免空泛（如"画面变化"）
   - 如不确定，标注"不确定：..."
   - 示例："场景从菜单切换到战斗"、"对话继续，角色A说完换角色B"

8. ui_key_text（0-2条，优先字幕/台词）：
   - 若画面存在明显字幕/台词，必须优先取其中一句完整句子
   - 其次为：系统提示/选项文本/游戏内关键UI
   - 【禁止】平台水印/用户名/点赞收藏等（同上排除规则）
   - 可为空数组 []

9. player_action_guess（可选）：
   - 对玩家可能的操作进行猜测
   - 必须带不确定性措辞："可能..."、"疑似..."、"或许..."
   - 不得当作结论陈述
   - 如无法猜测可为空字符串 ""

10. hook_detail（可选）：
    - 一条值得注意的细节（画面细节、数值、特殊元素等）
    - 可为空字符串 ""

只输出JSON，不要任何其他内容。"""

    def analyze_frames(
        self,
        frame_paths: list[Path],
        max_retries: int = 2,
        max_facts: int = 3,
        detail_level: str = "L1",
    ) -> ClaudeResponse:
        """Analyze video frames using Claude Vision.

        Args:
            frame_paths: List of paths to frame images
            max_retries: Maximum number of retries on failure
            max_facts: Maximum number of facts to return
            detail_level: "L0" for basic, "L1" for enhanced fields

        Returns:
            ClaudeResponse with analysis results
        """
        client = self._get_client()

        # Build content blocks with images
        content = []
        for path in frame_paths:
            data, media_type = self._encode_image(path)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            })

        # Add text prompt
        content.append({
            "type": "text",
            "text": self._build_prompt(max_facts, detail_level),
        })

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": content}],
                )

                # Parse response
                text = response.content[0].text
                return self._parse_response(text, self.model)

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    # Exponential backoff: 1s, 2s
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)

        # All retries failed
        return ClaudeResponse(
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model=self.model,
            error=str(last_error),
        )

    def _parse_response(self, text: str, model: str) -> ClaudeResponse:
        """Parse Claude's JSON response.

        Args:
            text: Raw response text
            model: Model used

        Returns:
            ClaudeResponse with parsed data
        """
        try:
            # Try to extract JSON from response
            text = text.strip()
            # Remove markdown code blocks if present
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            data = json.loads(text)

            scene_type = data.get("scene_type", "unknown")
            if scene_type not in self.SCENE_TYPES:
                scene_type = "unknown"

            return ClaudeResponse(
                scene_type=scene_type,
                ocr_text=data.get("ocr_text", []),
                facts=data.get("facts", []),
                caption=data.get("caption", ""),
                model=model,
                confidence=data.get("confidence"),
                # L1 fields
                scene_label=data.get("scene_label"),
                what_changed=data.get("what_changed"),
                ui_key_text=data.get("ui_key_text"),
                player_action_guess=data.get("player_action_guess"),
                hook_detail=data.get("hook_detail"),
            )
        except json.JSONDecodeError as e:
            return ClaudeResponse(
                scene_type="unknown",
                ocr_text=[],
                facts=[],
                caption=text[:200] if text else "",  # Use raw text as caption fallback
                model=model,
                error=f"JSON parse error: {e}",
            )


class MockClaudeClient:
    """Mock Claude client for testing without API calls."""

    def __init__(self, responses: dict[str, ClaudeResponse] | None = None):
        """Initialize mock client.

        Args:
            responses: Optional dict mapping segment_id to response
        """
        self.responses = responses or {}
        self.calls: list[tuple[list[Path], str]] = []  # Track calls for testing

    def analyze_frames(
        self,
        frame_paths: list[Path],
        max_retries: int = 2,
        max_facts: int = 3,
        detail_level: str = "L1",
        segment_id: str = "",
    ) -> ClaudeResponse:
        """Mock analyze that returns predefined or default response."""
        self.calls.append((frame_paths, segment_id))

        if segment_id in self.responses:
            return self.responses[segment_id]

        # Default mock response
        frame_count = len(frame_paths)
        response = ClaudeResponse(
            scene_type="unknown",
            ocr_text=[],
            facts=[f"共{frame_count}帧画面"],
            caption=f"【Mock】分析了{frame_count}帧画面",
            model="mock-model",
        )

        # Add L1 fields if detail_level is L1
        if detail_level == "L1":
            response.scene_label = "TVTest"
            response.what_changed = "测试画面，无变化"
            response.ui_key_text = []
            response.player_action_guess = ""
            response.hook_detail = ""

        return response
