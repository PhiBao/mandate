from datetime import datetime, timedelta, timezone

from eth_account import Account

from mandate.claims import (
    anchor_payload,
    build_claim_message,
    claim_digest,
    new_nonce,
    now_iso,
    sign_message,
    verify_claim,
)


def _make_claim(attacker: Account | None = None):
    wallet = Account.create()
    signer = attacker or wallet
    nonce = new_nonce()
    issued = now_iso()
    msg = build_claim_message("hyperliquid", wallet.address, "grp-1", "user-9", nonce, issued)
    sig = sign_message(msg, signer.key.hex())
    return wallet, msg, sig


class TestClaimVerification:
    def test_valid_claim_verifies(self):
        wallet, msg, sig = _make_claim()
        ok, reason = verify_claim(msg, sig, wallet.address)
        assert ok, reason

    def test_wrong_signer_rejected(self):
        wallet, msg, sig = _make_claim(attacker=Account.create())
        ok, reason = verify_claim(msg, sig, wallet.address)
        assert not ok
        assert reason == "signer_is_not_claimed_wallet"

    def test_tampered_message_rejected(self):
        wallet, msg, sig = _make_claim()
        tampered = msg.replace("grp-1", "grp-2")
        ok, _ = verify_claim(tampered, sig, wallet.address)
        assert not ok

    def test_expired_claim_rejected(self):
        wallet = Account.create()
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        msg = build_claim_message("hyperliquid", wallet.address, "g", "u", new_nonce(), old)
        sig = sign_message(msg, wallet.key.hex())
        ok, reason = verify_claim(msg, sig, wallet.address)
        assert not ok
        assert reason == "claim_expired"

    def test_future_issued_at_rejected(self):
        wallet = Account.create()
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        msg = build_claim_message("hyperliquid", wallet.address, "g", "u", new_nonce(), future)
        sig = sign_message(msg, wallet.key.hex())
        ok, reason = verify_claim(msg, sig, wallet.address)
        assert not ok
        assert reason == "issued_at_in_future"


class TestAnchoring:
    def test_digest_deterministic(self):
        msg = build_claim_message("hyperliquid", "0xabc", "g", "u", "n1", "2026-08-18T00:00:00+00:00")
        assert claim_digest(msg) == claim_digest(msg)

    def test_anchor_payload_is_bytes32(self):
        digest = claim_digest("any message")
        payload = anchor_payload(digest)
        assert isinstance(payload, bytes)
        assert len(payload) == 32
