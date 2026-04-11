from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'ai_webcam_avatar_recording',
        'label': 'AI Webcam Recording [video-format] [webcam]',
        'tags': ['video-format', 'webcam'],
        'description': 'AI-presenter webcam style with centered talking-head framing, clean screen-facing delivery, and recorded-from-computer realism.',
        'instruction': 'Render as an AI-presenter or AI-generated webcam recording with centered head-and-shoulders composition, direct-to-camera delivery, practical desk or room context, and believable webcam perspective. Preserve webcam realism, clear facial readability, and a slightly digital, recorded-on-computer feel without pushing the image into uncanny overprocessing or cinematic overlighting.',
        'main_category': 'AI Webcam / Work-Call / Virtual Meeting Video',
    },
    {
        'key': 'laptop_webcam_style',
        'label': 'Laptop Webcam [video-format] [webcam]',
        'tags': ['video-format', 'webcam'],
        'description': 'Laptop-webcam style with slightly low or monitor-level framing, desk-context realism, and casual recorded-call aesthetics.',
        'instruction': 'Render as laptop-webcam footage with realistic built-in camera perspective, modest field-of-view distortion, desk or workspace context, and screen-lit facial illumination. Preserve the ordinary home-office or casual-call feel instead of studio portrait video.',
        'main_category': 'AI Webcam / Work-Call / Virtual Meeting Video',
    },
    {
        'key': 'virtual_meeting_camera_style',
        'label': 'Virtual Meeting Camera [video-format] [webcam]',
        'tags': ['video-format', 'webcam'],
        'description': 'Virtual-meeting camera style with laptop-webcam framing, home-office realism, and work-call readability.',
        'instruction': 'Render as a virtual meeting or conference-call camera feed with eye-level webcam angle, natural indoor lighting, modest background context, and practical work-from-home realism. Preserve clarity, professionalism, and a believable meeting-camera feel without glamour lighting, extreme stylization, or dramatic composition.',
        'main_category': 'AI Webcam / Work-Call / Virtual Meeting Video',
    },
    {
        'key': 'webcam_recording_style',
        'label': 'Webcam Recording [video-format] [webcam]',
        'tags': ['video-format', 'webcam'],
        'description': 'Classic webcam-recording style with fixed computer-camera perspective, casual room context, and slightly imperfect digital realism.',
        'instruction': 'Render as a webcam recording with front-facing computer-camera perspective, modest lens distortion, natural screen-side lighting, and believable indoor background context. Preserve the slightly flat, practical, everyday realism of a webcam feed without overcorrecting it into polished cinema.',
        'main_category': 'AI Webcam / Work-Call / Virtual Meeting Video',
    },
]
