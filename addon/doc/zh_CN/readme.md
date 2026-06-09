# Polyglot for NVDA

Polyglot 是一个面向 NVDA 的全局翻译插件，重点在于快速、多引擎、可扩展。它可以翻译选中文本、剪贴板文本和 NVDA 最近一次朗读的内容，也可以拦截 NVDA 朗读内容并执行自动翻译。

插件的核心是动态引擎架构。每个翻译引擎都声明自己的能力和配置项，设置界面在运行时根据这些配置动态生成，因此核心逻辑保持精简，同时也方便继续接入新的翻译服务。

## 功能概览

- 翻译选中文本、剪贴板文本和 NVDA 最后一次朗读的文本。
- 提供 `NVDA+Alt+Z` 翻译命令层；在命令层中按 `H` 可显示命令层帮助。
- 支持实时自动翻译 NVDA 的朗读内容。
- 提供智能语音过滤，尽量跳过角色、状态、位置信息和格式提示等不适合翻译的内容。
- 带持久化翻译缓存，减少重复请求。
- 可在手动翻译成功后自动复制结果到剪贴板。
- 可直接通过快捷键切换引擎和语言。
- 提供独立的交互式翻译窗口，适合较长文本或反复试译。

## 安装

推荐直接通过 NVDA 插件商店安装。也可以手动安装：

