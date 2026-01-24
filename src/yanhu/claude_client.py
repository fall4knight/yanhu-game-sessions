"""Claude Vision API client for analyzing video frames."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OcrItem:
    """A single OCR text item with source tracking."""

    text: str
    t_rel: float  # Relative time in seconds (estimated)
    source_frame: str  # Frame filename (e.g., "frame_0005.jpg")


@dataclass
class UiSymbolItem:
    """A UI symbol (emoji/icon) with source tracking for time-based alignment."""

    symbol: str  # The emoji or symbol (e.g., "❤️", "⭐")
    t_rel: float  # Relative time in seconds (estimated)
    source_frame: str  # Frame filename where symbol appears


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
    raw_text: str | None = None  # Raw response when JSON parse fails
    # L1 fields (optional)
    scene_label: str | None = None
    what_changed: str | None = None
    ui_key_text: list[str] | None = None
    ui_symbols: list[str] | None = None  # Emoji/symbols like ❤️
    player_action_guess: str | None = None
    hook_detail: str | None = None
    # OCR items with source tracking (for ASR alignment)
    ocr_items: list[OcrItem] | None = None
    # UI symbol items with source tracking (for time-based binding)
    ui_symbol_items: list[UiSymbolItem] | None = None


class ClaudeClientError(Exception):
    """Error from Claude API client."""

    pass


class ClaudeClient:
    """Client for Claude Vision API with retry logic."""

    SCENE_TYPES = ["dialogue", "choice", "combat", "menu", "cutscene", "unknown"]
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_MAX_PARSE_RETRIES = 2

    # Correction prompt prepended on JSON parse retry
    JSON_CORRECTION_PROMPT = (
        "Your previous output was not valid JSON. "
        "Output ONLY valid JSON parsable by json.loads. "
        "Avoid unescaped double quotes; use 「」 instead.\n\n"
    )

    # Repair prompt for fixing invalid JSON without images
    JSON_REPAIR_PROMPT = """Fix this text to be valid JSON matching the schema below.
Output ONLY the corrected JSON, no explanation.

Schema:
{{
  "scene_type": "dialogue|choice|combat|menu|cutscene|unknown",
  "scene_label": "Loading|Menu|Cutscene|Combat|Dialogue|Error|TVTest|Unknown",
  "ocr_text": ["string array"],
  "ocr_items": [{{"text": "string", "frame_idx": 1}}],
  "facts": ["string array"],
  "caption": "string",
  "confidence": "low|med|high",
  "what_changed": "string",
  "ui_key_text": ["string array"],
  "ui_symbols": ["string array"],
  "player_action_guess": "string",
  "hook_detail": "string"
}}

Text to fix:
{raw_text}

