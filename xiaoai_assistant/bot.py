"""Bot 核心 - 语音对话编排器"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import AsyncIterator

from xiaoai_assistant.config import Config
from xiaoai_assistant.llm_client import LLMClient
from xiaoai_assistant.tts_client import TTSClient

logger = logging.getLogger(__name__)


class Bot:
    """语音对话机器人核心

    支持多种输入模式：
    - mina: 轮询 MiNA API（适合 LX06/S12 等老款音箱）
    - miio: MiIO 本地命令（实验性）
    - web: Web/API 触发
    - cli: 命令行交互

    工作流程：
    1. 接收用户语音/文本
    2. 调用 LLM 生成回复
    3. TTS 转换为语音
    4. 音箱播放
    """

    WAKEUP_KEYWORD = "小爱同学"

    def __init__(self, config: Config):
        self.config = config
        self.llm = LLMClient(config)
        self.tts = TTSClient(config)
        self.miio = None  # 注入
        self.mina_client = None  # 注入

        self.in_conversation = False
        self.conversation_history: list[dict] = []

        # 设置日志
        logging.basicConfig(
            level=logging.DEBUG if config.verbose else logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )

    def set_miio(self, miio_client) -> None:
        """注入 MiIO 客户端"""
        self.miio = miio_client
        self.tts.miio = miio_client

    def set_mina(self, mina_client) -> None:
        """注入 MiNA 客户端"""
        self.mina_client = mina_client

    async def close(self) -> None:
        """关闭资源"""
        await self.llm.close()

    # ─── 输入处理 ───────────────────────────────────────────────

    async def handle_text(self, text: str) -> str | None:
        """处理文本输入（来自 MiNA 或 Web）

        Args:
            text: 用户说的话

        Returns:
            AI 回复文本，None 表示跳过
        """
        if not text or not text.strip():
            return None

        text = text.strip()
        logger.info(f"收到文本: {text}")

        # 检查系统命令
        if self._is_end_command(text):
            self.in_conversation = False
            self.conversation_history.clear()
            return "好的，已结束持续对话"

        if self._is_start_command(text):
            self.in_conversation = True
            self.conversation_history.clear()
            return "好的，开始持续对话。请问有什么可以帮您的？"

        # 检查唤醒词
        is_wakeup = self._check_wakeup(text)
        if not is_wakeup and not self.in_conversation:
            logger.debug("非唤醒词，非持续对话，跳过")
            return None

        # 调用 LLM
        reply = await self.ask_llm(text)
        return reply

    def _check_wakeup(self, text: str) -> bool:
        """检查是否包含唤醒词"""
        text_lower = text.lower()
        keywords = [k.lower() for k in self.config.keywords]
        return any(text_lower.startswith(k) for k in keywords)

    def _is_start_command(self, text: str) -> bool:
        return self.config.start_cmd and text.strip() == self.config.start_cmd

    def _is_end_command(self, text: str) -> bool:
        return self.config.end_cmd and text.strip() == self.config.end_cmd

    async def handle_audio_record(self, record: dict) -> str | None:
        """处理 MiNA 音频记录（来自轮询回调）

        Args:
            record: MiNA 返回的音频记录，包含 query 字段

        Returns:
            AI 回复文本
        """
        query = record.get("query", "")
        return await self.handle_text(query)

    # ─── LLM 对话 ───────────────────────────────────────────────

    async def ask_llm(self, text: str, stream: bool = False) -> str:
        """调用 LLM 获取回复"""
        # 构建消息
        messages = self._build_messages(text)

        if stream:
            response = await self.llm.chat(messages, stream=True)
            if isinstance(response, AsyncIterator):
                collected = ""
                async for chunk in response:
                    collected += chunk
                reply = collected
            else:
                reply = response
        else:
            reply = await self.llm.chat(messages, stream=False)

        logger.info(f"LLM 回复: {reply[:100]}...")
        return reply

    def _build_messages(self, user_text: str) -> list[dict]:
        """构建 LLM 消息列表"""
        messages = []

        # System prompt
        if self.config.prompt:
            messages.append({"role": "system", "content": self.config.prompt})

        # 历史记录
        messages.extend(self.conversation_history)

        # 当前输入
        messages.append({"role": "user", "content": user_text})

        return messages

    async def chat(self, text: str) -> str:
        """单轮对话（自动添加到历史）"""
        reply = await self.handle_text(text)
        if reply:
            # 添加到历史
            self.conversation_history.append({"role": "user", "content": text})
            self.conversation_history.append({"role": "assistant", "content": reply})
            # 限制历史长度
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]
        return reply or ""

    # ─── 语音播放 ───────────────────────────────────────────────

    async def speak_and_play(self, text: str) -> bool:
        """TTS + 播放"""
        if not text:
            return False
        return await self.tts.speak(text)

    async def run_round(self, user_text: str) -> str:
        """执行一轮完整的对话：处理 → LLM → TTS"""
        # 1. 处理输入
        reply = await self.handle_text(user_text)
        if not reply:
            return ""

        # 2. 播放 TTS
        await self.speak_and_play(reply)

        return reply

    # ─── 主循环 ────────────────────────────────────────────────

    async def run_mina_loop(self) -> None:
        """MiNA 轮询主循环（适合老款音箱）"""
        if not self.mina_client:
            raise RuntimeError("MiNA 客户端未注入")

        logger.info("启动 MiNA 轮询模式...")
        await self.mina_client.init()

        async def on_record(record: dict):
            query = record.get("query", "")
            if not query:
                return
            reply = await self.run_round(query)
            if reply:
                logger.info(f"已回复: {reply[:50]}...")

        await self.mina_client.poll(on_record)

    async def run_web_mode(self) -> None:
        """Web/API 触发模式（适合 X8S 等新款音箱）"""
        logger.info("启动 Web 模式，等待触发...")

        async def handle_trigger(text: str) -> str:
            reply = await self.run_round(text)
            return reply or "处理完成"

        return handle_trigger  # 返回给调用者
