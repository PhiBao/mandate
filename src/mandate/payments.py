from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .budget import BudgetPolicy, SpendDecision, authorize_spend

if TYPE_CHECKING:
    from .memory import MandateMemory


class BudgetDenied(Exception):
    def __init__(self, decision: SpendDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


@dataclass(frozen=True)
class PaymentReceipt:
    url: str
    price_usd: float
    settled: bool
    body: object
    tx_hash: str | None = None


def _require_key() -> str:
    key = os.environ.get("MANDATE_EVM_PRIVATE_KEY", "")
    if not key:
        raise RuntimeError(
            "MANDATE_EVM_PRIVATE_KEY not set; live x402 purchases disabled until funded"
        )
    return key


def parse_payment_required(header_value: str | None) -> float | None:
    """Parse an x402 PAYMENT-REQUIRED header into a USD price on Base.

    Returns None whenever the header exists but cannot be priced for
    eip155:8453. Callers must treat None as deny — fail closed. A missing
    header is handled by the caller (a non-402 response means the resource
    is not paywalled and no payment will occur).
    """
    if not header_value:
        return None
    padded = header_value + "=" * (-len(header_value) % 4)
    try:
        import base64
        import json as _json

        payload = _json.loads(base64.b64decode(padded))
    except Exception:
        return None
    for req in payload.get("accepts") or []:
        if req.get("network") == "eip155:8453":
            amount = req.get("amount") or req.get("maxAmountRequired")
            if amount is not None:
                try:
                    return int(amount) / 1_000_000
                except (TypeError, ValueError):
                    return None
    return None


class X402Payer:
    def __init__(
        self,
        policy: BudgetPolicy | None = None,
        mem: MandateMemory | None = None,
    ) -> None:
        self.policy = policy or BudgetPolicy()
        self._mem = mem

    def authorize(
        self,
        probe: float | None,
        *,
        spent_today_usd: float,
        tier_rank: int,
        bootstrap_used: bool = False,
        chain: str | None = None,
        wallet: str | None = None,
    ) -> SpendDecision:
        if probe is None:
            return SpendDecision(False, "price_discovery_failed_fail_closed")
        if self._mem is not None and chain and wallet:
            bootstrap_used = self._mem.bootstrap_spend_used(chain, wallet)
        return authorize_spend(
            probe,
            spent_today_usd,
            self.policy,
            bootstrap_used=bootstrap_used,
            tier_rank=tier_rank,
        )

    async def fetch(
        self,
        url: str,
        *,
        spent_today_usd: float,
        tier_rank: int = 2,
        bootstrap_used: bool = False,
        chain: str | None = None,
        wallet: str | None = None,
        ledger_chat_id: str | None = None,
    ) -> PaymentReceipt:
        probe = await self._probe_price(url)
        decision = self.authorize(
            probe,
            spent_today_usd=spent_today_usd,
            tier_rank=tier_rank,
            bootstrap_used=bootstrap_used,
            chain=chain,
            wallet=wallet,
        )
        if not decision.allowed:
            raise BudgetDenied(decision)

        from eth_account import Account
        from x402 import x402Client
        from x402.http.clients import x402HttpxClient
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact.register import register_exact_evm_client

        account = Account.from_key(_require_key())
        client = x402Client()
        register_exact_evm_client(client, EthAccountSigner(account))

        async with x402HttpxClient(client) as http:
            response = await http.get(url)
            body = response.json()

        settled, tx_hash = self._read_settlement(response)

        if tier_rank == 0 and probe > 0 and self._mem is not None and chain and wallet:
            self._mem.mark_bootstrap_spend(chain, wallet)

        if ledger_chat_id and self._mem is not None and probe > 0:
            try:
                self._mem.append_ledger(
                    ledger_chat_id,
                    {
                        "what": url.split("/")[2] if "://" in url else url[:40],
                        "price_usd": probe,
                        "tx_hash": tx_hash,
                        "settled": settled,
                    },
                )
            except Exception:
                pass

        return PaymentReceipt(
            url=url, price_usd=probe, settled=settled, body=body, tx_hash=tx_hash
        )

    @staticmethod
    async def _probe_price(url: str) -> float | None:
        import httpx

        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.get(url, headers={"Accept": "application/json"})
        if resp.status_code != 402:
            return 0.0
        header = resp.headers.get("payment-required") or resp.headers.get(
            "Payment-Required"
        )
        return parse_payment_required(header)

    @staticmethod
    def _read_settlement(response: object) -> tuple[bool, str | None]:
        header = ""
        try:
            header = (
                response.headers.get("payment-response")
                or response.headers.get("x-payment-response")
                or ""
            )
        except AttributeError:
            return False, None
        if not header:
            return False, None
        try:
            from x402.http.utils import decode_payment_response_header

            settle = decode_payment_response_header(header)
            return bool(settle.success), settle.transaction or None
        except Exception:
            return False, None
