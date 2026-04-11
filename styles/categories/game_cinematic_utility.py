from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'defeat_stinger_style',
        'label': 'Defeat Stinger [game-cinematic] [atmosphere]',
        'tags': ['game-cinematic', 'atmosphere'],
        'description': 'Defeat-stinger style with compressed impact, emotional drop, and clean loss-state visual punctuation.',
        'instruction': 'Design as a defeat or failure stinger with concise timing, clear visual loss-state emphasis, and controlled emotional downturn. Preserve readability, tonal clarity, and efficient payoff without overcomplicating the moment with noisy effects.',
        'main_category': 'Game Cinematic Utility',
    },
    {
        'key': 'game_cinematic_intro',
        'label': 'Game Cinematic Intro [game-cinematic] [direction]',
        'tags': ['game-cinematic', 'direction'],
        'description': 'Game-intro cinematic style with lore setup, character emphasis, and strong opening-world identity.',
        'instruction': 'Direct the scene as a game cinematic intro with a clear opening hook, world-establishing imagery, character or faction emphasis, and premium narrative staging. Preserve readability, spectacle, and game-world identity without overloading the sequence with disconnected exposition.',
        'main_category': 'Game Cinematic Utility',
    },
    {
        'key': 'gameplay_highlight_reel',
        'label': 'Gameplay Highlight Reel [game-cinematic] [editing]',
        'tags': ['game-cinematic', 'editing'],
        'description': 'Gameplay-highlight style with readability-first action selection, escalating showcase beats, and polished promo pacing.',
        'instruction': 'Build the sequence as a gameplay highlight reel with clear showcase moments, rising intensity, readable player actions, and premium promotional pacing. Preserve gameplay clarity and viewer excitement without reducing the sequence to unreadable effect spam or random montage noise.',
        'main_category': 'Game Cinematic Utility',
    },
    {
        'key': 'lore_intro_sequence',
        'label': 'Lore Intro Sequence [game-cinematic] [title-motion]',
        'tags': ['game-cinematic', 'title-motion'],
        'description': 'Lore-intro style with myth-building imagery, controlled exposition pacing, and strong opening-world identity.',
        'instruction': 'Build the sequence as a lore intro using evocative imagery, strong symbolic beats, and readable exposition pacing that introduces the world, conflict, or backstory. Preserve intrigue, atmosphere, and narrative clarity without overloading the viewer with disconnected mythology fragments.',
        'main_category': 'Game Cinematic Utility',
    },
    {
        'key': 'main_menu_background_loop',
        'label': 'Main Menu Background Loop [loop] [game-cinematic]',
        'tags': ['loop', 'game-cinematic'],
        'description': 'Main-menu background style with subtle cinematic motion, UI-safe composition, and premium game-atmosphere continuity.',
        'instruction': 'Design as a looping main-menu background with subtle environmental or character motion, strong UI-safe negative space, and premium visual mood. Preserve loop smoothness, interface readability, and a strong game-identity feel without distracting narrative events.',
        'main_category': 'Game Cinematic Utility',
    },
    {
        'key': 'mission_briefing_style',
        'label': 'Mission Briefing Style [game-cinematic] [ui-motion]',
        'tags': ['game-cinematic', 'ui-motion'],
        'description': 'Mission-briefing style with tactical presentation, objective clarity, and game-interface-aware cinematic structure.',
        'instruction': 'Direct the sequence as a mission briefing with clear objective framing, tactical overlays or map logic where useful, and a strong sense of task, threat, and location. Preserve readability, urgency, and mission structure without turning the briefing into incoherent stylized noise.',
        'main_category': 'Game Cinematic Utility',
    },
    {
        'key': 'post_match_recap_style',
        'label': 'Post-Match Recap [sports] [editing]',
        'tags': ['sports', 'editing'],
        'description': 'Post-match recap style with result-driven structure, key-moment emphasis, and clean narrative summary of performance.',
        'instruction': 'Assemble the sequence as a post-match recap with clear structure around turning points, best and worst moments, reactions, and overall outcome. Preserve readability, emotional closure, and match narrative coherence rather than random disconnected highlights.',
        'main_category': 'Game Cinematic Utility',
    },
    {
        'key': 'victory_stinger_style',
        'label': 'Victory Stinger [game-cinematic] [title-motion]',
        'tags': ['game-cinematic', 'title-motion'],
        'description': 'Victory-stinger style with short high-impact payoff, celebratory energy, and reward-screen clarity.',
        'instruction': 'Design as a short victory stinger with strong payoff timing, celebratory motion, and clean visual emphasis on success, rank-up, win state, or achievement. Preserve punch, clarity, and replay friendliness without bloating the sequence with unnecessary filler.',
        'main_category': 'Game Cinematic Utility',
    },
]
