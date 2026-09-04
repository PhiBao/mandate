from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpendDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class BudgetPolicy:
    daily_cap_usd: float = 5.00
    per_call_cap_usd: float = 0.05


def authorize_spend(
    price_usd: float,
    spent_today_usd: float,
    policy: BudgetPolicy,
    *,
    bootstrap_used: bool = False,
    tier_rank: int = 0,
) -> SpendDecision:
    if price_usd > policy.per_call_cap_usd:
        return SpendDecision(False, f"price_{price_usd:.4f}_above_per_call_cap")
    if spent_today_usd + price_usd > policy.daily_cap_usd:
        return SpendDecision(False, "daily_budget_exhausted")
    if tier_rank == 0 and bootstrap_used:
        return SpendDecision(False, "tier0_no_recurring_spend_bootstrap_already_used")
    return SpendDecision(True, "authorized")
