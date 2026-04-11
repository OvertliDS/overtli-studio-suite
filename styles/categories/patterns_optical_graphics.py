from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'geometric_pattern_design',
        'label': 'Geometric Pattern Design [pattern] [graphic]',
        'tags': ['pattern', 'graphic'],
        'description': 'Geometric pattern style with repeat discipline, clear symmetry or tessellation logic, and clean decorative structure.',
        'instruction': 'Render as a geometric pattern with precise repetition, strong tile logic, disciplined spacing, and clear pattern hierarchy. Preserve repeatability and visual order rather than random decorative scattering.',
        'main_category': 'Patterns / Optical Graphics',
    },
    {
        'key': 'mandala_pattern',
        'label': 'Mandala Pattern [pattern] [symbolic]',
        'tags': ['pattern', 'symbolic'],
        'description': 'Mandala-pattern style with radial symmetry, ornamental layering, and centered meditative visual order.',
        'instruction': 'Render as a mandala with precise radial symmetry, concentric ornamental structure, and clean center-outward hierarchy. Preserve balance, pattern precision, and decorative harmony rather than asymmetrical clutter or muddy detail.',
        'main_category': 'Patterns / Optical Graphics',
    },
    {
        'key': 'op_art_pattern',
        'label': 'Op Art Pattern [pattern] [illusion]',
        'tags': ['pattern', 'illusion'],
        'description': 'Op-art pattern style with high-contrast geometry, visual vibration, and controlled perceptual movement.',
        'instruction': 'Render as op art with bold contrast, repeated geometry, and tightly controlled pattern spacing that creates visual vibration or movement. Preserve crisp graphic clarity and disciplined construction instead of messy texture or uncontrolled noise.',
        'main_category': 'Patterns / Optical Graphics',
    },
    {
        'key': 'tessellation_pattern',
        'label': 'Tessellation Pattern [pattern] [illusion]',
        'tags': ['pattern', 'illusion'],
        'description': 'Tessellation style with interlocking forms, repeat logic, and mathematically coherent visual rhythm.',
        'instruction': 'Render as a tessellated pattern with interlocking repeated shapes, tight repeat integrity, and clean figure-ground organization. Preserve seamless pattern logic and recognizable structural rhythm without irregular distortions that break the tessellation.',
        'main_category': 'Patterns / Optical Graphics',
    },
]
