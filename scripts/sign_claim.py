"""Sign a /claim message off-camera for the live demo take.

The bot prints the exact EIP-191 message in chat. Paste it into a file,
then run with the burner key in env (never as an argv flag):

    export LIVE_KEY=<burner key, off camera>
    .venv/bin/python scripts/sign_claim.py message.txt
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mandate.claims import sign_message  # noqa: E402


def main() -> None:
    key = os.environ.get("LIVE_KEY", "")
    if not key:
        raise SystemExit("LIVE_KEY not set")
    message = Path(sys.argv[1]).read_text().strip()
    print(sign_message(message, key))


if __name__ == "__main__":
    main()
