from __future__ import annotations

from typing import NotRequired, TypedDict


class AudioStylePreset(TypedDict):
    task: str
    name: str
    category: str
    instruction: str
    hint: str


class AudioStyleBundle(TypedDict):
    tts: str
    stt: str
    ttaudio: str
    description: NotRequired[str]
