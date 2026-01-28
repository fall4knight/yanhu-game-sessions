"""Gemini Generative Language API client for analyzing video frames."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path


class GeminiClientError(Exception):
    """Error from Gemini API client."""

    pass


@dataclass
class GeminiResponse:
    """Response from Gemini API."""

    scene_type: str
    ocr_text: list[str]
    facts: list[str]
    caption: str
    model: str
    confidence: str | None = None
    error: str | None = None
    raw_text: str | None = None
    # L1 fields (optional)
    scene_label: str | None = None
    what_changed: str | None = None
    ui_key_text: list[str] | None = None
    ui_symbols: list[str] | None = None
    player_action_guess: str | None = None
    hook_detail: str | None = None
    ocr_items: list[dict] | None = None
    ui_symbol_items: list[dict] | None = None


class GeminiClient:
    """Client for Gemini Generative Language API."""

    DEFAULT_MODEL = "gemini-1.5-pro"
    DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize Gemini client.

        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
            model: Model to use. Defaults to gemini-1.5-pro (or GEMINI_MODEL env var).

        Raises:
            GeminiClientError: If API key is not provided and not in environment.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise GeminiClientError(
                "GEMINI_API_KEY not found. Set it in your environment:\n"
                "  export GEMINI_API_KEY=AIza..."
            )
        self.model = model or os.environ.get("GEMINI_MODEL", self.DEFAULT_MODEL)

    def _encode_image(self, image_path: Path) -> tuple[str, str]:
        """Encode image to base64.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (base64_data, mime_type)
        """
        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")

        suffix = image_path.suffix.lower()
        mime_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/jpeg")

        return data, mime_type

    def _get_prompt_text(self, max_facts: int = 3, detail_level: str = "L1") -> str:
        """Get prompt text by reusing ClaudeClient's prompt.

        Args:
            max_facts: Maximum number of facts to extract
            detail_level: "L0" or "L1"

        Returns:
            Prompt text string
        """
        # Import here to avoid circular dependency
        from yanhu.claude_client import ClaudeClient

        # Create a minimal ClaudeClient instance to get prompt
        # We bypass __init__ to avoid API key requirement
        client = object.__new__(ClaudeClient)
        return client._get_prompt_text(max_facts, detail_level)

    def _build_request_body(
        self, image_paths: list[Path], prompt: str
    ) -> dict:
        """Build request body for Gemini API.

        Args:
            image_paths: List of image file paths
            prompt: Text prompt

        Returns:
            Request body dict
        """
        parts = []

        # Add images
        for path in image_paths:
            data, mime_type = self._encode_image(path)
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": data,
                }
            })

        # Add text prompt
        parts.append({"text": prompt})

        return {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 2048,
            },
        }

    def _extract_text_from_response(self, response_data: dict) -> str:
        """Extract text from Gemini API response.

        Args:
            response_data: JSON response from API

        Returns:
            Combined text from all parts

        Raises:
            GeminiClientError: If response format is unexpected
        """
        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                error = response_data.get("error", {})
                if error:
                    raise GeminiClientError(
                        f"Gemini API error: {error.get('message', str(error))}"
                    )
                raise GeminiClientError("No candidates in response")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            texts = []
            for part in parts:
                if "text" in part:
                    texts.append(part["text"])

            return "".join(texts)
        except KeyError as e:
            raise GeminiClientError(f"Unexpected response format: missing {e}")

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from response text.

        Args:
            text: Raw response text

        Returns:
            Parsed JSON dict

        Raises:
            json.JSONDecodeError: If parsing fails
        """
        # Strip markdown code blocks if present
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)

    def _repair_json(self, raw_text: str) -> dict | None:
        """Attempt to repair invalid JSON using a text-only API call.

        Args:
            raw_text: The invalid JSON text to repair

        Returns:
            Repaired JSON dict, or None if repair failed
        """
        try:
            import httpx
        except ImportError:
            return None

        # Get repair prompt from ClaudeClient
        from yanhu.claude_client import ClaudeClient

        repair_prompt = ClaudeClient.JSON_REPAIR_PROMPT.format(raw_text=raw_text)

        url = f"{self.DEFAULT_ENDPOINT}/{self.model}:generateContent?key={self.api_key}"

        body = {
            "contents": [{"parts": [{"text": repair_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            },
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=body)
                response.raise_for_status()
                data = response.json()

            repaired_text = self._extract_text_from_response(data)
            return self._parse_json_response(repaired_text)
        except Exception:
            return None

    def analyze_frames(
        self,
        frame_paths: list[Path],
        max_facts: int = 3,
        detail_level: str = "L1",
    ) -> GeminiResponse:
        """Analyze video frames using Gemini API.

        Args:
            frame_paths: List of paths to frame images
            max_facts: Maximum number of facts to extract
            detail_level: "L0" or "L1"

        Returns:
            GeminiResponse with analysis results
        """
        try:
            import httpx
        except ImportError:
            raise GeminiClientError(
                "httpx package not installed. "
                "This is required for Gemini API calls."
            )

        prompt = self._get_prompt_text(max_facts, detail_level)

        url = f"{self.DEFAULT_ENDPOINT}/{self.model}:generateContent?key={self.api_key}"
        body = self._build_request_body(frame_paths, prompt)

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            return GeminiResponse(
                scene_type="unknown",
                ocr_text=[],
                facts=[],
                caption="",
                model=self.model,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except httpx.RequestError as e:
            return GeminiResponse(
                scene_type="unknown",
                ocr_text=[],
                facts=[],
                caption="",
                model=self.model,
                error=f"Request error: {e}",
            )

        try:
            raw_text = self._extract_text_from_response(data)
        except GeminiClientError as e:
            return GeminiResponse(
                scene_type="unknown",
                ocr_text=[],
                facts=[],
                caption="",
                model=self.model,
                error=str(e),
            )

        # Try to parse JSON
        try:
            result = self._parse_json_response(raw_text)
        except json.JSONDecodeError:
            # Try repair
            result = self._repair_json(raw_text)
            if result is None:
                return GeminiResponse(
                    scene_type="unknown",
                    ocr_text=[],
                    facts=[],
                    caption="",
                    model=self.model,
                    error="JSON parse failed after repair attempt",
                    raw_text=raw_text,
                )

        # Build response from parsed JSON
        return GeminiResponse(
            scene_type=result.get("scene_type", "unknown"),
            ocr_text=result.get("ocr_text", []),
            facts=result.get("facts", []),
            caption=result.get("caption", ""),
            model=self.model,
            confidence=result.get("confidence"),
            scene_label=result.get("scene_label"),
            what_changed=result.get("what_changed"),
            ui_key_text=result.get("ui_key_text"),
            ui_symbols=result.get("ui_symbols"),
            player_action_guess=result.get("player_action_guess"),
            hook_detail=result.get("hook_detail"),
            ocr_items=result.get("ocr_items"),
            ui_symbol_items=result.get("ui_symbol_items"),
        )
