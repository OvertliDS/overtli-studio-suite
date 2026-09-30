"""Compatibility targets and local encoder checks; never silently truncate."""
from functools import lru_cache
from pathlib import Path

H3_CHARACTER_BUDGET = 7000
SOURCES = {
    "H3": "https://github.com/MiniMax-AI/cli/blob/main/src/video/v2.ts",
    "FLUX": "https://github.com/black-forest-labs/flux2/blob/main/src/flux2/text_encoder.py",
    "Qwen": "https://huggingface.co/Qwen/Qwen-Image-2.1",
}


@lru_cache(maxsize=2)
def _tokenizer(root):
    from transformers import Qwen2Tokenizer
    return Qwen2Tokenizer.from_pretrained(root, local_files_only=True)


def prompt_budget(prompt, guide, tokenizer_root=None):
    prompt = str(prompt or "")
    units = len(prompt.encode("utf-16-le")) // 2
    result = {"characters": len(prompt), "utf16_units": units, "tokens": None,
              "errors": [], "warnings": [], "token_count_kind": "unavailable; no character conversion used"}
    h3, flux = guide.startswith("H3"), "FLUX" in guide
    result["policy"] = "H3 hosted-compatible Director policy: 7000 UTF-16 units" if h3 else "Local encoder positions; FLUX reference target 512 tokens" if flux else "Local encoder positions; no published character cap"
    if h3 and units > H3_CHARACTER_BUDGET:
        result["errors"].append(f"Final H3 prompt uses {units:,}/7,000 UTF-16 units. Shorten main text, clip notes, styles, LoRA triggers or constants. Text preserved.")
    try:
        if tokenizer_root is None:
            import folder_paths
            tokenizer_root = str(Path(folder_paths.base_path)/"comfy/text_encoders/qwen25_tokenizer")
        template = prompt
        if flux:
            template = "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        elif not h3:
            template = "<|im_start|>system\nComprehend and analyze the provided prompt.<|im_end|>\n<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n"
        tokens = len(_tokenizer(str(tokenizer_root)).encode(template, add_special_tokens=False))
        result.update(tokens=tokens, token_count_kind="local Qwen tokenizer; text/template only, excludes visual/audio positions", local_position_ceiling=40960 if flux else 262144)
        if tokens > result["local_position_ceiling"]:
            result["errors"].append(f"Text alone needs {tokens:,} tokens, exceeding the local encoder's {result['local_position_ceiling']:,}-position configuration.")
        if flux and tokens > 512:
            result["warnings"].append(f"FLUX reference target is 512 tokens; this text/template has {tokens:,}. Local ComfyUI does not truncate at 512; shorter focused prompts are recommended.")
    except (ImportError, OSError, ValueError):
        result["tokenizer_status"] = "Exact local tokenizer unavailable; runtime encoder checks remain active. Estimates are not limits."
    return result


def validate_prompt_budget(prompt, guide, tokenizer_root=None):
    report = prompt_budget(prompt, guide, tokenizer_root)
    if report["errors"]:
        raise ValueError("\n".join(report["errors"]))
    return report


def validate_encoder_positions(tokens, guide):
    ceiling = 40960 if "FLUX" in guide else 262144
    for value in tokens.values() if isinstance(tokens, dict) else []:
        if not isinstance(value, list):
            continue
        for batch in value:
            if isinstance(batch, list) and len(batch) > ceiling:
                raise ValueError(f"Encoded prompt needs {len(batch):,} positions; {guide} supports at most {ceiling:,}. Shorten prompt/references.")
