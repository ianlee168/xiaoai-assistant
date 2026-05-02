# xiaoai-assistant

小爱音箱 AI 助手框架，参考 xiaogpt 和 wukong-robot 实现。

支持多种 LLM（ChatGPT/Groq/MiniMax/Moonshot）和多种 TTS 引擎。

## 功能特性

- 多输入模式：MiNA 轮询 / Web API / CLI 对话
- 多 LLM 支持：OpenAI、Groq、MiniMax、Moonshot、Gemini、Anthropic Claude
- 多 TTS 支持：小米内置 TTS、Edge TTS、OpenAI TTS
- 插件系统：可扩展的技能插件
- Python 3.8+：轻量、清晰、易于维护

## 硬件兼容性

| 型号 | 协议 | 音频上传 | 推荐模式 |
|------|------|---------|---------|
| LX06 | MiNA | 支持 | mina |
| S12 / S12A | MiNA | 支持 | mina |
| X8S | MiNA | 不支持 | web / cli |

> **注意**：X8S 等新款音箱使用 ai_protocol_3_0，音频数据不会上传到 MiNA API。

## 快速开始

### 安装

```bash
git clone https://github.com/ianlee168/xiaoai-assistant.git
cd xiaoai-assistant
pip install -e ".[all]"
```

### 配置

创建 `~/.xiaoai/config.yaml`：

```yaml
llm:
  provider: minimax
  api_key: your-api-key
  api_base: https://api.minimax.chat/v1
  model: MiniMax-M2.7
  temperature: 0.8

tts:
  provider: mi

speaker:
  hardware: LX06
  mi_did: "123456789"
  account: "18612345678"
  password: "your-password"

input_mode: mina
keywords:
  - 小爱同学
prompt: "你是一个友好的 AI 助手，请用简洁的语言回答。"
```

### 运行

```bash
# MiNA 轮询模式（适合 LX06/S12）
xiaoai --config ~/.xiaoai/config.yaml -m mina

# Web API 模式（适合 X8S 等新款音箱）
xiaoai --config ~/.xiaoai/config.yaml -m web

# CLI 对话模式（测试用）
xiaoai --config ~/.xiaoai/config.yaml -m cli

# 测试 LLM
xiaoai --config ~/.xiaoai/config.yaml --test-llm "你好"

# 测试 TTS
xiaoai --config ~/.xiaoai/config.yaml --test-tts "你好"
```

## 输入模式

### `mina` - MiNA 轮询模式

通过轮询 MiNA API 获取音箱的对话记录。**仅支持老款音箱**（LX06/S12 等）。

工作原理：
1. 每 3 秒轮询一次 MiNA API
2. 检测到用户语音输入后，提取文本
3. 调用 LLM 生成回复
4. 通过 TTS 在音箱上播放

### `web` - Web API 模式

启动一个 HTTP API 服务器，接收外部请求并触发对话。**适合 X8S 等新款音箱**。

```bash
# 启动 Web 服务器
xiaoai --config ~/.xiaoai/config.yaml -m web
```

API 端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/chat` | POST | 发送对话，返回 AI 回复并播报 TTS |
| `/chat/stream` | POST | 流式对话（Server-Sent Events） |
| `/tts` | POST | 直接 TTS 播报，不走 LLM |
| `/health` | GET | 健康检查 |
| `/status` | GET | 状态信息 |

调用示例：

```bash
# 触发对话
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，介绍你自己"}'

# 直接播报 TTS
curl -X POST http://localhost:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，我是小爱助手"}'
```

可以用这个模式结合 Home Assistant 或其他自动化工具，实现语音控制。

### `cli` - 命令行模式

直接在终端输入文本进行对话，用于测试 LLM 和 TTS。

## 项目结构

```
xiaoai-assistant/
├── xiaoai_assistant/
│   ├── __init__.py
│   ├── __main__.py         # 入口点
│   ├── cli.py              # CLI 入口
│   ├── config.py           # 配置管理
│   ├── bot.py              # 核心对话机器人
│   ├── llm_client.py        # LLM 客户端
│   ├── tts_client.py       # TTS 客户端
│   ├── mina_client.py       # MiNA API 客户端
│   ├── miio_client.py      # MiIO 协议客户端
│   ├── web_server.py        # Web API 服务器
│   └── cookie_utils.py     # Cookie 解析
├── tests/
├── docs/
└── README.md
```

## 配置参考

### LLM 提供商

| Provider | API Base | Model 示例 |
|----------|----------|-----------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.1-70b-versatile` |
| MiniMax | `https://api.minimax.chat/v1` | `MiniMax-M2.7` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta` | `gemini-1.5-flash` |

### 音箱型号硬件代码

LX06 / S12 / S12A / LX01 / LX04 / L06A / L05B / L05C / L07A / L15A / LX05A / L17A / X08E / X6A / X10A / X8S

## License

MIT
