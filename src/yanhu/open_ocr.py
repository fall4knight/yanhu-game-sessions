"""Local OCR backend (cheap + deterministic).

This module intentionally avoids LLM calls. It extracts on-screen text from frames
and returns verbatim OCR items.

Default implementation uses RapidOCR (PaddleOCR-style pipeline via ONNXRuntime).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class OpenOcrError(RuntimeError):
    pass


@dataclass
class OpenOcrLine:
    text: str
    score: float | None = None


class OpenOcrEngine:
    """Thin wrapper around a local OCR engine.

    We keep the interface tiny so we can swap implementations later (PaddleOCR,
    RapidOCR, Tesseract, etc.).
    """

    def __init__(self):
        try:
            # RapidOCR returns list of (box, text, score) per line.
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
        except Exception as e:  # pragma: no cover
            raise OpenOcrError(
                "rapidocr-onnxruntime is not installed. Install it to use open_ocr backend. "
                "\n\n  pip install rapidocr-onnxruntime opencv-python-headless onnxruntime"
            ) from e

        self._ocr = RapidOCR()

    def ocr_image(self, image_path: Path) -> list[OpenOcrLine]:
        """Run OCR on a single image.

        Args:
            image_path: frame image path

        Returns:
            List of extracted lines (best-effort)
        """
        try:
            result = self._ocr(str(image_path))
        except Exception as e:
            raise OpenOcrError(f"OCR failed for {image_path.name}: {e}") from e

        # rapidocr may return (result, elapsed)
        if isinstance(result, tuple) and len(result) >= 1:
            result = result[0]

        lines: list[OpenOcrLine] = []
        if not result:
            return lines

        for item in result:
            # item can be [box, text, score] or (text, score)
            try:
                if isinstance(item, (list, tuple)):
                    if len(item) >= 3:
                        text = str(item[1]).strip()
                        score = float(item[2]) if item[2] is not None else None
                    elif len(item) == 2:
                        text = str(item[0]).strip()
                        score = float(item[1]) if item[1] is not None else None
                    else:
                        continue
                else:
                    continue
            except Exception:
                continue

            if not text:
                continue

            lines.append(OpenOcrLine(text=text, score=score))

        return lines
