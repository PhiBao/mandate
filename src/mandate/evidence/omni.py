from __future__ import annotations

from dataclasses import dataclass

from ..claims import now_iso
from ..records import Position
from .venue import EvidenceBatch


@dataclass(frozen=True)
class OmniTraderProfile:
    address: str
    equity: float
    pnl: float
    data_quality: str
    positions_raw: list[dict]


class OmniHyperliquidAdapter:
    venue = "hyperliquid"
    base_url = "https://api.nansen.ai/api/v1/profiler/address"
    omni_url = "https://omniterminal.app/api/x402/v1"

    def __init__(self, payer=None) -> None:
        self._payer = payer

    async def fetch_closed_positions(
        self,
        wallet: str,
        *,
        since_iso: str | None = None,
        spent_today_usd: float = 0.0,
        ledger_chat_id: str | None = None,
    ) -> EvidenceBatch:
        cache_key = f"omni:{wallet.lower()}:{since_iso or 'all'}"
        mem = getattr(self._payer, "_mem", None) if self._payer else None
        if mem is not None:
            try:
                cached = mem.get_cached_evidence("hyperliquid", wallet, cache_key)
                if cached and isinstance(cached, dict) and cached.get("positions"):
                    fetched_at = cached.get("fetched_at")
                    if fetched_at:
                        try:
                            from datetime import datetime, timezone

                            dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
                            age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                            if age_h < 6.0:
                                from ..records import Position as _Pos

                                positions = [
                                    _Pos(
                                        open_at=p["open_at"],
                                        close_at=p["close_at"],
                                        asset=p["asset"],
                                        direction=p["direction"],
                                        entry_price=float(p["entry_price"]),
                                        exit_price=float(p["exit_price"]),
                                        return_pct=float(p["return_pct"]),
                                        notional_usd=float(p["notional_usd"]),
                                        quality=p["quality"],
                                        source_ids=p.get("source_ids", []),
                                    )
                                    for p in cached["positions"]
                                ]
                                return EvidenceBatch(
                                    positions=positions,
                                    source=cached.get("source", "omni:hyperliquid"),
                                    fetched_at=cached["fetched_at"],
                                    price_usd=float(cached.get("price_usd", 0.0)),
                                    quality_note=cached.get("quality_note", "") + " (cached)",
                                )
                        except Exception:
                            pass
            except Exception:
                pass
        if self._payer is None:
            raise RuntimeError("Omni adapter requires a funded X402Payer")
        profile = await self._payer.fetch(
            f"{self.omni_url}/trader-profile/{wallet}",
            spent_today_usd=spent_today_usd,
            chain=self.venue,
            wallet=wallet,
            ledger_chat_id=ledger_chat_id,
        )
        body = profile.body if isinstance(profile.body, dict) else {}
        quality = body.get("dataQuality") or body.get("data_quality") or "unknown"
        raw_positions = body.get("positions") or body.get("closedPositions") or []
        positions: list[Position] = []
        for raw in raw_positions:
            try:
                close_at = raw.get("closedAt") or raw.get("close_at") or now_iso()
                if since_iso and close_at < since_iso:
                    continue
                q = "ok" if quality in ("ok", "good", "verified") else "stale_price"
                entry = float(raw.get("entryPrice") or raw.get("entry_price") or 0)
                exit_p = float(raw.get("exitPrice") or raw.get("exit_price") or entry)
                ret = (exit_p - entry) / entry if entry else 0.0
                positions.append(
                    Position(
                        open_at=raw.get("openedAt") or raw.get("open_at") or close_at,
                        close_at=close_at,
                        asset=raw.get("asset") or raw.get("symbol") or "UNKNOWN",
                        direction=raw.get("direction") or ("long" if ret >= 0 else "short"),
                        entry_price=entry,
                        exit_price=exit_p,
                        return_pct=ret,
                        notional_usd=float(raw.get("notional") or raw.get("sizeUsd") or 0),
                        quality=q,
                        source_ids=["omni:hyperliquid"],
                    )
                )
            except (ValueError, TypeError, KeyError):
                continue
        batch = EvidenceBatch(
            positions=positions,
            source="omni:hyperliquid",
            fetched_at=now_iso(),
            price_usd=profile.price_usd,
            quality_note=quality,
        )
        if mem is not None:
            try:
                mem.cache_evidence(
                    "hyperliquid",
                    wallet,
                    cache_key,
                    {
                        "positions": [p.to_dict() for p in positions],
                        "source": batch.source,
                        "fetched_at": batch.fetched_at,
                        "price_usd": batch.price_usd,
                        "quality_note": batch.quality_note,
                    },
                )
            except Exception:
                pass
        return batch
