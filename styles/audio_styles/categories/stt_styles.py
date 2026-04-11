from __future__ import annotations

from ..types import AudioStylePreset

STYLES: list[AudioStylePreset] = [
    {
        "task": "stt",
        "name": "Verbatim Accuracy",
        "category": "Transcript / Fidelity",
        "instruction": "Keep wording as close as possible to source speech while restoring basic punctuation and casing.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Readable Transcript",
        "category": "Transcript / Clean",
        "instruction": "Improve readability with sentence boundaries and paragraph breaks while preserving factual meaning.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Meeting Notes",
        "category": "Transcript / Summary",
        "instruction": "Structure output into concise notes with decisions, action items, and named stakeholders.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Legal Deposition",
        "category": "Transcript / Formal",
        "instruction": "Preserve speaker fidelity and chronology with formal punctuation and strict attribution discipline.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Lecture Digest",
        "category": "Transcript / Educational",
        "instruction": "Emphasize key concepts, definitions, and topic transitions suitable for study notes.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Interview Highlights",
        "category": "Transcript / Editorial",
        "instruction": "Retain salient quotes and remove low-value filler while keeping factual intent unchanged.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Podcast Chapters",
        "category": "Transcript / Structured",
        "instruction": "Organize transcript into chapter-style sections with topical headings and timestamp-friendly segmentation.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Call Center QA",
        "category": "Transcript / Operations",
        "instruction": "Emphasize compliance-critical wording, intent markers, and action commitments with clear speaker boundaries.",
        "hint": "",
    },
    {
        "task": "stt",
        "name": "Research Interview Coding",
        "category": "Transcript / Research",
        "instruction": "Preserve nuanced language and participant phrasing while adding clean structure suitable for qualitative coding.",
        "hint": "",
    },
]
