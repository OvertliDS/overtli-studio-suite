from __future__ import annotations

from ..types import AudioStylePreset

STYLES: list[AudioStylePreset] = [
    {
        "task": "tts",
        "name": "Natural Narration",
        "category": "Delivery / Neutral",
        "instruction": "Prioritize calm, natural pacing with clear sentence boundaries and balanced emphasis.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Podcast Host",
        "category": "Delivery / Conversational",
        "instruction": "Shape delivery for energetic spoken flow with concise clauses and engaging transitions.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Dramatic Performance",
        "category": "Delivery / Expressive",
        "instruction": "Use theatrical rhythm, intentional pauses, and emotional contrast at key sentence endings.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Educational Explainer",
        "category": "Delivery / Instructional",
        "instruction": "Favor clear definitions, explicit signposting, and reduced ambiguity for teaching-style narration.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Broadcast News",
        "category": "Delivery / Formal",
        "instruction": "Maintain concise, objective phrasing with newsroom cadence and minimal conversational filler.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Meditative Guidance",
        "category": "Delivery / Wellness",
        "instruction": "Adopt slow pacing, soft transitions, and reassuring wording suitable for guided relaxation.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Audiobook Storyteller",
        "category": "Delivery / Narrative",
        "instruction": "Use immersive narration cadence, character-aware emphasis, and scene transition clarity for long-form listening.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Customer Support Agent",
        "category": "Delivery / Service",
        "instruction": "Keep phrasing warm and solution-oriented with clear next steps and confidence-building reassurance.",
        "hint": "",
    },
    {
        "task": "tts",
        "name": "Technical Presenter",
        "category": "Delivery / Technical",
        "instruction": "Prioritize precise terminology, compact explanatory phrasing, and stable pace for complex technical content.",
        "hint": "",
    },
]
