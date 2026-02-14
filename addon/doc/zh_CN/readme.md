# Polyglot - NVDA 多语言翻译插件

Polyglot 是一款为 [NVDA 屏幕阅读器](https://www.nvaccess.org/) 设计的翻译插件，旨在提供流畅的实时翻译体验。它采用灵活且可扩展的引擎架构，集成了多种主流翻译服务。

## 关于插件

Polyglot 通过直接在 NVDA 中打破语言隔阂，让世界触手可及。无论是浏览外文网页、阅读其他语言的文档，还是与全球各地的朋友聊天，Polyglot 都能为您提供选中文本、剪贴板内容、以及 NVDA 最后一次所朗读的内容的即时翻译。

其架构的核心亮点是**动态引擎系统**。开发者可以轻松接入新的翻译服务。设置界面会根据所选引擎的功能自动生成，提供了直观的操作体验。

本插件的开发环境和构建流程遵循标准的社区插件模板，确保了代码的一致性和后期贡献的便利性。

## 安装方法

我们始终推荐您从 NVDA 内置的插件商店直接安装本插件。您也可以：

1.  从 [Releases 页面](https://github.com/cary-rowen/polyglot/releases) 下载最新版本的插件。
2.  打开下载好的 `.nvda-addon` 文件。
3.  在 NVDA 的安装确认对话框中选择“是”。
4.  根据提示重启 NVDA。

## 功能特性

* **多来源翻译**：支持翻译：
    *   选中的文本。
    *   剪贴板中的内容。
    *   NVDA 最后朗读的内容。
* **高效命令层**：通过专用的快捷键层（`NVDA+Shift+T`），只需按下单个按键即可快速执行各类翻译命令。
* **自动翻译**：可自动翻译 NVDA 朗读的任何文本，非常适合沉浸式阅读。
* **可扩展引擎架构**：支持多种翻译服务。开发者可以在不修改插件核心代码的情况下轻松添加新引擎。
* **动态设置界面**：插件设置面板会根据当前选定的引擎自动调整，仅显示该引擎相关的配置选项。
* **剪贴板集成**：支持将翻译结果自动复制到剪贴板。
* **翻译缓存**：缓存翻译结果，在遇到重复文本时无需重复请求翻译，有效减少 API 调用次数。

## 使用与配置

在使用翻译功能前，您需要至少配置一个翻译引擎。所有设置均位于：**NVDA 菜单 -> 选项 -> 设置... -> Polyglot**。

### 命令层

命令层是 Polyglot 的核心设计，为您提供极其快速的翻译操作方式。

1.  **进入命令层**：按下 `NVDA+Shift+T`。您会听到一声短促的低音，表示命令层已激活。
2.  **执行命令**：按下下方列表中的任意按键。执行命令后，该层会自动退出。

**命令层快捷键一览：**

| 按键 | 动作 |
| :--- | :--- |
| `T` | 翻译当前选中的内容。 |
| `Shift+T` | 反向翻译选中的内容（目标语言 -> 源语言）。 |
| `B` | 翻译剪贴板中的文本。 |
| `Shift+B` | 反向翻译剪贴板中的文本。 |
| `L` | 翻译 NVDA 最后朗读的内容。 |
| `Shift+L` | 反向翻译最后朗读的内容。 |
| `S` | 切换到下一个源语言。 |
| `Shift+S` | 切换到上一个源语言。 |
| `G` | 切换到下一个目标语言。 |
| `Shift+G` | 切换到上一个目标语言。 |
| `E` | 切换到下一个翻译引擎。 |
| `Shift+E` | 切换到上一个翻译引擎。 |
| `W` | 交换源语言和目标语言。 |
| `A` | 播报当前使用的引擎和语言对。 |
| `C` | 将上次翻译的结果复制到剪贴板。 |
| `V` | 开启或关闭自动翻译模式。 |
| `O` | 打开 Polyglot 设置面板。 |
| `X` | 清除翻译缓存。 |
| `H` | 播报此快捷键列表帮助。 |

### 支持的引擎与配置说明

部分引擎无需密钥即可使用，部分则需要相应的 API 凭据。您可以在设置面板中进行配置。

| 引擎 | 凭据获取地址 |
| --- | --- |
| **Google 翻译 (免密钥版)** | 无需密钥。 |
| **微软翻译 (免密钥版)**| 无需密钥。 |
| **Lingva 翻译** | 无需密钥。 |
| **Yandex 翻译** | 无需密钥。 |
| **DeepL** | [DeepL API](https://www.deepl.com/pro-api) |
| **百度翻译** | [百度智能云](https://cloud.baidu.com/product/mt) |
| **彩云小译** | [彩云科技开放平台](https://docs.caiyunapp.com/lingocloud-api/index.html) |
| **小牛翻译 (Niutrans)** | [小牛翻译开放平台](https://niutrans.com/trans-service#price) |
| **腾讯翻译** | [腾讯云 API](https://console.cloud.tencent.com/) |
| **VIVO 翻译** | 需要 [NVDA 中文站](https://www.nvdacn.com) 账号 |
| **Ollama** | 您自行托管的 Ollama 服务器地址。 |
| **OpenRouter** | [OpenRouter.ai](https://openrouter.ai/keys) |

## 开发与贡献

有关 NVDA 插件开发生态的详细信息，请参阅 [NVDA 插件开发指南](https://github.com/nvdaaddons/DevGuide/wiki/NVDA-Add-on-Development-Guide)，并加入 [NVDA Add-ons 邮件列表](https://nvda-addons.groups.io/g/nvda-addons) 参与讨论。

### 参与贡献

我们非常欢迎各种形式的贡献！无论是添加新引擎、修复 Bug、完善文档还是改进翻译，您的帮助都至关重要。

*   **问题反馈与功能建议**：请在 [GitHub 代码库](https://github.com/cary-rowen/polyglot/issues) 中提交 Issue，并尽可能提供详细信息。
*   **拉取请求 (PR)**：Fork 本仓库，创建新分支，并在修改后提交 PR。

### 添加新的翻译引擎

得益于插件的架构设计，添加新引擎非常简单：

1.  **创建新引擎文件**：在 `polyglot/services/engines/` 目录下添加一个新的 Python 文件。
2.  **实现 `TranslationEngine` 接口**：您的新类必须继承自 `BaseHttpEngine` 并实现其所有抽象方法。

您可以参考现有的引擎文件（如 `google.py`）作为实战范例。

### 构建插件

本项目使用标准的 [NVDA 插件 Scons 模板](https://github.com/nvaccess/AddonTemplate) 进行开发和打包，关于如何构建和分发插件包的信息请参阅模板文档。

本项目采用 GNU General Public License v2.0 协议授权。详情请参阅 `COPYING.txt` 文件。
