# Polyglot for NVDA

Polyglot 是一个面向 NVDA 的全局翻译插件，重点在于快速、多引擎、可扩展。它可以翻译选中文本、剪贴板文本和 NVDA 最近一次朗读的内容，也可以拦截 NVDA 朗读内容并执行自动翻译。

插件的核心是动态引擎架构。每个翻译引擎都声明自己的能力和配置项，设置界面在运行时根据这些配置动态生成，因此核心逻辑保持精简，同时也方便继续接入新的翻译服务。

## 功能概览

- 翻译选中文本、剪贴板文本和 NVDA 最后一次朗读的文本。
- 提供 `NVDA+Shift+T` 命令层，适合纯键盘快速操作。
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
2. 选择一个翻译引擎。
3. 如果该引擎需要凭据，先完成配置。
4. 设置源语言和目标语言。
5. 按需启用自动复制结果和智能语音过滤。
6. 按 `NVDA+Shift+T` 进入命令层，再按下面的功能键执行操作。

## 命令层

按 `NVDA+Shift+T` 进入命令层。进入后会有一声短促提示音。大多数命令执行后会自动退出命令层；切换语言和切换引擎等命令会保持在命令层中，方便连续调整。

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
| `E` | 切换到下一个翻译引擎。 |
| `Shift+E` | 切换到上一个翻译引擎。 |
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
- 可以直接在窗口内选择引擎、源语言和目标语言。
- 对于 LLM 类引擎，可以在窗口里调整模型和提示词模板。
- 在源文本框中按 `Ctrl+Enter` 可直接发起翻译。
- 可在窗口内复制结果，也可一键清空输入和输出。

## 设置说明

### 通用设置

- `Copy manual translation results to clipboard`：手动翻译成功后，自动把结果复制到剪贴板。
- `Enable smart speech filter`：在处理 NVDA 朗读内容时，尽量跳过角色、状态、位置和格式等非正文信息。
- `Clear Cache`：清除持久化翻译缓存，按钮标签中会显示当前缓存条目数。

### 各引擎通用设置

大多数引擎都继承一组公共配置：

- `Source language` 和 `Target language`
- `Proxy mode`：使用系统代理，或完全禁用代理
- `Request timeout`：请求超时时间

如果某个引擎会返回检测到的源语言，还会额外显示：

- `Auto-swap if detected source matches target`：当源语言设为自动检测且识别结果与目标语言相同时，自动切换翻译方向
- `Swap to language`：发生自动切换时使用的替代目标语言

### 自动翻译行为

- 自动翻译依赖 NVDA 朗读管线里捕获到的文本。
- 插件会抑制自身的播报内容，避免出现翻译结果再次被翻译的循环。
- 如果自动翻译连续失败 3 次，会自动关闭。
- 智能语音过滤主要影响“朗读内容翻译”，不会改变普通手动文本翻译的行为。

### LLM 与 Polyglot 扩展设置

部分引擎会额外暴露高级选项：

- `Ollama 1` 和 `Ollama 2` 提供两个互相独立的保存槽，适合分别保存不同的 Ollama 地址和模型。
- `OpenRouter` 提供 API URL、API Key、模型预设、自定义模型名、提示词模板、自定义系统提示词和用户提示词。
- `Ollama` 引擎提供 API URL、模型名、可选 API Key、提示词模板和自定义提示词。
- `Google Translate (Polyglot)` 提供可配置的接口地址和 API Key 字段。
- `Google Translate (key-free)` 提供可选的镜像服务器开关。

## 引擎一览

当前仓库中包含以下翻译引擎：

| 引擎 | 所需凭据 | 说明 |
| --- | --- | --- |
| `Baidu Translate` | 百度 app ID 和 secret | 标准厂商 API 接入。 |
| `Caiyun` | 彩云 token | 标准厂商 API 接入。 |
| `DeepL` | DeepL API Key | 标准厂商 API 接入。 |
| `Google Translate (key-free)` | 无 | 可选启用镜像接口。 |
| `Google Translate (Polyglot)` | 可配置 API Key 和接口地址 | 代码内带默认接口值，实际可用性取决于服务状态。 |
| `Lingva Translate` | 无 | 使用公开 Lingva 接口，不报告检测语言。 |
| `Microsoft Translator (key-free)` | 无 | 会自动获取临时访问令牌。 |
| `Niutrans` | 小牛翻译 API Key | 标准厂商 API 接入。 |
| `Ollama 1` | Ollama 地址、模型名、可选密钥 | 第一个独立 Ollama 配置槽。 |
| `Ollama 2` | Ollama 地址、模型名、可选密钥 | 第二个独立 Ollama 配置槽。 |
| `OpenRouter` | OpenRouter API Key | 支持模型预设和可编辑提示词模板。 |
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
5. 确认该引擎能正确出现在动态设置面板和命令层中。

## 许可证

本项目使用 GNU General Public License v2 授权，详见 [COPYING.txt](../../../COPYING.txt)。
