"""配置测试"""
import pytest
from xiaoai_assistant.config import Config, LLMConfig, TTSConfig, SpeakerConfig


def test_config_defaults():
    cfg = Config()
    assert cfg.llm.provider == "openai"
    assert cfg.tts.provider == "mi"
    assert cfg.speaker.hardware == "LX06"
    assert cfg.input_mode == "mina"
    assert "小爱同学" in cfg.keywords


def test_config_from_dict():
    data = {
        "llm": {"provider": "groq", "model": "llama-3.1-70b-versatile"},
        "speaker": {"hardware": "X8S", "account": "test", "password": "test"},
        "input_mode": "cli",
    }
    cfg = Config.from_dict(data)
    assert cfg.llm.provider == "groq"
    assert cfg.llm.model == "llama-3.1-70b-versatile"
    assert cfg.speaker.hardware == "X8S"
    assert cfg.input_mode == "cli"
