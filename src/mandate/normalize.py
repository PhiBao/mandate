from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .records import Position

QUALITY_OK = "ok"
FLAGGED = {"stale_price", "partial_fill", "unresolved_pnl", "unknown"}


@dataclass(frozen=True)
class NormalizedSeries:
    returns: list[float]
    flagged_count: int
    window_days: float


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def normalize_positions(positions: list[Position]) -> NormalizedSeries:
    usable: list[float] = []
    flagged = 0
    earliest: datetime | None = None
    latest: datetime | None = None

    for p in positions:
        opened = _parse(p.open_at)
        closed = _parse(p.close_at)
        earliest = opened if earliest is None else min(earliest, opened)
        latest = closed if latest is None else max(latest, closed)
        if p.quality in FLAGGED or p.quality != QUALITY_OK:
            flagged += 1
            continue
        usable.append(p.return_pct)

    window_days = 0.0
    if earliest and latest and latest > earliest:
        window_days = (latest - earliest).total_seconds() / 86400.0

    return NormalizedSeries(returns=usable, flagged_count=flagged, window_days=window_days)
