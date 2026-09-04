from __future__ import annotations

import asyncio
import os
import signal

from .bot import MandateBot
from .config import Settings
from .memory import MandateMemory


async def run() -> None:
    settings = Settings.from_env()
    token = settings.require_telegram()
    mem = MandateMemory(settings.db_path)

    from .telegram import TelegramTransport, PollingRunner

    transport = TelegramTransport(token)
    bot = MandateBot(mem, transport)
    runner = PollingRunner(bot, transport)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    print(f"Mandate polling — db={settings.db_path}")
    while not stop.is_set():
        try:
            await asyncio.wait_for(runner.run_once(), timeout=30.0)
        except asyncio.TimeoutError:
            continue
        except Exception as exc:
            print(f"poll error: {exc}")
            await asyncio.sleep(2.0)

    await transport.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
