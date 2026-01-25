"""Session composition: generate timeline and overview documents."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from yanhu.aligner import AlignedQuote
from yanhu.analyzer import AnalysisResult
from yanhu.manifest import Manifest, SegmentInfo
from yanhu.symbol_binder import bind_symbols_to_ocr

# Platform watermark keywords to filter out from highlights
PLATFORM_WATERMARKS = frozenset(
    [
        "小红书",
        "关注",
        "点赞",
        "收藏",
        "分享",
        "评论",
        "关注我",
        "点赞收藏",
        "双击",
        "私信",
        "直播",
        "粉丝",
        "抖音",
        "快手",
        "微博",
        "bilibili",
        "B站",
        "喜欢",
        "转发",
        "投币",
        "充电",
        "一键三连",
    ]
)

# Pattern for @username
_USERNAME_PATTERN = re.compile(r"^@[\w\u4e00-\u9fff]+$")


def is_platform_watermark(text: str) -> bool:
    """Check if text is a platform watermark or username mention.

    Args:
        text: Text to check

    Returns:
        True if text is a platform watermark
    """
    text = text.strip()
    # Check @username pattern
    if _USERNAME_PATTERN.match(text):
        return True
    # Check exact match with platform keywords
    if text in PLATFORM_WATERMARKS:
        return True
    return False


def filter_watermarks(ui_texts: list[str] | None) -> list[str]:
    """Filter out platform watermarks from ui_key_text list.

    Args:
        ui_texts: List of UI text strings

    Returns:
        Filtered list with watermarks removed
    """
    if not ui_texts:
        return []
    return [t for t in ui_texts if not is_platform_watermark(t)]


def is_low_value_ui(ui_texts: list[str] | None) -> bool:
    """Check if ui_key_text only contains platform watermarks.

    Args:
        ui_texts: List of UI text strings

    Returns:
        True if all items are watermarks (low-value segment)
    """
    if not ui_texts:
        return False
    return all(is_platform_watermark(t) for t in ui_texts)


# Sentence boundary punctuation for Chinese and English
_SENTENCE_BOUNDARIES = frozenset("。！？；，、.!?;,")


def truncate_at_sentence_boundary(text: str, max_chars: int = 40) -> str:
    """Truncate text at a sentence boundary, not mid-word.

    Args:
        text: Text to truncate
        max_chars: Maximum characters (default 40)

    Returns:
        Truncated text at nearest sentence boundary
    """
    if not text or len(text) <= max_chars:
        return text

    # Find last sentence boundary before max_chars
    truncated = text[:max_chars]
    last_boundary = -1
    for i, char in enumerate(truncated):
        if char in _SENTENCE_BOUNDARIES:
            last_boundary = i

    # If found boundary, truncate there (include the punctuation)
    if last_boundary > 0:
        return text[: last_boundary + 1]

    # No boundary found - return full truncated portion (no mid-word cut)
    return truncated


def load_aligned_quotes(analysis_path: Path) -> list[AlignedQuote]:
    """Load aligned_quotes from analysis JSON file.

    Args:
        analysis_path: Path to analysis JSON

    Returns:
        List of AlignedQuote objects
    """
    if not analysis_path.exists():
        return []
    try:
        with open(analysis_path, encoding="utf-8") as f:
            data = json.load(f)
        quotes_data = data.get("aligned_quotes", [])
        return [AlignedQuote.from_dict(q) for q in quotes_data]
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        return []


def get_highlight_quote(
    segment: SegmentInfo,
    session_dir: Path,
    analysis: AnalysisResult,
    filtered_ui: list[str],
) -> str | None:
    """Get quote text for highlight, with aligned_quotes priority.

    Priority:
    1. aligned_quotes with source="both" (first one) -> "ocr (asr)"
    2. aligned_quotes with source="ocr" (first one) -> ocr text
    3. aligned_quotes with source="asr" (first one) -> asr text
    4. ui_key_text (filtered, first 1-2 items joined with " / ")
    5. ocr_text (first non-empty)

    Symbols from ui_symbol_items are applied to individual text items based on
    time-based binding (per-item, not global prefix).

    Args:
        segment: Segment info
        session_dir: Session directory path
        analysis: Analysis result
        filtered_ui: Filtered UI text

    Returns:
        Quote text with symbols applied per-item, or None if not available
    """
    # Try aligned_quotes first
    if segment.analysis_path:
        analysis_path = session_dir / segment.analysis_path
        aligned_quotes = load_aligned_quotes(analysis_path)

        if aligned_quotes:
            # Priority 1: source="both" with full format
            for q in aligned_quotes:
                if q.source == "both" and q.ocr and q.asr:
                    return f"{q.ocr} ({q.asr})"

            # Priority 2: first ocr
            for q in aligned_quotes:
                if q.ocr:
                    return q.ocr

            # Priority 3: first asr
            for q in aligned_quotes:
                if q.asr:
                    return q.asr

    # Fallback to ui_key_text (filtered) - join up to 2 items with per-item symbol binding
    if filtered_ui:
        items_with_symbols = apply_symbols_to_text_items(filtered_ui[:2], analysis)
        if len(items_with_symbols) >= 2:
            quote = f"{items_with_symbols[0]} / {items_with_symbols[1]}"
        else:
            quote = items_with_symbols[0]

        # Backward compatibility: if no symbols were applied via ui_symbol_items,
        # try old ui_symbols with apply_heart_to_chunk
        original_quote = (
            f"{filtered_ui[0]} / {filtered_ui[1]}"
            if len(filtered_ui) >= 2
            else filtered_ui[0]
        )
        if quote == original_quote:
            quote = apply_heart_to_chunk(quote, analysis)

        return quote

    # Fallback to ocr_text (use pick_dialogue_text for best selection) with symbol binding
    dialogue = pick_dialogue_text(analysis.ocr_text)
    if dialogue:
        # Apply symbols to the selected dialogue
        items_with_symbols = apply_symbols_to_text_items([dialogue], analysis)
        quote = items_with_symbols[0]

        # Backward compatibility: if no symbols were applied via ui_symbol_items,
        # try old ui_symbols with apply_heart_to_chunk
        if quote == dialogue:
            quote = apply_heart_to_chunk(quote, analysis)

        return quote

    # Final fallback: facts[0] or caption
    description = analysis.get_description()
    if description:
        return description

    return None


def get_highlight_summary(analysis: AnalysisResult) -> str | None:
    """Get summary text for highlight (facts[0] + what_changed).

    Args:
        analysis: Analysis result

    Returns:
        Summary text (truncated at sentence boundary), or None
    """
    parts = []

    # facts[0]
    if analysis.facts:
        parts.append(analysis.facts[0])

    # what_changed (truncated)
    if analysis.what_changed:
        truncated_change = truncate_at_sentence_boundary(analysis.what_changed, max_chars=40)
        parts.append(truncated_change)

    if parts:
        return " / ".join(parts)

    # Fallback to caption
    if analysis.caption:
        return truncate_at_sentence_boundary(analysis.caption, max_chars=40)

    return None


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "00:01:30" for 90 seconds
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_time_range(start: float, end: float) -> str:
    """Format a time range as HH:MM:SS - HH:MM:SS.

    Args:
        start: Start time in seconds
        end: End time in seconds

    Returns:
        Formatted string like "00:00:00 - 00:01:00"
    """
    return f"{format_timestamp(start)} - {format_timestamp(end)}"


def format_frames_list(
    frames: list[str], max_display: int = 3, session_id: str | None = None
) -> str:
    """Format frames list as markdown links.

    Args:
        frames: List of relative frame paths (e.g., "frames/part_0001/frame_0001.jpg")
        max_display: Maximum frames to show before truncating
        session_id: Session ID for generating web-accessible URLs

    Returns:
        Markdown formatted string with frame links
    """
    if not frames:
        return "_No frames extracted_"

    displayed = frames[:max_display]

    if session_id:
        # Generate web-accessible URLs: /s/<session_id>/frames/<part_id>/<filename>
        # Parse frame path: frames/part_XXXX/frame_YYYY.jpg -> part_XXXX, frame_YYYY.jpg
        links = []
        for f in displayed:
            frame_path = Path(f)
            # Extract part_id (parent directory name) and filename
            if len(frame_path.parts) >= 2:
                part_id = frame_path.parts[-2]  # e.g., "part_0001"
                filename = frame_path.name       # e.g., "frame_0001.jpg"
                url = f"/s/{session_id}/frames/{part_id}/{filename}"
                links.append(f"[{filename}]({url})")
            else:
                # Fallback: use relative path if structure unexpected
                links.append(f"[{frame_path.name}]({f})")
    else:
        # Backward compatibility: use relative paths
        links = [f"[{Path(f).name}]({f})" for f in displayed]

    result = ", ".join(links)
    remaining = len(frames) - max_display
    if remaining > 0:
        result += f" ... ({remaining} more)"

    return result


def get_segment_description(
    segment: SegmentInfo,
    session_dir: Path | None = None,
) -> str:
    """Get description for a segment from analysis or return placeholder.

    Priority: error check > facts (first) > caption > TODO

    Args:
        segment: Segment info from manifest
        session_dir: Path to session directory (needed to load analysis)

    Returns:
        Description from analysis (facts or caption) if available,
        error message if analysis failed, otherwise TODO
    """
    if segment.analysis_path and session_dir:
        analysis_file = session_dir / segment.analysis_path
        if analysis_file.exists():
            try:
                analysis = AnalysisResult.load(analysis_file)
                # Check for error first - do not output raw_text
                if analysis.error:
                    return f"TODO: analysis failed (see {segment.analysis_path})"
                description = analysis.get_description()
                if description:
                    return description
            except (OSError, KeyError):
                pass  # Fall through to TODO

    return "TODO: describe what happened"


def get_segment_l1_fields(
    segment: SegmentInfo,
    session_dir: Path | None = None,
) -> tuple[str | None, list[str]]:
    """Get L1 fields (what_changed, ui_key_text) from analysis.

    Args:
        segment: Segment info from manifest
        session_dir: Path to session directory (needed to load analysis)

    Returns:
        Tuple of (what_changed, ui_key_text) - both may be None/empty
        Returns empty values if analysis has error
    """
    if segment.analysis_path and session_dir:
        analysis_file = session_dir / segment.analysis_path
        if analysis_file.exists():
            try:
                analysis = AnalysisResult.load(analysis_file)
                # Don't return L1 fields if there's an error
                if analysis.error:
                    return (None, [])
                return (analysis.what_changed, analysis.ui_key_text or [])
            except (OSError, KeyError):
                pass
    return (None, [])


def get_segment_asr_text(segment: SegmentInfo, session_dir: Path | None) -> str | None:
    """Get first ASR text for a segment.

    Args:
        segment: Segment info
        session_dir: Path to session directory

    Returns:
        First ASR text item, or None if not available
    """
    if session_dir and segment.analysis_path:
        analysis_file = session_dir / segment.analysis_path
        if analysis_file.exists():
            try:
                with open(analysis_file, encoding="utf-8") as f:
                    import json

                    data = json.load(f)
                asr_items = data.get("asr_items", [])
                if asr_items and len(asr_items) > 0:
                    return asr_items[0].get("text", "")
            except (OSError, KeyError, json.JSONDecodeError):
                pass
    return None


def get_segment_quote(segment: SegmentInfo, session_dir: Path | None) -> str | None:
    """Get the first aligned quote for a segment.

    Uses get_first_quote from aligner for proper schema handling.

    Args:
        segment: Segment info
        session_dir: Path to session directory

    Returns:
        First quote display text from aligned_quotes, or None if not available
    """
    if session_dir and segment.analysis_path:
        from yanhu.aligner import get_first_quote

        analysis_file = session_dir / segment.analysis_path
        return get_first_quote(analysis_file)
    return None


def _find_nearest_asr_text(
    symbol_t_rel: float, segment: SegmentInfo, session_dir: Path | None
) -> str | None:
    """Find nearest ASR text snippet to a symbol's timestamp using time-based matching.

    Time base: segment-relative (0..segment_duration).
    - symbol.t_rel is segment-relative (0..segment_duration)
    - ASR t_start/t_end are absolute (session time), converted to segment-relative
    - Matching uses midpoint: mid = (t_start + t_end) / 2
    - Returns ASR item with minimal |symbol_t_rel - mid|

    Args:
        symbol_t_rel: Symbol timestamp (segment-relative seconds)
        segment: Segment info with start_time for time base conversion
        session_dir: Path to session directory for loading ASR data

    Returns:
        Nearest ASR text snippet, or None if no ASR data available
    """
    if not session_dir or not segment.analysis_path:
        return None

    analysis_file = session_dir / segment.analysis_path
    if not analysis_file.exists():
        return None

    # Load asr_items from analysis JSON
    try:
        import json

        with open(analysis_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    asr_items = data.get("asr_items", [])
    if not asr_items:
        # Fall back to ui_key_text (first non-empty)
        ui_key_text = data.get("ui_key_text", [])
        for text in ui_key_text:
            if text and text.strip():
                return text.strip()
        return None

    # Time-based matching: find ASR item with minimal distance
    best_text = None
    min_distance = float("inf")

    for item in asr_items:
        text = item.get("text")
        t_start = item.get("t_start")
        t_end = item.get("t_end")

        if not text or t_start is None or t_end is None:
            continue

        # Convert ASR times from absolute (session time) to segment-relative
        # by subtracting segment.start_time
        t_start_rel = t_start - segment.start_time
        t_end_rel = t_end - segment.start_time

        # Calculate midpoint in segment-relative time
        mid = (t_start_rel + t_end_rel) / 2

        # Calculate distance
        distance = abs(symbol_t_rel - mid)

        if distance < min_distance:
            min_distance = distance
            best_text = text.strip()

    return best_text


def _find_nearest_context(
    symbol_t_rel: float,
    symbol_source_frame: str,
    segment: SegmentInfo,
    session_dir: Path | None,
) -> str | None:
    """Find nearest context text for a symbol with deterministic priority.

    Priority (stable, evidence-first):
    A1) Same-frame OCR item (spatial locality - highest priority)
    A2) Nearest OCR item by time distance (fallback)
    B) Nearest aligned_quote (if available)
    C) Nearest ASR item (fallback only)

    Time base: Global session time (t_rel is absolute seconds from session start).

    Args:
        symbol_t_rel: Symbol timestamp (global session time in seconds)
        symbol_source_frame: Symbol source frame filename for same-frame matching
        segment: Segment info with start_time for filtering
        session_dir: Path to session directory for loading analysis data

    Returns:
        Nearest context text snippet, or None if no context available
    """
    if not session_dir or not segment.analysis_path:
        return None

    analysis_file = session_dir / segment.analysis_path
    if not analysis_file.exists():
        return None

    # Load analysis JSON
    try:
        import json

        with open(analysis_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    # Priority A: Nearest OCR item
    # A1: Same-frame OCR (highest priority - spatial locality)
    # A2: Time-distance OCR (fallback)
    ocr_items = data.get("ocr_items", [])
    if ocr_items:
        # First try: same frame as symbol (spatial match)
        same_frame_ocr = []
        for ocr in ocr_items:
            ocr_frame = ocr.get("source_frame", "")
            if ocr_frame and ocr_frame == symbol_source_frame:
                text = ocr.get("text", "").strip()
                if text:
                    same_frame_ocr.append((ocr.get("t_rel", 0.0), text))

        if same_frame_ocr:
            # Return the nearest same-frame OCR by time (or first if equal)
            same_frame_ocr.sort(key=lambda x: abs(symbol_t_rel - x[0]))
            return same_frame_ocr[0][1]

        # Fallback: nearest OCR by time distance
        nearest_ocr = None
        min_distance = float("inf")
        for ocr in ocr_items:
            ocr_t_rel = ocr.get("t_rel", 0.0)
            distance = abs(symbol_t_rel - ocr_t_rel)
            if distance < min_distance:
                min_distance = distance
                nearest_ocr = ocr.get("text", "").strip()
        if nearest_ocr:
            return nearest_ocr

    # Priority B: Nearest aligned_quote
    aligned_quotes = data.get("aligned_quotes", [])
    if aligned_quotes:
        from yanhu.aligner import AlignedQuote

        nearest_quote = None
        min_distance = float("inf")
        for quote_data in aligned_quotes:
            quote = AlignedQuote.from_dict(quote_data)
            quote_t = quote.t  # Global session time
            distance = abs(symbol_t_rel - quote_t)
            if distance < min_distance:
                min_distance = distance
                # Prefer OCR over ASR in quotes
                nearest_quote = quote.ocr or quote.asr
        if nearest_quote:
            return nearest_quote

    # Priority C: Nearest ASR item (fallback)
    asr_items = data.get("asr_items", [])
    if asr_items:
        nearest_asr = None
        min_distance = float("inf")
        for asr in asr_items:
            # ASR uses midpoint: (t_start + t_end) / 2
            t_start = asr.get("t_start", 0.0)
            t_end = asr.get("t_end", 0.0)
            asr_mid = (t_start + t_end) / 2.0
            distance = abs(symbol_t_rel - asr_mid)
            if distance < min_distance:
                min_distance = distance
                nearest_asr = asr.get("text", "").strip()
        if nearest_asr:
            return nearest_asr

    # Fallback: ui_key_text (first non-empty)
    ui_key_text = data.get("ui_key_text", [])
    for text in ui_key_text:
        if text and text.strip():
            return text.strip()

    return None


def get_segment_symbols(
    segment: SegmentInfo, session_dir: Path | None, session_id: str
) -> str | None:
    """Get emoji symbols from ui_symbol_items with frame links and nearest context text.

    Args:
        segment: Segment info from manifest
        session_dir: Path to session directory
        session_id: Session identifier for frame URL generation

    Returns:
        Formatted symbols string with frame links and ASR context, or None if no symbols
    """
    if not session_dir:
        return None
    analysis = get_segment_analysis(segment, session_dir)
    if not analysis:
        return None

    # Get ui_symbol_items
    if not hasattr(analysis, "ui_symbol_items") or not analysis.ui_symbol_items:
        return None

    # Extract part_id from segment.id (e.g., "part_0002")
    part_id = segment.id

    # Filter symbols belonging to this part
    # ONLY include evidence_ocr symbols for display (conservative default)
    segment_symbols = []
    for item in analysis.ui_symbol_items:
        # Only display symbols with explicit origin="evidence_ocr"
        # Filter out: inferred_llm, None, missing origin
        if not hasattr(item, "origin") or item.origin != "evidence_ocr":
            continue

        # Use source_part_id if available for precise binding
        if hasattr(item, "source_part_id") and item.source_part_id:
            if item.source_part_id == part_id:
                segment_symbols.append(item)
        else:
            # If no source_part_id, include it (backward compat)
            segment_symbols.append(item)

    if not segment_symbols:
        return None

    # Deduplicate symbols by (symbol, source_frame)
    seen = set()
    unique_symbols = []
    for item in segment_symbols:
        key = (item.symbol, item.source_frame)
        if key not in seen:
            seen.add(key)
            unique_symbols.append(item)

    if not unique_symbols:
        return None

    # Format as linked symbols with optional ASR context
    symbol_links = []
    for item in unique_symbols:
        # Generate frame URL: /s/<session_id>/frames/<part_id>/<filename>
        frame_filename = item.source_frame
        frame_url = f"/s/{session_id}/frames/{part_id}/{frame_filename}"

        # Find nearest context text using priority: same-frame OCR → time OCR → quotes → ASR
        nearest_context = _find_nearest_context(
            item.t_rel, item.source_frame, segment, session_dir
        )

        # Create markdown link: [emoji](url) with optional context
        if nearest_context:
            # Truncate long context text
            context_display = (
                nearest_context[:30] + "..." if len(nearest_context) > 30 else nearest_context
            )
            symbol_links.append(f"[{item.symbol}]({frame_url}) (near: '{context_display}')")
        else:
            symbol_links.append(f"[{item.symbol}]({frame_url})")

    return " ".join(symbol_links)


def has_valid_claude_analysis(manifest: Manifest, session_dir: Path) -> bool:
    """Check if any segment has valid Claude analysis.

    Valid analysis means:
    - model starts with "claude-"
    - AND (facts is non-empty OR caption is non-empty)

    Args:
        manifest: Session manifest with segments
        session_dir: Path to session directory

    Returns:
        True if any segment has valid Claude analysis
    """
    for segment in manifest.segments:
        if not segment.analysis_path:
            continue
        analysis_file = session_dir / segment.analysis_path
        if not analysis_file.exists():
            continue
        try:
            analysis = AnalysisResult.load(analysis_file)
            # Check if model starts with "claude-"
            if not (analysis.model and analysis.model.startswith("claude-")):
                continue
            # Check if facts or caption is non-empty
            if analysis.facts or analysis.caption:
                return True
        except (OSError, KeyError):
            pass
    return False


def compose_timeline(manifest: Manifest, session_dir: Path | None = None) -> str:
    """Generate timeline markdown from manifest.

    Args:
        manifest: Session manifest with segments
        session_dir: Path to session directory (for loading analysis files)

    Returns:
        Markdown content for timeline.md
    """
    lines = [
        f"# Timeline: {manifest.session_id}",
        "",
        f"**Session**: {manifest.session_id}",
        f"**Segments**: {len(manifest.segments)}",
        "",
        "---",
        "",
        "## Timeline",
        "",
    ]

    for seg in manifest.segments:
        time_range = format_time_range(seg.start_time, seg.end_time)
        frames_str = format_frames_list(seg.frames, session_id=manifest.session_id)
        description = get_segment_description(seg, session_dir)
        what_changed, ui_key_text = get_segment_l1_fields(seg, session_dir)
        asr_text = get_segment_asr_text(seg, session_dir)
        quote_text = get_segment_quote(seg, session_dir)
        symbols_text = get_segment_symbols(seg, session_dir, manifest.session_id)

        lines.extend(
            [
                f"### {seg.id} ({time_range})",
                "",
                f"**Frames**: {frames_str}",
                "",
            ]
        )

        # Add symbols line if present (right after Frames)
        if symbols_text:
            lines.append(f"**Symbols**: {symbols_text}")
            lines.append("")

        lines.append(f"> {description}")

        # Add L1 fields if present
        if what_changed:
            lines.append(f"- change: {what_changed}")
        if ui_key_text:
            lines.append(f"- ui: {', '.join(ui_key_text)}")
        # Add ASR text if present
        if asr_text:
            lines.append(f"- asr: {asr_text}")
        # Add quote if aligned_quotes exists
        if quote_text:
            lines.append(f"- quote: {quote_text}")

        lines.append("")

    return "\n".join(lines)


def _extract_highlights_summaries(session_dir: Path, max_items: int = 5) -> list[str]:
    """Extract summary bullets from highlights.md if present.

    Args:
        session_dir: Path to session directory
        max_items: Maximum number of summary items to extract

    Returns:
        List of summary strings (empty if highlights.md missing or invalid)
    """
    highlights_path = session_dir / "highlights.md"
    if not highlights_path.exists():
        return []

    try:
        content = highlights_path.read_text(encoding="utf-8")
        summaries = []

        # Parse highlights format:
        # - [HH:MM:SS] <QUOTE> (segment=..., score=...)
        #   - summary: <SUMMARY>
        for line in content.splitlines():
            if line.strip().startswith("- summary:"):
                summary_text = line.strip()[len("- summary:") :].strip()
                if summary_text:
                    summaries.append(summary_text)
                if len(summaries) >= max_items:
                    break

        return summaries
    except Exception:
        # Graceful degradation if file is malformed
        return []


def _extract_timeline_snippets(session_dir: Path, max_items: int = 5) -> list[str]:
    """Extract facts/quotes from timeline.md as fallback summary.

    Args:
        session_dir: Path to session directory
        max_items: Maximum number of snippets to extract

    Returns:
        List of fact strings from timeline blockquotes (empty if timeline.md missing)
    """
    timeline_path = session_dir / "timeline.md"
    if not timeline_path.exists():
        return []

    try:
        content = timeline_path.read_text(encoding="utf-8")
        snippets = []

        # Parse timeline format: blockquotes are facts
        # > <FACT>
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(">") and len(stripped) > 2:
                fact = stripped[1:].strip()
                if fact and not fact.startswith("TODO"):
                    snippets.append(fact)
                if len(snippets) >= max_items:
                    break

        return snippets
    except Exception:
        # Graceful degradation if file is malformed
        return []


def _generate_overview_summary(session_dir: Path | None) -> str:
    """Generate deterministic summary from existing outputs.

    Priority order:
    1. highlights.md summaries (preferred)
    2. timeline.md facts (fallback)
    3. Neutral message if nothing available

    Args:
        session_dir: Path to session directory (None if not available)

    Returns:
        Markdown-formatted summary content
    """
    if session_dir is None:
        return "No summary available yet."

    # Try highlights first
    summaries = _extract_highlights_summaries(session_dir, max_items=5)
    if summaries:
        bullets = "\n".join(f"- {s}" for s in summaries)
        return bullets

    # Fallback to timeline facts
    snippets = _extract_timeline_snippets(session_dir, max_items=5)
    if snippets:
        bullets = "\n".join(f"- {s}" for s in snippets)
        return bullets

    # Nothing available
    return "No summary available yet."


def _generate_overview_outcome(manifest: Manifest) -> str:
    """Generate conservative outcome summary.

    Does NOT infer win/loss unless explicit field exists.

    Args:
        manifest: Session manifest

    Returns:
        Outcome string
    """
    # Check for partial transcription
    if manifest.transcribe_coverage:
        return "Partial session (limited transcription)."

    # Default: successful processing
    return "Session processed successfully. Highlights and timeline generated."


def compose_overview(manifest: Manifest, session_dir: Path | None = None) -> str:
    """Generate overview markdown from manifest.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory (optional, for summary generation)

    Returns:
        Markdown content for overview.md
    """
    # Parse session_id to extract game name
    parts = manifest.session_id.split("_")
    game_name = parts[2] if len(parts) >= 3 else "Unknown"
    run_tag = parts[3] if len(parts) >= 4 else "Unknown"

    # Calculate total duration from segments
    if manifest.segments:
        total_duration = max(seg.end_time for seg in manifest.segments)
    else:
        total_duration = 0.0

    total_frames = sum(len(seg.frames) for seg in manifest.segments)

    lines = [
        f"# Overview: {manifest.session_id}",
        "",
        "## Session Info",
        "",
        f"- **Game**: {game_name}",
        f"- **Run Tag**: {run_tag}",
        f"- **Duration**: {format_timestamp(total_duration)}",
        f"- **Segments**: {len(manifest.segments)}",
        f"- **Total Frames**: {total_frames}",
        f"- **Created**: {manifest.created_at}",
    ]

    # Add transcription coverage info if partial
    if manifest.transcribe_coverage:
        cov = manifest.transcribe_coverage
        lines.extend(
            [
                "",
                "## Transcription Coverage",
                "",
                "⚠️ **PARTIAL SESSION**: Transcription was limited to reduce processing time.",
                "",
                f"- **Transcribed**: {cov['processed']}/{cov['total']} segments",
                f"- **Skipped**: {cov['skipped_limit']} segments",
            ]
        )

    # Generate deterministic summary and outcome
    summary_content = _generate_overview_summary(session_dir)
    outcome_content = _generate_overview_outcome(manifest)

    lines.extend(
        [
            "",
            "## Summary",
            "",
            summary_content,
            "",
            "## Outcome",
            "",
            outcome_content,
            "",
        ]
    )

    return "\n".join(lines)


def write_timeline(manifest: Manifest, session_dir: Path) -> Path:
    """Write timeline.md to session directory.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory

    Returns:
        Path to written timeline.md
    """
    content = compose_timeline(manifest, session_dir)
    output_path = session_dir / "timeline.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def write_overview(manifest: Manifest, session_dir: Path) -> Path:
    """Write overview.md to session directory.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory

    Returns:
        Path to written overview.md
    """
    content = compose_overview(manifest, session_dir)
    output_path = session_dir / "overview.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


# Change keywords for scoring what_changed field
CHANGE_KEYWORDS = ["切换", "转为", "从", "到", "变为", "进入", "退出", "开始", "结束"]

# Default minimum score threshold for highlight entry
DEFAULT_MIN_SCORE = 80

# Penalty for segments with only watermark UI
WATERMARK_PENALTY = 50

# Dialogue punctuation markers (for picking dialogue-like text)
_DIALOGUE_PUNCTUATION = frozenset(["?", "？", "!", "！", "。", "，"])


def _is_dialogue_like(text: str) -> bool:
    """Check if text looks like dialogue (has question/exclamation marks).

    Args:
        text: Text to check

    Returns:
        True if text contains dialogue punctuation
    """
    return any(p in text for p in ["?", "？", "!", "！"])


def pick_dialogue_text(ocr_texts: list[str] | None) -> str | None:
    """Pick the most dialogue-like text from OCR results.

    Priority:
    1. Text containing ?/! (most dialogue-like)
    2. Longest text (more content)

    Args:
        ocr_texts: List of OCR text strings

    Returns:
        Best dialogue text, or None if empty
    """
    if not ocr_texts:
        return None

    # Filter out empty and very short strings
    candidates = [t.strip() for t in ocr_texts if t.strip() and len(t.strip()) > 2]
    if not candidates:
        return None

    # Prefer dialogue-like text (with ? or !)
    dialogue_candidates = [t for t in candidates if _is_dialogue_like(t)]
    if dialogue_candidates:
        # Among dialogue texts, pick longest
        return max(dialogue_candidates, key=len)

    # Fallback: pick longest text
    return max(candidates, key=len)


def _has_heart_symbol(ui_symbols: list[str] | None) -> bool:
    """Check if ui_symbols contains a heart emoji.

    Detects all heart emoji variants:
    - ❤️ / ❤ (red heart, with/without VS16)
    - 💛 💙 💚 💜 🖤 🤍 🤎 (colored hearts)
    - 💔 (broken heart)
    - ♥️ / ♥ (heart suit)
    - "heart" tag (case-insensitive string)

    Args:
        ui_symbols: List of detected symbols/emoji

    Returns:
        True if contains any heart emoji or "heart" tag
    """
    if not ui_symbols:
        return False

    # Define heart emoji Unicode codepoints (without variation selectors)
    heart_codepoints = {
        0x2764,  # ❤ HEAVY BLACK HEART
        0x2665,  # ♥ HEART SUIT
        0x1F49B,  # 💛 YELLOW HEART
        0x1F499,  # 💙 BLUE HEART
        0x1F49A,  # 💚 GREEN HEART
        0x1F49C,  # 💜 PURPLE HEART
        0x1F5A4,  # 🖤 BLACK HEART
        0x1F90D,  # 🤍 WHITE HEART
        0x1F90E,  # 🤎 BROWN HEART
        0x1F494,  # 💔 BROKEN HEART
    }

    for sym in ui_symbols:
        sym_lower = sym.lower()
        # Check for "heart" tag (string form)
        if "heart" in sym_lower:
            return True
        # Check for heart emoji codepoints
        for char in sym:
            if ord(char) in heart_codepoints:
                return True
    return False


# Keywords that should have ❤️ inserted before them (if present)
_HEART_TARGET_KEYWORDS = ["都做过", "都做過"]


def apply_heart_to_chunk(chunk: str, analysis: AnalysisResult) -> str:
    """Apply ❤️ to a segment's text chunk based on ui_symbols.

    DEPRECATED: This function uses keyword matching. Use apply_symbols_to_quote instead
    for time-based symbol binding.

    Rules:
    - If ui_symbols contains heart AND chunk contains "都做过"/"都做過":
      Insert ❤️ before that keyword
    - If ui_symbols contains heart but no target keyword:
      Prefix the entire chunk with ❤️
    - Otherwise: return chunk unchanged

    Args:
        chunk: The text chunk for this segment
        analysis: Analysis result (for ui_symbols)

    Returns:
        Modified chunk with ❤️ applied appropriately
    """
    ui_symbols = getattr(analysis, "ui_symbols", None)
    if not _has_heart_symbol(ui_symbols):
        return chunk

    # Check for target keywords
    for keyword in _HEART_TARGET_KEYWORDS:
        if keyword in chunk:
            # Insert ❤️ before the keyword
            return chunk.replace(keyword, f"❤️ {keyword}", 1)

    # No target keyword found - prefix the entire chunk
    return f"❤️ {chunk}"


def apply_symbols_to_quote(quote: str, analysis: AnalysisResult) -> str:
    """Apply symbols to quote based on time-based binding (no keyword matching).

    Uses symbol_binder to find nearest OCR item by time. If the quote text
    matches a bound OCR item, adds the symbol as prefix.

    Falls back to simple prefix behavior for backward compatibility when
    time-based data (ui_symbol_items, ocr_items) is not available.

    Args:
        quote: The quote text for this segment
        analysis: Analysis result with ui_symbol_items and ocr_items

    Returns:
        Quote with bound symbols as prefix (e.g., "❤️ 对话文本")
    """
    # Get ui_symbol_items and ocr_items from analysis
    ui_symbol_items = getattr(analysis, "ui_symbol_items", None)
    ocr_items = getattr(analysis, "ocr_items", None)

    # If time-based data is available, use time-based binding
    if ui_symbol_items and ocr_items:
        # Bind symbols to OCR items by time
        bound_symbols = bind_symbols_to_ocr(ui_symbol_items, ocr_items, threshold=1.5)

        # Find symbols bound to this quote text
        symbols_for_quote = []
        for bound in bound_symbols:
            if bound.source == "bound" and bound.ocr_text:
                # Check if quote contains this OCR text
                if bound.ocr_text in quote:
                    symbols_for_quote.append(bound.symbol)

        # Apply symbols as prefix
        if symbols_for_quote:
            symbols_str = " ".join(symbols_for_quote)
            return f"{symbols_str} {quote}"

    # Fallback: use old behavior for backward compatibility
    # If ui_symbols contains heart, check for keywords or prefix
    ui_symbols = getattr(analysis, "ui_symbols", None)
    if _has_heart_symbol(ui_symbols):
        # Check for target keywords
        for keyword in _HEART_TARGET_KEYWORDS:
            if keyword in quote:
                # Insert ❤️ before the keyword
                return quote.replace(keyword, f"❤️ {keyword}", 1)
        # No target keyword found - prefix the entire quote
        return f"❤️ {quote}"

    return quote


def apply_symbols_to_text_items(
    text_items: list[str],
    analysis: AnalysisResult,
) -> list[str]:
    """Apply symbols to individual text items based on time-based binding.

    For each text item, checks if any symbol is bound to an OCR item
    containing this text. If found, prefixes the text item with the symbol.

    Args:
        text_items: List of text strings (from ui_key_text or ocr_text)
        analysis: Analysis result with ui_symbol_items and ocr_items

    Returns:
        List of text items with symbols applied to matching items
    """
    ui_symbol_items = getattr(analysis, "ui_symbol_items", None)
    ocr_items = getattr(analysis, "ocr_items", None)

    if not ui_symbol_items or not ocr_items:
        return text_items

    # Bind symbols to OCR items by time
    bound_symbols = bind_symbols_to_ocr(ui_symbol_items, ocr_items, threshold=1.5)

    # Create mapping: ocr_text -> symbols
    ocr_to_symbols: dict[str, list[str]] = {}
    for bound in bound_symbols:
        if bound.source == "bound" and bound.ocr_text:
            if bound.ocr_text not in ocr_to_symbols:
                ocr_to_symbols[bound.ocr_text] = []
            ocr_to_symbols[bound.ocr_text].append(bound.symbol)

    # Apply symbols to matching text items
    result = []
    for item in text_items:
        # Check if this item matches any OCR text with bound symbols
        symbols = ocr_to_symbols.get(item, [])
        if symbols:
            symbols_str = " ".join(symbols)
            result.append(f"{symbols_str} {item}")
        else:
            result.append(item)

    return result


def get_standalone_symbols(
    analysis: AnalysisResult,
    segment_id: str,
    segment_start_time: float,
) -> list[tuple[str, float]]:
    """Get standalone symbols (not bound to any OCR text) from analysis.

    Returns list of (symbol, absolute_time) tuples for symbols that don't
    match any OCR text within the threshold.

    Args:
        analysis: Analysis result with ui_symbol_items and ocr_items
        segment_id: Segment ID for reference
        segment_start_time: Segment start time in seconds

    Returns:
        List of (symbol, absolute_time) tuples for standalone symbols
    """
    ui_symbol_items = getattr(analysis, "ui_symbol_items", None)
    ocr_items = getattr(analysis, "ocr_items", None)

    if not ui_symbol_items:
        return []

    # If no ocr_items, all symbols are standalone
    if not ocr_items:
        return [
            (item.symbol, segment_start_time + item.t_rel) for item in ui_symbol_items
        ]

    # Bind symbols to OCR items by time
    bound_symbols = bind_symbols_to_ocr(ui_symbol_items, ocr_items, threshold=1.5)

    # Extract standalone symbols (source="symbol")
    standalone = []
    for bound in bound_symbols:
        if bound.source == "symbol":
            # Find the original ui_symbol_item to get t_rel
            for item in ui_symbol_items:
                if item.symbol == bound.symbol:
                    absolute_time = segment_start_time + item.t_rel
                    standalone.append((bound.symbol, absolute_time))
                    break

    return standalone


def get_highlight_text(
    analysis: AnalysisResult,
    filtered_ui: list[str],
) -> str:
    """Get the highlight text for a segment with per-item symbol binding.

    Priority:
    1. ui_key_text (filtered) - join first 2 with " / ", apply symbols per-item
    2. Best dialogue from ocr_text
    3. facts[0] or caption

    Symbols are applied to individual text items based on time-based binding,
    not as a global prefix.

    Args:
        analysis: Analysis result
        filtered_ui: UI text with watermarks removed

    Returns:
        Highlight text string with symbols applied to matching items
    """
    # Priority 1: ui_key_text (filtered) with per-item symbol binding
    if filtered_ui:
        items_with_symbols = apply_symbols_to_text_items(filtered_ui[:2], analysis)
        if len(items_with_symbols) >= 2:
            return f"{items_with_symbols[0]} / {items_with_symbols[1]}"
        return items_with_symbols[0]

    # Priority 2: Best dialogue from ocr_text
    dialogue = pick_dialogue_text(analysis.ocr_text)
    if dialogue:
        # Apply symbols to the selected dialogue
        items_with_symbols = apply_symbols_to_text_items([dialogue], analysis)
        return items_with_symbols[0]

    # Priority 3: facts[0] or caption
    description = analysis.get_description()
    if description:
        return description

    return "No description"


def has_dialogue_content(analysis: AnalysisResult, filtered_ui: list[str]) -> bool:
    """Check if segment has dialogue content (ui_key_text or ocr_text).

    Args:
        analysis: Analysis result
        filtered_ui: UI text with watermarks removed

    Returns:
        True if segment has dialogue content
    """
    if filtered_ui:
        return True
    if analysis.ocr_text and any(t.strip() for t in analysis.ocr_text):
        return True
    return False


def score_segment(analysis: AnalysisResult) -> int:
    """Score a segment for highlight selection.

    Scoring rules (deterministic, reproducible):
    - ui_key_text (filtered, non-watermark): +100 base + 10 per item
    - If ui_key_text only contains watermarks: -50 penalty
    - ocr_text count: +10 per item, +1 per 10 chars (medium weight)
    - facts: +50 base + 10 per fact item (high weight for analyzed content)
    - caption: +20 (medium weight for description)
    - scene_label Dialogue/Combat/Cutscene: +50/+40/+30 (medium-high weight)
    - what_changed contains change keywords: +5 per keyword (low weight)

    Args:
        analysis: AnalysisResult to score

    Returns:
        Integer score (higher = more highlight-worthy)
    """
    score = 0

    # Filter watermarks from ui_key_text
    filtered_ui = filter_watermarks(analysis.ui_key_text)

    # ui_key_text (filtered): highest weight
    if filtered_ui:
        score += 100
        # Bonus for more items
        score += len(filtered_ui) * 10

    # Penalty if original had UI but all were watermarks (low-value)
    if is_low_value_ui(analysis.ui_key_text):
        score -= WATERMARK_PENALTY

    # ocr_text: medium weight
    if analysis.ocr_text:
        score += len(analysis.ocr_text) * 10
        # Bonus for text length
        total_chars = sum(len(t) for t in analysis.ocr_text)
        score += total_chars // 10

    # facts: high weight (reward analyzed content even without UI/OCR)
    if analysis.facts:
        score += 50  # Base reward for having facts
        score += len(analysis.facts) * 10  # Bonus per fact

    # caption: medium weight (fallback description)
    if analysis.caption:
        score += 20

    # scene_label: medium-high weight
    scene_weights = {
        "Dialogue": 50,
        "Combat": 40,
        "Cutscene": 30,
    }
    if analysis.scene_label in scene_weights:
        score += scene_weights[analysis.scene_label]

    # what_changed contains change keywords: low weight
    if analysis.what_changed:
        for keyword in CHANGE_KEYWORDS:
            if keyword in analysis.what_changed:
                score += 5

    return score


def get_segment_analysis(
    segment: SegmentInfo,
    session_dir: Path,
) -> AnalysisResult | None:
    """Load analysis for a segment if available.

    Args:
        segment: Segment info from manifest
        session_dir: Path to session directory

    Returns:
        AnalysisResult if available and valid, None otherwise
    """
    if not segment.analysis_path:
        return None
    analysis_file = session_dir / segment.analysis_path
    if not analysis_file.exists():
        return None
    try:
        analysis = AnalysisResult.load(analysis_file)
        # Skip errored analysis
        if analysis.error:
            return None
        return analysis
    except (OSError, KeyError):
        return None


def _get_ui_dedup_key(ui_texts: list[str] | None) -> tuple[str, ...] | None:
    """Get deduplication key for ui_key_text.

    Args:
        ui_texts: List of UI text strings (already filtered)

    Returns:
        Tuple key for deduplication, or None if empty
    """
    if not ui_texts:
        return None
    return tuple(sorted(ui_texts))


def _extract_segment_number(segment_id: str) -> int:
    """Extract numeric part from segment ID like 'part_0003'.

    Args:
        segment_id: Segment ID string

    Returns:
        Numeric part as integer, or 0 if not found
    """
    match = re.search(r"(\d+)$", segment_id)
    if match:
        return int(match.group(1))
    return 0


def _are_adjacent_segments(seg1_id: str, seg2_id: str) -> bool:
    """Check if two segment IDs are adjacent (consecutive numbers).

    Args:
        seg1_id: First segment ID
        seg2_id: Second segment ID

    Returns:
        True if segments are adjacent
    """
    num1 = _extract_segment_number(seg1_id)
    num2 = _extract_segment_number(seg2_id)
    return abs(num1 - num2) == 1


def _merge_highlight_texts(text1: str, text2: str) -> str:
    """Merge two highlight texts with separator.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Merged text with " / " separator
    """
    return f"{text1} / {text2}"


def _merge_segment_ids(id1: str, id2: str) -> str:
    """Merge two segment IDs for display.

    Args:
        id1: First segment ID (e.g., "part_0003")
        id2: Second segment ID (e.g., "part_0004")

    Returns:
        Merged ID (e.g., "part_0003+0004")
    """
    num1 = _extract_segment_number(id1)
    num2 = _extract_segment_number(id2)
    # Always put smaller number first
    if num1 > num2:
        num1, num2 = num2, num1
        id1, id2 = id2, id1
    # Extract prefix from first ID
    prefix = id1[: id1.rfind("_") + 1] if "_" in id1 else ""
    return f"{prefix}{num1:04d}+{num2:04d}"


def get_content_tier(
    analysis: AnalysisResult,
    segment: SegmentInfo,
    session_dir: Path,
) -> str:
    """Classify segment content into tiers for highlight selection.

    Tier A (high priority): Has aligned_quotes, ui_key_text (filtered), or ui_symbol_items
    Tier B (medium): Has ocr_text or what_changed
    Tier C (low): Only has facts/caption (no dialogue/symbols/alignment)

    Note: asr_items alone do not qualify for Tier A, as they often contain
    noise/artifacts. Only actual dialogue (ui_key_text) and symbols count as high-value.

    Args:
        analysis: Analysis result
        segment: Segment info
        session_dir: Session directory path

    Returns:
        "A", "B", or "C"
    """
    # Check for Tier A indicators
    # 1. Check aligned_quotes
    if segment.analysis_path:
        analysis_path = session_dir / segment.analysis_path
        aligned_quotes = load_aligned_quotes(analysis_path)
        if aligned_quotes:
            return "A"

    # 2. Check ui_key_text (filtered)
    filtered_ui = filter_watermarks(analysis.ui_key_text)
    if filtered_ui:
        return "A"

    # 3. Check ui_symbol_items
    ui_symbol_items = getattr(analysis, "ui_symbol_items", None)
    if ui_symbol_items:
        return "A"

    # Note: asr_items not checked - often contains noise/artifacts
    # Only ui_key_text (dialogue) and symbols count as high-value content

    # Check for Tier B indicators
    if analysis.ocr_text or analysis.what_changed:
        return "B"

    # Default: Tier C (only facts/caption)
    return "C"


def normalize_description(text: str) -> str:
    """Normalize description text for deduplication.

    Removes punctuation, whitespace, and common particles to detect
    semantically similar descriptions.

    Args:
        text: Description text (facts[0] or caption)

    Returns:
        Normalized text for comparison
    """
    import re
    import unicodedata

    if not text:
        return ""

    # Convert to lowercase
    normalized = text.lower()

    # Remove punctuation (including Chinese punctuation)
    normalized = re.sub(r"[.,;:!?。，、；：！？「」『』【】（）()《》<>\-_/\\]", "", normalized)

    # Remove whitespace
    normalized = re.sub(r"\s+", "", normalized)

    # Normalize unicode (e.g., full-width to half-width)
    normalized = unicodedata.normalize("NFKC", normalized)

    return normalized


def is_similar_description(desc1: str, desc2: str, threshold: float = 0.5) -> bool:
    """Check if two descriptions are semantically similar.

    Uses character n-gram overlap to detect similarity. Descriptions are
    considered similar if they share >= threshold of n-grams.

    Args:
        desc1: First description
        desc2: Second description
        threshold: Similarity threshold (0.0-1.0), default 0.5

    Returns:
        True if descriptions are similar
    """
    if not desc1 or not desc2:
        return False

    # Extract character bi-grams and tri-grams for Chinese text
    def extract_ngrams(text: str, n: int = 2) -> set[str]:
        normalized = normalize_description(text)
        if len(normalized) < n:
            return {normalized}
        return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}

    # Combine bi-grams and tri-grams for better coverage
    ngrams1 = extract_ngrams(desc1, 2) | extract_ngrams(desc1, 3)
    ngrams2 = extract_ngrams(desc2, 2) | extract_ngrams(desc2, 3)

    if not ngrams1 or not ngrams2:
        return False

    # Calculate overlap ratio (Jaccard similarity)
    intersection = ngrams1 & ngrams2
    union = ngrams1 | ngrams2
    similarity = len(intersection) / len(union) if union else 0

    return similarity >= threshold


@dataclass
class HighlightEntry:
    """A highlight entry with quote, summary, and metadata."""

    score: int
    segment_id: str
    start_time: float
    quote: str | None  # Quote text (from aligned_quotes or fallback)
    summary: str | None  # Summary text (facts[0] / what_changed)
    symbols: str | None = None  # Emoji symbols with frame links

    def has_readable_content(self) -> bool:
        """Check if this highlight has readable text content (not symbols-only).

        A valid highlight must have at least one of:
        - Non-empty quote with readable text (not just emoji/punctuation)
        - Non-empty summary

        Returns:
            True if highlight has readable content, False if symbols-only
        """
        import re

        # Check summary first (most reliable)
        if self.summary and self.summary.strip():
            return True

        # Check quote for readable text
        if self.quote:
            # Strip whitespace and common punctuation
            text = self.quote.strip()
            # Remove emoji/symbols using regex (keep only word characters and spaces)
            readable_text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
            # If there's any remaining non-whitespace text, it's readable
            if readable_text.strip():
                return True

        # No readable content found
        return False


def _create_fallback_highlight(
    manifest: Manifest, session_dir: Path
) -> HighlightEntry:
    """Create a fallback highlight entry when no highlights pass threshold.

    ALWAYS returns a fallback entry. Uses first segment with valid analysis if available,
    otherwise uses first segment from manifest with generic text.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory

    Returns:
        HighlightEntry with score=0 (always non-None)
    """
    # Try to find first segment with analysis
    for segment in manifest.segments:
        analysis = get_segment_analysis(segment, session_dir)
        if analysis is None:
            continue

        # Use first fact or caption as fallback summary
        summary = None
        if analysis.facts:
            summary = analysis.facts[0]
        elif analysis.caption:
            summary = analysis.caption
        elif analysis.what_changed:
            summary = analysis.what_changed[:100]  # Truncate

        # Use first aligned quote if available, otherwise "Fallback highlight"
        quote = None
        if segment.analysis_path:
            analysis_path = session_dir / segment.analysis_path
            aligned_quotes = load_aligned_quotes(analysis_path)
            if aligned_quotes and len(aligned_quotes) > 0:
                # Get text from first quote (prefer ocr, then asr)
                first_quote = aligned_quotes[0]
                quote = first_quote.ocr or first_quote.asr

        if not quote:
            quote = "Fallback highlight (no content above threshold)"

        return HighlightEntry(
            score=0,
            segment_id=segment.id,
            start_time=segment.start_time,
            quote=quote,
            summary=summary,
            symbols=None,
        )

    # No segments have analysis - use first segment with generic fallback
    if manifest.segments:
        first_segment = manifest.segments[0]
        return HighlightEntry(
            score=0,
            segment_id=first_segment.id,
            start_time=first_segment.start_time,
            quote="Fallback highlight (analysis unavailable)",
            summary="Session processed but no analysis data available",
            symbols=None,
        )

    # No segments at all - use timestamp 0 with generic fallback
    # This should never happen in practice, but handle gracefully
    return HighlightEntry(
        score=0,
        segment_id="unknown",
        start_time=0.0,
        quote="Fallback highlight (no segments)",
        summary="Session manifest contains no segments",
        symbols=None,
    )


def compose_highlights(
    manifest: Manifest,
    session_dir: Path,
    top_k: int = 8,
    min_score: int = DEFAULT_MIN_SCORE,
) -> str:
    """Generate highlights markdown from manifest.

    Selection rules:
    1. Score all segments, filter watermarks from ui_key_text
    2. Primary selection: segments with score >= min_score only (no low-score fill)
    3. Deduplicate by ui_key_text (keep highest score)
    4. Merge adjacent dialogue segments (max 2 quotes per merged entry)
    5. Take top-k from merged list
    6. Output format: quote + summary line

    Output format per highlight:
    - [HH:MM:SS] <QUOTE> (segment=..., score=...)
      - summary: <facts[0]> / <what_changed truncated>

    Args:
        manifest: Session manifest with segments
        session_dir: Path to session directory
        top_k: Maximum number of highlights to include
        min_score: Minimum score threshold (strict - no fill below this)

    Returns:
        Markdown content for highlights.md
    """
    # Score all segments with valid analysis
    # Each entry: (score, segment, analysis, filtered_ui, quote, summary, tier)
    scored_segments: list[
        tuple[int, SegmentInfo, AnalysisResult, list[str], str | None, str | None, str]
    ] = []

    for segment in manifest.segments:
        analysis = get_segment_analysis(segment, session_dir)
        if analysis is None:
            continue
        score = score_segment(analysis)
        filtered_ui = filter_watermarks(analysis.ui_key_text)
        quote = get_highlight_quote(segment, session_dir, analysis, filtered_ui)
        summary = get_highlight_summary(analysis)
        tier = get_content_tier(analysis, segment, session_dir)
        scored_segments.append((score, segment, analysis, filtered_ui, quote, summary, tier))

    # Group by tier
    tier_a = [
        (s, seg, a, ui, q, sum)
        for s, seg, a, ui, q, sum, t in scored_segments
        if t == "A" and s >= min_score
    ]
    tier_b = [
        (s, seg, a, ui, q, sum)
        for s, seg, a, ui, q, sum, t in scored_segments
        if t == "B" and s >= min_score
    ]
    tier_c = [
        (s, seg, a, ui, q, sum)
        for s, seg, a, ui, q, sum, t in scored_segments
        if t == "C" and s >= min_score
    ]

    # Sort each tier by score (descending), then by time (ascending)
    tier_a.sort(key=lambda x: (-x[0], x[1].start_time))
    tier_b.sort(key=lambda x: (-x[0], x[1].start_time))
    tier_c.sort(key=lambda x: (-x[0], x[1].start_time))

    # Tiered selection: prioritize Tier A > B > C
    primary_selection: list[
        tuple[int, SegmentInfo, AnalysisResult, list[str], str | None, str | None]
    ] = []
    seen_ui_keys: set[tuple[str, ...]] = set()

    # Add Tier A (high priority: dialogue/symbols/alignment)
    # No deduplication for Tier A - preserve all dialogue/symbol content
    for score, segment, analysis, filtered_ui, quote, summary in tier_a:
        # Deduplicate by ui_key_text only (preserve dialogue variants)
        ui_key = _get_ui_dedup_key(filtered_ui)
        if ui_key is not None:
            if ui_key in seen_ui_keys:
                continue
            seen_ui_keys.add(ui_key)
        primary_selection.append((score, segment, analysis, filtered_ui, quote, summary))

    # Add Tier B (medium priority: OCR/what_changed)
    # Deduplicate by similarity for visual descriptions without dialogue
    seen_tier_b_descriptions: list[str] = []  # Track Tier B descriptions
    for score, segment, analysis, filtered_ui, quote, summary in tier_b:
        # For Tier B without ui_key_text, deduplicate by similarity
        if not filtered_ui:
            desc = analysis.facts[0] if analysis.facts else analysis.caption or ""
            if not desc:
                primary_selection.append(
                    (score, segment, analysis, filtered_ui, quote, summary)
                )
                continue

            # Check similarity against all previously seen Tier B descriptions
            # Use low threshold (0.1) to very aggressively catch similar visual descriptions
            # This prevents flooding highlights with repetitive "戴眼镜/特写" type content
            is_duplicate = False
            for seen_desc in seen_tier_b_descriptions:
                if is_similar_description(desc, seen_desc, threshold=0.1):
                    is_duplicate = True
                    break

            if is_duplicate:
                continue  # Skip similar description

            seen_tier_b_descriptions.append(desc)

        primary_selection.append((score, segment, analysis, filtered_ui, quote, summary))

    # Add Tier C (low priority: only facts/caption)
    # Strong deduplication by similarity detection
    seen_tier_c_descriptions: list[str] = []  # Track Tier C descriptions
    for score, segment, analysis, filtered_ui, quote, summary in tier_c:
        desc = analysis.facts[0] if analysis.facts else analysis.caption or ""
        if not desc:
            continue

        # Check similarity against all previously seen Tier C descriptions
        # Use threshold 0.5 to catch semantically similar visual descriptions
        is_duplicate = False
        for seen_desc in seen_tier_c_descriptions:
            if is_similar_description(desc, seen_desc, threshold=0.5):
                is_duplicate = True
                break

        if is_duplicate:
            continue  # Skip similar description

        seen_tier_c_descriptions.append(desc)
        primary_selection.append((score, segment, analysis, filtered_ui, quote, summary))

    # Sort primary selection by time for merging
    primary_selection.sort(key=lambda x: x[1].start_time)

    # Merge adjacent dialogue segments
    merged_highlights: list[HighlightEntry] = []
    segment_duration = manifest.segment_duration_seconds

    i = 0
    while i < len(primary_selection):
        score1, seg1, analysis1, ui1, quote1, summary1 = primary_selection[i]
        has_dialogue1 = has_dialogue_content(analysis1, ui1)

        # Check if next segment can be merged
        if i + 1 < len(primary_selection):
            score2, seg2, analysis2, ui2, quote2, summary2 = primary_selection[i + 1]
            has_dialogue2 = has_dialogue_content(analysis2, ui2)

            # Merge conditions: adjacent, both have dialogue, time gap <= segment_duration
            time_gap = seg2.start_time - seg1.end_time
            if (
                has_dialogue1
                and has_dialogue2
                and _are_adjacent_segments(seg1.id, seg2.id)
                and time_gap <= segment_duration
            ):
                # Merge: max 1 quote from each segment (total max 2)
                merged_id = _merge_segment_ids(seg1.id, seg2.id)
                merged_score = max(score1, score2)

                # Merge quotes: each segment contributes at most 1 quote
                # Note: symbols already applied per-item in get_highlight_text
                merged_quote = None
                if quote1 and quote2:
                    merged_quote = f"{quote1} / {quote2}"
                elif quote1:
                    merged_quote = quote1
                elif quote2:
                    merged_quote = quote2

                # Merge summaries: prefer first, fallback to second
                merged_summary = summary1 or summary2

                # Merge symbols from both segments
                symbols1 = get_segment_symbols(seg1, session_dir, manifest.session_id)
                symbols2 = get_segment_symbols(seg2, session_dir, manifest.session_id)
                merged_symbols = None
                if symbols1 and symbols2:
                    merged_symbols = f"{symbols1} {symbols2}"
                elif symbols1:
                    merged_symbols = symbols1
                elif symbols2:
                    merged_symbols = symbols2

                merged_highlights.append(
                    HighlightEntry(
                        score=merged_score,
                        segment_id=merged_id,
                        start_time=seg1.start_time,
                        quote=merged_quote,
                        summary=merged_summary,
                        symbols=merged_symbols,
                    )
                )
                i += 2  # Skip both segments
                continue

        # No merge - add single segment
        # Note: symbols already applied per-item in get_highlight_text
        final_quote = quote1
        symbols = get_segment_symbols(seg1, session_dir, manifest.session_id)
        merged_highlights.append(
            HighlightEntry(
                score=score1,
                segment_id=seg1.id,
                start_time=seg1.start_time,
                quote=final_quote,
                summary=summary1,
                symbols=symbols,
            )
        )
        i += 1

    # Add standalone symbol entries (symbols not bound to any OCR text)
    for score, segment, analysis, filtered_ui, quote, summary in primary_selection:
        standalone_symbols = get_standalone_symbols(
            analysis, segment.id, segment.start_time
        )
        for symbol, absolute_time in standalone_symbols:
            # Create a highlight entry for standalone symbol with reduced score
            # Use half the segment score since it's just a symbol without context
            symbol_score = score // 2
            merged_highlights.append(
                HighlightEntry(
                    score=symbol_score,
                    segment_id=segment.id,
                    start_time=absolute_time,
                    quote=symbol,
                    summary=None,
                )
            )

    # Filter out symbols-only entries (no readable content)
    # Keep only highlights with readable text (quote or summary)
    valid_highlights = [h for h in merged_highlights if h.has_readable_content()]

    # Sort by score (descending) and take top-k
    valid_highlights.sort(key=lambda x: -x.score)
    top_highlights = valid_highlights[:top_k]

    # Re-sort by time for display
    top_highlights.sort(key=lambda x: x.start_time)

    # Generate markdown
    lines = [
        f"# Highlights: {manifest.session_id}",
        "",
        f"**Top {len(top_highlights)} moments** (selected by content score)",
        "",
    ]

    for entry in top_highlights:
        timestamp = format_timestamp(entry.start_time)
        quote_text = entry.quote or "No quote"

        # Main highlight line with quote
        lines.append(
            f"- [{timestamp}] {quote_text} (segment={entry.segment_id}, score={entry.score})"
        )

        # Summary line (indented)
        if entry.summary:
            lines.append(f"  - summary: {entry.summary}")

        # Symbols line (indented)
        if entry.symbols:
            lines.append(f"  - symbols: {entry.symbols}")

    # If no highlights found, create a fallback entry
    if not top_highlights:
        fallback_entry = _create_fallback_highlight(manifest, session_dir)
        lines[2] = "**Top 1 moments** (fallback entry - no highlights above threshold)"
        timestamp = format_timestamp(fallback_entry.start_time)
        quote_text = fallback_entry.quote or "No quote"
        lines.append(
            f"- [{timestamp}] {quote_text} "
            f"(segment={fallback_entry.segment_id}, score={fallback_entry.score})"
        )
        if fallback_entry.summary:
            lines.append(f"  - summary: {fallback_entry.summary}")

    lines.append("")
    return "\n".join(lines)


def write_highlights(
    manifest: Manifest,
    session_dir: Path,
    top_k: int = 8,
    min_score: int = DEFAULT_MIN_SCORE,
) -> Path:
    """Write highlights.md to session directory.

    Args:
        manifest: Session manifest
        session_dir: Path to session directory
        top_k: Maximum number of highlights
        min_score: Minimum score threshold for primary selection

    Returns:
        Path to written highlights.md
    """
    content = compose_highlights(manifest, session_dir, top_k, min_score)
    output_path = session_dir / "highlights.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path
