"""Sign a /claim message — one command, prints a paste-ready line.

Two ways to use it:

1. EASY MODE (recommended): run the demo bot via scripts/run_demo_bot.py,
   send /claim <wallet> in Telegram, then just run:

       export LIVE_KEY=<burner key, from seed_demo.py output>
       .venv/bin/python scripts/sign_claim.py

   It reads the claim message the bot just sent (.claim_message.txt) and
   prints ONE line — copy-paste that line into Telegram. Done.

2. OLD MODE: paste the exact claim message into a file, then
   .venv/bin/python scripts/sign_claim.py message.txt
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mandate.claims import sign_message  # noqa: E402

CLAIM_FILE = Path(".claim_message.txt")
WALLET_LINE = "wallet:"


def _extract_message(raw: str) -> str:
    """Bot replies embed the claim message after the 'then:' line."""
    marker = "then:"
    if marker in raw:
        raw = raw.split(marker, 1)[1]
    return raw.strip()


def _wallet_from_message(message: str) -> str:
    for line in message.splitlines():
        if line.startswith(WALLET_LINE):
            return line.split(":", 1)[1].strip()
    raise SystemExit("claim message has no wallet line — wrong file?")


def main() -> None:
    key = os.environ.get("LIVE_KEY", "")
    if not key:
        raise SystemExit("LIVE_KEY not set — export LIVE_KEY=<burner key> first")

    if len(sys.argv) > 1:
        message = Path(sys.argv[1]).read_text().strip()
    else:
        if not CLAIM_FILE.exists():
            raise SystemExit(
                f"{CLAIM_FILE} not found — send /claim <wallet> in Telegram first "
                "(the demo bot saves the message automatically)."
            )
        message = _extract_message(CLAIM_FILE.read_text())

    wallet = _wallet_from_message(message)
    sig = sign_message(message, key)
    print(f"/claim {wallet} {sig}")


if __name__ == "__main__":
    main()
