"""Tests for Gemini API client."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yanhu.gemini_client import GeminiClient, GeminiClientError, GeminiResponse


class TestGeminiClientInit:
    """Test GeminiClient initialization."""

    def test_init_with_api_key(self):
        """Should initialize with provided API key."""
        client = GeminiClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.model == "gemini-1.5-pro"

    def test_init_with_custom_model(self):
        """Should use custom model if provided."""
        client = GeminiClient(api_key="test-key", model="gemini-1.5-flash")
        assert client.model == "gemini-1.5-flash"

    def test_init_from_env(self, monkeypatch):
        """Should read API key from environment."""
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        client = GeminiClient()
        assert client.api_key == "env-key"

    def test_init_model_from_env(self, monkeypatch):
        """Should read model from environment."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
        client = GeminiClient()
        assert client.model == "gemini-2.0-flash"

    def test_init_no_api_key_raises(self, monkeypatch):
        """Should raise error if no API key."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(GeminiClientError) as exc:
            GeminiClient()
        assert "GEMINI_API_KEY not found" in str(exc.value)


class TestGeminiClientEncodeImage:
    """Test image encoding."""

    def test_encode_jpeg(self, tmp_path):
        """Should encode JPEG image."""
        img_path = tmp_path / "test.jpg"
        img_path.write_bytes(b"fake jpeg data")

        client = GeminiClient(api_key="test-key")
        data, mime_type = client._encode_image(img_path)

        assert mime_type == "image/jpeg"
        assert len(data) > 0

    def test_encode_png(self, tmp_path):
        """Should encode PNG image."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        client = GeminiClient(api_key="test-key")
        data, mime_type = client._encode_image(img_path)

        assert mime_type == "image/png"


class TestGeminiClientParseJson:
    """Test JSON parsing."""

    def test_parse_clean_json(self):
        """Should parse clean JSON."""
        client = GeminiClient(api_key="test-key")
        text = '{"scene_type": "dialogue", "caption": "test"}'
        result = client._parse_json_response(text)
        assert result["scene_type"] == "dialogue"

    def test_parse_json_with_markdown(self):
        """Should strip markdown code blocks."""
        client = GeminiClient(api_key="test-key")
        text = '```json\n{"scene_type": "dialogue"}\n```'
        result = client._parse_json_response(text)
        assert result["scene_type"] == "dialogue"

    def test_parse_invalid_json_raises(self):
        """Should raise on invalid JSON."""
        client = GeminiClient(api_key="test-key")
        with pytest.raises(json.JSONDecodeError):
            client._parse_json_response("not json")


class TestGeminiClientExtractText:
    """Test response text extraction."""

    def test_extract_text_success(self):
        """Should extract text from valid response."""
        client = GeminiClient(api_key="test-key")
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Hello "},
                            {"text": "World"},
                        ]
                    }
                }
            ]
        }
        text = client._extract_text_from_response(response)
        assert text == "Hello World"

    def test_extract_text_no_candidates(self):
        """Should raise on no candidates."""
        client = GeminiClient(api_key="test-key")
        with pytest.raises(GeminiClientError) as exc:
            client._extract_text_from_response({"candidates": []})
        assert "No candidates" in str(exc.value)

    def test_extract_text_api_error(self):
        """Should raise on API error response."""
        client = GeminiClient(api_key="test-key")
        with pytest.raises(GeminiClientError) as exc:
            client._extract_text_from_response({
                "error": {"message": "Quota exceeded"}
            })
        assert "Quota exceeded" in str(exc.value)


class TestGeminiClientAnalyzeFrames:
    """Test analyze_frames with mocked httpx."""

    def test_analyze_frames_success(self, tmp_path):
        """Should return GeminiResponse on success."""
        # Create fake image
        img_path = tmp_path / "frame.jpg"
        img_path.write_bytes(b"fake image")

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": '{"scene_type": "dialogue", "ocr_text": ["test"], "facts": [], "caption": "A dialogue scene"}'}
                        ]
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = GeminiClient(api_key="test-key")
            result = client.analyze_frames([img_path])

            assert isinstance(result, GeminiResponse)
            assert result.scene_type == "dialogue"
            assert result.caption == "A dialogue scene"
            assert result.model == "gemini-1.5-pro"

    def test_analyze_frames_http_error(self, tmp_path):
        """Should return error response on HTTP error."""
        img_path = tmp_path / "frame.jpg"
        img_path.write_bytes(b"fake image")

        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)

            # Create proper HTTPStatusError
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_response
            )
            mock_client_class.return_value = mock_client

            client = GeminiClient(api_key="test-key")
            result = client.analyze_frames([img_path])

            assert result.error is not None
            assert "401" in result.error

    def test_analyze_frames_json_parse_error_with_repair(self, tmp_path):
        """Should attempt JSON repair on parse error."""
        img_path = tmp_path / "frame.jpg"
        img_path.write_bytes(b"fake image")

        # First response is invalid JSON, repair response is valid
        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            if call_count[0] == 1:
                # First call: invalid JSON
                mock_resp.json.return_value = {
                    "candidates": [{"content": {"parts": [{"text": "invalid json {"}]}}]
                }
            else:
                # Repair call: valid JSON
                mock_resp.json.return_value = {
                    "candidates": [{"content": {"parts": [
                        {"text": '{"scene_type": "unknown", "ocr_text": [], "facts": [], "caption": "repaired"}'}
                    ]}}]
                }
            return mock_resp

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = mock_post
            mock_client_class.return_value = mock_client

            client = GeminiClient(api_key="test-key")
            result = client.analyze_frames([img_path])

            # Should have attempted repair
            assert call_count[0] == 2
            assert result.caption == "repaired"


class TestGeminiClientPromptReuse:
    """Test that GeminiClient reuses ClaudeClient prompts."""

    def test_get_prompt_text_l0(self):
        """Should get L0 prompt from ClaudeClient."""
        client = GeminiClient(api_key="test-key")
        prompt = client._get_prompt_text(max_facts=3, detail_level="L0")
        assert "scene_type" in prompt
        assert "ocr_text" in prompt

    def test_get_prompt_text_l1(self):
        """Should get L1 prompt from ClaudeClient."""
        client = GeminiClient(api_key="test-key")
        prompt = client._get_prompt_text(max_facts=3, detail_level="L1")
        assert "scene_label" in prompt
        assert "what_changed" in prompt
