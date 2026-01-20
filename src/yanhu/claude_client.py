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
    caption: str
    model: str
    error: str | None = None


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

    def _build_prompt(self) -> str:
        """Build the analysis prompt."""
        # fmt: off
        # noqa: E501 - Chinese prompt content should not be split
        return """分析这些游戏画面截图。请用中文回答，严格按以下JSON格式输出，不要添加任何markdown标记或额外解释：

{
  "scene_type": "场景类型，必须是以下之一：dialogue（对话）、choice（选项/选择）、combat（战斗）、menu（菜单）、cutscene（过场动画）、unknown（无法判断）",
  "ocr_text": ["画面中出现的文字，如对话、字幕、系统提示等，每条单独一项"],
  "caption": "用一句中文总结这段画面发生了什么，包括出现的角色、场景、关键事件等"
}

只输出JSON，不要输出其他内容。"""  # noqa: E501
        # fmt: on

    def analyze_frames(
        self,
        frame_paths: list[Path],
        max_retries: int = 2,
    ) -> ClaudeResponse:
        """Analyze video frames using Claude Vision.

        Args:
            frame_paths: List of paths to frame images
            max_retries: Maximum number of retries on failure

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
            "text": self._build_prompt(),
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
                caption=data.get("caption", ""),
                model=model,
            )
        except json.JSONDecodeError as e:
            return ClaudeResponse(
                scene_type="unknown",
                ocr_text=[],
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
        segment_id: str = "",
    ) -> ClaudeResponse:
        """Mock analyze that returns predefined or default response."""
        self.calls.append((frame_paths, segment_id))

        if segment_id in self.responses:
            return self.responses[segment_id]

        # Default mock response
        frame_count = len(frame_paths)
        return ClaudeResponse(
            scene_type="unknown",
            ocr_text=[],
            caption=f"【Mock】分析了{frame_count}帧画面",
            model="mock-model",
        )
