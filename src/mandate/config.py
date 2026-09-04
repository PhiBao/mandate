from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: str
    telegram_token: str
    evm_private_key: str
    daily_budget_usd: float
    per_call_cap_usd: float
    claim_anchor_address: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_path=os.environ.get("MANDATE_DB_PATH", "~/.mandate/memory.db"),
            telegram_token=os.environ.get("MANDATE_TELEGRAM_TOKEN", ""),
            evm_private_key=os.environ.get("MANDATE_EVM_PRIVATE_KEY", ""),
            daily_budget_usd=float(os.environ.get("MANDATE_DAILY_BUDGET_USD", "5.00")),
            per_call_cap_usd=float(os.environ.get("MANDATE_PER_CALL_CAP_USD", "0.05")),
            claim_anchor_address=os.environ.get("MANDATE_CLAIM_ANCHOR", ""),
        )

    def require_telegram(self) -> str:
        if not self.telegram_token:
            raise RuntimeError("MANDATE_TELEGRAM_TOKEN not set")
        return self.telegram_token

    def require_key(self) -> str:
        if not self.evm_private_key:
            raise RuntimeError("MANDATE_EVM_PRIVATE_KEY not set")
        return self.evm_private_key
