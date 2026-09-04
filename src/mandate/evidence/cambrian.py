from __future__ import annotations

from dataclasses import dataclass

from ..claims import now_iso


@dataclass(frozen=True)
class InfluencerContrast:
    handle: str | None
    credibility_score: float | None
    track_accuracy_24h: float | None
    performance_tier: str | None
    signals: int | None


class CambrianContrastAdapter:
    venue = "cambrian"
    base_url = "https://x402.cambrian.org"

    def __init__(self, payer=None) -> None:
        self._payer = payer

    async def fetch_contrast(
        self, token: str = "BTC", *, spent_today_usd: float = 0.0
    ) -> InfluencerContrast | None:
        if self._payer is None:
            return None
        try:
            receipt = await self._payer.fetch(
                f"{self.base_url}/deep42/social-data/influencer-credibility?limit=1&sort_by=credibility&token_focus={token}",
                spent_today_usd=spent_today_usd,
                tier_rank=2,
            )
            body = receipt.body
            if isinstance(body, list) and body:
                top = body[0]
            elif isinstance(body, dict) and body.get("data"):
                top = body["data"][0]
            else:
                return None
            return InfluencerContrast(
                handle=top.get("twitterHandle") or top.get("handle"),
                credibility_score=top.get("credibilityScore"),
                track_accuracy_24h=top.get("trackRecordAccuracy24h"),
                performance_tier=top.get("trackRecordPerformanceTier"),
                signals=top.get("trackRecordSignals"),
            )
        except Exception:
            return None

    def render_contrast_line(self, c: InfluencerContrast | None) -> str:
        if not c or not c.handle:
            return ""
        tier = c.performance_tier or "unproven"
        acc = f"{c.track_accuracy_24h:.1f}%" if c.track_accuracy_24h is not None else "n/a"
        return (
            f"Contrast: top social-credibility @{c.handle} "
            f"(score {c.credibility_score:.1f}) is {tier} at {acc} 24h accuracy — "
            f"social credibility excludes accuracy; ours is only accuracy."
        )
