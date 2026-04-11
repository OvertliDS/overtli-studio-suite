from __future__ import annotations

from ..types import PromptStyle

STYLES: list[PromptStyle] = [
    {
        'key': 'live_wallpaper_ambient',
        'label': 'Live Wallpaper Ambient [loop] [ambient]',
        'tags': ['loop', 'ambient'],
        'description': 'Ambient live-wallpaper style with subtle motion, seamless looping, and screen-friendly visual calm.',
        'instruction': 'Design the video as a live wallpaper with minimal but continuous motion, elegant composition, and a seamless loop that feels natural over long viewing. Preserve visual calm, device-screen friendliness, and subtle animation rather than aggressive camera moves or disruptive narrative events.',
        'main_category': 'Loop / Wallpaper / Background Motion',
    },
    {
        'key': 'live_wallpaper_character_idle',
        'label': 'Live Wallpaper Character Idle [loop] [character]',
        'tags': ['loop', 'character'],
        'description': 'Character-idle live-wallpaper style with subtle breathing motion, small gesture loops, and premium screen presence.',
        'instruction': 'Design as a character-based live wallpaper using subtle idle animation such as breathing, blinking, hair drift, cloth motion, or minimal pose shifts. Preserve character appeal, loop smoothness, and background-app usability without turning the animation into a full narrative scene.',
        'main_category': 'Loop / Wallpaper / Background Motion',
    },
    {
        'key': 'live_wallpaper_neon_motion',
        'label': 'Live Wallpaper Neon Motion [loop] [stylized]',
        'tags': ['loop', 'stylized'],
        'description': 'Neon live-wallpaper style with subtle emissive motion, atmospheric drift, and loop-friendly futuristic mood.',
        'instruction': 'Design as a looping neon wallpaper with controlled emissive flicker, ambient haze drift, reflective highlights, and slow stylized movement. Preserve readability, loop smoothness, and wallpaper usability without turning the screen into high-distraction motion graphics.',
        'main_category': 'Loop / Wallpaper / Background Motion',
    },
    {
        'key': 'live_wallpaper_parallax',
        'label': 'Live Wallpaper Parallax [loop] [depth]',
        'tags': ['loop', 'depth'],
        'description': 'Parallax live-wallpaper style with layered depth, gentle motion drift, and premium dimensional screen presence.',
        'instruction': 'Design the animation as a parallax live wallpaper with foreground-midground-background separation, subtle layer drift, and seamless depth-enhancing motion. Preserve a premium sense of dimension and loop smoothness without drawing too much attention away from icons or UI.',
        'main_category': 'Loop / Wallpaper / Background Motion',
    },
    {
        'key': 'live_wallpaper_weather',
        'label': 'Live Wallpaper Weather [loop] [atmosphere]',
        'tags': ['loop', 'atmosphere'],
        'description': 'Weather live-wallpaper style with cyclical environmental motion, atmospheric continuity, and soft immersive realism.',
        'instruction': 'Design as a live wallpaper centered on weather motion such as rain, drifting clouds, snowfall, fog, or swaying trees. Preserve seamless looping, ambient realism, and calm environmental movement suitable for long-term background viewing.',
        'main_category': 'Loop / Wallpaper / Background Motion',
    },
    {
        'key': 'loopable_background_video_style',
        'label': 'Loopable Background Video [video-format] [ambient]',
        'tags': ['video-format', 'ambient'],
        'description': 'Loopable video style with seamless cyclical motion, stable composition, and ambient playback friendliness.',
        'instruction': 'Direct the sequence as a looping background video with cyclical motion, subtle temporal continuity, and a clean start-end relationship that can repeat seamlessly. Preserve visual calm, compositional stability, and loop integrity without obvious reset points or disruptive events.',
        'main_category': 'Loop / Wallpaper / Background Motion',
    },
]
