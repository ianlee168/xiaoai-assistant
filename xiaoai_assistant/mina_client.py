"""MiNA API 客户端 - 通过 MiNA 云端 API 获取音箱音频"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable

import aiohttp

from xiaoai_assistant.cookie_utils import parse_cookie_string

logger = logging.getLogger(__name__)

LATEST_ASK_API = (
    "https://userprofile.mina.mi.com/device_profile/v2/conversation"
    "?source=dialogu&hardware={hardware}&timestamp={timestamp}&limit=2"
)

COOKIE_TEMPLATE = (
    "deviceId={device_id}; serviceToken={service_token}; userId={user_id}"
)


class MiNAService:
    """MiNA API 服务"""

    def __init__(self, account, session: aiohttp.ClientSession):
        self.account = account
        self.session = session

    async def device_list(self) -> list[dict]:
        """获取设备列表"""
        url = "https://api.io.mi.com/app/miougateway/user/user_device_list"
        headers = await self._headers()
        resp = await self.session.get(url, headers=headers, ssl=False)
        data = await resp.json()
        if data.get("code") != 0:
            logger.error(f"device_list failed: {data}")
            return []
        return data.get("result", {}).get("devices", [])

    async def conversation_history(
        self, hardware: str, timestamp: int | None = None, limit: int = 2
    ) -> dict:
        """获取音箱对话记录（关键 API）"""
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        url = LATEST_ASK_API.format(hardware=hardware, timestamp=timestamp)
        headers = await self._headers(cookie=self._make_cookie())
        resp = await self.session.get(url, headers=headers, ssl=False)
        data = await resp.json()
        logger.debug(f"conversation_history: {data}")
        return data

    def _make_cookie(self) -> str:
        """从 token 文件构造 cookie"""
        with open(self.account.token_path) as f:
            user_data = json.loads(f.read())
        user_id = user_data.get("userId")
        service_token = user_data.get("micoapi")[1]
        device_id = self.account.device_id
        return COOKIE_TEMPLATE.format(
            device_id=device_id,
            service_token=service_token,
            user_id=user_id
        )

    async def _headers(self, cookie: str = "") -> dict:
        if not cookie:
            cookie = self._make_cookie()
        return {
            "Cookie": cookie,
            "User-Agent": "Android 12; Xiaomi M2004jaday Build/SKQ1",
            "Content-Type": "application/x-www-form-urlencoded",
        }


class MiAccount:
    """小米账号"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        token_path: str,
    ):
        self.session = session
        self.username = username
        self.password = password
        self.token_path = token_path
        self.device_id = ""
        self.user_id: str | None = None
        self.service_token: str | None = None

    async def login(self, service: str = "micoapi") -> None:
        """登录小米账号"""
        import hashlib

        import json

        url = "https://api.io.mi.com/app/pass/user/login"
        nonce = str(int(time.time() * 1000))
        sign_str = f"{self.password}{nonce}"
        signature = hashlib.sha256(sign_str.encode()).hexdigest()

        data = {
            "countryCode": "CN",
            "deviceId": f"device_{self.username}",
            "encryptedPwd": signature,
            "locale": "zh_CN",
            "loginSource": "miniapp",
            "serviceToken": "",
            "timestamp": nonce,
            "user": self.username,
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Android 12; Xiaomi M2004jaday Build/SKQ1",
        }

        resp = await self.session.post(url, json=data, headers=headers, ssl=False)
        result = await resp.json()

        if result.get("code") != 0:
            # 尝试备用登录
            await self._login_v2(service)
            return

        result_data = result.get("result", {})
        self.user_id = result_data.get("userId")
        self.service_token = result_data.get("serviceToken", {}).get(service)
        self._save_token(result_data, service)

    async def _login_v2(self, service: str) -> None:
        """备用登录 v2"""
        import hashlib

        url = "https://account.xiaomi.com/pass/serviceLogin"
        nonce = str(int(time.time() * 1000))
        sign_str = f"{self.password}{nonce}"
        signature = hashlib.sha256(sign_str.encode()).hexdigest()

        data = {
            "user": self.username,
            "hash": signature.upper(),
            "Sid": service,
            "callback": "https://api.io.mi.com/",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0",
        }

        resp = await self.session.post(url, data=data, headers=headers, ssl=False)
        text = await resp.text()

        # 提取 token
        import re
        match = re.search(r"serviceToken=([^&]+)", text)
        if match:
            self.service_token = match.group(1)

        if self.user_id and self.service_token:
            self._save_token({"userId": self.user_id, service: [None, self.service_token]}, service)

    def _save_token(self, result: dict, service: str) -> None:
        """保存 token"""
        import json
        import os

        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        with open(self.token_path, "w") as f:
            json.dump(result, f)


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
        self.account = MiAccount(
            session,
            config.speaker.account,
            config.speaker.password,
            config.speaker.mi_token_path,
        )
        self.mina_service = MiNAService(self.account, session)
        self.last_timestamp = int(time.time() * 1000)
        self.device_id = ""
        self._running = False

    async def init(self) -> bool:
        """初始化并登录"""
        try:
            await self.account.login("micoapi")
            devices = await self.mina_service.device_list()
            if not devices:
                logger.warning("未找到设备")
                return False

            # 查找对应 hardware 的设备
            for d in devices:
                if d.get("miotDID", "") == str(self.config.speaker.mi_did):
                    self.device_id = d.get("deviceID", "")
                    break
                if d.get("hardware", "") == self.config.speaker.hardware:
                    self.device_id = d.get("deviceID", "")
                    break

            if not self.device_id:
                # 尝试 miio 查
                try:
                    from miservice import MiIOService
                    miio = MiIOService(self.account)
                    miio_devs = await miio.device_list()
                    for d in miio_devs:
                        if d.get("model", "").endswith(self.config.speaker.hardware.lower()):
                            self.config.speaker.mi_did = d.get("did", "")
                            break
                except Exception as e:
                    logger.warning(f"miio device_list failed: {e}")

            logger.info(
                f"MiNA 初始化完成: hardware={self.config.speaker.hardware}, "
                f"mi_did={self.config.speaker.mi_did}, device_id={self.device_id}"
            )
            return True

        except Exception as e:
            logger.error(f"MiNA 初始化失败: {e}")
            return False

    def is_supported(self) -> bool:
        """检查当前硬件是否被支持"""
        return self.config.speaker.hardware in self.SUPPORTED_HARDWARE

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
                result = await self.mina_service.conversation_history(
                    self.config.speaker.hardware,
                    self.last_timestamp,
                )

                info = result.get("info", "{}")
                if isinstance(info, str):
                    info_data = json.loads(info) if info != "{}" else {}
                else:
                    info_data = info

                records = info_data.get("records", [])
                if records:
                    for record in records:
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
