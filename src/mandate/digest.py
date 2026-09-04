from __future__ import annotations

from dataclasses import dataclass

from .cards import CardData
from .tiers import Tier


@dataclass(frozen=True)
class DigestEntry:
    username: str
    tier: Tier | None
    n_trades: int
    change: str


def render_digest(
    group_name: str,
    entries: list[DigestEntry],
    spent_usd: float,
    saved_usd: float,
) -> str:
    lines = [f"This week in {group_name}"]
    if not entries:
        lines.append("· No verified traders yet. Claim a wallet to start building a record: /claim")
    for e in entries:
        if e.tier is None:
            lines.append(f"· @{e.username} still unverified after {e.n_trades} asks")
        else:
            arrow = {"T3_trusted": "↑", "T2_credible": "→", "T1_observed": "·", "T0_unproven": "↓"}.get(
                e.tier.value, "·"
            )
            lines.append(f"{arrow} @{e.username} → {e.tier.value} ({e.n_trades} trades) — {e.change}")
    lines.append(f"Data spend: ${spent_usd:.2f} (cache saved ${saved_usd:.2f})")
    return "\n".join(lines)


@dataclass(frozen=True)
class CredentialPage:
    wallet: str
    chain: str
    tier: Tier
    n_trades: int
    window_days: float
    win_rate: float
    mean_return: float
    ci_lo: float
    ci_hi: float
    benchmark_return: float | None
    anchor_tx: str | None
    claim_at: str

    def to_dict(self) -> dict:
        return {
            "wallet": self.wallet,
            "chain": self.chain,
            "tier": self.tier.value,
            "n_trades": self.n_trades,
            "window_days": self.window_days,
            "win_rate": self.win_rate,
            "mean_return": self.mean_return,
            "ci_lo": self.ci_lo,
            "ci_hi": self.ci_hi,
            "benchmark_return": self.benchmark_return,
            "anchor_tx": self.anchor_tx,
            "claim_at": self.claim_at,
            "verified_by": "Mandate — forward-only, deterministically computed, no model in the loop",
        }
