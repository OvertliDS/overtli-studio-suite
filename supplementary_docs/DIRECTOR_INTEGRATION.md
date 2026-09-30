# Director integration, version 1.2

The unified `OvertliStudioSuite` node accepts a connected authored prompt and outputs
the resolved prompt plus JSON structure checks. Existing `GZ_*` nodes retain their
IDs and behavior. Enhancement starts disabled so opening or migrating a workflow
does not contact a provider or change an authored prompt. Local auto-unload starts
enabled.

## Prompt authoring and library

H3 and Image Director use `web/director_shared.js`. Prompt fields grow with text,
wrap within the node, show character counts and approximate tokens (characters / 4),
and provide local literal find/replace with Ctrl+F. Use next match, replace one,
replace all, case matching, or Escape to close the search controls.

The separate editable constant field appends one trailing `[Constant]` block.
Replacing the constant replaces the previous trailing block. Disabling it preserves
the authored prompt. **Use example constant** fills the supplied cinematic,
consistency, anatomy and physics example; it remains editable. A constant is prompt
text, not a change to output pixel dimensions.

The standard shared library remains compatible with existing Image Director entries.
Addtl uses `overtli_addtl_prompt_library.json`. Search/category filters, prompt text
preview, tags and notes appear in the same layout. **Save new** rejects an existing
name; **Update existing** explicitly replaces it. Loading restores both authored
text, styles, custom guidance and the constant block. Saved recipes contain only
prompt options, never provider credentials. Library files use the existing local user store.

The same node contains searchable style presets (up to seven distinct styles),
custom style guidance, prompt saving and provider controls. Styles precede the
trailing constant. H3 replacement clips inherit the global constant.

Manual resizing and **Node size** controls preserve saved dimensions. Autosize
retains a usable 700-pixel minimum width and the saved manual dimensions. Prompt
accordions scroll within the chosen height rather than collapsing the node width.

**Final prompts sent to the model / Prepare final prompts** resolves the current
graph through generation's prompt producers, including clip/base replacement,
intent notes, LoRA triggers, Image composition and optional refinement prompts.
It never loads model weights. Enabled enhancement runs on request; an identical
generation reuses the result for ten minutes. Editing prompts/settings requires
a new snapshot. Unsupported custom text producers are reported as unresolved.

## Guides and checks

`guides/minimax_h3.md` and `guides/image_director.md` contain the complete supplied
engineering guides. Provider instructions select H3 Ref2VA, H3 Base, FLUX.2 Klein
9B or Qwen Image 2.1, preserve user instructions and authored dialogue, and include
the corresponding guide. These guides condition an LLM; they do not guarantee
rendered motion or visual fidelity.

Checks report Ref2VA's six ordered fields, Base's three fields, active reference
tags with independent Picture/Video/Audio numbering, chronological cuts and clip
duration where available. Warnings remain visible without rewriting an authored
prompt. Editors show estimates; prepared prompt budgets use the installed local
Qwen tokenizer without downloading anything, including the engine text template.
Visual/audio positions remain separate from the displayed text count.

### Engine budgets (verified 2026-09-30)

| Engine | Published contract | Local Director behavior |
| --- | --- | --- |
| MiniMax H3 | Official hosted CLI rejects text over 7,000 JavaScript string units | Enforces 7,000 UTF-16 units on the final composed prompt for hosted compatibility; local H3 does not inherently have that character cap |
| FLUX.2 Klein 9B | Official reference text encoder uses 512 tokens with truncation | Warns above the 512 text/template-token reference target; local ComfyUI pads to at least 512 and does not truncate there; configured local positional ceiling is 40,960 |
| Qwen Image 2.1 | No verified published character cap | Uses actual local text-token measurement; configured Qwen3-VL positional ceiling is 262,144, shared with visual positions |

The local H3 Qwen3-VL encoder also configures 262,144 positions. These are model
configuration ceilings, not practical VRAM budgets or guarantees that arbitrary
reference combinations fit. Runtime checks validate token batches; multimodal
expansion can require additional positions. Oversized text produces an actionable
error without silently truncating or changing authored text. Guides target under
6,000 H3 units to reserve space for constants and triggers. There is no fixed
character-to-token conversion: 7,000 English characters might be roughly 1,750
tokens, but use the measured count for the actual text.

