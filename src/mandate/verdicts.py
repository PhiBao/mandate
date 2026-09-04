from __future__ import annotations

from dataclasses import dataclass

from .memory import MandateMemory
from .normalize import normalize_positions
from .records import MandateEvent, Verdict, position_uid, stable_hash
from .stats import VerdictResult, compute_verdict
from .tiers import Tier, TraderState, evaluate
from .claims import now_iso


@dataclass(frozen=True)
class TraderEvaluation:
    verdict: Verdict
    tier: Tier
    tier_reasons: list[str]


class VerdictService:
    def __init__(self, mem: MandateMemory) -> None:
        self._mem = mem

    def ingest(self, chain: str, wallet: str, positions: list) -> int:
        seen: set[str] = set()
        try:
            existing = self._mem.read_positions(chain, wallet, limit=1000)
            for raw in existing:
                try:
                    seen.add(position_uid(raw))
                except Exception:
                    continue
        except Exception:
            seen = set()
        count = 0
        for p in positions:
            d = p.to_dict() if hasattr(p, "to_dict") else dict(p)  # type: ignore[arg-type]
            try:
                uid = position_uid(d)
            except Exception:
                uid = stable_hash(d)
            if uid in seen:
                continue
            if self._mem.position_exists(chain, wallet, uid):
                seen.add(uid)
                continue
            self._mem.append_position(chain, wallet, d)
            self._mem.client.set_tenant(f"trader:{chain}:{wallet.lower()}")
            self._mem.client.set_reference(f"pos:{uid}", {"at": d.get("close_at")})
            seen.add(uid)
            count += 1
        return count

    def evaluate_trader(
        self,
        chain: str,
        wallet: str,
        *,
        benchmark_return: float | None = None,
        risk_screen: str = "unknown",
        seed: int | None = None,
    ) -> TraderEvaluation:
        raw = self._mem.read_positions(chain, wallet)
        earliest = self._mem.get_earliest_claimed_at(chain, wallet)
        if earliest:
            raw = [r for r in raw if r.get("close_at", "") >= earliest]
        from .records import Position

        positions = [
            Position(
                open_at=r["open_at"],
                close_at=r["close_at"],
                asset=r["asset"],
                direction=r["direction"],
                entry_price=r["entry_price"],
                exit_price=r["exit_price"],
                return_pct=r["return_pct"],
                notional_usd=r["notional_usd"],
                quality=r["quality"],
                source_ids=r.get("source_ids", []),
            )
            for r in raw
        ]
        series = normalize_positions(positions)
        result: VerdictResult = compute_verdict(
            _to_input(series, benchmark_return), seed=seed
        )
        verdict = Verdict(
            computed_at=now_iso(),
            n_trades=result.n_trades,
            window_days=series.window_days,
            mean_return=result.mean_return,
            ci_lo=result.ci_lo,
            ci_hi=result.ci_hi,
            benchmark_return=benchmark_return,
            excess_mean=result.excess_mean,
            excess_ci_lo=result.excess_ci_lo,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            distinguishable=result.distinguishable,
            abstain=result.abstain,
            flagged_positions=series.flagged_count,
            reasons=list(result.reasons),
        )
        self._mem.save_verdict(chain, wallet, verdict)

        age_days = series.window_days
        decision = evaluate(TraderState(verdict=result, risk_screen=risk_screen, age_days=age_days))
        self._persist_mandate_if_changed(chain, wallet, decision.tier)
        return TraderEvaluation(verdict=verdict, tier=decision.tier, tier_reasons=decision.reasons)

    def _persist_mandate_if_changed(self, chain: str, wallet: str, tier: Tier) -> None:
        cur = self._mem.get_mandate(chain, wallet)
        cur_tier = cur.get("tier") if cur else None
        if cur_tier == tier.value:
            return
        self._mem.set_mandate(
            chain,
            wallet,
            MandateEvent(
                at=now_iso(),
                trader_ref=f"trader:{chain}:{wallet.lower()}",
                from_tier=cur_tier or Tier.UNPROVEN.value,
                to_tier=tier.value,
                reason="tier_changed_on_verdict",
            ),
        )


def _to_input(series, benchmark_return: float | None):
    from .stats import VerdictInput

    return VerdictInput(
        returns=series.returns,
        window_days=series.window_days,
        benchmark_return=benchmark_return,
        flagged_positions=series.flagged_count,
    )
