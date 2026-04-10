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

1.  Add the **`GZ_ProviderSettings`** node and save your keys or URLs once.
2.  Add the **`GZ_AdvancedTextEnhancer`** node.
3.  Choose your `provider` and `active_engine`.
4.  Connect optional `IMAGE` or `AUDIO` inputs when needed.
5.  Execute and use the native output directly in your workflow.

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

| Node | Purpose |
| :--- | :--- |
| ⚡ **`GZ_AdvancedTextEnhancer`** | **(Recommended)** Unified provider/engine router. |
| 📝 **`GZ_TextEnhancer`** | Pollinations text and optional vision enhancement. |
| 🎨 **`GZ_ImageGen`** | Pollinations image generation. |
| 🎬 **`GZ_VideoGen`** | Pollinations video generation. |
| 🗣️ **`GZ_TextToSpeech`** | Pollinations speech generation. |
| 🎧 **`GZ_SpeechToText`** | Pollinations speech transcription. |
| 🎵 **`GZ_TextToAudio`** | Pollinations text-to-music generation. |
| 🖥️ **`GZ_LMStudioTextEnhancer`**| LM Studio local text/vision route. |
| 🤖 **`GZ_CopilotAgent`** | GitHub Copilot CLI route. |
| ⚙️ **`GZ_ProviderSettings`** | Persisted provider settings helper. |
| 📚 **`GZ_PromptLibraryNode`** | Prompt library CRUD/refresh utility. |
| 🥞 **`GZ_StyleStackNode`** | Reusable style stack utility. |

-----

## 🌐 Provider Coverage

### ✨ Pollinations.ai

Full support for text, image, video, text-to-speech, speech-to-text, and text-to-music.

### 🖥️ LM Studio

Local text generation with optional image context for vision-capable local models.

### 🤖 GitHub Copilot CLI

Local CLI-based text enhancement with optional image or file-path context.

### 🔌 OpenAI-Compatible APIs

Available through `GZ_AdvancedTextEnhancer` with `provider = openai_compatible`.
Supported engines:

  * `text`
  * `image`
  * `text_to_speech`
  * `speech_to_text`
  * `text_to_music`

> **Note:** `video` remains provider-specific and is intentionally excluded from generic OpenAI-compatible flows.

-----

## 🧠 Prompting & Output Contracts

### The Composition Model

All primary routes follow the same strict sequence:

1.  **Custom Instructions**
2.  **Selected Mode Preset**
3.  **Raw Prompt**
4.  **Style Layers** (`style_preset_1..3` + `additional_styles`)

> 💡 **Tip:** The `additional_styles` input is socket-first (`forceInput`) and is designed to chain seamlessly from the `GZ_StyleStackNode`.

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
4. Suite default *(Lowest priority)*

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

**OpenAI-compatible route does not appear as its own node**
That is expected. Use `GZ_AdvancedTextEnhancer` with `provider = openai_compatible`.

**STT fails with missing input**
`GZ_SpeechToText` requires an `AUDIO` input connection to function.

**Video generation blocks the UI**
That is expected for synchronous provider-side video generation. The UI will resume once rendering is complete.

**LM Studio does not return models**
Make sure LM Studio is running and exposing its API endpoint correctly.

**Copilot route fails unexpectedly**
Check that:

  * GitHub Copilot CLI is installed and reachable.
  * The configured executable path is correct.
  * Your authentication session is valid.
  * Environment token overrides are not conflicting.

-----

## 🤝 Support & Funding

If this suite accelerates your workflow, consider supporting the continued development of Overtli tools using the GitHub Sponsor link on the repository sidebar.

## 📄 License

MIT. See `LICENSE`.