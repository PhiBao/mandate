from __future__ import annotations

import secrets
from datetime import datetime, timezone

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak

CLAIM_VALIDITY_SECONDS = 3600


def build_claim_message(
    chain: str,
    wallet: str,
    group_id: str,
    user_id: str,
    nonce: str,
    issued_at: str,
) -> str:
    return (
        "Mandate wallet claim\n"
        f"chain: {chain}\n"
        f"wallet: {wallet.lower()}\n"
        f"group: {group_id}\n"
        f"user: {user_id}\n"
        f"nonce: {nonce}\n"
        f"issued_at: {issued_at}\n"
        "Signing proves control of this wallet for forward-only verification."
    )


def new_nonce() -> str:
    return secrets.token_hex(16)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_digest(message: str) -> str:
    return "0x" + keccak(text=message).hex()


def sign_message(message: str, private_key: str) -> str:
    signed = Account.sign_message(encode_defunct(text=message), private_key)
    return signed.signature.hex()


def verify_claim(
    message: str,
    signature: str,
    claimed_wallet: str,
    *,
    max_age_seconds: int = CLAIM_VALIDITY_SECONDS,
    now: datetime | None = None,
) -> tuple[bool, str]:
    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    except Exception as exc:
        return False, f"signature_recover_failed:{type(exc).__name__}"

    if recovered.lower() != claimed_wallet.lower():
        return False, "signer_is_not_claimed_wallet"

    parsed = _parse_issued_at(message)
    if parsed is None:
        return False, "missing_or_bad_issued_at"

    ref = now or datetime.now(timezone.utc)
    age = (ref - parsed).total_seconds()
    if age > max_age_seconds:
        return False, "claim_expired"
    if age < -300:
        return False, "issued_at_in_future"

    expected = build_claim_message(*_fields_from_message(message))
    if expected != message:
        return False, "message_template_mismatch"

    return True, "ok"


def anchor_payload(message_hash: str) -> bytes:
    return bytes.fromhex(message_hash[2:] if message_hash.startswith("0x") else message_hash)


def _parse_issued_at(message: str) -> datetime | None:
    for line in message.splitlines():
        if line.startswith("issued_at:"):
            raw = line.split(":", 1)[1].strip()
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                return None
    return None


def _fields_from_message(message: str) -> tuple[str, str, str, str, str, str]:
    vals: dict[str, str] = {}
    for line in message.splitlines():
        if ":" in line and not line.endswith(":"):
            key, _, val = line.partition(":")
            vals[key.strip()] = val.strip()
    return (
        vals.get("chain", ""),
        vals.get("wallet", ""),
        vals.get("group", ""),
        vals.get("user", ""),
        vals.get("nonce", ""),
        vals.get("issued_at", ""),
    )
