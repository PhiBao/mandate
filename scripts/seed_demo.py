"""Seed a demo Telegram group DB with two members.

Veteran  -> skilled mock record  -> CREDIBLE card
Rookie   -> lucky mock record    -> OBSERVED ("not distinguishable from luck")

Claim timestamps predate every ingested position close, so the seeded
record is forward-only consistent. Mock fills are the declared demo
evidence path (Omni returns 500); the live-claim take on camera uses a
real EIP-191 signature with the printed burner key.

Usage:
    .venv/bin/python scripts/seed_demo.py --db demo.db --group <chat_id> \\
        --veteran-user alice --veteran-id <tg_id> \\
        --rookie-user bob --rookie-id <tg_id>

Find numeric Telegram IDs via:
    curl 'https://api.telegram.org/bot$TOKEN/getUpdates'  (after members say hi)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from eth_account import Account  # noqa: E402

from mandate.claims import build_claim_message, claim_digest, new_nonce  # noqa: E402
from mandate.evidence.mock import MockHyperliquidSource  # noqa: E402
from mandate.memory import MandateMemory, group_tenant  # noqa: E402
from mandate.records import Claim  # noqa: E402
from mandate.verdicts import VerdictService  # noqa: E402


def _seed_member(mem, svc, group, username, user_id, wallet, claim_days_ago,
                 start_days_ago, mean, sd, n, seed):
    claimed_at = (datetime.now(timezone.utc) - timedelta(days=claim_days_ago)).isoformat()
    start = datetime.now(timezone.utc) - timedelta(days=start_days_ago)
    msg = build_claim_message("hyperliquid", wallet, group, user_id, new_nonce(), claimed_at)
    mem.record_claim(Claim(
        chain="hyperliquid", wallet=wallet.lower(), group_id=group, user_id=user_id,
        nonce="seed", message=msg, message_hash=claim_digest(msg),
        signature="0x00-seed", claimed_at=claimed_at,
    ))
    mem.client.set_tenant(group_tenant(group))
    mem.client.set_entity("member_map", username, {"user_id": user_id})
    positions = MockHyperliquidSource(
        wallet, mean=mean, sd=sd, n=n, seed=seed, start=start).fetch_closed_positions()
    added = svc.ingest("hyperliquid", wallet, positions)
    ev = svc.evaluate_trader("hyperliquid", wallet, risk_screen="pass", seed=42)
    return added, ev


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--veteran-user", required=True)
    ap.add_argument("--veteran-id", required=True)
    ap.add_argument("--rookie-user", required=True)
    ap.add_argument("--rookie-id", required=True)
    args = ap.parse_args()

    mem = MandateMemory(args.db)
    svc = VerdictService(mem)

    vet_wallet = Account.create().address
    added_v, ev_v = _seed_member(
        mem, svc, args.group, args.veteran_user, args.veteran_id, vet_wallet,
        claim_days_ago=65, start_days_ago=60,
        mean=0.03, sd=0.08, n=60, seed=7)

    rk_wallet = Account.create().address
    added_r, ev_r = _seed_member(
        mem, svc, args.group, args.rookie_user, args.rookie_id, rk_wallet,
        claim_days_ago=50, start_days_ago=45,
        mean=0.02, sd=0.45, n=40, seed=11)

    print(f"veteran @{args.veteran_user} {vet_wallet}")
    print(f"  ingested={added_v} n={ev_v.verdict.n_trades} "
          f"distinguishable={ev_v.verdict.distinguishable} tier={ev_v.tier.value}")
    print(f"rookie  @{args.rookie_user} {rk_wallet}")
    print(f"  ingested={added_r} n={ev_r.verdict.n_trades} "
          f"distinguishable={ev_r.verdict.distinguishable} tier={ev_r.tier.value}")
    assert ev_v.tier.value == "T2_credible", "veteran must be CREDIBLE"
    assert ev_r.tier.value == "T1_observed", "rookie must be OBSERVED"

    live = Account.create()
    print(f"live-claim burner {live.address}")
    print(f"LIVE_KEY={live.key.hex()}  <-- valueless burner, keep OFF camera")
    print("seeded OK")


if __name__ == "__main__":
    main()
