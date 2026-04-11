from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'alchemical_symbolic_art',
        'label': 'Alchemical Symbolic Art [symbolic] [esoteric]',
        'tags': ['symbolic', 'esoteric'],
        'description': 'Alchemical-symbolic style with occult diagram language, hermetic motifs, and mysterious structured composition.',
        'instruction': 'Render as symbolic alchemical art with circles, sigils, diagrams, vessels, celestial references, and layered hermetic iconography arranged in a coherent way. Preserve mystery and symbolic richness while keeping the structure intentional and visually readable.',
        'main_category': 'Symbolic / Esoteric',
    },
    {
        'key': 'astrological_chart_art',
        'label': 'Astrological Chart Art [symbolic] [diagram]',
        'tags': ['symbolic', 'diagram'],
        'description': 'Astrological-chart style with radial structure, celestial markers, and elegant symbolic readability.',
        'instruction': 'Render as an astrological chart with radial organization, zodiac or celestial symbolism, clean ring structures, and ornamental but readable hierarchy. Preserve clarity, symbolic order, and decorative balance without overcrowding the chart.',
        'main_category': 'Symbolic / Esoteric',
    },
    {
        'key': 'mystic_diagram',
        'label': 'Mystic Diagram [symbolic] [diagram]',
        'tags': ['symbolic', 'diagram'],
        'description': 'Mystic-diagram style with layered symbolic structure, sacred order, and arcane visual clarity.',
        'instruction': 'Render as a mystic diagram with concentric systems, symbolic nodes, connecting lines, and coherent esoteric organization. Preserve ritual-like order and diagram readability rather than decorative ambiguity that hides the structure.',
        'main_category': 'Symbolic / Esoteric',
    },
    {
        'key': 'sigil_design',
        'label': 'Sigil Design [symbolic] [minimal]',
        'tags': ['symbolic', 'minimal'],
        'description': 'Sigil-design style with compact symbolic geometry, ritual-like intentionality, and strong emblematic clarity.',
        'instruction': 'Render as a sigil with concentrated symbolic form, geometric discipline, and clear central structure. Preserve emblem-like clarity, occult atmosphere, and intentional design coherence rather than random scribble-like abstraction.',
        'main_category': 'Symbolic / Esoteric',
    },
]
