from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from ..records import Position


class MockHyperliquidSource:
    def __init__(
        self,
        wallet: str,
        *,
        mean: float,
        sd: float,
        n: int,
        seed: int = 0,
        start: datetime | None = None,
        flagged_rate: float = 0.05,
    ) -> None:
        self.wallet = wallet.lower()
        self.mean = mean
        self.sd = sd
        self.n = n
        self.seed = seed
        self.flagged_rate = flagged_rate
        self.start = start or (datetime.now(timezone.utc) - timedelta(days=n))

    def fetch_closed_positions(self) -> list[Position]:
        rng = random.Random(self.seed)
        positions: list[Position] = []
        t = self.start
        for i in range(self.n):
            hold_hours = rng.uniform(2.0, 48.0)
            close_t = t + timedelta(hours=hold_hours)
            quality = "stale_price" if rng.random() < self.flagged_rate else "ok"
            ret = rng.gauss(self.mean, self.sd)
            entry = 100.0 * (1.0 + rng.uniform(-0.5, 0.5))
            direction = "long" if ret >= 0 else "short"
            exit_price = entry * (1.0 + abs(ret))
            if direction == "short":
                exit_price = entry * (1.0 - abs(ret))
            positions.append(
                Position(
                    open_at=t.isoformat(),
                    close_at=close_t.isoformat(),
                    asset=f"ASSET{i % 7}",
                    direction=direction,
                    entry_price=round(entry, 6),
                    exit_price=round(exit_price, 6),
                    return_pct=ret,
                    notional_usd=round(rng.uniform(200, 5000), 2),
                    quality=quality,
                    source_ids=["mock:hyperliquid"],
                )
            )
            t = close_t
        return positions
