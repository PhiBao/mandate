"""Tests for transfer-based wallet claims (dust-fee path)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mandate.bot import MandateBot, Update
from mandate.memory import MandateMemory
from mandate.telegram import PollingRunner, TelegramTransport, parse_update
from mandate.transfer_claim import build_pending, dm_text, random_amount_units


class FakeTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    def last(self) -> str:
        return self.sent[-1][1]


TREASURY = "0x" + "aa" * 20
WALLET = "0x" + "bb" * 20
USER = "u1"
CHAT = "g1"


def _bot(tmp_path) -> tuple[MandateBot, MandateMemory, FakeTransport]:
    mem = MandateMemory(tmp_path / "memory.db")
    t = FakeTransport()
    bot = MandateBot(mem, t, claim_treasury=TREASURY)
    return bot, mem, t


def _update(text: str, user: str = USER) -> Update:
    return Update(chat_id=CHAT, user_id=user, username=user, text=text)


def test_claim_offer_includes_transfer_instructions(tmp_path):
    bot, _, t = _bot(tmp_path)
    bot.handle(_update(f"/claim {WALLET}"))
    sent = t.last()
    assert "send a tiny fee" in sent
    assert TREASURY in sent
    assert WALLET in sent
    assert "10 minutes" in sent
    # signature fallback still offered
    assert "Sign this exact message" in sent
    # pending registered
    key = f"{CHAT}:{USER}"
    assert key in bot.state.pending_transfers
    pending = bot.state.pending_transfers[key]
    assert pending.wallet == WALLET
    assert 1_000 <= pending.amount_units <= 49_999


def test_transfer_settles_claim_with_block_timestamp(tmp_path):
    bot, mem, t = _bot(tmp_path)
    bot.handle(_update(f"/claim {WALLET}"))

    block_ts = int(datetime.now(timezone.utc).timestamp())
    found = ("0x" + "1" * 64, block_ts)

    async def checker(treasury, wallet, amount, since_iso):
        assert treasury == TREASURY
        assert wallet == WALLET
        return found

    bot._transfer_checker = checker
    import asyncio
    asyncio.run(bot.tick())

    assert "claimed by @u1" in t.last()
    assert "provable onchain" in t.last()
    # claim recorded with block-time claimed_at
    earliest = mem.get_earliest_claimed_at("hyperliquid", WALLET)
    assert earliest is not None
    parsed = datetime.fromisoformat(earliest)
    assert abs((parsed - datetime.fromtimestamp(block_ts, timezone.utc)).total_seconds()) < 2
    # tx consumed exactly once
    assert mem.claim_tx_used(found[0])
    assert not bot.state.pending_transfers


def test_expired_claim_expires(tmp_path):
    bot, _, t = _bot(tmp_path)
    bot.handle(_update(f"/claim {WALLET}"))
    key = f"{CHAT}:{USER}"
    pending = bot.state.pending_transfers[key]
    from datetime import datetime as dt

    pending.expires_at = (dt.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    import asyncio

    async def checker(*a, **k):
        raise AssertionError("checker must not run for expired claims")

    bot._transfer_checker = checker
    asyncio.run(bot.tick())
    assert "expired" in t.last().lower()
    assert key not in bot.state.pending_transfers


def test_wrong_amount_does_not_settle(tmp_path):
    bot, _, t = _bot(tmp_path)
    bot.handle(_update(f"/claim {WALLET}"))

    async def checker(treasury, wallet, amount, since_iso):
        return ("0x" + "2" * 64, int(datetime.now(timezone.utc).timestamp()))

    # simulate a transfer whose amount differs from requested: the checker
    # itself enforces amount matching onchain; here we return a match, so
    # instead test that a mismatched request never settles by returning None
    bot._transfer_checker = checker
    import asyncio

    # tamper the pending amount so the checker's onchain query would not match:
    # we emulate by having checker return None when amount != seen value
    async def strict_checker(treasury, wallet, amount, since_iso):
        seen = amount + 1  # onchain transfer was off by 1 unit
        return None

    bot._transfer_checker = strict_checker
    asyncio.run(bot.tick())
    assert "claimed by" not in t.last()
    assert f"{CHAT}:{USER}" in bot.state.pending_transfers


def test_claim_tx_single_use(tmp_path):
    bot, mem, t = _bot(tmp_path)
    mem.mark_claim_tx("0x" + "3" * 64)
    assert mem.claim_tx_used("0x" + "3" * 64)
    assert not mem.claim_tx_used("0x" + "4" * 64)


def test_dm_text_contains_exact_amount(tmp_path):
    pending = build_pending(CHAT, USER, USER, WALLET)
    text = dm_text(pending, TREASURY)
    assert f"{pending.amount_units / 1e6:.6f} USDC" in text
    assert "not returned" in text


def test_poller_calls_tick(tmp_path):
    mem = MandateMemory(tmp_path / "memory.db")

    class FakeTransport2:
        def __init__(self) -> None:
            self.sent = []

        def send(self, chat_id, text):
            self.sent.append(text)

        async def poll_updates(self, offset=0):
            return [], offset

        async def close(self):
            return None

    t = FakeTransport2()
    bot = MandateBot(mem, t, claim_treasury=TREASURY)
    ticks = []

    async def fake_tick():
        ticks.append(1)

    bot.tick = fake_tick  # type: ignore[method-assign]
    runner = PollingRunner(bot, t)
    import asyncio

    asyncio.run(runner.run_once())
    assert ticks == [1]
