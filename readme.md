# Polyglot for NVDA

Polyglot is an NVDA global add-on focused on fast, flexible multilingual translation. It can translate selected text, clipboard content, and the last text spoken by NVDA, and it can also intercept spoken content for live auto-translation.

The add-on is built around a dynamic engine architecture. Translation engines declare their own capabilities and configuration schema, and the settings UI is generated from that schema at runtime. That keeps the core plugin small while making it straightforward to add new services.

## What It Does

- Translates selected text, clipboard text, and the last spoken NVDA utterance.
- Provides a translation command layer on `NVDA+Alt+Z`; press `H` in the layer to show command layer help.
- Supports live auto-translation of spoken NVDA content.
- Includes a smart speech filter to avoid translating roles, states, and formatting noise.
- Persists a translation cache to reduce repeated requests.
- Can copy manual translation results to the clipboard automatically.
- Lets you switch engines and languages without leaving the keyboard.
- Exposes a dedicated interactive translation dialog for longer or iterative translation work.

## Installation

The preferred installation path is the NVDA Add-on Store. You can also install manually:

1. Download the latest `.nvda-addon` package from the [Releases page](https://github.com/cary-rowen/polyglot/releases).
2. Open the downloaded file.
3. Confirm installation in NVDA.
4. Restart NVDA when prompted.

## Quick Start

1. Open `NVDA menu -> Preferences -> Settings -> Polyglot`.
2. Choose a translation engine and make sure it is enabled.
3. Configure any required credentials for that engine.
4. Set source and target languages.
5. Optionally enable clipboard copy and the smart speech filter.
6. Press `NVDA+Alt+Z`, then use one of the command-layer keys below. Press `H` in the layer to show command layer help.

## Command Layer

Press `NVDA+Alt+Z` to enter the command layer. A short beep confirms that the layer is active. Press `H` in the layer to show command layer help. Most commands execute once and exit the layer. Language and engine switching commands stay inside the layer so you can continue cycling. Engine switching cycles through enabled engines only.

| Key | Action |
| --- | --- |
| `T` | Translate the current selection. |
| `Shift+T` | Translate the current selection in reverse. |
| `B` | Translate clipboard text. |
| `Shift+B` | Translate clipboard text in reverse. |
| `L` | Translate the last text spoken by NVDA. |
| `Shift+L` | Translate the last text spoken by NVDA in reverse. |
| `S` | Next source language. |
| `Shift+S` | Previous source language. |
| `G` | Next target language. |
| `Shift+G` | Previous target language. |
| `E` | Next enabled engine. |
| `Shift+E` | Previous enabled engine. |
| `W` | Swap source and target languages. |
| `A` | Announce the current engine and language pair. |
| `C` | Copy the last translation result. |
| `V` | Toggle auto-translation. |
| `I` | Open the interactive translation dialog. |
| `O` | Open Polyglot settings. |
| `X` | Clear the translation cache. |
| `H` | Show command-layer help. |

## Interactive Translation Dialog

The interactive dialog is designed for longer text and iterative translation work.

- Open it from the command layer with `I`.
- Select an enabled engine, source language, and target language without leaving the dialog.
- Disabled engines remain configurable in settings, but are not listed in this dialog.
- For LLM-style engines, adjust model and prompt template directly in the dialog.
- Press `Ctrl+Enter` in the source text box to translate.
- Copy the result or clear both panes without reopening the window.

## Settings Guide

### Common Settings

- `Copy manual translation results to clipboard`: Copies manual translation output after a successful request.
- `Enable smart speech filter`: When translating spoken NVDA output, skips non-content speech such as roles, states, location, and formatting details where possible.
- `Clear Cache`: Clears the persistent translation cache and shows the current item count in the button label.

### Shared Engine Settings

Most engines inherit a common set of settings:

- `Enable this engine`: controls whether the engine is available for translation requests, command-layer engine switching, and the interactive dialog. Disabled engines remain visible and configurable in settings.
- `Source language` and `Target language`
- `Proxy mode`: use system proxy settings or disable proxy usage
- `Request timeout`

If an engine reports detected source language, Polyglot also exposes:

- `Auto-swap if detected source matches target`: useful when the source language is set to auto-detect
- `Swap to language`: the alternative target used during auto-swap

### Auto-Translation Behavior

- Auto-translation acts on spoken NVDA content captured by the speech pipeline.
- The add-on suppresses its own spoken messages to avoid translation loops.
- If auto-translation fails three times in a row, it is turned off automatically.
- The smart speech filter mainly affects spoken-content translation, not standard manual text translation.

### LLM and Polyglot-Specific Options

Some engines expose additional controls:

- `Ollama 1` and `Ollama 2` provide two separate saved profiles for different local or remote Ollama setups.
- `OpenRouter` exposes API URL, API key, model preset, custom model name, prompt template, and custom prompts.
- `Ollama` engines expose API URL, model name, optional API key, prompt template, and custom prompts.
- `Google Translate (Polyglot)` exposes a configurable endpoint URL and API key field.
- `Google Translate (key-free)` offers an optional mirror-server toggle.

## Chrome AI Offline Translation

Polyglot can use Chrome's built-in Translator API for offline translation. Translation is handled by an isolated local Chrome instance, so the text is not sent to a third-party translation service.

### Requirements

- Google Chrome must be installed.
- Chrome 138 or later is recommended.
- The first use of a language direction requires the local translation model to be prepared. Polyglot can download the model through its model manager, or you can let Chrome download it.

### How To Use

Select `Chrome AI (Offline)` in Polyglot settings, then choose the source and target languages.

On first use, if the required model is not installed, Polyglot asks how to proceed. Choose Yes to download and install the model with Polyglot's model manager; use this if Chrome's model download service is slow, blocked, or unreliable on your network. Choose No to let Chrome download the model. Choose Cancel to cancel the current translation. After the model is ready, translation continues automatically.

### Network And Models

Translation runs locally. Models can be installed by Polyglot's model manager or downloaded by Chrome. If Chrome's model download service is slow or unavailable on your network, choose Yes in the prompt, or open the Polyglot ChromeAI model manager from NVDA's Tools menu to install or remove offline models in advance.

### Privacy And Data

Polyglot uses a separate Chrome data directory for Chrome AI, so it does not affect your regular Chrome profile. Models, cache data, and runtime data are kept to avoid repeated downloads.

The default location is:

```text
%LOCALAPPDATA%\Polyglot\ChromeAI
```

If the `LOCALAPPDATA` environment variable is not available, Polyglot falls back to the `polyglot_chrome_ai` directory under the NVDA configuration directory.

When NVDA exits, Polyglot closes the Chrome instance it started.

### Limitations

- Supported languages and language pairs are determined by Chrome's Translator API.
- First use requires the model to be prepared; model downloads may be affected by network conditions.
- If the Translator API is unavailable, update Chrome or make sure the related Chrome feature is enabled.

## Engine Overview

The repository currently includes the following engines:

| Engine | Credentials | Notes |
| --- | --- | --- |
| `Baidu Translate` | Baidu app ID and secret | Standard vendor API integration. |
| `Caiyun` | Caiyun token | Standard vendor API integration. |
| `Chrome AI (Offline)` | None | Uses Chrome's built-in Translator API with local models; the model must be prepared on first use. |
| `DeepL` | DeepL API key | Standard vendor API integration. |
| `Google Translate (key-free)` | None | Supports an optional mirror endpoint toggle. |
| `Google Translate (Polyglot)` | Configurable API key and endpoint | Ships with default endpoint values in code; availability depends on service status. |
| `Lingva Translate` | None | Public Lingva endpoint, no language-detection reporting in responses. |
| `Microsoft Translator (key-free)` | None | Fetches a temporary token automatically. |
| `Niutrans` | Niutrans API key | Standard vendor API integration. |
| `Ollama 1` | Ollama URL, model name, optional key | First saved Ollama profile. |
| `Ollama 2` | Ollama URL, model name, optional key | Second saved Ollama profile. |
| `OpenRouter` | OpenRouter API key | Supports model presets and editable prompt templates. |
| `Tencent Translate` | Tencent secret ID and secret key | Standard vendor API integration. |
| `Tencent Translate (Polyglot)` | NVDACN username and password | Polyglot-backed Tencent route. |
| `VIVO Translate` | NVDACN username and password | Limited language set, no auto-detect source language. |
| `Volcengine (Polyglot)` | NVDACN username and password | Polyglot-backed Volcengine route. |
| `Yandex Translate` | None | Public-style endpoint, no detected-language reporting. |

## Contributing

Contributions are welcome across code, documentation, localization, testing, and engine integrations.

- Issues: [GitHub Issues](https://github.com/cary-rowen/polyglot/issues)
- Releases: [GitHub Releases](https://github.com/cary-rowen/polyglot/releases)

When adding a new engine:

1. Create a module under `addon/globalPlugins/polyglot/services/engines/`.
2. Implement `TranslationEngine` or, for HTTP engines, extend `BaseHttpEngine`.
3. Return a config spec from `getConfigSpec()` if the engine needs settings.
4. Use supported control types from `views/factory.py`: `choice`, `text`, `password`, `checkbox`, and `spinctrl`.
5. Verify the engine appears correctly in the dynamic settings panel and, when enabled, command-layer switching and the interactive dialog.

## License

This project is licensed under the GNU General Public License v2. See [COPYING.txt](COPYING.txt).
