import pytest

from mandate.evidence.mock import MockHyperliquidSource
from mandate.memory import MandateMemory
from mandate.normalize import normalize_positions
from mandate.records import Position
from mandate.tiers import Tier
from mandate.verdicts import VerdictService


def _positions(mean, sd, n, seed) -> list[Position]:
    return MockHyperliquidSource("0x" + "e" * 40, mean=mean, sd=sd, n=n, seed=seed).fetch_closed_positions()


class TestNormalize:
    def test_flagged_positions_excluded_and_counted(self):
        positions = _positions(0.02, 0.10, 50, seed=4)
        assert any(p.quality != "ok" for p in positions)
        series = normalize_positions(positions)
        flagged = sum(1 for p in positions if p.quality != "ok")
        assert series.flagged_count == flagged
        assert len(series.returns) == len(positions) - flagged

    def test_window_days_spans_series(self):
        series = normalize_positions(_positions(0.01, 0.05, 30, seed=2))
        assert series.window_days > 20


class TestEndToEndPipeline:
    @pytest.fixture()
    def wired(self, tmp_path):
        mem = MandateMemory(tmp_path / "e2e.db")
        svc = VerdictService(mem)
        return mem, svc

    def test_skilled_wallet_reaches_credible(self, wired):
        mem, svc = wired
        wallet = "0x" + "1" * 40
        good = MockHyperliquidSource(wallet, mean=0.03, sd=0.08, n=60, seed=7).fetch_closed_positions()
        svc.ingest("hyperliquid", wallet, good)

        ev = svc.evaluate_trader("hyperliquid", wallet, risk_screen="pass", seed=42)
        assert ev.verdict.distinguishable
        assert ev.tier is Tier.CREDIBLE
        assert mem.get_verdict("hyperliquid", wallet)["n_trades"] > 0

    def test_lucky_wallet_stays_observed(self, wired):
        _, svc = wired
        wallet = "0x" + "2" * 40
        lucky = MockHyperliquidSource(wallet, mean=0.02, sd=0.45, n=40, seed=11).fetch_closed_positions()
        svc.ingest("hyperliquid", wallet, lucky)

        ev = svc.evaluate_trader("hyperliquid", wallet, risk_screen="pass", seed=42)
        assert not ev.verdict.distinguishable
        assert ev.tier is Tier.OBSERVED
        assert any("luck" in r for r in ev.tier_reasons)

    def test_verdict_survives_fresh_process(self, wired):
        mem, svc = wired
        wallet = "0x" + "3" * 40
        svc.ingest("hyperliquid", wallet, _positions(0.03, 0.08, 60, 7))
        svc.evaluate_trader("hyperliquid", wallet, risk_screen="pass", seed=42)

        fresh_svc = VerdictService(MandateMemory(mem.db_path))
        stored = fresh_svc._mem.get_verdict("hyperliquid", wallet)
        assert stored is not None
        assert stored["distinguishable"] is True
