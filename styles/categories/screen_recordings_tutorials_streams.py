from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'livestream_desktop_overlay_style',
        'label': 'Livestream Desktop Overlay [screen] [streaming]',
        'tags': ['screen', 'streaming'],
        'description': 'Livestream-desktop style with layered overlays, chat or alert zones, and broadcast-friendly screen composition.',
        'instruction': 'Render as a livestream desktop scene with visible content windows, stream overlays, chat or notification areas, and screen-first readability. Preserve the balance between content, overlays, and creator presence without cluttering the screen into unreadable broadcast noise.',
        'main_category': 'Screen Recordings / Tutorials / Streams',
    },
    {
        'key': 'presentation_screen_recording_style',
        'label': 'Presentation Screen Recording [screen] [business]',
        'tags': ['screen', 'business'],
        'description': 'Presentation-capture style with slide readability, presenter-flow clarity, and professional screen-share realism.',
        'instruction': 'Render as a recorded slide presentation or screen-shared talk with readable slides, sensible pointer movement, and professional presentation pacing. Preserve legibility, structure, and realistic meeting or webinar screen behavior without over-animating the content.',
        'main_category': 'Screen Recordings / Tutorials / Streams',
    },
    {
        'key': 'screen_recording_desktop_style',
        'label': 'Screen Recording Desktop [video-format] [screen]',
        'tags': ['video-format', 'screen'],
        'description': 'Desktop screen-recording style with software-interface clarity, cursor-driven interaction, and tutorial-ready digital readability.',
        'instruction': 'Render as a desktop screen recording with clear interface visibility, realistic cursor movement, readable windows, and clean digital capture structure. Preserve software legibility, user interaction flow, and true screen-capture logic without adding fake cinematic depth or non-screen-based camera behavior.',
        'main_category': 'Screen Recordings / Tutorials / Streams',
    },
    {
        'key': 'screen_recording_mobile_style',
        'label': 'Screen Recording Mobile [video-format] [screen]',
        'tags': ['video-format', 'screen'],
        'description': 'Mobile screen-recording style with app-first visibility, touch-driven flow, and platform-native phone-interface realism.',
        'instruction': 'Render as a mobile screen recording with readable app UI, believable touch or swipe behavior, and a clean portrait-oriented digital interface. Preserve true phone-screen structure, app hierarchy, and functional clarity without overdecorating the interface or introducing impossible screen behavior.',
        'main_category': 'Screen Recordings / Tutorials / Streams',
    },
    {
        'key': 'software_tutorial_screen_style',
        'label': 'Software Tutorial Screen [screen] [instruction]',
        'tags': ['screen', 'instruction'],
        'description': 'Tutorial screen-capture style with educational clarity, cursor emphasis, and workflow-friendly visibility.',
        'instruction': 'Render as a software tutorial screen recording with highly readable UI elements, clear cursor or pointer emphasis, step-by-step interaction logic, and strong instructional pacing. Preserve functional clarity and demonstration usefulness over decorative motion or cinematic flourishes.',
        'main_category': 'Screen Recordings / Tutorials / Streams',
    },
]
