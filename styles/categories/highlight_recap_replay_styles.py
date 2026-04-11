from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'best_of_montage_style',
        'label': 'Best Of Montage [editing] [sequence]',
        'tags': ['editing', 'sequence'],
        'description': 'Best-of montage style with curated peak moments, variety, and satisfying rhythm across multiple clips or scenes.',
        'instruction': 'Assemble the sequence as a best-of montage using standout moments, visual variety, and clean editorial rhythm. Preserve a sense of celebration, progression, and polish while making sure each included beat reads clearly and contributes something distinct.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
    {
        'key': 'character_arc_recap_style',
        'label': 'Character Arc Recap [editing] [performance]',
        'tags': ['editing', 'performance'],
        'description': 'Character-recap style with emotional continuity, defining moments, and growth-focused sequence logic.',
        'instruction': 'Build the sequence around a character arc, selecting moments that clearly show emotional change, conflict, growth, or collapse. Preserve performance coherence and thematic progression so the recap feels like a story rather than a random fan edit.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
    {
        'key': 'fail_compilation_style',
        'label': 'Fail Compilation Style [editing] [comedy]',
        'tags': ['editing', 'comedy'],
        'description': 'Fail-compilation style with fast comedic setup-payoff structure, readable mishaps, and reaction-focused timing.',
        'instruction': 'Build the sequence as a fail compilation with quick setup, immediate visual payoff, and strong comedic timing around mistakes, misses, or unintended outcomes. Preserve clarity of each fail so the humor comes from readable cause and effect rather than chaotic editing.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
    {
        'key': 'highlight_reel_style',
        'label': 'Highlight Reel Style [editing] [sports]',
        'tags': ['editing', 'sports'],
        'description': 'Highlight-reel style with best-moment emphasis, escalating energy, and concise showcase structure.',
        'instruction': 'Build the sequence as a highlight reel focused on strongest moments, best actions, and emotionally satisfying peaks. Preserve readability, momentum, and progression so each moment lands clearly and the overall reel feels curated rather than like a random clip dump.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
    {
        'key': 'lowlight_reel_style',
        'label': 'Lowlight Reel Style [editing] [sports]',
        'tags': ['editing', 'sports'],
        'description': 'Lowlight-reel style with failure beats, awkward outcomes, and clearly readable negative turning points.',
        'instruction': 'Build the sequence as a lowlight reel focusing on missed chances, mistakes, collapses, or awkward failures with clear setup and payoff. Preserve readability and timing so each low moment is understandable and lands cleanly without muddy editing or confusing context.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
    {
        'key': 'season_recap_style',
        'label': 'Season Recap Style [editing] [documentary]',
        'tags': ['editing', 'documentary'],
        'description': 'Season-recap style with progression arc, milestone emphasis, and emotionally coherent retrospective structure.',
        'instruction': 'Assemble the sequence as a season recap with clear progression, turning points, milestone moments, and an overall rise-fall-resolution emotional arc. Preserve continuity, reflection, and thematic structure instead of making the recap feel like disconnected highlights.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
    {
        'key': 'sports_replay_style',
        'label': 'Sports Replay Style [sports] [editing]',
        'tags': ['sports', 'editing'],
        'description': 'Replay style with action isolation, key-moment emphasis, and clean event-readability for analysis or impact.',
        'instruction': 'Present the sequence like a sports replay with emphasis on the defining action beat, readable motion path, and clear visual focus on what happened and why it matters. Preserve impact, timing, and legibility rather than burying the replay in effects or clutter.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
    {
        'key': 'tactical_breakdown_style',
        'label': 'Tactical Breakdown Style [sports] [analysis]',
        'tags': ['sports', 'analysis'],
        'description': 'Tactical-breakdown style with strategic readability, positional clarity, and event-focused visual explanation.',
        'instruction': 'Direct or edit the sequence like a tactical breakdown with strong emphasis on spacing, movement patterns, decision points, and key positional relationships. Preserve instructional clarity, analytical usefulness, and readable action geography over pure hype.',
        'main_category': 'Highlight / Recap / Replay Styles',
    },
]
