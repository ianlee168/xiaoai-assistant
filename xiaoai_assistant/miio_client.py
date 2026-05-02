"""MiIO 协议客户端 - 本地控制小爱音箱（播放 TTS/执行命令）"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)

# MiIO 命令映射（HARDWARE_COMMAND_DICT）
MIIO_COMMANDS = {
    "LX06": {"tts": "5-1", "wakeup": "5-5"},
    "S12": {"tts": "5-1", "wakeup": "5-5"},
    "S12A": {"tts": "5-1", "wakeup": "5-5"},
    "LX01": {"tts": "5-1", "wakeup": "5-5"},
    "LX04": {"tts": "5-1", "wakeup": "5-4"},
    "L06A": {"tts": "5-1", "wakeup": "5-5"},
    "L05B": {"tts": "5-3", "wakeup": "5-4"},
    "L05C": {"tts": "5-3", "wakeup": "5-4"},
    "L07A": {"tts": "5-1", "wakeup": "5-5"},
    "L15A": {"tts": "7-3", "wakeup": "7-4"},
    "L17A": {"tts": "7-3", "wakeup": "7-4"},
    "X08E": {"tts": "7-3", "wakeup": "7-4"},
    "X6A": {"tts": "7-3", "wakeup": "7-4"},
    "X10A": {"tts": "7-3", "wakeup": "7-4"},
    "LX05A": {"tts": "5-1", "wakeup": "5-5"},
    "X8S": {"tts": "5-1", "wakeup": "5-5"},  # X8S 支持 MiIO 命令
}

DEFAULT_COMMANDS = {"tts": "5-1", "wakeup": "5-5"}


class MiIOClient:
    """MiIO 客户端 - 通过 MiIO 协议向音箱发送命令

    用途：
    - 播放 TTS 语音
    - 停止当前播放
    - 获取播放状态

    注意：MiIO 是"单向"的，只能发送命令到音箱，
    不能从音箱获取音频数据（那是 MiNA 的工作）。
    """

    def __init__(self, config, session: asyncio.ClientSession | None = None):
        self.config = config
        self.session = session
        self.account = None  # 初始化时注入

    async def play_tts(self, text: str) -> bool:
        """让音箱播放 TTS

        Args:
            text: 要播放的文本

        Returns:
            True 成功，False 失败
        """
        try:
            # 使用 miservice 的 miio_command
            from miservice import miio_command

            hw = self.config.speaker.hardware
            cmd = MIIO_COMMANDS.get(hw, DEFAULT_COMMANDS)
            tts_cmd = cmd["tts"]

            # 构造 TTS 命令
            # 使用 tts_byte 接口
            result = await self._send_miio_command(
                "tts_byte",
                {"text": text}
            )
            logger.debug(f"TTS 播放结果: {result}")
            return True

        except Exception as e:
            logger.error(f"TTS 播放失败: {e}")
            return False

    async def stop(self) -> bool:
        """停止音箱当前播放"""
        try:
            result = await self._send_miio_command("stop", {})
            return True
        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            return False

    async def process_mibrain_info(self) -> str | None:
        """查询音箱当前播放状态

        Returns:
            播放状态，如 "rAUDIOPLAYER_STATE: PLAYING"
        """
        try:
            result = await self._send_miio_command("process_mibrain_info", {})
            if result:
                logger.debug(f"mibrain_info: {result}")
                return str(result)
            return None
        except Exception as e:
            logger.error(f"mibrain_info 查询失败: {e}")
            return None

    async def _send_miio_command(self, command: str, params: dict) -> dict | None:
        """通过 MiIO 发送命令"""
        if self.account is None:
            logger.error("account 未初始化")
            return None

        try:
            from miservice import MiIOService
            miio = MiIOService(self.account)

            hw = self.config.speaker.hardware
            cmd = MIIO_COMMANDS.get(hw, DEFAULT_COMMANDS)

            if command == "tts_byte":
                return await miio.tts_byte(
                    self.config.speaker.mi_did,
                    params.get("text", ""),
                    cmd["tts"]
                )
            elif command == "stop":
                return await miio.miio_command(
                    self.config.speaker.mi_did,
                    "app_control",
                    {"action": "stop"}
                )
            elif command == "process_mibrain_info":
                return await miio.miio_command(
                    self.config.speaker.mi_did,
                    "process_mibrain_info",
                    {}
                )

        except Exception as e:
            logger.error(f"MiIO 命令 {command} 失败: {e}")
            return None
