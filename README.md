<div align="center">

<img src="assets/logo.gif" height="120" alt="OVERTLI Logo">

# OVERTLI STUDIO LLM Suite

**Windows-first ComfyUI custom nodes for local and cloud AI generation, featuring a unified advanced router for seamless multi-engine workflows.**

[![Platform: Windows First](https://img.shields.io/badge/Platform-Windows_First-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-Custom_Nodes-000000?style=for-the-badge&logo=python&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](#license)

<br>

<a href="https://pollinations.ai">
  <img src="https://img.shields.io/badge/Powered%20by-Pollinations.ai-ff1493?style=for-the-badge&logoColor=white" alt="Powered by Pollinations.ai" />
</a>
&nbsp;
<a href="https://lmstudio.ai">
  <img src="https://img.shields.io/badge/Local%20AI-LM%20Studio-5A5A5A?style=for-the-badge&logoColor=white" alt="LM Studio" />
</a>
&nbsp;
<a href="https://github.com/features/copilot">
  <img src="https://img.shields.io/badge/CLI%20Integration-GitHub%20Copilot-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Copilot" />
</a>

</div>

---

## 🚀 Installation & Quick Start

### Installation

1. Navigate to your ComfyUI custom nodes directory and clone this repository:
   ```powershell
   cd ComfyUI/custom_nodes/
   git clone https://github.com/OvertliDS/overtli-studio-suite.git
   ```

2. Navigate into the cloned folder and install the required dependencies using your ComfyUI Python environment:
   ```powershell
   cd overtli-studio-suite
   pip install -r requirements.txt
   ```

3.  Restart ComfyUI.

### Quick Start Workflow

*You can find the nodes by simply searching for "Overtli".*

1.  Add the **`GZ_ProviderSettings`** node and save your keys or URLs once.
2.  Add the **`GZ_AdvancedTextEnhancer`** or **`GZ_LLMTextEnhancer`** node.
3.  Choose your `provider` and `active_engine`.
4.  Connect optional `IMAGE` or `AUDIO` inputs when needed.
5.  Execute and use the native output directly in your workflow.

### Use With Existing ComfyUI Workflows (CLIP Text Encode)

You can use OVERTLI as a **drop-in prompt enhancer** without rebuilding your graph.

1.  Add any text-capable OVERTLI node (for example `GZ_TextEnhancer`, `GZ_LLMTextEnhancer`, or `GZ_AdvancedTextEnhancer` with `active_engine = text`).
2.  Connect the node's `STRING` output to your existing **CLIP Text Encode** node `text` input.
3.  Keep the rest of your workflow unchanged (sampler, model, VAE, etc.).

This lets you enhance or rewrite any prompt while still using your current ComfyUI pipeline.

### Example Workflow

For users who want a sample workflow with Flux2Klein 9B GGUF, use workflows/OvertliStudioSuite_x_Flux2Klein9B-GGUF.json from this repo.

-----

## ✨ Core Capabilities

  * **Unified Advanced Routing:** Manage multi-engine workflows through a single, powerful provider node.
  * **Native Media Contracts:** Full support for standard ComfyUI output types.
      * `AUDIO` for text-to-speech and text-to-music generation.
      * `VIDEO` for video generation capabilities.
      * The Advanced Router dynamically returns `STRING + IMAGE + VIDEO + AUDIO`.
  * **Native Previews:** Fully integrated with ComfyUI’s native image and text preview rendering.

-----

## 🧩 Registered Nodes

| Node | Purpose | Supports |
| :--- | :--- | :--- |
| ⚡ **`GZ_AdvancedTextEnhancer`** | **(Recommended)** Unified provider/engine router. | Provider-aware engine routing: `text`, `image`, `video`, `text_to_speech`, `speech_to_text`, `text_to_music` with validation. |
| 🔌 **`GZ_OpenAICompatibleTextEnhancer`** | Dedicated OpenAI-compatible all-engines node. | `text`, `image_gen`, `video_gen`, `text_to_speech_gen`, `speech_to_text_gen`, `text_to_music_gen` through OpenAI-compatible APIs. |
| 📝 **`GZ_TextEnhancer`** | Pollinations text and optional vision enhancement. | Pollinations text generation, optional vision image context, grouped mode presets. |
| 🎨 **`GZ_ImageGen`** | Pollinations image generation. | Pollinations image generation models. |
| 🎬 **`GZ_VideoGen`** | Pollinations video generation. | Pollinations video generation models (`VIDEO` output). |
| 🗣️ **`GZ_TextToSpeech`** | Pollinations speech generation. | Pollinations text-to-speech models (`AUDIO` output). |
| 🎧 **`GZ_SpeechToText`** | Pollinations speech transcription. | Pollinations speech-to-text models (`STRING` transcript output). |
| 🎵 **`GZ_TextToAudio`** | Pollinations text-to-music generation. | Pollinations text-to-music generation (`AUDIO` output). |
| 🖥️ **`GZ_LLMTextEnhancer`**| **(Recommended for local)** Local/OpenAI-compatible text+vision route (LM Studio, Ollama, similar endpoints). | Text generation with optional image context over local/OpenAI-compatible chat endpoints. |
| 🤖 **`GZ_CopilotAgent`** | GitHub Copilot CLI route. | Copilot CLI text generation with optional image attachment context. |
| ⚙️ **`GZ_ProviderSettings`** | Persisted provider settings helper. | Save/load provider model, endpoint, and API key settings for this suite. |
| 📚 **`GZ_PromptLibraryNode`** | Prompt library CRUD/refresh utility. | Prompt management and reusable preset selection. |
| 🥞 **`GZ_StyleStackNode`** | Reusable style stack utility. | Composable style bundles for prompt layering across nodes. |

-----

## 🌐 Provider Coverage

### ✨ Pollinations.ai

Full support for text, image, video, text-to-speech, speech-to-text, and text-to-music.

### 🖥️ LM Studio

Local text generation with optional image context for vision-capable local models.

### 🤖 GitHub Copilot CLI

Local CLI-based text enhancement with optional image context.

### 🔌 OpenAI-Compatible APIs

Available through both:

  * `GZ_OpenAICompatibleTextEnhancer` (dedicated node)
  * `GZ_AdvancedTextEnhancer` with `provider = openai_compatible`

Supported engines:

  * `text`
  * `image`
  * `video`
  * `text_to_speech`
  * `speech_to_text`
  * `text_to_music`

> **Note:** exact modality availability still depends on the target OpenAI-compatible provider and selected model. The suite now exposes these engines with explicit runtime validation and terminal-visible errors when a provider/model endpoint cannot satisfy a request.

-----

## 🔑 Provider Setup & Authentication
The Overtli Studio Suite is designed to be as "zero-config" as possible, supporting cloud, local, and standard API protocols.

### ✨ Pollinations.ai (Cloud)
API Key: Visit enter.pollinations.ai to generate your key.

Setup: Enter your key into the GZ_ProviderSettings node or set the GZ_POLLINATIONS_API_KEY environment variable, as well as support in Pollinations nodes to enter api key directly.

Pricing: `Free` tagged models allow free generations, but pollen usage is determined based on your free plan tier within enter.pollinations.ai so aim to reach higher tiers for more free generations or top up using gems while waiting for your pollen to reset. `Paid` models are supported as well if gems have been purchased. 

### 🤖 GitHub Copilot CLI (Cloud/Local Hybrid)
Auto-Detection: If you are already signed in via the GitHub CLI (gh auth login), Overtli will automatically detect your session and "just work."

Prerequisites: Requires an active Copilot subscription and the GitHub CLI installed (It will open a copilot-cli terminal silently by default for communication).

Vision/Image context: OVERTLI writes Comfy `IMAGE` inputs to temporary local files and references them with Copilot CLI `@path` attachment syntax so vision-capable models receive the actual image bytes.

Background behavior: Copilot auth recovery and vision-cache retry handling are managed automatically in the background so the node surface stays simple. With `vision_enabled` on, prior runtime vision-cache entries do not silently block new image attempts by default.

### 🖥️ LM Studio (Local)
Host: Defaults to http://localhost:1234.

Setup: Ensure LM Studio is running and the "Local Server" is started. No API key is required by default.

Vision: Support for vision-capable local models is integrated directly into the GZ_LLMTextEnhancer.


### 🔌 OpenAI-Compatible APIs (Custom)
Flexibility: Use any provider that supports the OpenAI standard (e.g., Groq, Together AI, LocalAI).

Setup: Requires a Base URL and API Key configured in the GZ_ProviderSettings node (or just use the GZ_AdvancedTextEnhancer or GZ_LLMTextEnhancer node).

-----

## 🧠 Prompting & Output Contracts

### The Composition Model

All primary routes follow the same strict sequence:

1.  **Custom Instructions**
2.  **Selected Mode Preset**
3.  **Raw Prompt** (User Prompt)
4.  **Style Layers** (`style_preset_1..3` + `additional_styles`)

> 💡 **Tip:** The `additional_styles` input is socket-first (`forceInput`) and is designed to chain seamlessly from the `GZ_StyleStackNode`.

### Quick Instruction Modes Overview

Instruction presets are grouped by task family and can be toggled on/off per route. 

At-a-glance preset counts (current build):

- **Total instruction presets:** **63** (excluding `Off` options)
- **Text:** 14
- **Image:** 24 (4 vision + 10 generation + 6 editing + 4 narrative)
- **Video:** 11 (8 generation + 3 analysis)
- **TTS:** 8
- **Text-to-Audio:** 3
- **Speech-to-Text:** 3

- **Text modes:** examples include `Enhance` (expand a short idea into a richer prompt), `Refine` (tighten wording while preserving intent), and `Translation Prompt` (convert to generation-ready English).
- **Image modes:** examples include `Tags` (comma-separated visual tags), `Simple Description` (single concise visual description), `Concept Art` (design-forward scene direction), and `Upscale Image Prompt` (detail-preserving enhancement guidance).
- **Video modes:** examples include `Cinematic Video Prompt` (film-style motion direction), `Loop Video Prompt` (seamless repeating motion guidance), and `Video Summary` (chronological visual recap of footage).
- **TTS modes:** examples include `Voiceover Script` (clean narration pacing for speech synthesis), `Character Voice` (expressive dialogue delivery), and `SSML Enhancement` (markup-driven timing and emphasis control).
- **Text-to-Audio modes:** examples include `Audio Prompt Enhance` (clarify generation intent), `Music Direction` (genre/instrument/energy guidance), and `Ambience and Foley` (layered environmental sound design).
- **Speech-to-Text modes:** examples include `Clean Transcript` (readability cleanup while preserving meaning), `Punctuation and Casing` (restore sentence structure), and `Structured Notes` (concise key points and actions).

If a mode is set to `Off`, the route relies on custom instructions + raw prompt + style layers.

*Only enable ONE instruction group*

### Quick Style Layering Overview

- **Built-in style library:** **656** presets (+ `Off` option)

- **Built-in style slots:** up to **3** per primary node (`style_preset_1..3`).
- **Extended style stack:** connect `additional_styles` from **`GZ_StyleStackNode`** for up to **7** extra styles.
- **Total style layers available:** up to **10** (3 built-in + 7 stacked).

Style examples (brief):

- **Photograph (Real Life):** grounded, natural realism with real lens/lighting behavior.
- **Cinematic Still:** film-like framing, layered depth, and motivated key/fill/rim lighting.
- **Anime Illustration:** expressive line work, controlled cel-shading, and clean silhouette readability.
- **Line Art (Clean):** minimal contour-focused visuals with crisp outlines and low noise.
- **Concept Art:** production-style world/design visualization with clear value hierarchy.

### Output Contracts

| Route Type | Native ComfyUI Output |
| :--- | :--- |
| **Text** | `STRING` |
| **Image** | `IMAGE` |
| **Video** | `VIDEO` |
| **Audio-producing** | `AUDIO` |
| **Advanced Router** | `STRING`, `IMAGE`, `VIDEO`, `AUDIO` |

-----

## ⚙️ Settings and Precedence

Persistent settings are stored locally in:

```text
ComfyUI/user/overtli_studio_settings.json
```

**Resolution Precedence:**

1.  Runtime node input *(Highest priority)*
2.  Environment variable
3.  Persisted settings
4.  Suite default *(Lowest priority)*

<details>
<summary><b>🔧 Click to view useful Environment Variables</b></summary>

* `GZ_POLLINATIONS_API_KEY`
* `GZ_POLLINATIONS_CHAT_TIMEOUT`
* `GZ_POLLINATIONS_IMAGE_TIMEOUT`
* `GZ_POLLINATIONS_VIDEO_TIMEOUT`
* `GZ_POLLINATIONS_TTS_TIMEOUT`
* `GZ_POLLINATIONS_STT_TIMEOUT`
* `GZ_POLLINATIONS_AUDIO_TIMEOUT`
* `GZ_LMSTUDIO_HOST`
* `GZ_LMSTUDIO_PORT`
* `GZ_LMSTUDIO_API_KEY`
* `GZ_COPILOT_EXECUTABLE`
* `GZ_COPILOT_MODEL`
* `GZ_COPILOT_TIMEOUT`
* `GZ_OPENAI_COMPAT_BASE_URL`
* `GZ_OPENAI_COMPAT_API_KEY`
* `GZ_OPENAI_COMPAT_MODEL`
* `GZ_LOG_LEVEL`
* `GZ_TEMP_DIR`

</details>

-----

## 🧯 Troubleshooting

**OpenAI-compatible route does not appear in the node list**
You should see both:

  * `GZ_OpenAICompatibleTextEnhancer` (dedicated node), and
  * `GZ_AdvancedTextEnhancer` with `provider = openai_compatible`.

If they are missing, restart ComfyUI and confirm this custom node folder is loaded without import errors.

**STT fails with missing input**
`GZ_SpeechToText` requires an `AUDIO` input connection to function.

**Video generation blocks the UI**
That is expected for synchronous provider-side video generation. The UI will resume once rendering is complete.

**LM Studio/Ollama does not return models**
Make sure LM Studio/Ollama is running and exposing its API endpoint correctly.

**Copilot route fails unexpectedly**
Check that:

  * GitHub Copilot CLI is installed and reachable.
  * The configured executable path is correct if adjusted manually.
  * Your authentication session is valid.
  * Environment token overrides are not conflicting.

-----

## 🤝 Support & Funding

If this suite accelerates your workflow, consider supporting the continued development of Overtli tools and other projects using the GitHub Sponsor link on the repository sidebar.

## 📄 License

MIT. See `LICENSE`.
