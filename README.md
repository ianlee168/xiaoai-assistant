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

> 注意：X8S 等新款音箱使用 ai_protocol_3_0，音频数据不会上传到 MiNA API。

## 快速开始

### 安装

```bash
git clone https://github.com/ianlee168/xiaoai-assistant.git
cd xiaoai-assistant
pip install -e ".[all]"
```

### 配置

创建 ~/.xiaoai/config.yaml：

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

# CLI 对话模式（测试用）
xiaoai --config ~/.xiaoai/config.yaml -m cli

# 测试 LLM
xiaoai --config ~/.xiaoai/config.yaml --test-llm "你好"

# 测试 TTS
xiaoai --config ~/.xiaoai/config.yaml --test-tts "你好"
```

## 项目结构

```
xiaoai-assistant/
├── xiaoai_assistant/
│   ├── __init__.py
│   ├── __main__.py      # 入口点
│   ├── cli.py           # CLI 入口
│   ├── config.py        # 配置管理
│   ├── bot.py           # 核心对话机器人
│   ├── llm_client.py    # LLM 客户端
│   ├── tts_client.py    # TTS 客户端
│   ├── mina_client.py   # MiNA API 客户端
│   ├── miio_client.py  # MiIO 协议客户端
│   └── cookie_utils.py  # Cookie 解析
├── tests/
├── docs/
└── README.md
```

## License

MIT
