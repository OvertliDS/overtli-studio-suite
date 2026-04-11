from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'animated_storybook_sequence',
        'label': 'Animated Storybook Sequence [animation-direction] [scene-type]',
        'tags': ['animation-direction', 'scene-type'],
        'description': 'Storybook-animation style with page-like staging, illustrative motion, and gentle narrative progression.',
        'instruction': 'Direct the scene like an animated storybook with illustration-aware framing, readable character action, soft transitions, and page-turn-like visual logic. Preserve charm, clarity, and narrative simplicity while keeping the motion expressive and controlled.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'anime_ending_style',
        'label': 'Anime Ending Style [animation-direction] [atmosphere]',
        'tags': ['animation-direction', 'atmosphere'],
        'description': 'Anime-ending style with softer pacing, reflective imagery, and mood-driven visual repetition or drift.',
        'instruction': 'Direct the sequence like an anime ending with calmer tempo, emotional reflection, looping motifs, and visually lyrical staging. Preserve softness, character presence, and tonal unity without losing readability or drifting into empty filler.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'anime_opening_style',
        'label': 'Anime Opening Style [animation-direction] [music-video]',
        'tags': ['animation-direction', 'music-video'],
        'description': 'Anime-opening style with rhythm-driven montage, bold character shots, symbolic imagery, and emotionally charged visual escalation.',
        'instruction': 'Direct the sequence like an anime opening with strong character-introduction shots, rhythmic montage flow, dynamic graphic transitions, symbolic motifs, and escalating emotion timed to the music or dramatic energy. Preserve iconic silhouettes, readable action, and thematic coherence rather than random flashy imagery.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'cartoon_action_sequence',
        'label': 'Cartoon Action Sequence [animation-direction] [sequence]',
        'tags': ['animation-direction', 'sequence'],
        'description': 'Cartoon-action style with exaggerated motion, readable staging, and playful high-energy physicality.',
        'instruction': 'Direct the scene as cartoon action with clear pose-to-pose readability, elastic motion logic, strong impact timing, and visually understandable cause-and-effect. Preserve fun, energy, and exaggerated appeal without making the action unreadably chaotic.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'cartoon_slapstick_comedy',
        'label': 'Cartoon Slapstick Comedy [animation-direction] [performance]',
        'tags': ['animation-direction', 'performance'],
        'description': 'Slapstick-cartoon style with elastic timing, visual gags, and strong reaction readability.',
        'instruction': 'Direct the sequence as slapstick comedy with strong anticipation, impact timing, expressive reactions, and clean setup-payoff structure for visual jokes. Preserve clarity of comedic beats and exaggerated animation logic without muddling the scene with too many simultaneous gags.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'limited_animation_style',
        'label': 'Limited Animation Style [animation-direction] [stylized]',
        'tags': ['animation-direction', 'stylized'],
        'description': 'Limited-animation style with held poses, selective motion emphasis, and efficient expressive staging.',
        'instruction': 'Direct the scene with limited-animation logic using held drawings or poses, selective movement, and carefully chosen motion accents. Preserve style, clarity, and expressive economy rather than trying to simulate full-fluid animation everywhere.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'motion_graphics_explainer_style',
        'label': 'Motion Graphics Explainer [animation-direction] [graphic]',
        'tags': ['animation-direction', 'graphic'],
        'description': 'Explainer-animation style with clean icon motion, information clarity, and polished motion-design hierarchy.',
        'instruction': 'Direct the sequence as motion-graphics explainer content with clean transitions, readable icon and text relationships, strong hierarchy, and precise graphic timing. Preserve explanatory clarity and visual polish without decorative motion overload.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'storybook_animation_style',
        'label': 'Storybook Animation Style [animation-direction] [atmosphere]',
        'tags': ['animation-direction', 'atmosphere'],
        'description': 'Storybook-animation style with page-like composition, gentle motion, and warm illustrative continuity.',
        'instruction': 'Direct the scene like animated storybook footage with careful composition, soft motion, illustrative environments, and graceful progression between beats. Preserve charm, readability, and narrative warmth rather than overcomplicating the animation.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
    {
        'key': 'stylized_animation_comedy_scene',
        'label': 'Stylized Animation Comedy Scene [animation-direction] [performance]',
        'tags': ['animation-direction', 'performance'],
        'description': 'Comedy-animation style with exaggerated timing, readable poses, and playful visual rhythm.',
        'instruction': 'Direct the scene as stylized animated comedy with clear pose-to-pose readability, strong timing contrast, expressive reactions, and visual humor built through staging and rhythm. Preserve clarity and performance appeal without turning the motion into chaotic randomness.',
        'main_category': 'Animation / Cartoon Video Styles',
    },
]
