import random

from mandate.stats import VerdictInput, compute_verdict, max_drawdown


def _series(mean: float, sd: float, n: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    return [rng.gauss(mean, sd) for _ in range(n)]


class TestPremiseGate:
    def test_skilled_trader_is_distinguishable(self):
        returns = _series(mean=0.03, sd=0.08, n=60, seed=7)
        v = compute_verdict(VerdictInput(returns=returns, window_days=90.0), seed=42)
        assert not v.abstain
        assert v.distinguishable, f"ci_lo={v.ci_lo:.4f}"
        assert v.ci_lo > 0

    def test_lucky_trader_is_not_distinguishable(self):
        returns = _series(mean=0.02, sd=0.45, n=40, seed=11)
        assert sum(returns) / len(returns) > 0
        v = compute_verdict(VerdictInput(returns=returns, window_days=60.0), seed=42)
        assert not v.distinguishable
        assert any("luck" in r for r in v.reasons)

    def test_high_winrate_small_sample_stays_unproven(self):
        returns = [0.05, 0.04, 0.06, -0.01, 0.03]
        v = compute_verdict(VerdictInput(returns=returns, window_days=10.0), seed=1)
        assert v.distinguishable is False
        assert "insufficient_sample_for_skill_verdict" in v.reasons


class TestBenchmarkAdjustment:
    def test_beta_in_bull_market_is_not_skill(self):
        returns = _series(mean=0.04, sd=0.06, n=45, seed=3)
        raw = compute_verdict(
            VerdictInput(returns=returns, window_days=90.0), seed=99
        )
        assert raw.distinguishable

        benchmarked = compute_verdict(
            VerdictInput(returns=returns, window_days=90.0, benchmark_return=0.18),
            seed=99,
        )
        assert not benchmarked.distinguishable
        assert benchmarked.excess_mean is not None
        assert benchmarked.excess_mean < raw.mean_return


class TestDrawdown:
    def test_known_series(self):
        dd = max_drawdown([0.10, -0.20, 0.05])
        assert abs(dd - 0.20) < 1e-9

    def test_no_drawdown_on_monotonic_gains(self):
        assert max_drawdown([0.01, 0.02, 0.03]) == 0.0

    def test_total_loss_caps_at_one(self):
        assert max_drawdown([-1.5]) == 1.0


class TestDeterminism:
    def test_same_seed_same_result(self):
        returns = _series(0.02, 0.15, 50, 5)
        a = compute_verdict(VerdictInput(returns=returns, window_days=30.0), seed=123)
        b = compute_verdict(VerdictInput(returns=returns, window_days=30.0), seed=123)
        assert a == b

    def test_empty_input_abstains(self):
        v = compute_verdict(VerdictInput(returns=[], window_days=0.0))
        assert v.abstain
        assert v.n_trades == 0
