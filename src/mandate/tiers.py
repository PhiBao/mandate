from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .stats import MIN_TRADES_T1, MIN_TRADES_T2, VerdictResult

MAX_DRAWDOWN_T3 = 0.35
MIN_AGE_DAYS_T3 = 60.0
MIN_TRADES_T3 = 100


class Tier(str, Enum):
    UNPROVEN = "T0_unproven"
    OBSERVED = "T1_observed"
    CREDIBLE = "T2_credible"
    TRUSTED = "T3_trusted"


RISK_PASS = "pass"
RISK_WARN = "warn"
RISK_BLOCK = "block"
RISK_UNKNOWN = "unknown"


@dataclass(frozen=True)
class TraderState:
    verdict: VerdictResult | None
    risk_screen: str = RISK_UNKNOWN
    age_days: float = 0.0


@dataclass(frozen=True)
class TierDecision:
    tier: Tier
    reasons: list[str]


def evaluate(state: TraderState) -> TierDecision:
    reasons: list[str] = []
    v = state.verdict

    if v is None or v.abstain or v.n_trades < MIN_TRADES_T1:
        missing = _t1_gaps(v)
        return TierDecision(Tier.UNPROVEN, ["below_t1_threshold", *missing])

    if state.risk_screen in (RISK_WARN, RISK_BLOCK):
        return TierDecision(
            Tier.OBSERVED,
            [f"risk_screen_{state.risk_screen}_caps_at_observed"],
        )

    t2_gaps = _t2_gaps(v)
    if t2_gaps:
        return TierDecision(Tier.OBSERVED, [*t2_gaps])

    t3_gaps = _t3_gaps(v, state)
    if t3_gaps:
        return TierDecision(Tier.CREDIBLE, [*t3_gaps])

    return TierDecision(Tier.TRUSTED, ["all_t3_conditions_met"])


def _t1_gaps(v: VerdictResult | None) -> list[str]:
    if v is None:
        return ["no_verdict"]
    gaps: list[str] = []
    if v.n_trades < MIN_TRADES_T1:
        gaps.append(f"n_trades_{v.n_trades}_below_{MIN_TRADES_T1}")
    return gaps


def _t2_gaps(v: VerdictResult) -> list[str]:
    gaps: list[str] = []
    if v.n_trades < MIN_TRADES_T2:
        gaps.append(f"n_trades_{v.n_trades}_below_{MIN_TRADES_T2}")
    if not v.distinguishable:
        gaps.append("returns_not_distinguishable_from_luck")
    return gaps


def _t3_gaps(v: VerdictResult, state: TraderState) -> list[str]:
    gaps: list[str] = []
    if v.n_trades < MIN_TRADES_T3:
        gaps.append(f"n_trades_{v.n_trades}_below_{MIN_TRADES_T3}")
    if state.age_days < MIN_AGE_DAYS_T3:
        gaps.append(f"age_{state.age_days:.0f}d_below_{MIN_AGE_DAYS_T3:.0f}d")
    if v.excess_ci_lo is None or v.excess_ci_lo <= 0:
        gaps.append("excess_ci_not_above_benchmark")
    if v.max_drawdown > MAX_DRAWDOWN_T3:
        gaps.append(f"drawdown_{v.max_drawdown:.2f}_above_limit")
    return gaps


def tier_rank(tier: Tier) -> int:
    return list(Tier).index(tier)
