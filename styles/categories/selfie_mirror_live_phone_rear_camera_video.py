from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'facetime_call_style',
        'label': 'FaceTime / Video Call Style [video-format] [mobile]',
        'tags': ['video-format', 'mobile'],
        'description': 'Video-call style with front-camera intimacy, conversational framing, and real-time casual communication realism.',
        'instruction': 'Render as a phone video-call feed with direct face framing, natural indoor or mobile lighting, intimate conversational proximity, and the slightly compressed realism of live call video. Preserve casual, human, real-time communication feel instead of polishing it into formal interview cinematography.',
        'main_category': 'Selfie / Mirror / Live Phone / Rear-Camera Video',
    },
    {
        'key': 'live_phone_recording_style',
        'label': 'Live Phone Recording [video-format] [mobile]',
        'tags': ['video-format', 'mobile'],
        'description': 'Live phone-recording style with casual handheld realism, practical exposure shifts, and native mobile-capture immediacy.',
        'instruction': 'Render as live phone-recorded footage with realistic handheld motion, automatic exposure adaptation, everyday soundstage implied visually, and native mobile-camera framing. Preserve the spontaneous, lightly imperfect realism of someone recording in the moment instead of smoothing it into cinematic footage.',
        'main_category': 'Selfie / Mirror / Live Phone / Rear-Camera Video',
    },
    {
        'key': 'mirror_selfie_video_style',
        'label': 'Mirror Selfie Video [video-format] [mobile]',
        'tags': ['video-format', 'mobile'],
        'description': 'Mirror-selfie video style with reflected phone framing, casual performance presence, and social-native realism.',
        'instruction': 'Render as a mirror-selfie video with believable reflected composition, visible phone-in-hand framing, room or bathroom context, and casual real-world movement. Preserve spontaneous social-media realism, reflection behavior, and lived-in background texture without making it look staged or overproduced.',
        'main_category': 'Selfie / Mirror / Live Phone / Rear-Camera Video',
    },
    {
        'key': 'rear_camera_phone_video',
        'label': 'Rear Camera Phone Video [video-format] [mobile]',
        'tags': ['video-format', 'mobile'],
        'description': 'Rear-phone-camera video style with stronger subject detail, practical handheld framing, and believable on-the-go realism.',
        'instruction': 'Render as rear-camera phone footage with realistic handheld composition, better sensor clarity than a webcam, practical autofocus behavior, and everyday capture framing. Preserve natural phone-video realism and moment-based spontaneity without turning it into stabilized commercial camera work.',
        'main_category': 'Selfie / Mirror / Live Phone / Rear-Camera Video',
    },
    {
        'key': 'selfie_video_front_camera',
        'label': 'Selfie Video Front Camera [video-format] [mobile]',
        'tags': ['video-format', 'mobile'],
        'description': "Front-camera selfie-video style with arm's-length framing, personal immediacy, and native phone-recording realism.",
        'instruction': 'Render as a front-camera selfie video with natural handheld distance, portrait or casual framing, phone-camera perspective, and direct personal presence. Preserve realistic skin, motion, and environment context with the authentic feel of a self-recorded mobile clip rather than a polished commercial talking-head.',
        'main_category': 'Selfie / Mirror / Live Phone / Rear-Camera Video',
    },
    {
        'key': 'bodycam_phone_vertical_style',
        'label': 'Vertical Walking Phone Vlog [video-format] [social]',
        'tags': ['video-format', 'social'],
        'description': 'Walking-vlog style with front-facing phone capture, moving background context, and real-time creator immediacy.',
        'instruction': "Render as a vertical phone vlog while walking, with arm's-length framing, changing background movement, practical autoexposure shifts, and direct-to-camera creator energy. Preserve the realistic instability, movement rhythm, and mobile-first framing of true on-the-go recording without making it unreadably shaky.",
        'main_category': 'Selfie / Mirror / Live Phone / Rear-Camera Video',
    },
]
