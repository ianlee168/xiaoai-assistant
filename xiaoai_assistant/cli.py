"""CLI 入口点"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from xiaoai_assistant.bot import Bot
from xiaoai_assistant.config import Config
from xiaoai_assistant.mina_client import MiNAClient
from xiaoai_assistant.miio_client import MiIOClient

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="小爱音箱 AI 助手")
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=str(Path.home() / ".xiaoai" / "config.yaml"),
        help="配置文件路径"
    )
    parser.add_argument(
        "--input-mode", "-m",
        choices=["mina", "miio", "web", "cli"],
        default=None,
        help="输入模式"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="调试模式"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="详细输出"
    )
    parser.add_argument(
        "--test-llm",
        metavar="TEXT",
        help="测试 LLM（不启动音箱循环）"
    )
    parser.add_argument(
        "--test-tts",
        metavar="TEXT",
        help="测试 TTS 播报"
    )
    args = parser.parse_args()

    # 加载配置
    config_path = Path(args.config)
    if config_path.exists():
        config = Config.from_yaml(config_path)
    else:
        print(f"配置文件不存在: {config_path}")
        print("使用默认配置...")
        config = Config()

    # 命令行覆盖
    config.verbose = args.verbose > 0 or args.debug or config.verbose
    config.debug = args.debug or config.debug
    if args.input_mode:
        config.input_mode = args.input_mode

    # 环境变量
    config.update_from_env()

    # 设置日志
    logging.basicConfig(
        level=logging.DEBUG if config.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # 测试模式
    if args.test_llm:
        asyncio.run(test_llm(config, args.test_llm))
        return

    if args.test_tts:
        asyncio.run(test_tts(config, args.test_tts))
        return

    # 正常启动
    asyncio.run(run(config))


async def test_llm(config: Config, text: str):
    """测试 LLM"""
    from xiaoai_assistant.llm_client import LLMClient
    llm = LLMClient(config)
    messages = [
        {"role": "system", "content": config.prompt},
        {"role": "user", "content": text}
    ]
    print(f"发送: {text}")
    reply = await llm.chat(messages)
    print(f"回复: {reply}")
    await llm.close()


async def test_tts(config: Config, text: str):
    """测试 TTS"""
    from xiaoai_assistant.tts_client import TTSClient
    tts = TTSClient(config)
    print(f"播报: {text}")
    await tts.speak(text)


async def run(config: Config):
    """主运行逻辑"""
    bot = Bot(config)

    # 根据输入模式初始化
    if config.input_mode == "mina":
        await run_mina(config, bot)
    elif config.input_mode == "web":
        await run_web(config, bot)
    elif config.input_mode == "cli":
        await run_cli(config, bot)
    else:
        print(f"未知输入模式: {config.input_mode}")
        sys.exit(1)


async def run_mina(config: Config, bot: Bot):
    """MiNA 轮询模式"""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        mina_client = MiNAClient(config, session)
        miio_client = MiIOClient(config)

        bot.set_mina(mina_client)
        bot.set_miio(miio_client)

        # 注入 account
        miio_client.account = mina_client.account

        try:
            await bot.run_mina_loop()
        except KeyboardInterrupt:
            logger.info("收到退出信号")
            mina_client.stop()
        finally:
            await bot.close()


async def run_web(config: Config, bot: Bot):
    """Web API 模式 - 启动 HTTP 服务器"""
    import aiohttp
    from xiaoai_assistant.web_server import create_web_server

    async with aiohttp.ClientSession() as session:
        # 初始化 MiIO
        miio_client = MiIOClient(config)
        from xiaoai_assistant.mina_client import MiAccount
        account = MiAccount(
            session,
            config.speaker.account,
            config.speaker.password,
            config.speaker.mi_token_path,
        )
        try:
            await account.login("micoapi")
            miio_client.account = account
        except Exception as e:
            logger.warning(f"MiNA 登录失败（TTS 可能无法使用）: {e}")

        bot.set_miio(miio_client)

        # 启动 Web 服务器
        server = await create_web_server(bot, host="0.0.0.0", port=8000)
        await server.run_forever()

        await bot.close()


async def run_cli(config: Config, bot: Bot):
    """CLI 对话模式"""
    import aiohttp

    async with aiohttp.ClientSession() as session:
        # 初始化 MiIO
        miio_client = MiIOClient(config)

        # 尝试登录以获取 account
        from xiaoai_assistant.mina_client import MiAccount
        account = MiAccount(
            session,
            config.speaker.account,
            config.speaker.password,
            config.speaker.mi_token_path,
        )
        try:
            await account.login("micoapi")
            miio_client.account = account
        except Exception as e:
            logger.warning(f"登录失败: {e}")

        bot.set_miio(miio_client)

        print("=" * 50)
        print("小爱音箱 AI 助手（CLI 模式）")
        print("输入文本测试，Ctrl+C 退出")
        print("=" * 50)

        while True:
            try:
                user_input = input("\n你说: ").strip()
                if not user_input:
                    continue
                reply = await bot.run_round(user_input)
                if reply:
                    print(f"AI 回复: {reply}")
                else:
                    print("（无回复）")
            except KeyboardInterrupt:
                print("\n退出")
                break

        await bot.close()
