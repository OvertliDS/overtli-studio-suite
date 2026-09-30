"""Resolve only the pure prompt producers used by Director graphs.

Never execute arbitrary graph nodes, load model weights, encode images, or sample.
The registered composition methods are shared with generation, including LoRA
metadata planning. Studio enhancement is explicit and reused by an identical run.
"""
import inspect
import json
from .prompt_budgets import prompt_budget

PURE = {
    "OvertliStudioSuite", "OvertliImageDirectorUI", "OvertliImagePromptComposer",
    "OvertliImagePromptTriggerMerge", "OvertliH3ReferenceDirectorUI",
    "OvertliH3AudioDirectorUI", "OvertliH3SequenceDirectorUI",
    "OvertliH3ReferenceIntentPrompt", "OvertliH3ReferenceClipSettings",
    "OvertliH3ContinuationPrompt", "OvertliH3SequenceClipSettings",
    "OvertliH3AudioSyncPrompt", "OvertliH3ReferenceRunControl",
    "OvertliH3PromptPrefix",
    "OvertliImageGenerationState", "OvertliImageDirectorResolve",
    "OvertliH3DualPassControl",
    "OvertliH3SequenceDefaults", "OvertliH3ClipSettings", "OvertliH3RunControl",
}


def inspect_prompts(output, registry=None):
    if not isinstance(output, dict) or len(output) > 3000:
        raise ValueError("Invalid or oversized prompt graph.")
    if registry is None:
        import nodes
        registry = nodes.NODE_CLASS_MAPPINGS
    cache, visiting = {}, set()

    def resolve(value):
        if isinstance(value, list) and len(value) == 2 and str(value[0]) in output and isinstance(value[1], int):
            return run(str(value[0]), value[1])
        return value

    def run(node_id, slot):
        key = (node_id, slot)
        if key in cache:
            return cache[key]
        if key in visiting:
            raise ValueError("Cycle in prompt graph.")
        visiting.add(key)
        row = output[node_id]
        kind, inputs = row.get("class_type"), row.get("inputs", {})
        if kind in {"PixaromaText", "PrimitiveString", "PrimitiveStringMultiline"}:
            values = (str(inputs.get("text", inputs.get("value", ""))),)
        elif kind == "OvertliH3ReferencePromptCheck" and slot == 0:
            values = (resolve(inputs.get("prompt", "")),)
        elif kind in {"OvertliH3OptionalLoRAStack", "OvertliMultiLoraStack"}:
            expected = 1 if kind == "OvertliH3OptionalLoRAStack" else 3
            if slot != expected:
                raise ValueError("Prompt preview cannot evaluate model/CLIP tensors.")
            cls = registry[kind]
            kwargs = {k: resolve(v) for k, v in inputs.items() if k not in {"model", "clip"}}
            if kind == "OvertliMultiLoraStack":
                kwargs["has_clip"] = "clip" in inputs
            values = tuple(None if i != slot else cls.prompt_plan(**kwargs) for i in range(slot + 1))
        elif kind in PURE:
            cls = registry[kind]
            fn = getattr(cls(), cls.FUNCTION)
            params = inspect.signature(fn).parameters
            accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
            kwargs = {k: resolve(v) for k, v in inputs.items() if accepts_kwargs or k in params}
            values = fn(**kwargs)
            if isinstance(values, dict):
                values = values["result"]
        else:
            raise ValueError(f"Prompt preview cannot resolve {kind}. Connect a supported text source or inspect its output before generation.")
        for index, value in enumerate(values):
            cache[node_id, index] = value
        visiting.remove(key)
        return cache[key]

    prompts, unresolved = [], []
    for node_id, row in output.items():
        kind = str(row.get("class_type", ""))
        if kind == "OvertliImageRefineConditioning":
            label = row.get("_meta", {}).get("title") or kind
            try:
                inputs = row.get("inputs", {})
                text = registry[kind].prompt_plan(resolve(inputs["director_state"]))
                if text:
                    guide = str(resolve(inputs["engine"]))
                    prompts.append({"node": node_id, "label": label, "field": "refine prompt", "prompt": text,
                                    "characters": len(text), "budget": prompt_budget(text, guide)})
            except (ValueError, KeyError, TypeError) as exc:
                unresolved.append({"node": node_id, "label": label, "error": str(exc)})
            continue
        if "Conditioning" not in kind and kind not in {"CLIPTextEncode", "CLIPTextEncodeFlux", "CLIPTextEncodeSDXL", "MiniMaxH3ToVideo", "MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"}:
            continue
        for field in ("prompt", "text", "text_l", "text_g"):
            if field not in row.get("inputs", {}):
                continue
            label = row.get("_meta", {}).get("title") or kind
            try:
                text = str(resolve(row["inputs"][field]))
                guide = "H3 Ref2VA" if "H3" in kind else "Qwen Image 2.1" if "Qwen" in kind else "FLUX.2 Klein 9B"
                if kind == "OvertliImageEngineConditioning":
                    guide = str(resolve(row["inputs"].get("engine", guide)))
                budget = prompt_budget(text, guide)
                prompts.append({"node": node_id, "label": label, "field": field, "prompt": text, "characters": len(text), "budget": budget})
            except (ValueError, KeyError, TypeError) as exc:
                unresolved.append({"node": node_id, "label": label, "error": str(exc)})
    if not prompts and not unresolved:
        # Standalone Studio preview remains useful without a conditioning node.
        for node_id, row in output.items():
            if row.get("class_type") == "OvertliStudioSuite":
                text = str(run(node_id, 0))
                prompts.append({"node": node_id, "label": "Studio output", "field": "prompt", "prompt": text, "characters": len(text)})
    return {"prompts": prompts, "unresolved": unresolved, "complete": not unresolved and not any(p.get("budget", {}).get("errors") for p in prompts),
            "note": "Resolved by generation's prompt producers. An unchanged enhancement is cached for ten minutes; editing inputs or settings requires a new preview."}
