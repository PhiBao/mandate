"""Transfer-based wallet claims — the noob path.

Flow:
  1. Member sends `/claim <wallet>` in the group.
  2. Bot DMs: "send exactly <random> USDC from that wallet to the treasury
     within 10 minutes". The random 6-decimal amount is the per-claim nonce.
  3. Member sends the dust from whatever wallet app they already use.
  4. The bot watches USDC Transfer logs on Base; a matching transfer proves
     key control (only the key holder can send from that address), and its
     block timestamp becomes `claimed_at` — the forward-only clock is
     provable onchain, no DB trust required.

The dust is a disclosed, non-refundable verification fee (anti-spam).
A transfer is consumed by exactly one claim (`claimtx:{hash}` refs).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CLAIM_WINDOW_SECONDS = 600

RPC_URL = "https://mainnet.base.org"


@dataclass
class PendingTransfer:
    chat_id: str
    user_id: str
    username: str
    wallet: str            # as typed by the user (checksummed later)
    amount_units: int      # USDC raw units (6 decimals)
    created_at: str
    expires_at: str


def random_amount_units() -> int:
    """0.001000..0.049999 USDC in raw units — collision-unlikely per-claim nonce."""
    return 1_000 + secrets.randbelow(49_000)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_pending(chat_id: str, user_id: str, username: str, wallet: str) -> PendingTransfer:
    created = datetime.now(timezone.utc)
    return PendingTransfer(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        wallet=wallet,
        amount_units=random_amount_units(),
        created_at=created.isoformat(),
        expires_at=(created + timedelta(seconds=CLAIM_WINDOW_SECONDS)).isoformat(),
    )


def dm_text(pending: PendingTransfer, treasury: str) -> str:
    amount = f"{pending.amount_units / 1e6:.6f}"
    return (
        f"To claim {pending.wallet}:\n\n"
        f"1. Send EXACTLY  {amount} USDC\n"
        f"   from {pending.wallet}\n"
        f"   to {treasury}\n"
        f"   on Base, within 10 minutes.\n\n"
        f"This tiny fee proves you control the wallet and starts your "
        f"forward-only record at the transfer's block timestamp. "
        f"It is a verification fee — it is not returned.\n\n"
        f"You will get a confirmation here the moment it lands. "
        f"This request expires at {pending.expires_at[:19]}Z."
    )


def _topic_addr(addr: str) -> str:
    return "0x" + addr[2:].lower().rjust(64, "0")


async def find_matching_transfer(
    treasury: str,
    wallet: str,
    amount_units: int,
    since_iso: str,
    rpc_url: str = RPC_URL,
) -> tuple[str, int] | None:
    """Return (tx_hash, block_timestamp) for the first matching USDC
    transfer treasury<-wallet of exactly amount_units since since_iso."""
    since = datetime.fromisoformat(since_iso)
    since_hex = hex(int(since.timestamp()))
    async with httpx.AsyncClient(timeout=30.0) as client:
        latest = int(await _rpc(client, rpc_url, "eth_blockNumber", []), 16)
        logs = await _rpc(
            client,
            rpc_url,
            "eth_getLogs",
            [{
                "address": USDC_BASE,
                "topics": [
                    TRANSFER_TOPIC,
                    _topic_addr(wallet),
                    _topic_addr(treasury),
                ],
                "fromBlock": since_hex,
                "toBlock": hex(latest),
            }],
        )
        for log in logs:
            try:
                data = log.get("data", "0x")
                if len(data) >= 66 and int(data[2:66], 16) == amount_units:
                    receipt = await _rpc(
                        client, rpc_url, "eth_getBlockByNumber", [log["blockNumber"], False]
                    )
                    ts = int(receipt["timestamp"], 16)
                    block_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                    if block_iso >= since_iso:
                        return log["transactionHash"], ts
            except (ValueError, KeyError, TypeError):
                continue
    return None


async def _rpc(client: httpx.AsyncClient, rpc_url: str, method: str, params: list) -> object:
    resp = await client.post(
        rpc_url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("error"):
        raise RuntimeError(f"rpc {method}: {body['error']}")
    return body["result"]
