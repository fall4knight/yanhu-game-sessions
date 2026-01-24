"""Bind UI symbols to OCR items based on time alignment (no keyword matching)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BoundSymbol:
    """A symbol bound to OCR text or standalone."""

    symbol: str
    ocr_text: str | None  # None if no nearby OCR (standalone symbol)
    source: str  # "bound" or "symbol"
    time_delta: float | None  # Time difference if bound


def bind_symbols_to_ocr(
    ui_symbol_items: list,
    ocr_items: list,
    threshold: float = 1.5,
) -> list[BoundSymbol]:
    """Bind UI symbols to OCR items based on nearest time neighbor.

    Args:
        ui_symbol_items: List of UiSymbolItem with symbol, t_rel, source_frame
        ocr_items: List of OcrItem with text, t_rel, source_frame
        threshold: Max time delta in seconds (default 1.5s)

    Returns:
        List of BoundSymbol, either bound to OCR text or standalone
    """
    results = []

    for symbol_item in ui_symbol_items:
        symbol = symbol_item.symbol
        symbol_time = symbol_item.t_rel

        # Find nearest OCR item by time
        best_match = None
        best_delta = float("inf")

        for ocr_item in ocr_items:
            delta = abs(ocr_item.t_rel - symbol_time)
            if delta < best_delta:
                best_delta = delta
                best_match = ocr_item

        # Bind if within threshold
        if best_match and best_delta <= threshold:
            results.append(
                BoundSymbol(
                    symbol=symbol,
                    ocr_text=best_match.text,
                    source="bound",
                    time_delta=best_delta,
                )
            )
        else:
            # Standalone symbol (no nearby OCR)
            results.append(
                BoundSymbol(
                    symbol=symbol,
                    ocr_text=None,
                    source="symbol",
                    time_delta=None,
                )
            )

    return results
