from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'board_game_card_layout',
        'label': 'Board Game Card Layout [card] [game]',
        'tags': ['card', 'game'],
        'description': 'Board-game card style with clear rules hierarchy, icon readability, and playable tabletop layout structure.',
        'instruction': 'Design as a board-game card with readable title zone, iconography, stat or cost placement, and clear rules-text hierarchy. Preserve tabletop usability, strong card-border structure, and small-format readability without overcrowding the card face.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'card_back_pattern_design',
        'label': 'Card Back Pattern Design [card] [ornamental]',
        'tags': ['card', 'ornamental'],
        'description': 'Card-back pattern style with centered symmetry, decorative rhythm, and premium deck-ready surface design.',
        'instruction': 'Design as a card back with strong symmetry, centered focal ornament, border discipline, and repeatable deck-style clarity. Preserve a clean premium finish and collectible-card elegance without excessive detail that muddies the pattern at small scale.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'character_stat_card',
        'label': 'Character Stat Card [card] [game]',
        'tags': ['card', 'game'],
        'description': 'Character-stat card style with dominant portrait hierarchy, attribute readability, and collectible roster-card clarity.',
        'instruction': 'Design as a character stat card with a strong character focal image, readable attribute layout, clear nameplate, and polished collectible-card framing. Preserve visual impact and stat clarity while keeping the format game-usable and not overloaded with competing decorations.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'deck_builder_card_template',
        'label': 'Deck Builder Card Template [card] [game]',
        'tags': ['card', 'game'],
        'description': 'Deck-builder card template style with combat/stat hierarchy, repeatable layout logic, and expandable collectible-card usability.',
        'instruction': 'Design as a deck-builder card template with clearly separated title, artwork, stats, resource costs, and ability text zones. Preserve strong repeatable system structure and gameplay readability, avoiding decorative complexity that would weaken fast card scanning.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'loot_item_card',
        'label': 'Loot / Item Card [card] [game]',
        'tags': ['card', 'game'],
        'description': 'Loot-item card style with item-centered hierarchy, rarity signaling, and readable game-inventory presentation.',
        'instruction': 'Design as an item or loot card with a dominant item render, rarity or tier cues, clean metadata zones, and strong iconographic readability. Preserve compact usability, card-system consistency, and clear item identity without cluttering the layout.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'oracle_card_design',
        'label': 'Oracle Card Design [card] [spiritual]',
        'tags': ['card', 'spiritual'],
        'description': 'Oracle-card style with serene symbolic focus, premium card-face composition, and message-forward spiritual clarity.',
        'instruction': 'Design as an oracle card with a strong central image, cohesive symbolic tone, elegant border or framing logic, and clean card-face readability. Preserve calm, premium presentation and intuitive visual clarity without cluttering the card with too many competing motifs.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'playing_card_face_design',
        'label': 'Playing Card Face Design [card] [game]',
        'tags': ['card', 'game'],
        'description': 'Playing-card face style with suit hierarchy, mirrored-card logic, and crisp compact readability.',
        'instruction': 'Design as a playing-card face with clear suit indicators, rank hierarchy, balanced face-card structure where applicable, and strict small-format readability. Preserve symmetry, clean borders, and deck-system consistency without decorative overload.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'tarot_card_design',
        'label': 'Tarot Card Design [card] [occult]',
        'tags': ['card', 'occult'],
        'description': 'Tarot-card design style with symbolic hierarchy, ornate framing, and archetypal narrative clarity.',
        'instruction': 'Design as a tarot card with strong central imagery, symbolic composition, decorative frame structure, and clear upright card readability. Preserve mystical atmosphere, archetypal clarity, and collectible-card polish without becoming visually chaotic or unreadably ornate.',
        'main_category': 'Card / Collectible Formats',
    },
    {
        'key': 'trading_card_design',
        'label': 'Trading Card Design [design] [game]',
        'tags': ['design', 'game', 'card', 'collectible'],
        'description': 'Collectible trading-card style with strong character focal hierarchy, stat-zone clarity, and premium card-face presentation.',
        'instruction': 'Design as a trading card with a dominant focal image, clear title or name zone, readable stats or metadata sections, and polished collectible-card layout logic. Preserve strong visual impact, card-border discipline, and small-format readability without overcrowding the design.',
        'main_category': 'Card / Collectible Formats',
    },
]
