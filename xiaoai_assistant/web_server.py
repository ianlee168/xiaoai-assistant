"""Web API Server - 让 X8S 等新款音箱通过 HTTP 触发对话"""
from __future__ import annotations

import asyncio
import logging
from aiohttp import web

from xiaoai_assistant.bot import Bot

logger = logging.getLogger(__name__)


class WebServer:
    """Web API 服务器

    用途：适合 X8S 等不支持 MiNA 音频上传的音箱。
    用户通过 HTTP POST 请求发送文本，服务器处理后通过音箱播放 TTS。

    API 端点：
    - POST /chat          - 发送对话，返回 AI 回复
    - POST /chat/stream   - 流式对话
    - POST /tts           - 直接 TTS 播报
    - GET  /health        - 健康检查
    - GET  /status        - 状态信息
    """

    def __init__(self, bot: Bot, host: str = "0.0.0.0", port: int = 8000):
        self.bot = bot
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self) -> None:
        self.app.router.add_post("/chat", self.handle_chat)
        self.app.router.add_post("/chat/stream", self.handle_chat_stream)
        self.app.router.add_post("/tts", self.handle_tts)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/status", self.handle_status)

    async def handle_chat(self, request: web.Request) -> web.Response:
        """POST /chat - 发送对话，返回 AI 回复并播报 TTS

        Body: {"text": "今天天气怎么样？"}
        Response: {"reply": "今天北京晴，温度15-25度...", "success": true}
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        text = data.get("text", "").strip()
        if not text:
            return web.json_response({"error": "text is required"}, status=400)

        try:
            reply = await self.bot.run_round(text, force_llm=True)
            return web.json_response({
                "reply": reply or "",
                "success": True,
            })
        except Exception as e:
            logger.error(f"chat error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_chat_stream(self, request: web.Request) -> web.Response:
        """POST /chat/stream - 流式对话

        Body: {"text": "你好"}
        Response: text/event-stream
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        text = data.get("text", "").strip()
        if not text:
            return web.json_response({"error": "text is required"}, status=400)

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
        await response.prepare(request)

        try:
            # 流式 LLM
            from xiaoai_assistant.llm_client import LLMClient
            llm = LLMClient(self.bot.config)
            messages = [
                {"role": "system", "content": self.bot.config.prompt},
                {"role": "user", "content": text}
            ]

            collected = ""
            async for chunk in await llm.chat(messages, stream=True):
                collected += chunk
                await response.write(f"data: {chunk}\n\n".encode())

            await response.write(b"data: [DONE]\n\n")

            # TTS 播报
            if collected and self.bot.tts:
                asyncio.create_task(self.bot.tts.speak(collected))

            await response.write_eof()
            return response

        except Exception as e:
            logger.error(f"stream error: {e}")
            await response.write(f"data: error: {e}\n\n".encode())
            await response.write_eof()
            return response

    async def handle_tts(self, request: web.Request) -> web.Response:
        """POST /tts - 直接 TTS 播报

        Body: {"text": "你好，我是小爱助手"}
        Response: {"success": true}
        """
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)

        text = data.get("text", "").strip()
        if not text:
            return web.json_response({"error": "text is required"}, status=400)

        try:
            await self.bot.speak_and_play(text)
            return web.json_response({"success": True})
        except Exception as e:
            logger.error(f"tts error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_health(self, request: web.Request) -> web.Response:
        """GET /health - 健康检查"""
        return web.json_response({"status": "ok"})

    async def handle_status(self, request: web.Request) -> web.Response:
        """GET /status - 状态信息"""
        return web.json_response({
            "mode": self.bot.config.input_mode,
            "llm": self.bot.config.llm.provider,
            "tts": self.bot.config.tts.provider,
            "speaker": self.bot.config.speaker.hardware,
            "in_conversation": self.bot.in_conversation,
        })

    async def start(self) -> None:
        """启动服务器"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"Web API 服务器已启动: http://{self.host}:{self.port}")
        logger.info("端点:")
        logger.info("  POST /chat        - 发送对话")
        logger.info("  POST /chat/stream - 流式对话")
        logger.info("  POST /tts         - 直接 TTS 播报")
        logger.info("  GET  /health      - 健康检查")
        logger.info("  GET  /status      - 状态信息")

    async def run_forever(self) -> None:
        """运行服务器直到 Ctrl+C"""
        await self.start()
        try:
            await asyncio.Event().wait()  # 永远等待
        except asyncio.CancelledError:
            pass


async def create_web_server(bot: Bot, host: str = "0.0.0.0", port: int = 8000) -> WebServer:
    """创建并启动 Web 服务器"""
    server = WebServer(bot, host, port)
    return server
