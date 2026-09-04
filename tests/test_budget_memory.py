import pytest

from mandate.budget import BudgetPolicy, authorize_spend
from mandate.claims import build_claim_message, claim_digest, new_nonce, now_iso, sign_message
from mandate.memory import MandateMemory, trader_tenant
from mandate.records import Claim, Verdict
from mandate.stats import VerdictResult


class TestBudget:
    def test_normal_spend_allowed(self):
        d = authorize_spend(0.01, 0.0, BudgetPolicy())
        assert d.allowed

    def test_per_call_cap_enforced(self):
        d = authorize_spend(0.50, 0.0, BudgetPolicy(per_call_cap_usd=0.05))
        assert not d.allowed

    def test_daily_cap_enforced(self):
        p = BudgetPolicy(daily_cap_usd=1.0)
        assert authorize_spend(0.01, 0.995, p).allowed is False

    def test_tier0_recurring_blocked_after_bootstrap(self):
        d = authorize_spend(
            0.01, 0.0, BudgetPolicy(), bootstrap_used=True, tier_rank=0
        )
        assert not d.allowed
        assert "tier0" in d.reason

    def test_tier2_recurring_allowed(self):
        d = authorize_spend(0.01, 0.0, BudgetPolicy(), bootstrap_used=True, tier_rank=2)
        assert d.allowed


def _claim_for(wallet: str) -> Claim:
    msg = build_claim_message("hyperliquid", wallet, "grp-1", "user-9", new_nonce(), now_iso())
    return Claim(
        chain="hyperliquid",
        wallet=wallet,
        group_id="grp-1",
        user_id="user-9",
        nonce="n",
        message=msg,
        message_hash=claim_digest(msg),
        signature="0x00",
        claimed_at=now_iso(),
    )


@pytest.fixture()
def mem(tmp_path):
    return MandateMemory(tmp_path / "mem.db")


class TestMemoryLayer:
    def test_claim_roundtrip_and_multi_wallet_aggregation(self, mem):
        w1, w2 = f"0x{'a' * 40}", f"0x{'b' * 40}"
        mem.record_claim(_claim_for(w1))
        mem.record_claim(_claim_for(w2))

        mem.client.set_tenant(trader_tenant("hyperliquid", w1))
        identity = mem.client.get_entity("identity", "current")
        assert len(identity["body"]["claims"]) == 1

        mem.client.set_tenant(trader_tenant("hyperliquid", w2))
        identity2 = mem.client.get_entity("identity", "current")
        assert len(identity2["body"]["claims"]) == 1

    def test_verdict_supersession_keeps_current_only(self, mem):
        w = f"0x{'c' * 40}"

        def make(lo: float) -> Verdict:
            r = VerdictResult(
                n_trades=50,
                mean_return=0.03,
                ci_lo=lo,
                ci_hi=0.06,
                excess_mean=None,
                excess_ci_lo=None,
                max_drawdown=0.1,
                win_rate=0.6,
                distinguishable=lo > 0,
                abstain=False,
                reasons=[],
            )
            return Verdict(
                computed_at=now_iso(),
                n_trades=r.n_trades,
                window_days=30.0,
                mean_return=r.mean_return,
                ci_lo=r.ci_lo,
                ci_hi=r.ci_hi,
                benchmark_return=None,
                excess_mean=None,
                excess_ci_lo=None,
                max_drawdown=r.max_drawdown,
                win_rate=r.win_rate,
                distinguishable=r.distinguishable,
                abstain=False,
                flagged_positions=0,
                reasons=[],
            )

        mem.save_verdict("hyperliquid", w, make(-0.01))
        mem.save_verdict("hyperliquid", w, make(0.02))

        current = mem.get_verdict("hyperliquid", w)
        assert current["ci_lo"] == pytest.approx(0.02)
        assert current["supersedes"]

    def test_mandate_state_and_bootstrap_flag(self, mem):
        from datetime import datetime, timezone

        w = f"0x{'d' * 40}"
        ev_time = datetime.now(timezone.utc).isoformat()
        from mandate.records import MandateEvent

        mem.set_mandate(
            "hyperliquid",
            w,
            MandateEvent(at=ev_time, trader_ref="t", from_tier="T0", to_tier="T2", reason="promoted"),
        )
        assert mem.get_mandate("hyperliquid", w)["tier"] == "T2"
        assert mem.bootstrap_spend_used("hyperliquid", w) is False
        mem.mark_bootstrap_spend("hyperliquid", w)
        assert mem.bootstrap_spend_used("hyperliquid", w) is True

    def test_ledger_appends(self, mem):
        mem.append_ledger("grp-1", {"what": "omni profile", "price_usd": 0.005})
        mem.append_ledger("grp-1", {"what": "coingecko price", "price_usd": 0.005})
        mem.client.set_tenant("ledger:grp-1")
        events = mem.client.read_events(limit=10)
        assert len(events) == 2
