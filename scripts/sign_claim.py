"""Sign a /claim message — fallback path for zero-cost wallets.

Primary claim path (no terminal needed): the bot asks for a tiny USDC
fee transfer; see src/mandate/transfer_claim.py. This script is the
signature fallback:

1. The bot prints the exact EIP-191 message in chat — paste it into a file.
2. Run with the wallet key in env (never as an argv flag):

       export LIVE_KEY=<key>
       .venv/bin/python scripts/sign_claim.py message.txt

   It prints ONE line: `/claim <wallet> <sig>` — paste that back into chat.
3. Or sign the same message in MetaMask via docs/sign.html (static page,
   no server) and paste the resulting /claim line back into chat.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mandate.claims import sign_message  # noqa: E402

CLAIM_FILE = Path(".claim_message.txt")
WALLET_LINE = "wallet:"


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
                "usage: .venv/bin/python scripts/sign_claim.py message.txt "
                "(paste the exact claim message the bot printed into message.txt first)"
            )
        message = Path(CLAIM_FILE).read_text().strip()

    wallet = _wallet_from_message(message)
    sig = sign_message(message, key)
    print(f"/claim {wallet} {sig}")


if __name__ == "__main__":
    main()
