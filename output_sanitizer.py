from __future__ import annotations

import logging
import re

from .shared_utils import normalize_string_input

logger = logging.getLogger(__name__)

_INSTRUCTION_ECHO_LEAD_PATTERN = re.compile(
    r"^\s*(i['’]ll|i\s+will|i\s+am\s+going\s+to|i'm\s+going\s+to|let\s+me|i\s+can)\b",
    flags=re.IGNORECASE,
)

_TIME_STAMP_PATTERN = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
_SPEAKER_PREFIX_PATTERN = re.compile(r"^\s*(?:[A-Za-z][A-Za-z0-9_\- ]{0,30}|SPEAKER\s+\d+)\s*:")
_SCRIPT_CUE_PATTERN = re.compile(
    r"^\s*(INT\.|EXT\.|FADE\s+IN:|FADE\s+OUT:|CUT\s+TO:|DISSOLVE\s+TO:|\([^)]+\))",
    flags=re.IGNORECASE,
)


def _looks_like_dialogue_or_transcript(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False

    cue_lines = sum(1 for line in lines if _SCRIPT_CUE_PATTERN.search(line))
    speaker_lines = sum(1 for line in lines if _SPEAKER_PREFIX_PATTERN.search(line))
    timestamp_lines = sum(1 for line in lines if _TIME_STAMP_PATTERN.search(line))

    if cue_lines >= 1 and len(lines) >= 3:
        return True
    if speaker_lines >= 3:
        return True
    if timestamp_lines >= 3:
        return True

    return False


def sanitize_text_output(response_text: str, *, mode_hint: str = "generic") -> str:
    """Sanitize text output by removing instruction-confirmation lead paragraphs.

    The sanitizer is intentionally conservative:
    - It never modifies STT/transcript mode outputs.
    - It avoids script/dialogue/transcript-like outputs.
    - It only drops a short first paragraph that looks like an AI confirmation lead-in
      when substantial body content follows.
    """
    text = normalize_string_input(response_text)
    if not text:
        return text

    mode = normalize_string_input(mode_hint, default="generic").lower()
    if mode in {"stt", "speech_to_text", "transcript"}:
        return text.strip()

    if _looks_like_dialogue_or_transcript(text):
        return text.strip()

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) < 2:
        return text.strip()

    lead = paragraphs[0]
    body = "\n\n".join(paragraphs[1:]).strip()
    if not body or len(body) < 80:
        return text.strip()

    if len(lead) > 500 or not _INSTRUCTION_ECHO_LEAD_PATTERN.search(lead):
        return text.strip()

    lead_normalized = lead.lower()
    intent_markers = (
        "reference image",
        "analy",
        "study",
        "craft",
        "generation-ready prompt",
        "then ",
        "single, dense descriptive paragraph",
        "i will",
        "i'll",
    )
    if sum(marker in lead_normalized for marker in intent_markers) < 2:
        return text.strip()

    logger.info("Removed instruction-echo lead paragraph from response output (mode=%s).", mode)
    return body
