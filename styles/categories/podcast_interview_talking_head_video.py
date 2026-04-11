from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'creator_talking_head_style',
        'label': 'Creator Talking Head [video-format] [social]',
        'tags': ['video-format', 'social'],
        'description': 'Creator talking-head style with strong direct address, audience-facing framing, and polished but personal content-creator realism.',
        'instruction': 'Render as creator talking-head content with strong eye contact, centered or slightly offset framing, readable gestures, and a creator-studio or personal-space setup. Preserve warmth, relatability, and platform-native delivery without overproducing it into an advertisement or flattening it into sterile corporate video.',
        'main_category': 'Podcast / Interview / Talking-Head Video',
    },
    {
        'key': 'formal_interview_video',
        'label': 'Formal Interview Video [interview] [cinematography]',
        'tags': ['interview', 'cinematography'],
        'description': 'Formal interview-video style with composed framing, controlled performance space, and professional editorial realism.',
        'instruction': "Render as a formal interview with stable composition, controlled lighting, clear eyeline logic, and a strong emphasis on the speaker's face, posture, and delivery. Preserve professionalism, emotional readability, and documentary-style polish without making the scene feel overly theatrical or staged like a commercial.",
        'main_category': 'Podcast / Interview / Talking-Head Video',
    },
    {
        'key': 'podcast_clip_style',
        'label': 'Podcast Clip Style [video-format] [talking-head]',
        'tags': ['video-format', 'talking-head'],
        'description': 'Podcast-clip style with seated conversational framing, microphone visibility, and shareable social-edit readability.',
        'instruction': 'Render as a podcast clip with readable seated framing, conversational body language, mic and studio-context realism, and a composition suitable for clipped social distribution. Preserve clarity, performance presence, and discussion energy without overdirecting the scene.',
        'main_category': 'Podcast / Interview / Talking-Head Video',
    },
    {
        'key': 'podcast_remote_call',
        'label': 'Podcast Remote Call [video-format] [interview]',
        'tags': ['video-format', 'interview'],
        'description': 'Remote-call podcast style with split-screen or webcam-call realism, conversational timing, and digitally mediated interview clarity.',
        'instruction': 'Render as a remote podcast or internet interview with clear screen-based composition, believable webcam framing, natural home-office or studio context, and conversation-first readability. Preserve realistic call aesthetics, balanced speaker presence, and platform-like authenticity without overdesigning the interface or polishing away the remote-call feel.',
        'main_category': 'Podcast / Interview / Talking-Head Video',
    },
    {
        'key': 'podcast_video_studio',
        'label': 'Podcast Video Studio [video-format] [talking-head]',
        'tags': ['video-format', 'talking-head'],
        'description': 'Studio-podcast video style with seated conversational framing, mic visibility, relaxed performance rhythm, and polished creator-broadcast realism.',
        'instruction': 'Render as a podcast-video setup with readable seated framing, visible microphones or recording setup, soft but controlled studio lighting, and natural conversational body language. Preserve authentic host-guest energy, clean shot composition, and creator-studio realism without turning it into a glossy commercial or an overly cinematic drama scene.',
        'main_category': 'Podcast / Interview / Talking-Head Video',
    },
    {
        'key': 'street_interview_style',
        'label': 'Street Interview [interview] [documentary]',
        'tags': ['interview', 'documentary'],
        'description': 'Street-interview style with handheld immediacy, environmental noise context, and spontaneous public-space realism.',
        'instruction': 'Render as a street interview with believable handheld framing, public-space background context, quick reactive composition, and casual but readable subject coverage. Preserve candid realism, environmental texture, and spontaneous interaction without making the footage too shaky or chaotic to follow.',
        'main_category': 'Podcast / Interview / Talking-Head Video',
    },
    {
        'key': 'vox_pop_interview_style',
        'label': 'Vox Pop Interview [interview] [broadcast]',
        'tags': ['interview', 'broadcast'],
        'description': 'Vox-pop interview style with quick-answer framing, public-location realism, and news-segment readability.',
        'instruction': 'Render as vox-pop or man-on-the-street interview footage with concise framing, public environment context, and clear subject response focus. Preserve fast, readable street-report rhythm and authentic broadcast-style immediacy without clutter or over-stylized camera behavior.',
        'main_category': 'Podcast / Interview / Talking-Head Video',
    },
]
