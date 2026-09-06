"""Add the real demo wallet (kiter9's claim + real Hyperliquid positions)
to an existing demo DB, mirroring the live Fly record.

Run AFTER scripts/seed_demo.py:

    .venv/bin/python scripts/seed_real_wallet.py --db demo.db \
        --group <CHAT_ID> --user kiter9 --user-id <TG_ID> \
        --wallet 0x4ba1e9e275EF61B56C99532D0066506436201D73 \
        --claimed-at 2026-09-05T02:16:59.602659+00:00

The claim timestamp and positions are real (public Hyperliquid fills API,
forward-only since the claim), so the local demo card for this member is
the live product record, not mock data.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mandate.claims import build_claim_message, claim_digest, new_nonce  # noqa: E402
from mandate.evidence.hyperliquid_free import HyperliquidFreeAdapter  # noqa: E402
from mandate.memory import MandateMemory, group_tenant  # noqa: E402
from mandate.records import Claim  # noqa: E402
from mandate.verdicts import VerdictService  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--wallet", required=True)
    ap.add_argument("--claimed-at", required=True)
    args = ap.parse_args()

    mem = MandateMemory(args.db)
    svc = VerdictService(mem)
    wallet = args.wallet.lower()

    msg = build_claim_message("hyperliquid", wallet, args.group, args.user_id, new_nonce(), args.claimed_at)
    mem.record_claim(Claim(
        chain="hyperliquid", wallet=wallet, group_id=args.group, user_id=args.user_id,
        nonce="seed-real", message=msg, message_hash=claim_digest(msg),
        signature="0x00-seed-real", claimed_at=args.claimed_at,
    ))
    mem.client.set_tenant(group_tenant(args.group))
    mem.client.set_entity("member_map", args.user, {"user_id": args.user_id})

    adapter = HyperliquidFreeAdapter(mem=None)
    batch = asyncio.run(adapter.fetch_closed_positions(wallet, since_iso=args.claimed_at))
    added = svc.ingest("hyperliquid", wallet, batch.positions)
    ev = svc.evaluate_trader("hyperliquid", wallet, risk_screen="pass", seed=42)
    print(f"real wallet {wallet}")
    print(f"  positions fetched={len(batch.positions)} ingested={added} "
          f"n={ev.verdict.n_trades} distinguishable={ev.verdict.distinguishable} tier={ev.tier.value}")
    print("real member seeded OK")


if __name__ == "__main__":
    main()
