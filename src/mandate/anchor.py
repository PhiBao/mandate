from __future__ import annotations

import os

from eth_account import Account
from eth_utils import keccak

RPC_URL = os.environ.get("MANDATE_BASE_RPC", "https://mainnet.base.org")
CHAIN_ID = 8453

ANCHOR_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "claimHash", "type": "bytes32"},
            {"internalType": "string", "name": "venue", "type": "string"},
        ],
        "name": "anchor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def anchor_calldata(claim_hash_hex: str, venue: str = "hyperliquid") -> str:
    h = claim_hash_hex[2:] if claim_hash_hex.startswith("0x") else claim_hash_hex
    selector = keccak(text="anchor(bytes32,string)")[:4].hex()
    padded_hash = h.lower().rjust(64, "0")
    venue_hex = venue.encode().hex()
    offset = "0000000000000000000000000000000000000000000000000000000000000040"
    length = format(len(venue), "064x")
    padded_venue = venue_hex.ljust(((len(venue_hex) + 63) // 64) * 64, "0")
    return "0x" + selector + padded_hash + offset + length + padded_venue


async def anchor_onchain(claim_hash_hex: str, venue: str = "hyperliquid") -> str | None:
    address = os.environ.get("MANDATE_CLAIM_ANCHOR", "")
    key = os.environ.get("MANDATE_EVM_PRIVATE_KEY", "")
    if not address or not key:
        return None
    try:
        from eth_account import Account as Acct
        import httpx

        acct = Acct.from_key(key)
        data = anchor_calldata(claim_hash_hex, venue)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendTransaction",
            "params": [{"from": acct.address, "to": address, "data": data}],
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(RPC_URL, json=payload)
            body = resp.json()
            return body.get("result")
    except Exception:
        return None
