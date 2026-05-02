"""MiIO 协议客户端 - 本地控制小爱音箱（播放 TTS/执行命令）"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from miservice import MiAccount
    from xiaoai_assistant.config import Config

logger = logging.getLogger(__name__)

# MiIO 命令映射
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
    "X8S": {"tts": "5-1", "wakeup": "5-5"},
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

    def __init__(self, config: "Config"):
        self.config = config
        self.account: "MiAccount | None" = None

    async def play_tts(self, text: str) -> bool:
        """让音箱播放 TTS

        Args:
            text: 要播放的文本

        Returns:
            True 成功，False 失败
        """
        if not self.account:
            logger.warning("MiIO 未登录，跳过 TTS")
            return False

        try:
            from miservice import MiIOService

            miio = MiIOService(self.account)
            hw = self.config.speaker.hardware
            cmd = MIIO_COMMANDS.get(hw, DEFAULT_COMMANDS)

            await miio.tts_byte(
                self.config.speaker.mi_did,
                text,
                cmd["tts"]
            )
            logger.debug(f"TTS 播放成功: {text[:30]}...")
            return True

        except Exception as e:
            logger.error(f"TTS 播放失败: {e}")
            return False

    async def stop(self) -> bool:
        """停止音箱当前播放"""
        if not self.account:
            return False
        try:
            from miservice import MiIOService
            miio = MiIOService(self.account)
            await miio.miio_command(
                self.config.speaker.mi_did,
                "app_control",
                {"action": "stop"}
            )
            return True
        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            return False
