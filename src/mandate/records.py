from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Claim:
    chain: str
    wallet: str
    group_id: str
    user_id: str
    nonce: str
    message: str
    message_hash: str
    signature: str
    claimed_at: str
    anchor_tx: str | None = None
    block_time: str | None = None

    kind = "claim"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Claim":
        return cls(
            chain=d["chain"],
            wallet=d["wallet"],
            group_id=d["group_id"],
            user_id=d["user_id"],
            nonce=d["nonce"],
            message=d["message"],
            message_hash=d["message_hash"],
            signature=d["signature"],
            claimed_at=d["claimed_at"],
            anchor_tx=d.get("anchor_tx"),
            block_time=d.get("block_time"),
        )


@dataclass(frozen=True)
class Position:
    open_at: str
    close_at: str
    asset: str
    direction: str
    entry_price: float
    exit_price: float
    return_pct: float
    notional_usd: float
    quality: str
    source_ids: list[str] = field(default_factory=list)

    kind = "position"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Verdict:
    computed_at: str
    n_trades: int
    window_days: float
    mean_return: float
    ci_lo: float
    ci_hi: float
    benchmark_return: float | None
    excess_mean: float | None
    excess_ci_lo: float | None
    max_drawdown: float
    win_rate: float
    distinguishable: bool
    abstain: bool
    flagged_positions: int
    reasons: list[str]
    evidence_ids: list[str] = field(default_factory=list)
    supersedes: str | None = None

    kind = "verdict"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MandateEvent:
    at: str
    trader_ref: str
    from_tier: str
    to_tier: str
    reason: str
    verdict_hash: str | None = None

    kind = "mandate_event"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def position_uid(p: dict[str, Any] | "Position") -> str:
    raw: dict[str, Any] = p.to_dict() if hasattr(p, "to_dict") else dict(p)  # type: ignore[arg-type]
    core = {
        "close_at": raw.get("close_at"),
        "asset": raw.get("asset"),
        "direction": raw.get("direction"),
        "entry_price": raw.get("entry_price"),
        "exit_price": raw.get("exit_price"),
        "notional_usd": raw.get("notional_usd"),
        "source_ids": raw.get("source_ids"),
    }
    return stable_hash(core)


def stable_hash(obj: Any) -> str:
    import hashlib

    return hashlib.sha256(dumps(obj).encode()).hexdigest()