Sources: [MiniMax H3 validation](https://github.com/MiniMax-AI/cli/blob/main/src/video/v2.ts),
[FLUX reference encoder](https://github.com/black-forest-labs/flux2/blob/main/src/flux2/text_encoder.py),
[Qwen Image 2.1](https://huggingface.co/Qwen/Qwen-Image-2.1),
[Qwen pipeline](https://github.com/huggingface/diffusers/blob/main/src/diffusers/pipelines/qwenimage21/pipeline_qwenimage21.py).
Local checks were traced through ComfyUI `minimax.py`, `qwen3vl.py`, `qwen_image21.py`
and `llama.py`; keep the distinction when updating engines.

## Providers, persistence and unload

Choose a provider and use **Refresh models** after connection changes. Catalogs and
failures are cached for five minutes; workflow loading and node schema discovery
never poll provider model catalogs. Legacy Pollinations schemas use cached catalog
data too. Inference and explicit refresh may perform network requests.

Provider URLs/API keys are saved through the existing settings store. Keys are
redacted on reads and never placed in workflow state. Blank key fields preserve a
stored key; explicit clear buttons remove it. Local blank URLs use the native
defaults, LM Studio at `127.0.0.1:1234` and Ollama at `127.0.0.1:11434`.

LM Studio uses native `/api/v1/chat`, advertised reasoning options, a bounded
response/context budget, and final message output. Local context defaults to 8192
tokens, separately from the 2048-token response budget, and expands when the full
guide plus response needs more room. Auto-unload enumerates and
unloads only instances of the selected model through `/api/v1/models/unload`, then
checks host state. Unified Studio sends Ollama `/api/chat` with `num_ctx`,
`num_predict` and `keep_alive: 0`; legacy enhancers retain `/api/generate`. Both verify
the selected model disappears from `/api/ps`. Unload runs in `finally`, including
failed inference; failures produce actionable errors. Other loaded models are
preserved.

Codex requires a signed-in installed CLI. Models come from its current app-server
`model/list`; this may differ from models displayed by the desktop app. Tests run
an isolated ephemeral `codex exec` with a read-only sandbox, supplied guide and
prompt, no repository rules/configuration, and a temporary output file. Only the
owned subprocess is stopped. No fixed cloud model list is embedded in the UI.

References: [LM Studio chat](https://lmstudio.ai/docs/developer/rest/chat),
[LM Studio unload](https://lmstudio.ai/docs/developer/rest/unload),
[Ollama generate](https://docs.ollama.com/api/generate),
[Codex app-server](https://developers.openai.com/codex/app-server/).

## Media, Addtl and optional Pixaroma integration

Director integrations require the matching H3/Image Director frontend and backend.
Save Video/comparison additionally require **ComfyUI-Pixaroma** and its available
FFmpeg proxy helper. Studio prompt authoring remains usable without Pixaroma.

`workflow_migration.py` upgrades graphs surgically. It preserves prompt text,
selected references and authored LoRA strengths, intercepts the existing prompt
wire with one Studio node, and adds H3 slots four/five at 0.5. Image Director's
existing eight slots remain intact. Addtl defaults show NSFW LoRAs and disable blur.
Detected author/embedded/sidecar/Civitai recommendations take precedence over the
0.5 fallback; a detection result does not overwrite a strength edited while the
request was running. Actual thumbnails use sibling images or a cached published
preview, including a JPEG poster for a video-only LoRA preview.

Addtl paths use `input/OvertliDS/addtl`, `output/OvertliDS/addtl`,
`temp/OvertliDS/addtl/previews`, a separate prompt library, and separate H3 latent
continuation storage. Existing selected references are copied with streaming hash
checks and collision-safe names, preserving originals. `OvertliAddtlLoadImage`
and `OvertliAddtlLoadVideo` list recursive Addtl files in their native schemas and
validate the selected path. Managed standard selectors exclude Addtl entries.

Save Video retains its upstream `PixaromaSaveVideo` ID so its original frontend
controls continue to work. Missing save state defaults to durable **Save** for all
four formats; explicit **Preview** remains temporary. The selected folder is
respected, including registered external folders. Each saved master gets an
`.overtli.json` sidecar containing its resolved prompt, LoRA plan and Director
state. API keys are not included.

The H3 Output tab compares two latest saved outputs or uploaded comparison files.
Players synchronize play/pause, seek and rate; frame steps use saved FPS or the
entered uploaded-clip FPS. MP4 HQ and ProRes use browser proxies when required;
uploaded codecs fall back to a bounded proxy on decode failure. Master files are
preserved. Comparison metadata can be expanded beside each player. Uploading an
older saved file allows comparison against the latest output.

## Verification and recovery

Run Python tests with your ComfyUI-compatible Python environment:

```powershell
python -m pytest supplementary_docs/tests -q
node supplementary_docs/tests/test_director_frontend.cjs
```

Restart ComfyUI after backend changes. Save ongoing browser edits before refreshing
custom-node JavaScript, then reopen the upgraded saved workflow. Backend restart
alone does not replace an already loaded graph or its unsaved state.

Migration callers should checkpoint workflows and active Director copies first.
Restore those exact files to roll back; do not regenerate all authored workflows
or reset an unrelated dirty checkout. Artistic quality and unavailable provider
services require separate live validation.
