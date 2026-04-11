"""Compatibility shim for legacy advanced openai-engine imports."""

from engine import openai_compatible_text_enhancer as _impl

globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})

del _impl

