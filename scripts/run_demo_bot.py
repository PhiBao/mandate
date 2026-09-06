"""Run the demo bot locally with a claim-signing assistant.

Like running `python -m mandate.main`, but when the bot sends a
"sign this exact message" reply, the exact message is ALSO saved to
`.claim_message.txt` in the repo root. Then signing a claim is:

    export LIVE_KEY=<burner key>          # from seed_demo.py output
    .venv/bin/python scripts/sign_claim.py   # prints one paste-ready line

Paste that single line back into Telegram. No manual copying of the
claim message, no editing files.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mandate.bot import MandateBot  # noqa: E402
from mandate.config import Settings  # noqa: E402
from mandate.main import PollingRunner  # noqa: E402  (re-exported path)
from mandate.memory import MandateMemory  # noqa: E402
from mandate.telegram import TelegramTransport, parse_update  # noqa: E402

CLAIM_FILE = Path(".claim_message.txt")
MARKER = "Sign this exact message"


class DemoTransport(TelegramTransport):
    """Saves claim-signing instructions to disk when the bot sends them."""

    def send(self, chat_id: str, text: str) -> None:
        if MARKER in text and text.count("\n") >= 8:
            message_part = text.split(f"{MARKER} with the wallet's private key, then:\n", 1)[-1]
            CLAIM_FILE.write_text(message_part)
            print("\n" + "=" * 62)
            print(f" CLAIM MESSAGE SAVED -> {CLAIM_FILE}")
            print(" Now sign it (off camera or on camera, your choice):")
            print(f"   export LIVE_KEY=<burner key>")
            print(f"   .venv/bin/python scripts/sign_claim.py")
            print(" Paste the printed line back into Telegram. That's it.")
            print("=" * 62 + "\n")
        super().send(chat_id, text)


async def run() -> None:
    settings = Settings.from_env()
    token = settings.require_telegram()
    mem = MandateMemory(settings.db_path)
    treasury = os.environ.get("MANDATE_CLAIM_TREASURY", "0x4Ba1e9e275EF61B56C99532D0066506436201D73")
    bot = MandateBot(mem, DemoTransport(token), claim_treasury=treasury)
    runner = PollingRunner(bot, DemoTransport(token))
    print(f"Demo bot polling — db={settings.db_path} (claim assistant active)")
    while True:
        try:
            await runner.run_once()
        except Exception as exc:
            print(f"poll error: {exc}")
            await asyncio.sleep(2.0)


if __name__ == "__main__":
    asyncio.run(run())
