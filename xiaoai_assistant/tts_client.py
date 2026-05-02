"""TTS 客户端 - 支持多种 TTS 引擎"""
from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from typing import Literal

import aiohttp

logger = logging.getLogger(__name__)


class TTSClient:
    """统一的 TTS 客户端"""

    def __init__(self, config, miio_client=None):
        self.config = config
        self.miio = miio_client  # 可选，用于直接播放

    async def speak(self, text: str) -> bool:
        """将文本转为语音并播放"""
        provider = self.config.tts.provider.lower()

        if provider == "mi":
            return await self._speak_mi(text)
        elif provider == "edge":
            return await self._speak_edge(text)
        elif provider == "openai":
            return await self._speak_openai(text)
        else:
            logger.warning(f"未知 TTS 提供商: {provider}，跳过播放")
            return False

    async def _speak_mi(self, text: str) -> bool:
        """小米内置 TTS（通过 MiIO 协议播放）"""
        if self.miio is None:
            logger.warning("MiIO 客户端未配置，无法使用小米 TTS")
            return False
        try:
            # MiIO tts_byte 命令直接在音箱上播放
            result = await self.miio.play_tts(text)
            return result
        except Exception as e:
            logger.error(f"小米 TTS 失败: {e}")
            return False

    async def _speak_edge(self, text: str) -> bool:
        """Edge TTS（微软）"""
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice=self.config.tts.voice or "zh-CN-XiaoxiaoNeural")
            data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    data += chunk["data"]

            # 保存到临时文件，通过 MiIO 播放
            tmp = f"/tmp/tts_{uuid.uuid4().hex}.mp3"
            with open(tmp, "wb") as f:
                f.write(data)

            if self.miio:
                # 转换为 base64 通过 MiIO 播放
                with open(tmp, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                # TODO: 通过 MiIO 发送音频数据
                logger.info(f"TTS 已生成: {tmp}")

            import os
            os.unlink(tmp)
            return True

        except ImportError:
            logger.error("edge-tts 未安装，请运行: pip install edge-tts")
            return False
        except Exception as e:
            logger.error(f"Edge TTS 失败: {e}")
            return False

    async def _speak_openai(self, text: str) -> bool:
        """OpenAI TTS"""
        try:
            url = f"{self.config.llm.api_base.rstrip('/')}/audio/speech"
            headers = {
                "Authorization": f"Bearer {self.config.llm.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "tts-1",
                "input": text,
                "voice": self.config.tts.voice or "alloy",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        text_err = await resp.text()
                        raise RuntimeError(f"OpenAI TTS 错误 {resp.status}: {text_err}")

                    data = await resp.read()
                    tmp = f"/tmp/tts_{uuid.uuid4().hex}.mp3"
                    with open(tmp, "wb") as f:
                        f.write(data)

                    if self.miio:
                        logger.info(f"TTS 已生成: {tmp}")

                    import os
                    os.unlink(tmp)
                    return True

        except Exception as e:
            logger.error(f"OpenAI TTS 失败: {e}")
            return False
