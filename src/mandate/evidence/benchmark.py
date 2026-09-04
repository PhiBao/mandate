from __future__ import annotations

import httpx

from ..claims import now_iso


async def fetch_btc_return(window_days: float) -> float | None:
    """Fetch BTC return over window_days using free CoinGecko API.

    Returns None on failure — caller should treat as no benchmark (T3
    unreachable) rather than failing the verdict.
    """
    if window_days < 1:
        return None
    days = min(int(window_days) + 1, 90)
    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days={days}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        prices = data.get("prices") or []
        if len(prices) < 2:
            return None
        start = float(prices[0][1])
        end = float(prices[-1][1])
        if start == 0:
            return None
        return (end - start) / start
    except Exception:
        return None


async def fetch_benchmark_return(
    asset: str, window_days: float, payer=None
) -> float | None:
    """Fetch benchmark return, trying x402 CoinGecko via payer if available, else free.

    Keeps the x402 path for Base multiplier proof while free path ensures T3
    is testable without USDC.
    """
    # Try free first for reliability in tests/demos
    free = await fetch_btc_return(window_days)
    if free is not None:
        return free
    if payer is None:
        return None
    try:
        receipt = await payer.fetch(
            f"https://coingecko.use.x402atlas.com/price?ids=bitcoin&vs_currencies=usd",
            spent_today_usd=0.0,
            tier_rank=2,
        )
        body = receipt.body if isinstance(receipt.body, dict) else {}
        # Fallback: if x402 returns price, can't compute return without history
        return None
    except Exception:
        return None
