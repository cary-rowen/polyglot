# Polyglot - Real-time Translation for NVDA

> **:warning: Work in Progress - Please Note :warning:**
>
> This project is currently in a phase of active and heavy development. The codebase is subject to frequent and significant changes.
>
> To prevent any wasted effort and ensure a smooth development process, we kindly ask that you **do not submit Pull Requests at this stage**.
>
> Additionally, please **refrain from building and distributing the add-on package** to the community, as it is not yet stable or ready for general use.
>
> We greatly appreciate your interest and will announce when the project is ready for community contributions and wider testing. Thank you for your understanding!

[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

A sophisticated translation add-on for the [NVDA screen reader](https://www.nvaccess.org/), designed to provide seamless, real-time translation capabilities. It integrates with multiple translation services through a flexible and extensible engine-based architecture.

## About

Polyglot brings the world closer by breaking down language barriers directly within your NVDA screen reader. Whether you're browsing foreign websites, reading international documents, or chatting with friends from around the globe, Polyglot offers instant translation of selected text, clipboard content, or even the last text spoken by NVDA.

Its key architectural feature is a **dynamic engine system**, which allows developers to easily plug in new translation services. The settings interface is generated dynamically based on the capabilities of the selected engine, providing a tailored and intuitive user experience.

The development environment and build process for this add-on are set up using the standard community development template, ensuring consistency and ease of contribution.

## Installation

1.  Download the latest version of the add-on from the [Releases page](https://github.com/cary-rowen/polyglot/releases).
2.  Open the downloaded `.nvda-addon` file.
3.  NVDA will ask you to confirm the installation. Choose "Yes".
4.  Restart NVDA when prompted.

## Features

*   🗣️ **Multiple Translation Sources**: Instantly translate:
    *   Selected text.
    *   Content from the clipboard.
    *   The last text spoken by NVDA.
*   🚀 **Efficient Command Layer**: A dedicated keyboard layer (`NVDA+Shift+T`) provides quick access to all translation commands with single-key presses.
*   🔄 **Automatic Speech Translation**: An optional mode that automatically translates any text spoken by NVDA, perfect for immersive reading.
*   🔌 **Extensible Engine Architecture**: Easily supports multiple translation services. New engines can be added by developers without changing the core add-on.
*   ⚙️ **Dynamic Settings UI**: The add-on's settings panel automatically adapts to show the specific configuration options for the currently selected engine.
*   ↔️ **Language Swapping**: Instantly swap the source and target languages with a single command.
*   📋 **Clipboard Integration**: Automatically copy translation results to the clipboard.
*   🧠 **Translation Cache**: Caches results to provide instant translations for repeated text and reduce API usage.

## Usage and Configuration

Before using the translation features, you must configure at least one engine. All settings are located in **NVDA Menu -> Preferences -> Settings... -> Polyglot**.

### The Command Layer

The heart of Polyglot is its command layer. This provides a fast and efficient way to perform translation tasks.

1.  **Enter the Layer**: Press `NVDA+Shift+T`. You will hear a short, low-pitched beep indicating the layer is active.
2.  **Execute a Command**: Press one of the keys listed below. The layer automatically deactivates after the command.

**Layer Commands:**

| Key | Action |
| :--- | :--- |
| `T` | Translate the current selection. |
| `Shift+T` | Translate the current selection in the reverse direction (target -> source). |
| `B` | Translate the text from the clipboard. |
| `Shift+B` | Translate clipboard text in the reverse direction. |
| `L` | Translate the last text spoken by NVDA. |
| `Shift+L` | Translate the last spoken text in the reverse direction. |
| `S` | Swap the source and target languages. |
| `A` | Announce the current engine and language pair. |
| `C` | Copy the last translation result to the clipboard. |
| `V` | Toggle auto-translation mode on or off. |
| `O` | Open the Polyglot settings panel. |
| `X` | Clear the translation cache. |
| `H` | Announce this list of layer commands. |

### Supported Engines and Configuration

Some engines work without a key, while others require credentials. Configure them in the Polyglot settings panel.

| Engine | Where to get credentials |
| --- | --- |
| **Google Translate (key-free)** | No key required. |
| **Microsoft Translator (key-free)**| No key required. |
| **Lingva Translate** | No key required. |
| **Yandex Translate** | No key required. |
| **DeepL** | [DeepL API](https://www.deepl.com/pro-api) |
| **Baidu Translate** | [Baidu AI Cloud](https://cloud.baidu.com/product/mt) |
| **Niutrans** | [Niutrans Open Platform](https://niutrans.com/trans-service#price) |
| **Tencent Translate** | [Tencent Cloud API](https://console.cloud.tencent.com/) |
| **VIVO Translate** | Requires an account with [NVDACN](https://www.nvdacn.com) |
| **Ollama** | Your self-hosted Ollama server URL. |
| **OpenRouter** | [OpenRouter.ai](https://openrouter.ai/keys) |

## For Developers and Contributors

For details about the NVDA add-on development ecosystem, please see the [NVDA Add-on Development Guide](https://github.com/nvdaaddons/DevGuide/wiki/NVDA-Add-on-Development-Guide) and join the discussion on the [NVDA Add-ons mailing list](https://nvda-addons.groups.io/g/nvda-addons).

### Contributing

Contributions are welcome! Whether it's adding a new engine, fixing a bug, improving documentation, or adding translations, your help is appreciated.

*   **Bug Reports & Feature Requests**: Please open an issue on the [GitHub repository](https://github.com/cary-rowen/polyglot/issues). Provide as much detail as possible.
*   **Pull Requests**: Fork the repository, create a new branch, and submit a pull request with your changes.

### Adding a New Translation Engine

The add-on's architecture makes it easy to add new engines.

1.  **Create a New Engine File**: Add a new Python file in the `polyglot/services/engines/` directory.
2.  **Implement the `TranslationEngine` Interface**: Your new class must inherit from `BaseHttpEngine` and implement all its abstract methods.

Refer to the existing engine files (e.g., `google.py`) for a practical example.

### Building the Add-on

This add-on uses the standard [NVDA Add-on Scons Template](https://github.com/nvdaaddons/template) for development and packaging.

**Prerequisites**:

*   Git
*   Python (3.13 64-bit or later is recommended)
*   SCons (4.9.1 or later)
*   GNU Gettext (for localization)
*   Markdown (for documentation)

**Build Commands**:

Run these commands from the root directory of the project:

1.  **`scons`**: Builds the add-on files into the root directory for easy testing.
2.  **`scons pot`**: Generates a translatable `.pot` template file in the root directory.

The project includes a GitHub Actions workflow (`.github/workflows/build_addon.yml`) for automated builds. Pushing a tag (e.g., `v1.2.3`) will automatically create a release and upload the `.nvda-addon` file as an asset.

## Roadmap (TODO)

### Core Features
-   [ ] Implement a GUI to browse and manage the translation cache.
-   [ ] Explore options for offline, on-device translation engines.

### UI/UX Improvements
-   [ ] Enhance UI state management to provide real-time feedback (e.g., character limits for some engines).
-   [ ] Add a "Test" button in engine settings to verify credentials.

## License

This project is licensed under the GNU General Public License v2.0. See the `COPYING.txt` file for more details.
