from __future__ import annotations

from ..types import AudioStylePreset

STYLES: list[AudioStylePreset] = [
    {
        "task": "ttaudio",
        "name": "Cinematic Atmosphere",
        "category": "Music / Cinematic",
        "instruction": "Focus on layered ambience, evolving motion, and a deep foreground-to-background soundstage.",
        "hint": "cinematic atmospheric",
    },
    {
        "task": "ttaudio",
        "name": "Lo-Fi Chill",
        "category": "Music / Chill",
        "instruction": "Target warm, mellow lo-fi textures with soft dynamics and unobtrusive rhythmic pulse.",
        "hint": "lo-fi chill",
    },
    {
        "task": "ttaudio",
        "name": "Epic Trailer",
        "category": "Music / Trailer",
        "instruction": "Build high-impact trailer energy with dramatic rises, bold low-end emphasis, and climactic transitions.",
        "hint": "epic trailer",
    },
    {
        "task": "ttaudio",
        "name": "Ambient Focus",
        "category": "Music / Productivity",
        "instruction": "Generate low-distraction ambient textures with stable dynamics and smooth harmonic continuity.",
        "hint": "ambient focus",
    },
    {
        "task": "ttaudio",
        "name": "Synthwave Drive",
        "category": "Music / Retro",
        "instruction": "Use retro synth motifs, pulsing bass, and forward-driving groove for night-drive energy.",
        "hint": "synthwave retro",
    },
    {
        "task": "ttaudio",
        "name": "Acoustic Intimate",
        "category": "Music / Acoustic",
        "instruction": "Favor close-mic acoustic textures, gentle dynamics, and emotionally intimate arrangement.",
        "hint": "acoustic intimate",
    },
    {
        "task": "ttaudio",
        "name": "Upbeat Corporate",
        "category": "Music / Commercial",
        "instruction": "Generate clean, optimistic corporate underscore with light rhythmic drive and motivational tonal balance.",
        "hint": "corporate upbeat",
    },
    {
        "task": "ttaudio",
        "name": "Dark Tension Pulse",
        "category": "Music / Suspense",
        "instruction": "Emphasize suspenseful low pulse, sparse motifs, and gradually intensifying atmosphere for thriller scenes.",
        "hint": "dark suspense pulse",
    },
    {
        "task": "ttaudio",
        "name": "Festival EDM Lift",
        "category": "Music / Electronic",
        "instruction": "Build energetic EDM progression with punchy drops, bright synth leads, and crowd-lift transitions.",
        "hint": "festival edm",
    },
]
