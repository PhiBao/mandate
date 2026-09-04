from __future__ import annotations

from dataclasses import dataclass

from .tiers import Tier


@dataclass(frozen=True)
class CardData:
    display_name: str
    tier: Tier | None
    n_trades: int = 0
    win_rate: float = 0.0
    mean_return: float = 0.0
    ci_lo: float = 0.0
    ci_hi: float = 0.0
    window_days: float = 0.0
    benchmark_return: float | None = None
    excess_mean: float | None = None
    max_drawdown: float = 0.0
    unverified_asks: int = 0
    wallets_claimed: int = 0
    flagged_positions: int = 0
    reasons: tuple[str, ...] = ()


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def render_standing(card: CardData) -> str:
    if card.tier is None:
        return _render_unverified(card)
    header = {
        Tier.UNPROVEN: "UNPROVEN",
        Tier.OBSERVED: "NOT PROVEN",
        Tier.CREDIBLE: "CREDIBLE",
        Tier.TRUSTED: "TRUSTED",
    }[card.tier]
    lines = [f"{card.display_name} — {header} ({card.tier.value})"]

    if card.tier in (Tier.UNPROVEN, Tier.OBSERVED):
        lines.append(
            f"{card.n_trades} closed trades since {card.window_days:.0f}d · Win rate {card.win_rate * 100:.0f}%"
        )
        lines.append(f"Mean return {_pct(card.mean_return)} — but 95% CI: {_pct(card.ci_lo)} to {_pct(card.ci_hi)}")
        if card.ci_lo <= 0:
            lines.append("Interval includes zero. Not distinguishable from luck.")
        else:
            lines.append("Interval clears zero.")
        if card.benchmark_return is not None and card.excess_mean is not None:
            lines.append(
                f"Over the same window: benchmark {_pct(card.benchmark_return)}, this wallet {_pct(card.mean_return)}."
            )
    elif card.tier is Tier.CREDIBLE:
        lines.append(
            f"{card.n_trades} closed trades over {card.window_days:.0f} days"
            + (f" · {card.wallets_claimed} wallet(s) claimed, all counted" if card.wallets_claimed else "")
        )
        lines.append(f"Median-style mean {_pct(card.mean_return)} · Win rate {card.win_rate * 100:.0f}%")
        if card.excess_mean is not None:
            lines.append(f"Excess vs benchmark {_pct(card.excess_mean)} · CI lower bound {_pct(card.ci_lo)}")
        lines.append(f"Max drawdown {_pct(-card.max_drawdown)} · No risk flags")
    else:
        lines.append(
            f"{card.n_trades} closed trades · {card.window_days:.0f}d sustained record"
        )
        lines.append(f"Excess vs benchmark {_pct(card.excess_mean or 0.0)} · Drawdown within limits")

    if card.flagged_positions:
        lines.append(f"{card.flagged_positions} positions excluded for data quality.")
    return "\n".join(lines)


def render_unverified_ask(display_name: str, asks: int) -> str:
    return (
        f"{display_name} — UNVERIFIED\n"
        f"No wallet claimed. Asked {asks} time(s).\n"
        "This call cannot be checked against any record.\n"
        "Claim a wallet to build a verifiable track record: /claim"
    )


def _render_unverified(card: CardData) -> str:
    return render_unverified_ask(card.display_name, card.unverified_asks)


def render_why(card: CardData, derivation: list[str]) -> str:
    head = render_standing(card)
    trail = "\n".join(f"· {step}" for step in derivation)
    return f"{head}\n\nWhy:\n{trail}"
