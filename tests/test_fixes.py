from datetime import datetime, timedelta, timezone

from mandate.evidence.mock import MockHyperliquidSource
from mandate.memory import MandateMemory
from mandate.records import Claim
from mandate.claims import build_claim_message, claim_digest, new_nonce, now_iso
from mandate.verdicts import VerdictService


def _past(days=90):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _claim_at(mem, wallet, days_ago=90, group="grp-1", user="tester"):
    past = _past(days_ago)
    msg = build_claim_message("hyperliquid", wallet, group, user, new_nonce(), past)
    mem.record_claim(Claim(chain="hyperliquid", wallet=wallet.lower(), group_id=group, user_id=user, nonce="n", message=msg, message_hash=claim_digest(msg), signature="0x00", claimed_at=past))
    return past


class TestIngestIdempotent:
    def test_second_ingest_of_same_positions_counts_zero(self, tmp_path):
        mem = MandateMemory(tmp_path / "idem.db")
        svc = VerdictService(mem)
        w = "0x" + "a" * 40
        pos = MockHyperliquidSource(w, mean=0.03, sd=0.08, n=20, seed=1).fetch_closed_positions()
        c1 = svc.ingest("hyperliquid", w, pos)
        c2 = svc.ingest("hyperliquid", w, pos)
        assert c1 == 20
        assert c2 == 0
        assert len(mem.read_positions("hyperliquid", w)) == 20

    def test_mandate_auto_persisted_on_evaluate(self, tmp_path):
        mem = MandateMemory(tmp_path / "mandate.db")
        svc = VerdictService(mem)
        w = "0x" + "b" * 40
        _claim_at(mem, w, days_ago=90)
        pos = MockHyperliquidSource(w, mean=0.03, sd=0.08, n=60, seed=7, start=datetime.now(timezone.utc) - timedelta(days=60)).fetch_closed_positions()
        svc.ingest("hyperliquid", w, pos)
        assert mem.get_mandate("hyperliquid", w) is None
        ev = svc.evaluate_trader("hyperliquid", w, risk_screen="pass", seed=42)
        # Mandate should now be persisted automatically
        m = mem.get_mandate("hyperliquid", w)
        assert m is not None
        assert m["tier"] == ev.tier.value

    def test_forward_only_excludes_pre_claim_positions(self, tmp_path):
        mem = MandateMemory(tmp_path / "fwd.db")
        svc = VerdictService(mem)
        w = "0x" + "c" * 40
        # Ingest old positions first (start 100 days ago)
        old_start = datetime.now(timezone.utc) - timedelta(days=100)
        old_pos = MockHyperliquidSource(w, mean=0.03, sd=0.08, n=30, seed=2, start=old_start).fetch_closed_positions()
        svc.ingest("hyperliquid", w, old_pos)
        # Claim 20 days ago - should exclude most old positions (they closed >20d ago)
        # Actually mock positions span from old_start forward ~30*25h=31 days, so last close ~69 days ago
        # Claiming 20 days ago means all old positions close before claim => filtered out
        _claim_at(mem, w, days_ago=20)
        ev_old = svc.evaluate_trader("hyperliquid", w, risk_screen="pass", seed=42)
        assert ev_old.verdict.n_trades == 0
        # Now ingest fresh positions after claim
        fresh_start = datetime.now(timezone.utc) - timedelta(days=15)
        fresh = MockHyperliquidSource(w, mean=0.03, sd=0.08, n=40, seed=3, start=fresh_start).fetch_closed_positions()
        svc.ingest("hyperliquid", w, fresh)
        ev_new = svc.evaluate_trader("hyperliquid", w, risk_screen="pass", seed=42)
        assert 35 <= ev_new.verdict.n_trades <= 40
        assert ev_new.verdict.n_trades + ev_new.verdict.flagged_positions == 40


class TestAskCountPersistence:
    def test_ask_counts_survive_bot_recreation(self, tmp_path):
        from mandate.bot import MandateBot, Update

        class FakeTransport:
            def send(self, chat_id, text): pass

        db = tmp_path / "ask.db"
        mem1 = MandateMemory(db)
        bot1 = MandateBot(mem1, FakeTransport())
        upd = Update(chat_id="grp-1", user_id="u1", username="alice", text="long $BTC")
        bot1.handle(upd)
        bot1.handle(upd)
        assert mem1.get_ask_count("grp-1", "u1") == 2
        # Fresh bot with same DB should see same count
        mem2 = MandateMemory(db)
        bot2 = MandateBot(mem2, FakeTransport())
        from mandate.cards import CardData
        card = bot2._build_card("grp-1", "alice")
        assert card.unverified_asks == 2

    def test_search_traders_returns_hits(self, tmp_path):
        mem = MandateMemory(tmp_path / "search.db")
        w = "0x" + "d" * 40
        _claim_at(mem, w, days_ago=10)
        mem.search_traders  # ensure method exists
        hits = mem.search_traders("wallet claimed", limit=5)
        assert isinstance(hits, list)


class TestHyperliquidFreeAdapter:
    def test_fill_to_position_filters_non_closing(self):
        from mandate.evidence.hyperliquid_free import _fill_to_position
        # Non-closing fill should be None
        assert _fill_to_position({"closedPnl": "0.0", "dir": "Open Long", "px": "100", "sz": "1", "time": 123}, "0xabc") is None
        # Closing fill should convert
        pos = _fill_to_position({"closedPnl": "10.0", "dir": "Close Long", "px": "100", "sz": "1", "time": 1700000000000, "coin": "BTC", "hash": "0xdead"}, "0xabc")
        assert pos is not None
        assert pos.asset == "BTC"
        assert pos.direction == "long"

    def test_cache_wired_via_mem(self, tmp_path):
        import asyncio
        from mandate.evidence.hyperliquid_free import HyperliquidFreeAdapter
        from mandate.evidence.mock import MockHyperliquidSource as _Mock  # noqa
        mem = MandateMemory(tmp_path / "cache.db")
        w = "0x" + "e" * 40
        # Pre-populate cache
        mem.cache_evidence("hyperliquid", w, f"hl_free:{w.lower()}:all:2000", {"positions": [{"open_at": "2026-01-01T00:00:00+00:00", "close_at": "2026-01-02T00:00:00+00:00", "asset": "BTC", "direction": "long", "entry_price": 100.0, "exit_price": 105.0, "return_pct": 0.05, "notional_usd": 100.0, "quality": "ok", "source_ids": ["x"]}], "source": "hyperliquid:free", "fetched_at": now_iso(), "price_usd": 0.0, "quality_note": "public_hyperliquid_free"})
        adapter = HyperliquidFreeAdapter(mem=mem)
        batch = asyncio.run(adapter.fetch_closed_positions(w))
        assert batch.source == "hyperliquid:free"
        assert len(batch.positions) == 1
        assert "cached" in batch.quality_note
