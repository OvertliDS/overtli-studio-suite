from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'scanline_crt_graphic',
        'label': 'CRT / Scanline Graphic [experimental] [retro-tech]',
        'tags': ['experimental', 'retro-tech'],
        'description': 'CRT-display style with scanlines, phosphor glow, analog softness, and retro-screen signal character.',
        'instruction': 'Render with CRT-display qualities such as scanlines, soft phosphor bloom, slight geometry curvature, signal texture, and retro electronic display atmosphere. Preserve readability and screen authenticity without excessive blur or unreadable distortion.',
        'main_category': 'Experimental / Generative',
    },
    {
        'key': 'datamosh_visual',
        'label': 'Datamosh Visual [experimental] [digital]',
        'tags': ['experimental', 'digital'],
        'description': 'Datamosh-inspired style with motion-smear corruption, frame-collapse artifacts, and compressed-video distortion aesthetics.',
        'instruction': 'Render with datamosh-like visual behavior using frame blending, compression smears, motion-driven artifacting, and digital collapse aesthetics. Preserve a coherent visual idea beneath the distortion so the piece feels intentional and artistically controlled.',
        'main_category': 'Experimental / Generative',
    },
    {
        'key': 'generative_art_system',
        'label': 'Generative Art System [experimental] [abstract]',
        'tags': ['experimental', 'abstract'],
        'description': 'Generative-art style with rule-based visual systems, emergent structure, and algorithmic compositional logic.',
        'instruction': 'Render as generative art with visible system logic, repeated procedural structure, controlled variation, and coherent emergent form. Preserve the sense of algorithmic order and visual discovery rather than random decorative complexity.',
        'main_category': 'Experimental / Generative',
    },
    {
        'key': 'glitch_aesthetic',
        'label': 'Glitch Aesthetic [experimental] [digital]',
        'tags': ['experimental', 'digital'],
        'description': 'Glitch-art style with digital corruption cues, signal breakup, and controlled visual disruption.',
        'instruction': 'Render as glitch art with scanline breaks, compression artifacts, RGB shifts, tearing, or digital corruption cues used intentionally and compositionally. Preserve readability and aesthetic control so the disruption feels designed rather than like accidental file damage.',
        'main_category': 'Experimental / Generative',
    },
    {
        'key': 'procedural_noise_art',
        'label': 'Procedural Noise Art [experimental] [abstract]',
        'tags': ['experimental', 'abstract'],
        'description': 'Procedural-noise abstract style with layered signal fields, emergent texture, and system-driven visual density.',
        'instruction': 'Render as procedural noise art using layered fields, controlled randomness, signal-like textures, and coherent visual rhythm. Preserve structure and aesthetic intentionality so the result feels system-generated and interesting rather than muddy or formless.',
        'main_category': 'Experimental / Generative',
    },
]
