from eth_account import Account

from mandate.bot import MandateBot, Update
from mandate.claims import build_claim_message, new_nonce, now_iso, sign_message
from mandate.evidence.mock import MockHyperliquidSource
from mandate.memory import MandateMemory
from mandate.tiers import Tier
from mandate.verdicts import VerdictService


class FakeTransport:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    def last(self) -> str:
        return self.sent[-1][1]


def _bot(tmp_path):
    mem = MandateMemory(tmp_path / "bot.db")
    t = FakeTransport()
    return MandateBot(mem, t), mem, t


def _update(text: str, user="alice", chat="grp-1"):
    return Update(chat_id=chat, user_id=user, username=user, text=text)


class TestUnverifiedPath:
    def test_call_from_unverified_user_gets_ask_card(self, tmp_path):
        bot, _, t = _bot(tmp_path)
        bot.handle(_update("long $ETH here, targets above"))
        assert "UNVERIFIED" in t.last()
        assert "Asked 1 time(s)" in t.last()

    def test_asks_escalate(self, tmp_path):
        bot, _, t = _bot(tmp_path)
        bot.handle(_update("long"))
        bot.handle(_update("still long"))
        assert "Asked 2 time(s)" in t.last()


class TestClaimFlow:
    def test_full_claim_flow_with_real_signature(self, tmp_path):
        bot, mem, t = _bot(tmp_path)
        wallet = Account.create()

        bot.handle(_update(f"/claim {wallet.address}"))
        sent = t.last()
        assert "Sign this exact message" in sent

        msg_start = sent.index("Mandate wallet claim")
        message = sent[msg_start:]
        sig = sign_message(message, wallet.key.hex())

        bot.handle(_update(f"/claim {wallet.address} {sig}"))
        assert "verified and timestamped" in t.last()

        mem.client.set_tenant(f"member:grp-1:alice")
        claims = mem.client.list_entities("claim")
        assert len(claims) == 1

    def test_wrong_signer_rejected(self, tmp_path):
        bot, _, t = _bot(tmp_path)
        wallet = Account.create()
        attacker = Account.create()

        bot.handle(_update(f"/claim {wallet.address}"))
        message = t.last()[t.last().index("Mandate wallet claim"):]
        sig = sign_message(message, attacker.key.hex())

        bot.handle(_update(f"/claim {wallet.address} {sig}"))
        assert "rejected" in t.last()
        assert "signer_is_not_claimed_wallet" in t.last()


class TestStandingCards:
    def _seed_credible_trader(self, tmp_path):
        from datetime import datetime, timedelta, timezone

        bot, mem, t = _bot(tmp_path)
        wallet = Account.create()
        svc = VerdictService(mem)
        past = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        positions = MockHyperliquidSource(
            wallet.address, mean=0.03, sd=0.08, n=60, seed=7,
            start=datetime.now(timezone.utc) - timedelta(days=60),
        ).fetch_closed_positions()
        svc.ingest("hyperliquid", wallet.address.lower(), positions)

        from mandate.claims import build_claim_message, claim_digest

        msg = build_claim_message(
            "hyperliquid", wallet.address.lower(), "grp-1", "bob", new_nonce(), past
        )
        from mandate.records import Claim

        mem.record_claim(
            Claim(
                chain="hyperliquid",
                wallet=wallet.address.lower(),
                group_id="grp-1",
                user_id="bob",
                nonce="n",
                message=msg,
                message_hash=claim_digest(msg),
                signature="0x00",
                claimed_at=past,
            )
        )
        ev = svc.evaluate_trader("hyperliquid", wallet.address.lower(), risk_screen="pass", seed=42)
        mem.set_mandate(
            "hyperliquid",
            wallet.address.lower(),
            __import__("mandate.records", fromlist=["MandateEvent"]).MandateEvent(
                at=now_iso(),
                trader_ref="t",
                from_tier="T1",
                to_tier=ev.tier.value,
                reason="promoted",
            ),
        )
        return bot, t, wallet

    def test_standing_shows_credible_card(self, tmp_path):
        bot, t, wallet = self._seed_credible_trader(tmp_path)
        bot.handle(_update("/standing @bob", user="carol"))
        out = t.last()
        assert "CREDIBLE" in out
        assert "closed trades" in out
        assert "drawdown" in out.lower()

    def test_standing_of_stranger_is_unverified(self, tmp_path):
        bot, t, _ = self._seed_credible_trader(tmp_path)
        bot.handle(_update("/standing @stranger", user="carol"))
        assert "UNVERIFIED" in t.last()


class TestWhyDerivation:
    def test_why_includes_methodology(self, tmp_path):
        bot, _, t = _bot(tmp_path)
        bot.handle(_update("/why @someone"))
        assert "bootstrapped" in t.last()
        assert "no model in the loop" in t.last()


class TestSearchCommand:
    def test_search_usage_without_query(self, tmp_path):
        bot, _, t = _bot(tmp_path)
        bot.handle(_update("/search", user="carol"))
        assert "Usage: /search" in t.last()

    def test_search_no_matches(self, tmp_path):
        bot, _, t = _bot(tmp_path)
        bot.handle(_update("/search zzz-no-such-trader", user="carol"))
        out = t.last()
        assert "No matches" in out or "Peers matching" in out
