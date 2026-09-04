from mandate.stats import VerdictResult
from mandate.tiers import (
    RISK_BLOCK,
    RISK_PASS,
    RISK_WARN,
    Tier,
    TraderState,
    evaluate,
)


def _verdict(n=60, ci_lo=0.01, excess_ci_lo=None, mdd=0.10, abstain=False):
    return VerdictResult(
        n_trades=n,
        mean_return=0.03,
        ci_lo=ci_lo,
        ci_hi=0.05,
        excess_mean=None if excess_ci_lo is None else 0.02,
        excess_ci_lo=excess_ci_lo,
        max_drawdown=mdd,
        win_rate=0.61,
        distinguishable=True,
        abstain=abstain,
        reasons=[],
    )


class TestTierLadder:
    def test_no_verdict_is_unproven(self):
        d = evaluate(TraderState(verdict=None))
        assert d.tier is Tier.UNPROVEN

    def test_small_sample_is_unproven(self):
        d = evaluate(TraderState(verdict=_verdict(n=5, abstain=False)))
        assert d.tier is Tier.UNPROVEN

    def test_tracked_but_unproven_is_observed(self):
        v = _verdict(n=40)
        v = VerdictResult(
            n_trades=v.n_trades,
            mean_return=v.mean_return,
            ci_lo=-0.02,
            ci_hi=v.ci_hi,
            excess_mean=None,
            excess_ci_lo=None,
            max_drawdown=v.max_drawdown,
            win_rate=v.win_rate,
            distinguishable=False,
            abstain=False,
            reasons=["ci_includes_zero_not_distinguishable_from_luck"],
        )
        d = evaluate(TraderState(verdict=v))
        assert d.tier is Tier.OBSERVED
        assert any("luck" in r for r in d.reasons)

    def test_credible_on_skill_and_risk_pass(self):
        d = evaluate(TraderState(verdict=_verdict(), risk_screen=RISK_PASS))
        assert d.tier is Tier.CREDIBLE

    def test_warn_caps_at_observed(self):
        d = evaluate(TraderState(verdict=_verdict(), risk_screen=RISK_WARN))
        assert d.tier is Tier.OBSERVED
        assert any("risk" in r for r in d.reasons)

    def test_block_caps_at_observed(self):
        d = evaluate(TraderState(verdict=_verdict(), risk_screen=RISK_BLOCK))
        assert d.tier is Tier.OBSERVED

    def test_trusted_requires_full_conditions(self):
        v = _verdict(n=120, excess_ci_lo=0.005, mdd=0.20)
        d = evaluate(TraderState(verdict=v, risk_screen=RISK_PASS, age_days=75.0))
        assert d.tier is Tier.TRUSTED

    def test_trusted_blocked_by_age(self):
        v = _verdict(n=120, excess_ci_lo=0.005, mdd=0.20)
        d = evaluate(TraderState(verdict=v, risk_screen=RISK_PASS, age_days=30.0))
        assert d.tier is Tier.CREDIBLE
        assert any("age" in r for r in d.reasons)

    def test_trusted_blocked_by_drawdown(self):
        v = _verdict(n=120, excess_ci_lo=0.005, mdd=0.50)
        d = evaluate(TraderState(verdict=v, risk_screen=RISK_PASS, age_days=90.0))
        assert d.tier is Tier.CREDIBLE
        assert any("drawdown" in r for r in d.reasons)

    def test_reasons_are_human_readable(self):
        d = evaluate(TraderState(verdict=_verdict(n=15)))
        assert d.reasons
        assert all(isinstance(r, str) and "_" not in r[:1] for r in d.reasons)
