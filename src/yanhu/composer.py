"""Session composition: generate timeline and overview documents."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from yanhu.aligner import AlignedQuote
from yanhu.analyzer import AnalysisResult
from yanhu.manifest import Manifest, SegmentInfo

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

    Note: Does NOT apply heart emoji - caller should use apply_heart_to_chunk.

    Args:
        segment: Segment info
        session_dir: Session directory path
        analysis: Analysis result
        filtered_ui: Filtered UI text

    Returns:
        Quote text (without heart emoji), or None if not available
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

    # Fallback to ui_key_text (filtered) - join up to 2 items
    if filtered_ui:
        if len(filtered_ui) >= 2:
            return f"{filtered_ui[0]} / {filtered_ui[1]}"
        return filtered_ui[0]

    # Fallback to ocr_text (use pick_dialogue_text for best selection)
    dialogue = pick_dialogue_text(analysis.ocr_text)
    if dialogue:
        return dialogue

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


def format_frames_list(frames: list[str], max_display: int = 3) -> str:
    """Format frames list as markdown links.

    Args:
        frames: List of relative frame paths
        max_display: Maximum frames to show before truncating

    Returns:
        Markdown formatted string with frame links
    """
    if not frames:
        return "_No frames extracted_"

    displayed = frames[:max_display]
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
        frames_str = format_frames_list(seg.frames)
        description = get_segment_description(seg, session_dir)
        what_changed, ui_key_text = get_segment_l1_fields(seg, session_dir)
        asr_text = get_segment_asr_text(seg, session_dir)
        quote_text = get_segment_quote(seg, session_dir)

        lines.extend(
            [
                f"### {seg.id} ({time_range})",
                "",
                f"**Frames**: {frames_str}",
                "",
                f"> {description}",
            ]
        )

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


def compose_overview(manifest: Manifest) -> str:
    """Generate overview markdown from manifest.

    Args:
        manifest: Session manifest

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
        "",
        "## Summary",
        "",
        "> TODO: AI-generated summary will appear here after Vision/ASR analysis.",
        "",
        "## Outcome",
        "",
        "> TODO: Session outcome (win/loss/progress) to be determined.",
        "",
    ]

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
    content = compose_overview(manifest)
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

    Args:
        ui_symbols: List of detected symbols/emoji

    Returns:
        True if contains ❤️ or heart-like symbol
    """
    if not ui_symbols:
        return False
    for sym in ui_symbols:
        sym_lower = sym.lower()
        if "❤" in sym or "heart" in sym_lower:
            return True
    return False


# Keywords that should have ❤️ inserted before them (if present)
_HEART_TARGET_KEYWORDS = ["都做过", "都做過"]


def apply_heart_to_chunk(chunk: str, analysis: AnalysisResult) -> str:
    """Apply ❤️ to a segment's text chunk based on ui_symbols.

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


def get_highlight_text(
    analysis: AnalysisResult,
    filtered_ui: list[str],
) -> str:
    """Get the highlight text for a segment (without ❤️ prefix).

    Priority:
    1. ui_key_text (filtered) - join first 2 with " / "
    2. Best dialogue from ocr_text
    3. facts[0] or caption

    Note: ❤️ is NOT applied here. Use apply_heart_to_chunk() after
    getting the text to apply segment-specific emoji placement.

    Args:
        analysis: Analysis result
        filtered_ui: UI text with watermarks removed

    Returns:
        Highlight text string (without ❤️ prefix)
    """
    # Priority 1: ui_key_text (filtered)
    if filtered_ui:
        if len(filtered_ui) >= 2:
            return f"{filtered_ui[0]} / {filtered_ui[1]}"
        return filtered_ui[0]

    # Priority 2: Best dialogue from ocr_text
    dialogue = pick_dialogue_text(analysis.ocr_text)
    if dialogue:
        return dialogue

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


@dataclass
class HighlightEntry:
    """A highlight entry with quote, summary, and metadata."""

    score: int
    segment_id: str
    start_time: float
    quote: str | None  # Quote text (from aligned_quotes or fallback)
    summary: str | None  # Summary text (facts[0] / what_changed)


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
    # Each entry: (score, segment, analysis, filtered_ui, quote, summary)
    scored_segments: list[
        tuple[int, SegmentInfo, AnalysisResult, list[str], str | None, str | None]
    ] = []

    for segment in manifest.segments:
        analysis = get_segment_analysis(segment, session_dir)
        if analysis is None:
            continue
        score = score_segment(analysis)
        filtered_ui = filter_watermarks(analysis.ui_key_text)
        quote = get_highlight_quote(segment, session_dir, analysis, filtered_ui)
        summary = get_highlight_summary(analysis)
        scored_segments.append((score, segment, analysis, filtered_ui, quote, summary))

    # Sort by score (descending), then by time (ascending) for same score
    scored_segments.sort(key=lambda x: (-x[0], x[1].start_time))

    # Primary selection: score >= min_score only (strict threshold, no fill)
    seen_ui_keys: set[tuple[str, ...]] = set()
    primary_selection: list[
        tuple[int, SegmentInfo, AnalysisResult, list[str], str | None, str | None]
    ] = []

    for score, segment, analysis, filtered_ui, quote, summary in scored_segments:
        # Strict min_score - segments below don't enter at all
        if score < min_score:
            continue

        # Deduplicate by ui_key_text
        ui_key = _get_ui_dedup_key(filtered_ui)
        if ui_key is not None:
            if ui_key in seen_ui_keys:
                continue  # Skip duplicate
            seen_ui_keys.add(ui_key)

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

                # Apply heart to each segment's quote separately
                chunk1 = apply_heart_to_chunk(quote1, analysis1) if quote1 else None
                chunk2 = apply_heart_to_chunk(quote2, analysis2) if quote2 else None

                # Merge quotes: each segment contributes at most 1 quote
                merged_quote = None
                if chunk1 and chunk2:
                    merged_quote = f"{chunk1} / {chunk2}"
                elif chunk1:
                    merged_quote = chunk1
                elif chunk2:
                    merged_quote = chunk2

                # Merge summaries: prefer first, fallback to second
                merged_summary = summary1 or summary2

                merged_highlights.append(
                    HighlightEntry(
                        score=merged_score,
                        segment_id=merged_id,
                        start_time=seg1.start_time,
                        quote=merged_quote,
                        summary=merged_summary,
                    )
                )
                i += 2  # Skip both segments
                continue

        # No merge - add single segment (apply heart to its quote)
        final_quote = apply_heart_to_chunk(quote1, analysis1) if quote1 else None
        merged_highlights.append(
            HighlightEntry(
                score=score1,
                segment_id=seg1.id,
                start_time=seg1.start_time,
                quote=final_quote,
                summary=summary1,
            )
        )
        i += 1

    # Sort by score (descending) and take top-k
    merged_highlights.sort(key=lambda x: -x.score)
    top_highlights = merged_highlights[:top_k]

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

    # If no highlights found
    if not top_highlights:
        lines.append("_No highlights available. Run analysis first._")

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
