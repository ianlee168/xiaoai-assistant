"""MiNA API 客户端 - 通过 MiNA 云端 API 获取音箱音频

直接复用 miservice-fork 库的 MiAccount 和 MiNAService。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable

import aiohttp
from miservice import MiAccount, MiNAService

logger = logging.getLogger(__name__)

LATEST_ASK_API = (
    "https://userprofile.mina.mi.com/device_profile/v2/conversation"
    "?source=dialogu&hardware={hardware}&timestamp={timestamp}&limit=2"
)


class MiNAClient:
    """MiNA 轮询客户端 - 适合 LX06/S12 等老款音箱

    X8S 等新款音箱使用 ai_protocol_3_0，音频数据不上传 MiNA API，
    因此这类音箱无法使用此客户端。
    """

    SUPPORTED_HARDWARE = {
        "LX06", "S12", "S12A", "LX01", "LX04",
        "L06A", "L05B", "L05C", "L07A", "L15A",
        "LX05A", "L17A", "X08E", "X6A", "X10A",
    }

    def __init__(self, config, session: aiohttp.ClientSession):
        self.config = config
        self.session = session
        self._account: MiAccount | None = None
        self._mina_service: MiNAService | None = None
        self.last_timestamp = int(time.time() * 1000)
        self._running = False

    async def init(self) -> bool:
        """初始化并登录"""
        try:
            self._account = MiAccount(
                self.session,
                self.config.speaker.account,
                self.config.speaker.password,
                self.config.speaker.mi_token_path,
            )
            await self._account.login("micoapi")
            self._mina_service = MiNAService(self._account)

            # 获取设备列表，查找对应 hardware
            devices = await self._mina_service.device_list()
            if not devices:
                logger.warning("未找到设备")
                return False

            device_id = ""
            for d in devices:
                if str(self.config.speaker.mi_did) and d.get("miotDID", "") == str(self.config.speaker.mi_did):
                    device_id = d.get("deviceID", "")
                    break
                if d.get("hardware", "") == self.config.speaker.hardware:
                    device_id = d.get("deviceID", "")
                    if not self.config.speaker.mi_did:
                        self.config.speaker.mi_did = d.get("miotDID", "")
                    break

            # 设置 device_id 到 account（供 MiIO 使用）
            self._account.device_id = device_id

            logger.info(
                f"MiNA 初始化完成: hardware={self.config.speaker.hardware}, "
                f"mi_did={self.config.speaker.mi_did}, device_id={device_id}"
            )
            return True

        except Exception as e:
            logger.error(f"MiNA 初始化失败: {e}")
            return False

    @property
    def account(self) -> MiAccount:
        """返回已登录的账号（供 MiIO 客户端使用）"""
        if not self._account:
            raise RuntimeError("MiNA 客户端未初始化，请先调用 init()")
        return self._account

    @property
    def mina_service(self) -> MiNAService:
        if not self._mina_service:
            raise RuntimeError("MiNA 服务未初始化")
        return self._mina_service

    def is_supported(self) -> bool:
        """检查当前硬件是否被支持"""
        return self.config.speaker.hardware in self.SUPPORTED_HARDWARE

    async def get_latest_ask(self) -> dict | None:
        """获取最新的音箱对话记录"""
        if not self._mina_service:
            return None
        try:
            result = await self._mina_service.nlp_result_get(
                self.config.speaker.mi_did
            )
            info = result.get("info", "{}")
            if isinstance(info, str):
                info_data = json.loads(info) if info and info != "{}" else {}
            else:
                info_data = info
            records = info_data.get("records", [])
            if records:
                return records[0]
            return None
        except Exception as e:
            logger.debug(f"get_latest_ask: {e}")
            return None

    async def poll(self, callback: Callable[[dict], None]) -> None:
        """轮询 MiNA API，检测用户语音输入

        适合设备：LX06、S12、S12A 等老款音箱（无 ai_protocol_3_0）
        不适合设备：X8S（新款，ai_protocol_3_0 音频不上传）
        """
        if not self.is_supported():
            logger.warning(
                f"硬件 {self.config.speaker.hardware} 不在 MiNA 支持列表中，"
                "可能无法获取音频数据"
            )

        self._running = True
        while self._running:
            try:
                record = await self.get_latest_ask()
                if record:
                    ts = record.get("time", 0)
                    if ts > self.last_timestamp:
                        self.last_timestamp = ts
                    logger.debug(f"收到记录: {record}")
                    callback(record)

                await asyncio.sleep(3)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"poll error: {e}")
                await asyncio.sleep(5)

    def stop(self) -> None:
        """停止轮询"""
        self._running = False
