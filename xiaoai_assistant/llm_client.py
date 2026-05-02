"""LLM 客户端 - 支持多种 LLM 提供商"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import aiohttp

logger = logging.getLogger(__name__)


class LLMClient:
    """统一的 LLM 客户端"""

    PROVIDERS = {
        "openai", "groq", "minimax", "moonshot",
        "gemini", "anthropic", "qwen", "deepseek"
    }

    def __init__(self, config):
        self.config = config
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def chat(
        self, messages: list[dict], stream: bool = False
    ) -> str | AsyncIterator[str]:
        """发送对话请求，返回文本或流式迭代器"""
        provider = self.config.llm.provider.lower()

        if provider == "openai":
            return await self._chat_openai(messages, stream)
        elif provider == "groq":
            return await self._chat_openai(messages, stream)  # Groq 也用 OpenAI 兼容 API
        elif provider == "minimax":
            return await self._chat_openai(messages, stream)
        elif provider == "moonshot":
            return await self._chat_openai(messages, stream)
        elif provider == "gemini":
            return await self._chat_gemini(messages)
        elif provider == "anthropic":
            return await self._chat_anthropic(messages)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    async def _chat_openai(
        self, messages: list[dict], stream: bool = False
    ) -> str | AsyncIterator[str]:
        """OpenAI 兼容 API"""
        url = f"{self.config.llm.api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.llm.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.llm.model,
            "messages": messages,
            "temperature": self.config.llm.temperature,
            "max_tokens": self.config.llm.max_tokens,
            "stream": stream,
        }

        async with self.session.post(
            url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=self.config.llm.timeout)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"LLM API 错误 {resp.status}: {text}")

            if stream:
                async def gen():
                    async for line in resp.content:
                        line = line.decode().strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            import json
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content

                return gen()
            else:
                import json
                data = await resp.json()
                return data["choices"][0]["message"]["content"]

    async def _chat_gemini(self, messages: list[dict]) -> str:
        """Google Gemini API"""
        # 构建 prompt
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.llm.model}:generateContent"
        params = {"key": self.config.llm.api_key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.config.llm.temperature,
                "maxOutputTokens": self.config.llm.max_tokens,
            }
        }

        async with self.session.post(
            url, json=payload, params=params,
            timeout=aiohttp.ClientTimeout(total=self.config.llm.timeout)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Gemini API 错误 {resp.status}: {text}")
            import json
            data = await resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _chat_anthropic(self, messages: list[dict]) -> str:
        """Anthropic Claude API"""
        # 转换消息格式
        sys_msg = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                sys_msg = m["content"]
            else:
                filtered.append(m)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.config.llm.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.llm.model,
            "messages": filtered,
            "max_tokens": self.config.llm.max_tokens,
            "temperature": self.config.llm.temperature,
        }
        if sys_msg:
            payload["system"] = sys_msg

        async with self.session.post(
            url, json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.config.llm.timeout)
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Anthropic API 错误 {resp.status}: {text}")
            import json
            data = await resp.json()
            return data["content"][0]["text"]