Output ONLY valid JSON:"""

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
                    "anthropic package not installed. Install with:\n  pip install anthropic"
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

【JSON 格式硬规则】：
- 输出必须可被 json.loads 解析
- 所有文本字段内部禁止出现未转义的英文双引号 "
- 如需引号请改用中文书名号「」或括号（）
- 示例：正确「对话内容」，错误 "对话内容"

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

3. facts（1到{max_facts}条"硬事实"短句）：
   【只允许写画面可直接观察到的内容】：
   - 镜头类型：特写/中景/远景/切镜
   - 字幕存在：是否有字幕，大致位置/颜色
   - 角色外观：眼镜/制服/盔甲/武器/发型/服装颜色（不要命名身份）
   - 场景元素：战斗UI/血条/技能栏/对话框/菜单界面
   - 若不确定，用"疑似"前缀
   【禁止写入】：
   - 角色身份/名字（除非出现在字幕中）
   - 剧情推断（如"决战""回忆"）
   - 测试画面/彩条：写具体内容如"彩条测试卡；无文字；无UI元素"

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

【JSON 格式硬规则】：
- 输出必须可被 json.loads 解析
- 所有文本字段内部禁止出现未转义的英文双引号 "
- 如需引号请改用中文书名号「」或括号（）
- 示例：正确「对话内容」，错误 "对话内容"

输出格式：
{{
  "scene_type": "枚举值",
  "scene_label": "Loading|Menu|Cutscene|Combat|Dialogue|Error|TVTest|Unknown",
  "ocr_text": ["文字1", "文字2"],
  "ocr_items": [
    {{"text": "字幕句子1", "frame_idx": 1}},
    {{"text": "字幕句子2", "frame_idx": 3}}
  ],
  "facts": ["客观事实1", "客观事实2"],
  "caption": "一句话客观总结",
  "confidence": "low|med|high",
  "what_changed": "描述变化或状态",
  "ui_key_text": ["关键台词1", "关键台词2"],
  "ui_symbols": ["❤️"],
  "ui_symbol_items": [
    {{"symbol": "❤️", "source_frames": ["frame_0005.jpg", "frame_0007.jpg"]}}
  ],
  "player_action_guess": "可能...|疑似...",
  "hook_detail": "一条可咀嚼细节"
}}

【重要】文本提取规则——排除平台水印/用户名/Logo：
【必须排除的文本类型】（绝对不要写入 ocr_text/ocr_items/ui_key_text）：
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

3. ocr_text（最多8条，完整覆盖本段字幕——召回优先）：
   【核心要求——完整覆盖】：
   - 尽可能完整收集本段画面中出现的所有字幕/台词句子
   - 优先收集"变化的句子"（不同帧间出现的不同字幕）
   - 每条字幕必须完整一句（允许有错字，但禁止截断半句）
   - 不要只取第一条——要覆盖本段内所有可见的字幕句
   【逐字保真——禁止纠错】：
   - 字幕原文必须逐字保留，完全按画面显示输出
   - 禁止纠错、润色、替换量词（如"只/支""副/幅"等）
   - 即使识别出错字也原样保留（如"一只步摇"不要改成"一支步摇"）
   【识别技巧】字幕/对白通常为：
     - 成行文本、对话框区域、带描边/阴影/半透明背景
     - 靠近人物或画面中央/下方，但位置不限（可能在中间/上方/对话框内）
     - 与画面内容相关的叙事性文字
   - 若画面有多块文本：先判断哪块是剧情字幕/台词，只提取那部分
   - 无法识别或全是水印/平台UI则返回空数组 []

4. ocr_items（带帧索引的字幕列表——用于时间对齐）：
   - 将 ocr_text 中的每条字幕关联到首次出现的帧索引
   - frame_idx 从 1 开始（第1张图=1，第2张=2...）
   - 用于后续 ASR 时间戳对齐
   - 格式: [{{"text": "字幕句子", "frame_idx": 1}}, ...]
   - text 必须与 ocr_text 一致（逐字保真，禁止纠错）
   - 若无字幕则返回空数组 []

5. facts（1到{max_facts}条"硬事实"短句）：
   【只允许写画面可直接观察到的内容】：
   - 镜头类型：特写/中景/远景/切镜/多画面
   - 字幕存在：是否有字幕/配字，大致位置（底部/中央/上方），颜色/描边
   - 角色外观特征：眼镜/制服/盔甲/武器/翅膀形状/发光颜色/发型/服装颜色
   - 场景元素：战斗UI/血条/技能栏/传送特效/菜单界面/对话框
   - 若不确定某元素，必须用"疑似"前缀
   【禁止写入 facts】：
   - 角色身份/名字（如"嫦娥""夏侯惇""和亲公主"）除非该词出现在字幕中
   - 剧情推断（如"仰望星空""决战时刻""回忆往事"）
   - 情绪判断（如"悲伤""激动""紧张"）
   - 若字幕中出现角色名/剧情词，应写入 ocr_text/ui_key_text，而非 facts
   【"战斗"一词的使用规则】：
   - 禁止直接写"战斗场面/战斗中/战斗画面/剧情推进"
   - 仅当画面出现【血条/技能栏/武器挥砍特效/伤害数值/战斗UI】时，才允许用"战斗"
   - 否则必须用更硬的描述：
     - "黑白色调动作画面"
     - "出现数字 246/8428（疑似伤害数值）"
     - "角色挥动武器的动作帧"
   - 若要推断"疑似战斗"，请放到 player_action_guess
   【示例】：
   - 正确："白底黑字字幕位于画面下方"
   - 正确："角色穿戴盔甲，手持长柄武器"
   - 正确："画面左侧显示血条UI"
   - 正确："黑白色调画面，显示数字246和8428"
   - 错误："嫦娥飞天"（身份推断）
   - 错误："战斗场面"（无血条/技能栏证据时禁止使用）

6. caption：一句话客观总结（作为 fallback）

7. confidence：对分析结果的置信度
   - "high"：画面清晰、信息明确
   - "med"：部分模糊或不确定
   - "low"：画面不清或无法判断

8. what_changed（必填，基于可观测变化）：
   - 引用可观测的变化：字幕内容变化/镜头切换/特效出现/UI变化
   - 避免剧情脑补（如"剧情推进""故事发展"）
   【禁止使用主观姿态/情绪词】：
   - 禁止："仰望/悲伤/愤怒/害怕/激动/紧张/回忆/思念"
   - 替换为可观测描述：
     - "仰望" → "抬头特写/视线方向向上/镜头上移"
     - "悲伤" → "低头特写/面部阴影/眼部特写"
   - 主观解释放到 player_action_guess，并带"可能/疑似"
   - 如不确定，标注"不确定：..."
   - 示例：
     - "字幕从'...'变为'...'"
     - "镜头从远景切到角色抬头特写"
     - "出现技能释放特效"
     - "对话框消失，进入过场画面"

9. ui_key_text（0-2条，从 ocr_text 中选最关键的）：
   【选择优先级——关键句优先】：
   - 【人物/事件名】含公主/太和/王位/玉簪/步摇/遗物/封号等名词的句子
   - 【转折词句】含 但/却/只/只留/不见/最后/其实/原来 的句子
   - 【强情绪问句】含 ?/？/!/！ 的反问句或感叹句
   - 【梗点关键词】含 daddy/爸/都做过/拍拖/那我算什么/男人/女人 的句子
   【示例应优先入选】：
   - "其实就是太和公主"
   - "公主不见踪影"
   - "只留一支素雅的步摇"
   - "却再也没有回来"
   【禁止】平台水印/用户名/点赞收藏等（同上排除规则）
   - 可为空数组 []

10. ui_symbols（0-3条，画面中的明显符号/emoji）：
   - 检测画面中是否出现明显的【心形/emoji/特殊符号/图标】
   - 优先写 emoji 本身（如 "❤️"、"💔"、"😢"、"🔥"）
   - 若无法确定具体 emoji，写标签（如 "heart"、"broken_heart"、"fire"）
   - 只记录画面中实际显示的符号，不要推断
   - 可为空数组 []

11. ui_symbol_items（符号时间定位，必需）：
   - **如果 ui_symbols 非空，则必须为每个符号提供其出现的帧位置**
   - 格式：[{{"symbol": "❤️", "source_frames": ["frame_0005.jpg", "frame_0007.jpg"]}}]
   - source_frames：该符号出现的帧列表（最多3个帧，按出现顺序）
   - 如果符号在多帧出现，选择最清晰/最突出的帧
   - 用于后续时间对齐，不需要推断
   - 如果 ui_symbols 为空，则 ui_symbol_items 也必须为空数组 []

12. player_action_guess（推断放这里）：
    - 所有"身份判断/剧情推断/情绪推断"都放这里，而非 facts
    - 必须带不确定性措辞："可能..."、"疑似..."、"看起来..."
    - 保持一句话短句
    - 示例："可能是角色释放大招"、"疑似剧情回忆片段"
    - 如无法猜测可为空字符串 ""

13. hook_detail（可选）：
    - 一条值得注意的细节（画面细节、数值、特殊元素等）
    - 可为空字符串 ""

只输出JSON，不要任何其他内容。"""

    def analyze_frames(
        self,
        frame_paths: list[Path],
        max_retries: int = 2,
        max_facts: int = 3,
        detail_level: str = "L1",
        max_parse_retries: int | None = None,
    ) -> ClaudeResponse:
        """Analyze video frames using Claude Vision.

        Args:
            frame_paths: List of paths to frame images
            max_retries: Maximum number of retries on API failure
            max_facts: Maximum number of facts to return
            detail_level: "L0" for basic, "L1" for enhanced fields
            max_parse_retries: Max retries for JSON parse errors (default 2)

        Returns:
            ClaudeResponse with analysis results
        """
        if max_parse_retries is None:
            max_parse_retries = self.DEFAULT_MAX_PARSE_RETRIES

        client = self._get_client()

        # Build content blocks with images
        image_content = []
        for path in frame_paths:
            data, media_type = self._encode_image(path)
            image_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data,
                    },
                }
            )

        base_prompt = self._build_prompt(max_facts, detail_level)

        # Retry logic with exponential backoff for API errors
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # First attempt: normal analysis with images
                content = image_content + [{"type": "text", "text": base_prompt}]
                response = client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": content}],
                )

                raw_text = response.content[0].text
                result = self._try_parse_response(raw_text, self.model)

                if result.error is None:
                    return result

                # JSON parse failed, try retry with correction prompt
                result = self._retry_with_correction(
                    client, image_content, base_prompt, raw_text, max_parse_retries
                )
                return result

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    # Exponential backoff: 1s, 2s
                    wait_time = 2**attempt
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

    def _retry_with_correction(
        self,
        client,
        image_content: list[dict],
        base_prompt: str,
        raw_text: str,
        max_parse_retries: int,
    ) -> ClaudeResponse:
        """Retry JSON parsing with correction prompts.

        Args:
            client: Anthropic client
            image_content: Image content blocks
            base_prompt: Original analysis prompt
            raw_text: Raw text from failed parse attempt
            max_parse_retries: Maximum parse retries

        Returns:
            ClaudeResponse (either successful or with error)
        """
        last_raw_text = raw_text

        for retry in range(max_parse_retries):
            try:
                if retry == 0:
                    # First retry: with images + correction prompt
                    correction_prompt = self.JSON_CORRECTION_PROMPT + base_prompt
                    content = image_content + [{"type": "text", "text": correction_prompt}]
                else:
                    # Subsequent retries: repair pass without images (cheaper)
                    repair_prompt = self.JSON_REPAIR_PROMPT.format(
                        raw_text=last_raw_text[:1000]  # Limit raw text size
                    )
                    content = [{"type": "text", "text": repair_prompt}]

                response = client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": content}],
                )

                last_raw_text = response.content[0].text
                result = self._try_parse_response(last_raw_text, self.model)

                if result.error is None:
                    return result

            except Exception:
                # API error during retry, continue to next retry
                pass

        # All parse retries failed, return error response
        truncated_text = last_raw_text[:500] if last_raw_text else None
        return ClaudeResponse(
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model=self.model,
            error=f"JSON parse error after {max_parse_retries} retries",
            raw_text=truncated_text,
        )

    def _try_parse_response(self, text: str, model: str) -> ClaudeResponse:
        """Try to parse Claude's JSON response without raising exceptions.

        Args:
            text: Raw response text
            model: Model used

        Returns:
            ClaudeResponse with parsed data or error field set
        """
        return self._parse_response(text, model)

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

            # Parse ocr_items with frame_idx
            raw_ocr_items = data.get("ocr_items", [])
            ocr_items = None
            if raw_ocr_items:
                ocr_items = []
                for item in raw_ocr_items:
                    if isinstance(item, dict) and "text" in item:
                        frame_idx = item.get("frame_idx", 1)
                        # Create OcrItem with placeholder values
                        # (t_rel and source_frame will be set by analyzer)
                        ocr_items.append(
                            OcrItem(
                                text=item["text"],
                                t_rel=0.0,  # Will be calculated by analyzer
                                source_frame=f"frame_{frame_idx:04d}.jpg",
                            )
                        )

            # Parse ui_symbol_items with source_frames
            raw_symbol_items = data.get("ui_symbol_items", [])
            ui_symbol_items = None
            if raw_symbol_items:
                ui_symbol_items = []
                for item in raw_symbol_items:
                    if isinstance(item, dict) and "symbol" in item:
                        source_frames = item.get("source_frames", [])
                        # Use first frame as primary source
                        source_frame = source_frames[0] if source_frames else "frame_0001.jpg"
                        ui_symbol_items.append(
                            UiSymbolItem(
                                symbol=item["symbol"],
                                t_rel=0.0,  # Will be calculated by analyzer
                                source_frame=source_frame,
                            )
                        )

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
                ui_symbols=data.get("ui_symbols"),
                player_action_guess=data.get("player_action_guess"),
                hook_detail=data.get("hook_detail"),
                ocr_items=ocr_items,
                ui_symbol_items=ui_symbol_items,
            )
        except json.JSONDecodeError as e:
            # Truncate raw_text to 500 chars to avoid bloating analysis files
            truncated_text = text[:500] if text else None
            return ClaudeResponse(
                scene_type="unknown",
                ocr_text=[],
                facts=[],
                caption="",
                model=model,
                error=f"JSON parse error: {e}",
                raw_text=truncated_text,
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
        max_parse_retries: int = 2,
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


class FakeClaudeClient:
    """Fake Claude client that returns a sequence of raw text responses.

    Used for testing JSON parse retry logic without making API calls.
    """

    def __init__(self, raw_responses: list[str]):
        """Initialize fake client with a sequence of raw responses.

        Args:
            raw_responses: List of raw text responses to return in order.
                          Each call to analyze_frames consumes responses
                          until a valid JSON is found or retries exhausted.
        """
        self.raw_responses = list(raw_responses)  # Copy to avoid mutation
        self.call_count = 0
        self.calls: list[tuple[list[Path], str]] = []

    def analyze_frames(
        self,
        frame_paths: list[Path],
        max_retries: int = 2,
        max_facts: int = 3,
        detail_level: str = "L1",
        segment_id: str = "",
        max_parse_retries: int = 2,
    ) -> ClaudeResponse:
        """Fake analyze that simulates JSON parse retry behavior.

        Consumes raw_responses in order, retrying on parse failures.
        """
        self.calls.append((frame_paths, segment_id))

        last_raw_text = ""
        # Initial attempt + max_parse_retries
        for attempt in range(1 + max_parse_retries):
            if not self.raw_responses:
                break

            raw_text = self.raw_responses.pop(0)
            last_raw_text = raw_text
            self.call_count += 1

            # Try to parse
            result = self._try_parse(raw_text)
            if result.error is None:
                return result

        # All attempts failed
        truncated_text = last_raw_text[:500] if last_raw_text else None
        return ClaudeResponse(
            scene_type="unknown",
            ocr_text=[],
            facts=[],
            caption="",
            model="fake-model",
            error=f"JSON parse error after {max_parse_retries} retries",
            raw_text=truncated_text,
        )

    def _try_parse(self, text: str) -> ClaudeResponse:
        """Try to parse response text as JSON."""
        try:
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            data = json.loads(text)

            scene_type = data.get("scene_type", "unknown")
            if scene_type not in ClaudeClient.SCENE_TYPES:
                scene_type = "unknown"

            # Parse ocr_items with frame_idx
            raw_ocr_items = data.get("ocr_items", [])
            ocr_items = None
            if raw_ocr_items:
                ocr_items = []
                for item in raw_ocr_items:
                    if isinstance(item, dict) and "text" in item:
                        frame_idx = item.get("frame_idx", 1)
                        ocr_items.append(
                            OcrItem(
                                text=item["text"],
                                t_rel=0.0,
                                source_frame=f"frame_{frame_idx:04d}.jpg",
                            )
                        )

            # Parse ui_symbol_items with source_frames
            raw_symbol_items = data.get("ui_symbol_items", [])
            ui_symbol_items = None
            if raw_symbol_items:
                ui_symbol_items = []
                for item in raw_symbol_items:
                    if isinstance(item, dict) and "symbol" in item:
                        source_frames = item.get("source_frames", [])
                        source_frame = source_frames[0] if source_frames else "frame_0001.jpg"
                        ui_symbol_items.append(
                            UiSymbolItem(
                                symbol=item["symbol"],
                                t_rel=0.0,
                                source_frame=source_frame,
                            )
                        )

            return ClaudeResponse(
                scene_type=scene_type,
                ocr_text=data.get("ocr_text", []),
                facts=data.get("facts", []),
                caption=data.get("caption", ""),
                model="fake-model",
                confidence=data.get("confidence"),
                scene_label=data.get("scene_label"),
                what_changed=data.get("what_changed"),
                ui_key_text=data.get("ui_key_text"),
                ui_symbols=data.get("ui_symbols"),
                player_action_guess=data.get("player_action_guess"),
                hook_detail=data.get("hook_detail"),
                ocr_items=ocr_items,
                ui_symbol_items=ui_symbol_items,
            )
        except json.JSONDecodeError as e:
            return ClaudeResponse(
                scene_type="unknown",
                ocr_text=[],
                facts=[],
                caption="",
                model="fake-model",
                error=f"JSON parse error: {e}",
                raw_text=text[:500] if text else None,
            )
