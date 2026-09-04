from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

DEFAULT_DRAWS = 10_000
ALPHA = 0.05
MIN_TRADES_T2 = 30
MIN_TRADES_T1 = 10


def bootstrap_mean_ci(
    returns: list[float],
    draws: int = DEFAULT_DRAWS,
    alpha: float = ALPHA,
    seed: int | None = None,
) -> tuple[float, float]:
    if not returns:
        raise ValueError("returns must be non-empty")
    rng = random.Random(seed)
    n = len(returns)
    means: list[float] = []
    for _ in range(draws):
        sample = rng.choices(returns, k=n)
        means.append(math.fsum(sample) / n)
    means.sort()
    lo_idx = max(0, math.ceil((alpha / 2) * draws) - 1)
    hi_idx = min(draws - 1, math.ceil((1 - alpha / 2) * draws) - 1)
    return means[lo_idx], means[hi_idx]


def max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        equity *= 1.0 + r
        if equity <= 0:
            return 1.0
        peak = max(peak, equity)
        mdd = max(mdd, 1.0 - equity / peak)
    return mdd


@dataclass(frozen=True)
class VerdictInput:
    returns: list[float]
    window_days: float
    benchmark_return: float | None = None
    flagged_positions: int = 0
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerdictResult:
    n_trades: int
    mean_return: float
    ci_lo: float
    ci_hi: float
    excess_mean: float | None
    excess_ci_lo: float | None
    max_drawdown: float
    win_rate: float
    distinguishable: bool
    abstain: bool
    reasons: list[str]


def compute_verdict(
    inp: VerdictInput,
    draws: int = DEFAULT_DRAWS,
    seed: int | None = None,
) -> VerdictResult:
    reasons: list[str] = []
    n = len(inp.returns)

    if n == 0:
        return VerdictResult(
            n_trades=0,
            mean_return=0.0,
            ci_lo=0.0,
            ci_hi=0.0,
            excess_mean=None,
            excess_ci_lo=None,
            max_drawdown=0.0,
            win_rate=0.0,
            distinguishable=False,
            abstain=True,
            reasons=["no_usable_positions"],
        )

    abstain = False
    if inp.flagged_positions > 0:
        reasons.append(f"{inp.flagged_positions}_positions_flagged_excluded")
    if n < MIN_TRADES_T2:
        reasons.append("insufficient_sample_for_skill_verdict")
        if n < MIN_TRADES_T1:
            abstain = True
            reasons.append("insufficient_sample_for_tracking")

    mean = math.fsum(inp.returns) / n
    ci_lo, ci_hi = bootstrap_mean_ci(inp.returns, draws=draws, seed=seed)
    mdd = max_drawdown(inp.returns)
    wins = sum(1 for r in inp.returns if r > 0)

    if inp.benchmark_return is None:
        excess_mean = None
        excess_ci_lo = None
        distinguishable = ci_lo > 0 and n >= MIN_TRADES_T2
        if not distinguishable and ci_lo <= 0 and n >= MIN_TRADES_T2:
            reasons.append("ci_includes_zero_not_distinguishable_from_luck")
    else:
        excess_mean = mean - inp.benchmark_return
        excess_ci_lo = ci_lo - inp.benchmark_return
        distinguishable = excess_ci_lo > 0 and n >= MIN_TRADES_T2
        if n >= MIN_TRADES_T2 and excess_ci_lo <= 0:
            reasons.append("excess_ci_includes_zero_not_distinguishable_from_luck")

    return VerdictResult(
        n_trades=n,
        mean_return=mean,
        ci_lo=ci_lo,
        ci_hi=ci_hi,
        excess_mean=excess_mean,
        excess_ci_lo=excess_ci_lo,
        max_drawdown=mdd,
        win_rate=wins / n,
        distinguishable=distinguishable,
        abstain=abstain,
        reasons=reasons,
    )
