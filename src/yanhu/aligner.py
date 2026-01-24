"""OCR/ASR alignment fusion (quote-first approach).

Aligns OCR text with ASR transcription to create unified quotes
while preserving original text verbatim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from yanhu.analyzer import OcrItem
from yanhu.transcriber import AsrItem


@dataclass
class AlignedQuote:
    """A single aligned quote with timestamp and source info.

    Schema:
    - source="ocr": {t, source, ocr}
    - source="asr": {t, source, asr}
    - source="both": {t, source, ocr, asr}
    """

    t: float  # Timestamp (relative to session)
    source: str  # "ocr", "asr", or "both"
    ocr: str | None = None  # OCR text (verbatim)
    asr: str | None = None  # ASR text (verbatim)

    def to_dict(self) -> dict:
        result: dict = {
            "t": self.t,
            "source": self.source,
        }
        if self.ocr is not None:
            result["ocr"] = self.ocr
        if self.asr is not None:
            result["asr"] = self.asr
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "AlignedQuote":
        # Backward compatible: support old "quote" field
        ocr = data.get("ocr")
        asr = data.get("asr")
        source = data.get("source", "ocr")

        # Legacy support: if "quote" exists but ocr/asr don't
        if "quote" in data and ocr is None and asr is None:
            quote = data["quote"]
            if source == "ocr":
                ocr = quote
            elif source == "asr":
                asr = quote
            else:  # both - treat as OCR for backward compat
                ocr = quote

        return cls(
            t=data["t"],
            source=source,
            ocr=ocr,
            asr=asr,
        )

    def get_display_text(self) -> str:
        """Get display text for timeline.

        Returns OCR text, with ASR annotation if both present.
        """
        if self.source == "both" and self.ocr and self.asr:
            return f"{self.ocr} (asr: {self.asr})"
        elif self.ocr:
            return self.ocr
        elif self.asr:
            return self.asr
        return ""


def align_ocr_asr(
    ocr_items: list[OcrItem],
    asr_items: list[AsrItem],
    window: float = 1.5,
    max_quotes: int = 6,
) -> list[AlignedQuote]:
    """Align OCR items with ASR items using time window matching.

    Alignment rules:
    - Use ocr_items as anchor points
    - For each ocr_item.t_rel, find asr_items within [t-window, t+window]
    - If matched: source="both", quote = OCR text (verbatim)
    - If not matched: source="ocr"
    - Unmatched asr_items are appended as source="asr"
    - Results sorted by timestamp, limited to max_quotes

    Args:
        ocr_items: List of OCR items with timestamps
        asr_items: List of ASR items with timestamps
        window: Time window in seconds for matching (default 1.5s)
        max_quotes: Maximum number of quotes to return (default 6)

    Returns:
        List of aligned quotes sorted by timestamp
    """
    aligned: list[AlignedQuote] = []
    matched_asr_indices: set[int] = set()

    # Phase 1: Align OCR items with ASR
    for ocr in ocr_items:
        t_ocr = ocr.t_rel
        best_asr_idx: int | None = None
        best_distance: float = float("inf")

        # Find nearest ASR item within window
        for i, asr in enumerate(asr_items):
            if i in matched_asr_indices:
                continue

            # Use asr.t_start for matching
            t_asr = asr.t_start
            distance = abs(t_asr - t_ocr)

            if distance <= window and distance < best_distance:
                best_distance = distance
                best_asr_idx = i

        if best_asr_idx is not None:
            # Found matching ASR - preserve both texts
            matched_asr_indices.add(best_asr_idx)
            aligned.append(
                AlignedQuote(
                    t=t_ocr,
                    source="both",
                    ocr=ocr.text,
                    asr=asr_items[best_asr_idx].text,
                )
            )
        else:
            # No matching ASR - OCR only
            aligned.append(
                AlignedQuote(
                    t=t_ocr,
                    source="ocr",
                    ocr=ocr.text,
                )
            )

    # Phase 2: Add unmatched ASR items
    for i, asr in enumerate(asr_items):
        if i not in matched_asr_indices:
            aligned.append(
                AlignedQuote(
                    t=asr.t_start,
                    source="asr",
                    asr=asr.text,
                )
            )

    # Sort by timestamp
    aligned.sort(key=lambda q: q.t)

    # Limit to max_quotes
    if len(aligned) > max_quotes:
        aligned = aligned[:max_quotes]

    return aligned


def align_segment(
    analysis_path: Path,
    window: float = 1.5,
    max_quotes: int = 6,
) -> list[AlignedQuote]:
    """Align OCR and ASR data for a segment.

    Reads analysis JSON, performs alignment, and returns quotes.
    Does NOT write back to file (caller should do that).

    Args:
        analysis_path: Path to analysis JSON file
        window: Time window for matching
        max_quotes: Maximum quotes to return

    Returns:
        List of aligned quotes
    """
    if not analysis_path.exists():
        return []

    try:
        with open(analysis_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    # Extract ocr_items
    ocr_items: list[OcrItem] = []
    for item in data.get("ocr_items", []):
        try:
            ocr_items.append(OcrItem.from_dict(item))
        except (KeyError, TypeError):
            pass

    # Extract asr_items
    asr_items: list[AsrItem] = []
    for item in data.get("asr_items", []):
        try:
            asr_items.append(AsrItem.from_dict(item))
        except (KeyError, TypeError):
            pass

    return align_ocr_asr(ocr_items, asr_items, window, max_quotes)


def merge_aligned_quotes_to_analysis(
    aligned_quotes: list[AlignedQuote],
    analysis_path: Path,
) -> None:
    """Merge aligned quotes into analysis JSON.

    Args:
        aligned_quotes: List of aligned quotes to write
        analysis_path: Path to analysis JSON file
    """
    if not analysis_path.exists():
        return

    try:
        with open(analysis_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    # Write aligned_quotes
    data["aligned_quotes"] = [q.to_dict() for q in aligned_quotes]

    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_first_quote(analysis_path: Path) -> str | None:
    """Get the first quote display text from aligned_quotes in analysis JSON.

    Returns formatted text: OCR text, with ASR annotation if both present.

    Args:
        analysis_path: Path to analysis JSON file

    Returns:
        First quote display text, or None if not available
    """
    if not analysis_path.exists():
        return None

    try:
        with open(analysis_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    aligned_quotes = data.get("aligned_quotes", [])
    if aligned_quotes:
        quote_data = aligned_quotes[0]
        quote = AlignedQuote.from_dict(quote_data)
        return quote.get_display_text()

    return None
