from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'news_segment_style',
        'label': 'News Segment Style [broadcast] [documentary]',
        'tags': ['broadcast', 'documentary'],
        'description': 'News-segment style with anchor or field-report clarity, broadcast structure, and information-first visual control.',
        'instruction': 'Render as a news segment with broadcast-friendly framing, clear presenter or subject emphasis, restrained visual pacing, and information-first readability. Preserve journalistic structure and polished clarity without cinematic sensationalism.',
        'main_category': 'Other / Misc',
    },
    {
        'key': 'prestige_tv_drama_style',
        'label': 'Prestige TV Drama Style [broadcast] [cinematic]',
        'tags': ['broadcast', 'cinematic'],
        'description': 'Prestige-drama style with restrained camera language, psychologically focused framing, and polished narrative realism.',
        'instruction': 'Direct the scene like prestige television drama with measured camera movement, performance-sensitive framing, and moody but readable visual control. Preserve emotional sophistication, compositional precision, and narrative realism without overstyling the sequence into trailer excess.',
        'main_category': 'Other / Misc',
    },
    {
        'key': 'reality_tv_style',
        'label': 'Reality TV Style [broadcast] [documentary]',
        'tags': ['broadcast', 'documentary'],
        'description': 'Reality-TV style with reactive camera behavior, character-driven immediacy, and entertainment-focused observational framing.',
        'instruction': 'Render as reality TV with quick reactive framing, personality-centered emphasis, lively coverage, and scene structure that highlights interpersonal dynamics. Preserve readability, spontaneity, and entertaining real-time behavior without descending into visual chaos.',
        'main_category': 'Other / Misc',
    },
    {
        'key': 'sitcom_multicam_style',
        'label': 'Sitcom Multicam Style [broadcast] [performance]',
        'tags': ['broadcast', 'performance'],
        'description': 'Multicam sitcom style with stage-like coverage, performance-forward blocking, and clean comedic timing readability.',
        'instruction': 'Direct the scene like a multicam sitcom with broad readable blocking, coverage-friendly staging, and timing that supports punchlines and reactions. Preserve set geography, ensemble readability, and bright presentational clarity without forcing prestige-drama visual language onto the scene.',
        'main_category': 'Other / Misc',
    },
]
