# Polyglot - Multilingual Translation Add-on for NVDA

Polyglot is a translation add-on for the [NVDA screen reader](https://www.nvaccess.org/), designed to provide a seamless, real-time translation experience. It features a flexible and extensible engine-based architecture that integrates with several major translation services.

## About the Add-on

Polyglot brings the world closer by breaking down language barriers directly within NVDA. Whether you are browsing foreign websites, reading documents in other languages, or chatting with friends from around the globe, Polyglot provides instant translation of selected text, clipboard content, and the last text spoken by NVDA.

The core highlight of its architecture is the **dynamic engine system**. Developers can easily integrate new translation services, and the settings interface is automatically generated based on the capabilities of the selected engine, providing an intuitive user experience.

The development environment and build process for this add-on follow standard community templates, ensuring code consistency and making it easier for future contributions.

## Installation

We always recommend installing this add-on directly from the built-in NVDA Add-on Store. Alternatively, you can:

1.  Download the latest version of the add-on from the [Releases page](https://github.com/cary-rowen/polyglot/releases).
2.  Open the downloaded `.nvda-addon` file.
3.  Choose "Yes" in the NVDA installation confirmation dialog.
4.  Restart NVDA when prompted.

## Features

* **Multiple Translation Sources**: Support for translating:
    *   Selected text.
    *   Clipboard content.
    *   The last text spoken by NVDA.
* **Efficient Command Layer**: A dedicated keyboard layer (`NVDA+Shift+T`) allows you to execute various translation commands quickly with a single key press.
* **Auto-Translation**: Automatically translates any text spoken by NVDA, perfect for immersive reading.
* **Extensible Engine Architecture**: Supports multiple translation services. Developers can easily add new engines without modifying the core code.
* **Dynamic Settings UI**: The settings panel automatically adapts to the currently selected engine, showing only relevant configuration options.
* **Clipboard Integration**: Supports automatically copying translation results to the clipboard.
* **Translation Cache**: Caches results so that repeated text does not require a new translation request, effectively reducing API usage.

## Usage and Configuration

Before using the translation features, you must configure at least one translation engine. All settings are located at: **NVDA Menu -> Preferences -> Settings... -> Polyglot**.

### The Command Layer

The Command Layer is the heart of Polyglot, providing an extremely fast way to perform translation tasks.

1.  **Enter the Layer**: Press `NVDA+Shift+T`. You will hear a short, low-pitched beep indicating the layer is active.
2.  **Execute a Command**: Press any key from the list below. The layer will automatically exit after the command is executed.

**Command Layer Shortcuts:**

| Key | Action |
| :--- | :--- |
| `T` | Translate the current selection. |
| `Shift+T` | Translate the selection in reverse (Target -> Source). |
| `B` | Translate text from the clipboard. |
| `Shift+B` | Translate clipboard text in reverse. |
| `L` | Translate the last text spoken by NVDA. |
| `Shift+L` | Translate the last spoken text in reverse. |
| `S` | Cycle to the next source language. |
| `Shift+S` | Cycle to the previous source language. |
| `G` | Cycle to the next target language. |
| `Shift+G` | Cycle to the previous target language. |
| `E` | Cycle to the next translation engine. |
| `Shift+E` | Cycle to the previous translation engine. |
| `W` | Swap the source and target languages. |
| `A` | Announce the current engine and language pair. |
| `C` | Copy the last translation result to the clipboard. |
| `V` | Toggle auto-translation mode on or off. |
| `O` | Open the Polyglot settings panel. |
| `X` | Clear the translation cache. |
| `H` | Announce this list of layer shortcuts. |

### Supported Engines and Configuration

Some engines work without a key, while others require API credentials. You can configure them in the settings panel.

| Engine | Where to get credentials |
| --- | --- |
| **Google Translate (key-free)** | No key required. |
| **Microsoft Translator (key-free)**| No key required. |
| **Lingva Translate** | No key required. |
| **Yandex Translate** | No key required. |
| **DeepL** | [DeepL API](https://www.deepl.com/pro-api) |
| **Baidu Translate** | [Baidu AI Cloud](https://cloud.baidu.com/product/mt) |
| **Caiyun Translate** | [Caiyun Open Platform](https://docs.caiyunapp.com/lingocloud-api/index.html) |
| **Niutrans** | [Niutrans Open Platform](https://niutrans.com/trans-service#price) |
| **Tencent Translate** | [Tencent Cloud API](https://console.cloud.tencent.com/) |
| **VIVO Translate** | Requires an [NVDACN](https://www.nvdacn.com) account |
| **Ollama** | Your self-hosted Ollama server URL. |
| **OpenRouter** | [OpenRouter.ai](https://openrouter.ai/keys) |

## Development and Contribution

For details about the NVDA add-on development ecosystem, please refer to the [NVDA Add-on Development Guide](https://github.com/nvdaaddons/DevGuide/wiki/NVDA-Add-on-Development-Guide) and join the discussion on the [NVDA Add-ons mailing list](https://nvda-addons.groups.io/g/nvda-addons).

### Contributing

Contributions of all forms are welcome! Whether it's adding a new engine, fixing bugs, improving documentation, or refining translations, your help is greatly appreciated.

*   **Bug Reports & Feature Requests**: Please open an issue on the [GitHub repository](https://github.com/cary-rowen/polyglot/issues) and provide as much detail as possible.
*   **Pull Requests**: Fork the repository, create a new branch, and submit a PR with your changes.

### Adding a New Translation Engine

Thanks to the add-on's architecture, adding a new engine is simple:

1.  **Create a New Engine File**: Add a new Python file in the `polyglot/services/engines/` directory.
2.  **Implement the `TranslationEngine` Interface**: Your new class must inherit from `BaseHttpEngine` and implement all its abstract methods.

You can refer to existing engine files (e.g., `google.py`) as a practical example.

### Building the Add-on

This project uses the standard [NVDA Add-on Scons Template](https://github.com/nvaccess/AddonTemplate) for development and packaging. For information on how to build and distribute the add-on package, please refer to the template documentation.

This project is licensed under the GNU General Public License v2.0. See the `COPYING.txt` file for more details.