1. 从 [Releases 页面](https://github.com/cary-rowen/polyglot/releases) 下载最新的 `.nvda-addon` 安装包。
2. 打开下载好的文件。
3. 在 NVDA 中确认安装。
4. 按提示重启 NVDA。

## 快速开始

1. 打开 `NVDA 菜单 -> 选项 -> 设置 -> Polyglot`。
2. 选择一个翻译引擎，并确认该引擎已启用。
3. 如果该引擎需要凭据，先完成配置。
4. 设置源语言和目标语言。
5. 按需启用自动复制结果和智能语音过滤。
6. 按 `NVDA+Alt+Z` 进入命令层，再按下面的功能键执行操作；在命令层中按 `H` 可显示命令层帮助。

## 命令层

按 `NVDA+Alt+Z` 进入命令层。进入后会有一声短促提示音。在命令层中按 `H` 可显示命令层帮助。大多数命令执行后会自动退出命令层；切换语言和切换引擎等命令会保持在命令层中，方便连续调整。切换引擎只会在已启用的引擎之间循环。

| 按键 | 动作 |
| --- | --- |
| `T` | 翻译当前选中的文本。 |
| `Shift+T` | 反向翻译当前选中的文本。 |
| `B` | 翻译剪贴板文本。 |
| `Shift+B` | 反向翻译剪贴板文本。 |
| `L` | 翻译 NVDA 最后一次朗读的文本。 |
| `Shift+L` | 反向翻译 NVDA 最后一次朗读的文本。 |
| `S` | 切换到下一个源语言。 |
| `Shift+S` | 切换到上一个源语言。 |
| `G` | 切换到下一个目标语言。 |
| `Shift+G` | 切换到上一个目标语言。 |
| `E` | 切换到下一个已启用的翻译引擎。 |
| `Shift+E` | 切换到上一个已启用的翻译引擎。 |
| `W` | 交换源语言和目标语言。 |
| `A` | 播报当前引擎和语言对。 |
| `C` | 复制最近一次翻译结果。 |
| `V` | 开启或关闭自动翻译。 |
| `I` | 打开交互式翻译窗口。 |
| `O` | 打开 Polyglot 设置面板。 |
| `X` | 清空翻译缓存。 |
| `H` | 打开命令层帮助。 |

## 交互式翻译窗口

交互式翻译窗口适合长文本、反复调整参数或需要边改边试的场景。

- 在命令层按 `I` 打开窗口。
- 可以直接在窗口内选择已启用的引擎、源语言和目标语言。
- 禁用的引擎仍可在设置中配置，但不会出现在该窗口的引擎列表中。
- 对于 LLM 类引擎，可以在窗口里调整模型和提示词模板。
- 在源文本框中按 `Ctrl+Enter` 可直接发起翻译。
- 可在窗口内复制结果，也可一键清空输入和输出。

## 设置说明

### 通用设置

- `将手动翻译结果复制到剪贴板`：手动翻译成功后，自动把结果复制到剪贴板。
- `启用智能语音过滤（忽略无需翻译的文本，例如角色、状态、位置和其他格式信息）`：在处理 NVDA 朗读内容时，尽量跳过角色、状态、位置和格式等非正文信息。
- `清除缓存`：清除持久化翻译缓存，按钮标签中会显示当前缓存条目数。

### 各引擎通用设置

大多数引擎都继承一组公共配置：

- `启用此引擎`：控制该引擎是否可用于翻译请求、命令层引擎切换和交互式翻译窗口。禁用后的引擎仍会保留在设置中，方便继续配置。
- `源语言` 和 `目标语言`
- `代理模式`：使用系统代理，或完全禁用代理
- `请求超时`：请求超时时间

如果某个引擎会返回检测到的源语言，还会额外显示：

- `当检测到的源语言与目标语言相同时自动交换 (源语言须为“自动检测”)`：当源语言设为自动检测且识别结果与目标语言相同时，自动切换翻译方向
- `交换至语言`：发生自动切换时使用的替代目标语言

### 自动翻译行为

- 自动翻译依赖 NVDA 朗读管线里捕获到的文本。
- 插件会抑制自身的播报内容，避免出现翻译结果再次被翻译的循环。
- 如果自动翻译连续失败 3 次，会自动关闭。
- 智能语音过滤主要影响“朗读内容翻译”，不会改变普通手动文本翻译的行为。

### LLM 与 Polyglot 扩展设置

部分引擎会额外暴露高级选项：

- `Ollama 1` 和 `Ollama 2` 提供两个互相独立的保存槽，适合分别保存不同的 Ollama 地址和模型。
- `OpenRouter` 提供 API 地址、API 密钥、模型预设、自定义模型名称、提示词模板、自定义系统提示词和用户提示词。
- `Ollama` 引擎提供 API 地址、模型名称、API 密钥（可选）、提示词模板和自定义提示词。
- `Google Translate (Polyglot)` 提供可配置的端点 URL 和 API 密钥字段。
- `Google Translate (key-free)` 提供可选的镜像服务器开关。

## Chrome AI 离线翻译

Polyglot 可以使用 Chrome 内置的 Translator API 进行离线翻译。翻译由本机独立的 Chrome 实例完成，文本不会发送到第三方翻译服务。

### 使用条件

- 已安装 Google Chrome。
- 建议使用 Chrome 138 或更高版本。
- 首次使用某个语言方向时，需要准备对应的本机翻译模型。Polyglot 可以通过模型管理器下载模型，也可以让 Chrome 自行下载。

### 使用方式

在 Polyglot 设置中选择 `Chrome AI (Offline)`，并设置源语言和目标语言。

首次翻译时，如果所需模型尚未安装，Polyglot 会弹出询问对话框。选择“是”会使用 Polyglot 模型管理器下载并安装模型；如果你的网络访问 Chrome 模型下载服务较慢、被阻断或不稳定，建议选择此项。选择“否”会让 Chrome 下载模型；选择“取消”会取消本次翻译。模型准备好后，翻译会自动继续。

### 网络与模型

翻译在本机完成。模型可以由 Polyglot 模型管理器安装，也可以由 Chrome 下载。如果你的网络访问 Chrome 模型下载服务较慢或不可用，可以在询问对话框中选择“是”，也可以从 NVDA 的“工具”菜单打开 Polyglot ChromeAI 模型管理器，提前安装或移除需要的离线模型。

### 隐私与数据

Polyglot 会为 Chrome AI 使用独立的 Chrome 数据目录，避免影响日常 Chrome 配置。模型、缓存和运行数据会保留，以减少重复下载。

默认位置为：

```text
%LOCALAPPDATA%\Polyglot\ChromeAI
```

如果系统中没有 `LOCALAPPDATA` 环境变量，则会回退到 NVDA 配置目录下的 `polyglot_chrome_ai` 目录。

NVDA 退出时，Polyglot 会关闭由插件启动的 Chrome 实例。

### 限制

- 支持的语言和语言对由 Chrome Translator API 决定。
- 首次使用需要准备模型，模型下载可能受网络环境影响。
- 如果 Translator API 不可用，请更新 Chrome，或确认相关 Chrome 功能已启用。

## 引擎一览

当前仓库中包含以下翻译引擎：

| 引擎 | 所需凭据 | 说明 |
| --- | --- | --- |
| `Baidu Translate` | 百度 app ID 和 secret | 标准厂商 API 接入。 |
| `Caiyun` | 彩云 token | 标准厂商 API 接入。 |
| `Chrome AI (Offline)` | 无 | 使用 Chrome 内置 Translator API 和本机模型；首次使用时需要准备模型。 |
| `DeepL` | DeepL API 密钥 | 标准厂商 API 接入。 |
| `Google Translate (key-free)` | 无 | 可选启用镜像接口。 |
| `Google Translate (Polyglot)` | 可配置 API 密钥和端点 URL | 代码内带默认接口值，实际可用性取决于服务状态。 |
| `Lingva Translate` | 无 | 使用公开 Lingva 接口，不报告检测语言。 |
| `Microsoft Translator (key-free)` | 无 | 会自动获取临时访问令牌。 |
| `Niutrans` | 小牛翻译 API 密钥 | 标准厂商 API 接入。 |
| `Ollama 1` | Ollama 地址、模型名、可选密钥 | 第一个独立 Ollama 配置槽。 |
| `Ollama 2` | Ollama 地址、模型名、可选密钥 | 第二个独立 Ollama 配置槽。 |
| `OpenRouter` | OpenRouter API 密钥 | 支持模型预设和可编辑提示词模板。 |
| `Tencent Translate` | 腾讯 secret ID 和 secret key | 标准厂商 API 接入。 |
| `Tencent Translate (Polyglot)` | NVDACN 用户名和密码 | 使用 Polyglot/NVDACN 路由的腾讯翻译。 |
| `VIVO Translate` | NVDACN 用户名和密码 | 支持语言较少，不支持源语言自动检测。 |
| `Volcengine (Polyglot)` | NVDACN 用户名和密码 | 使用 Polyglot/NVDACN 路由的火山翻译。 |
| `Yandex Translate` | 无 | 使用公开接口风格，不报告检测语言。 |

## 参与贡献

欢迎贡献代码、文档、翻译、测试和新的引擎接入。

- 问题跟踪：[GitHub Issues](https://github.com/cary-rowen/polyglot/issues)
- 版本发布：[GitHub Releases](https://github.com/cary-rowen/polyglot/releases)

如果你要新增一个翻译引擎：

1. 在 `addon/globalPlugins/polyglot/services/engines/` 下创建模块。
2. 实现 `TranslationEngine`，或者对 HTTP 引擎继承 `BaseHttpEngine`。
3. 如果引擎需要设置项，在 `getConfigSpec()` 中返回配置描述。
4. 使用 `views/factory.py` 已支持的控件类型：`choice`、`text`、`password`、`checkbox`、`spinctrl`。
5. 确认该引擎能正确出现在动态设置面板中，并在启用后参与命令层切换和交互式翻译窗口。

## 许可证

本项目使用 GNU General Public License v2 授权，详见 [COPYING.txt](../../../COPYING.txt)。
