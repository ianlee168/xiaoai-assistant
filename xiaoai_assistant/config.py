"""配置管理"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"  # openai, groq, minimax, moonshot, gemini
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    temperature: float = 0.8
    max_tokens: int = 512
    timeout: int = 30


@dataclass
class TTSConfig:
    """TTS 配置"""
    provider: str = "mi"  # mi, edge, openai
    api_key: str = ""
    api_base: str = ""
    voice: str = "mi"
    speed: float = 1.0


@dataclass
class SpeakerConfig:
    """音箱配置"""
    hardware: str = "LX06"  # LX06, S12, S12A, X8S ...
    mi_did: str = ""  # 设备 DID
    account: str = ""  # 小米账号
    password: str = ""  # 小米密码
    mi_token_path: str = str(Path.home() / ".mi.token")
    cookie: str = ""  # 可选，直接提供 cookie


@dataclass
class PluginConfig:
    """插件配置"""
    enabled: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)


@dataclass
class Config:
    """主配置"""
    # LLM
    llm: LLMConfig = field(default_factory=LLMConfig)
    # TTS
    tts: TTSConfig = field(default_factory=TTSConfig)
    # 音箱
    speaker: SpeakerConfig = field(default_factory=SpeakerConfig)
    # 插件
    plugins: PluginConfig = field(default_factory=PluginConfig)

    # 全局
    debug: bool = False
    verbose: bool = False
    mute_xiaoai: bool = False  # 静默小爱音箱（不让她回答）

    # 输入模式
    input_mode: str = "mina"  # mina, miio, web, cli
    # 唤醒词（MiNA 轮询模式）
    keywords: list[str] = field(default_factory=lambda: ["小爱同学"])

    # 持续对话
    continuous_dialogue: bool = False
    start_cmd: str = "开始持续对话"
    end_cmd: str = "结束持续对话"

    # Prompt
    prompt: str = "你是一个友好的 AI 助手，请用简洁的语言回答用户的问题。"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """从 YAML 文件加载配置"""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data or {})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """从字典加载配置"""
        cfg = cls()

        if "llm" in data:
            for k, v in data["llm"].items():
                if hasattr(cfg.llm, k):
                    setattr(cfg.llm, k, v)

        if "tts" in data:
            for k, v in data["tts"].items():
                if hasattr(cfg.tts, k):
                    setattr(cfg.tts, k, v)

        if "speaker" in data:
            for k, v in data["speaker"].items():
                if hasattr(cfg.speaker, k):
                    setattr(cfg.speaker, k, v)

        if "plugins" in data:
            for k, v in data["plugins"].items():
                if hasattr(cfg.plugins, k):
                    setattr(cfg.plugins, k, v)

        # 全局
        if "debug" in data:
            cfg.debug = data["debug"]
        if "verbose" in data:
            cfg.verbose = data["verbose"]
        if "mute_xiaoai" in data:
            cfg.mute_xiaoai = data["mute_xiaoai"]
        if "input_mode" in data:
            cfg.input_mode = data["input_mode"]
        if "keywords" in data:
            cfg.keywords = data["keywords"]
        if "continuous_dialogue" in data:
            cfg.continuous_dialogue = data["continuous_dialogue"]
        if "start_cmd" in data:
            cfg.start_cmd = data["start_cmd"]
        if "end_cmd" in data:
            cfg.end_cmd = data["end_cmd"]
        if "prompt" in data:
            cfg.prompt = data["prompt"]

        return cfg

    def update_from_env(self) -> None:
        """从环境变量补充配置"""
        if os.getenv("MI_USER"):
            self.speaker.account = os.getenv("MI_USER")
        if os.getenv("MI_PASS"):
            self.speaker.password = os.getenv("MI_PASS")
        if os.getenv("MI_DID"):
            self.speaker.mi_did = os.getenv("MI_DID")
        if os.getenv("OPENAI_API_KEY"):
            self.llm.api_key = os.getenv("OPENAI_API_KEY")
