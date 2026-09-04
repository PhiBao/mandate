from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..records import Position


@dataclass(frozen=True)
class EvidenceBatch:
    positions: list[Position]
    source: str
    fetched_at: str
    price_usd: float
    tx_hash: str | None = None
    quality_note: str = ""


class VenueAdapter(Protocol):
    venue: str

    async def fetch_closed_positions(
        self,
        wallet: str,
        *,
        since_iso: str | None = None,
        spent_today_usd: float = 0.0,
        ledger_chat_id: str | None = None,
    ) -> EvidenceBatch: ...
