from __future__ import annotations

from typing import NotRequired, TypedDict


class PromptStyle(TypedDict):
    key: str
    label: str
    tags: list[str]
    description: str
    instruction: str
    main_category: NotRequired[str]
    raw_label: NotRequired[str]


STYLE_OFF_LABEL = "Off"
