import asyncio
import base64
import json

import pytest

from mandate.budget import BudgetPolicy
from mandate.evidence.cambrian import CambrianContrastAdapter
from mandate.evidence.omni import OmniHyperliquidAdapter
from mandate.memory import MandateMemory
from mandate.payments import BudgetDenied, PaymentReceipt, X402Payer, parse_payment_required


def _requirements_header(amount: str, network: str = "eip155:8453") -> str:
    payload = {"x402Version": 2, "accepts": [{"network": network, "amount": amount}]}
    return base64.b64encode(json.dumps(payload).encode()).decode()


class TestParsePaymentRequired:
    def test_valid_base_requirement_returns_usd_price(self):
        assert parse_payment_required(_requirements_header("5000")) == 0.005

    def test_missing_header_is_none(self):
        assert parse_payment_required(None) is None

    def test_garbage_header_is_none(self):
        assert parse_payment_required("not-base64!!!") is None

    def test_wrong_network_only_is_none(self):
        header = _requirements_header("5000", network="solana:mainnet")
        assert parse_payment_required(header) is None

    def test_unparsable_amount_is_none(self):
        assert parse_payment_required(_requirements_header("abc")) is None


class TestAuthorizeFailClosed:
    def test_failed_price_discovery_denies_even_with_headroom(self):
        payer = X402Payer(BudgetPolicy(daily_cap_usd=100.0))
        decision = payer.authorize(None, spent_today_usd=0.0, tier_rank=2)
        assert not decision.allowed
        assert "fail_closed" in decision.reason

    def test_free_probe_still_allowed(self):
        payer = X402Payer()
        assert payer.authorize(0.0, spent_today_usd=0.0, tier_rank=2).allowed


class TestBootstrapWiring:
    def test_tier0_first_call_allowed_then_denied_via_memory(self, tmp_path):
        mem = MandateMemory(tmp_path / "gate.db")
        payer = X402Payer(mem=mem)
        chain, wallet = "hyperliquid", "0x" + "b" * 40

        first = payer.authorize(
            0.005, spent_today_usd=0.0, tier_rank=0, chain=chain, wallet=wallet
        )
        assert first.allowed

        mem.mark_bootstrap_spend(chain, wallet)

        second = payer.authorize(
            0.005, spent_today_usd=0.0, tier_rank=0, chain=chain, wallet=wallet
        )
        assert not second.allowed
        assert "bootstrap_already_used" in second.reason

    def test_without_memory_handle_kwarg_flag_still_gates(self):
        payer = X402Payer()
        denied = payer.authorize(
            0.005,
            spent_today_usd=0.0,
            tier_rank=0,
            bootstrap_used=True,
        )
        assert not denied.allowed


class TestFetchOrdering:
    def test_denial_happens_before_key_load(self, monkeypatch):
        monkeypatch.delenv("MANDATE_EVM_PRIVATE_KEY", raising=False)

        async def fake_probe(url: str) -> float | None:
            return None

        monkeypatch.setattr(X402Payer, "_probe_price", staticmethod(fake_probe))
        payer = X402Payer()

        with pytest.raises(BudgetDenied) as excinfo:
            asyncio.run(payer.fetch("https://example.com/data", spent_today_usd=0.0))

        assert "fail_closed" in str(excinfo.value)


class _RecordingPayer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def fetch(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return PaymentReceipt(url=url, price_usd=0.005, settled=True, body={})


class TestAdapterSpendPassthrough:
    def test_omni_threads_spend_and_trader_identity(self):
        payer = _RecordingPayer()
        adapter = OmniHyperliquidAdapter(payer=payer)
        wallet = "0x" + "c" * 40

        batch = asyncio.run(
            adapter.fetch_closed_positions(wallet, spent_today_usd=0.02)
        )

        _, kwargs = payer.calls[0]
        assert kwargs["spent_today_usd"] == 0.02
        assert kwargs["chain"] == "hyperliquid"
        assert kwargs["wallet"] == wallet
        assert batch.source == "omni:hyperliquid"

    def test_cambrian_threads_spend(self):
        payer = _RecordingPayer()
        adapter = CambrianContrastAdapter(payer=payer)

        asyncio.run(adapter.fetch_contrast(spent_today_usd=0.01))

        _, kwargs = payer.calls[0]
        assert kwargs["spent_today_usd"] == 0.01
