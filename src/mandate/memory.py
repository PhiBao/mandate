from __future__ import annotations

from pathlib import Path
from typing import Any

from sibyl_memory_client import MemoryClient
from sibyl_memory_client.exceptions import NotFoundError

from .records import Claim, MandateEvent, Verdict, stable_hash


def group_tenant(chat_id: str) -> str:
    return f"group:{chat_id}"


def member_tenant(chat_id: str, user_id: str) -> str:
    return f"member:{chat_id}:{user_id}"


def trader_tenant(chain: str, wallet: str) -> str:
    return f"trader:{chain}:{wallet.lower()}"


def ledger_tenant(chat_id: str) -> str:
    return f"ledger:{chat_id}"


class MandateMemory:
    def __init__(self, db_path: str | Path = "~/.mandate/memory.db") -> None:
        self._db_path = str(Path(db_path).expanduser())
        self._client = MemoryClient.local(self._db_path)

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def client(self) -> MemoryClient:
        return self._client

    def record_claim(self, claim: Claim) -> str:
        ref = trader_tenant(claim.chain, claim.wallet)
        self._client.set_tenant(member_tenant(claim.group_id, claim.user_id))
        self._client.set_entity(
            "claim",
            claim.wallet.lower(),
            {
                "trader_ref": ref,
                "message_hash": claim.message_hash,
                "claimed_at": claim.claimed_at,
                "anchor_tx": claim.anchor_tx,
            },
        )
        self._client.set_tenant(ref)
        try:
            existing = self._client.get_entity("identity", "current")
            claims = list(existing["body"]["claims"])
        except NotFoundError:
            claims = []
        claims.append(
            {
                "group_id": claim.group_id,
                "user_id": claim.user_id,
                "claimed_at": claim.claimed_at,
                "message_hash": claim.message_hash,
            }
        )
        self._client.set_entity("identity", "current", {"claims": claims})
        event_id = self._client.write_event(
            evaluated=[f"wallet {claim.wallet} claimed by user {claim.user_id} in group {claim.group_id}"],
            acted=[f"bound claim hash {claim.message_hash} at {claim.claimed_at}"],
            forward=["verify performance forward from claimed_at only"],
            extra={"kind": "claim", "message_hash": claim.message_hash},
        )
        return event_id

    def save_verdict(self, chain: str, wallet: str, verdict: Verdict) -> str:
        self._client.set_tenant(trader_tenant(chain, wallet))
        body = verdict.to_dict()
        try:
            current = self._client.get_entity("verdict", "current")
        except NotFoundError:
            current = None
        if current:
            body["supersedes"] = stable_hash(current["body"])
        self._client.set_entity("verdict", "current", body)
        return self._client.write_event(
            evaluated=[f"verdict distinguishable={verdict.distinguishable} n={verdict.n_trades}"],
            acted=[f"stored verdict over {verdict.n_trades} closed positions"],
            forward=[*verdict.reasons] if verdict.reasons else ["no_flags"],
            extra={"kind": "verdict"},
        )

    def get_verdict(self, chain: str, wallet: str) -> dict[str, Any] | None:
        self._client.set_tenant(trader_tenant(chain, wallet))
        try:
            found = self._client.get_entity("verdict", "current")
        except NotFoundError:
            return None
        return found["body"]

    def set_mandate(self, chain: str, wallet: str, event: MandateEvent) -> str:
        self._client.set_tenant(trader_tenant(chain, wallet))
        self._client.set_entity("mandate", "current", {"tier": event.to_tier, "since": event.at})
        return self._client.write_event(
            evaluated=[f"tier change {event.from_tier} -> {event.to_tier}"],
            acted=[event.reason],
            forward=["enforce authority per new tier"],
            extra={"kind": "mandate_event"},
        )

    def get_mandate(self, chain: str, wallet: str) -> dict[str, Any] | None:
        self._client.set_tenant(trader_tenant(chain, wallet))
        try:
            found = self._client.get_entity("mandate", "current")
        except NotFoundError:
            return None
        return found["body"]

    def mark_bootstrap_spend(self, chain: str, wallet: str) -> None:
        self._client.set_tenant(trader_tenant(chain, wallet))
        self._client.set_state("bootstrap_spend_used", {"used": True})

    def bootstrap_spend_used(self, chain: str, wallet: str) -> bool:
        self._client.set_tenant(trader_tenant(chain, wallet))
        state = self._client.get_state("bootstrap_spend_used")
        return bool(state and state["body"].get("used"))

    def append_ledger(self, chat_id: str, entry: dict[str, Any]) -> str:
        self._client.set_tenant(ledger_tenant(chat_id))
        return self._client.write_event(
            evaluated=[entry.get("what", "")],
            acted=[f"spent ${entry.get('price_usd', 0):.4f} via x402"],
            forward=["track cache savings"],
            extra=entry,
        )

    def append_position(self, chain: str, wallet: str, position: dict[str, Any]) -> str:
        self._client.set_tenant(trader_tenant(chain, wallet))
        return self._client.write_event(
            evaluated=[f"closed {position['asset']} {position['direction']} {position['return_pct']:+.4f}"],
            acted=["recorded closed position"],
            forward=["include in next verdict computation"],
            extra={"kind": "position", **position},
        )

    def read_positions(self, chain: str, wallet: str, limit: int = 500) -> list[dict[str, Any]]:
        from .records import Position

        self._client.set_tenant(trader_tenant(chain, wallet))
        events = self._client.read_events(limit=limit)
        out: list[dict[str, Any]] = []
        for e in events:
            extra = e.get("extra")
            if isinstance(extra, dict) and extra.get("kind") == "position":
                try:
                    Position(
                        open_at=extra["open_at"],
                        close_at=extra["close_at"],
                        asset=extra["asset"],
                        direction=extra["direction"],
                        entry_price=float(extra["entry_price"]),
                        exit_price=float(extra["exit_price"]),
                        return_pct=float(extra["return_pct"]),
                        notional_usd=float(extra["notional_usd"]),
                        quality=extra["quality"],
                    )
                    out.append(extra)
                except (KeyError, TypeError, ValueError):
                    continue
        return out

    def cache_evidence(self, chain: str, wallet: str, key: str, body: dict[str, Any]) -> None:
        self._client.set_tenant(trader_tenant(chain, wallet))
        self._client.set_reference(f"ev:{key}", body)

    def get_cached_evidence(self, chain: str, wallet: str, key: str) -> dict[str, Any] | None:
        self._client.set_tenant(trader_tenant(chain, wallet))
        found = self._client.get_reference(f"ev:{key}")
        if not found:
            return None
        raw = found.get("body")
        if isinstance(raw, str):
            import json as _json

            try:
                return _json.loads(raw)
            except ValueError:
                return None
        return raw

    def get_earliest_claimed_at(self, chain: str, wallet: str) -> str | None:
        self._client.set_tenant(trader_tenant(chain, wallet))
        try:
            identity = self._client.get_entity("identity", "current")
        except NotFoundError:
            return None
        claims = identity["body"].get("claims") or []
        if not claims:
            return None
        return min(c["claimed_at"] for c in claims if c.get("claimed_at"))

    def position_exists(self, chain: str, wallet: str, uid: str) -> bool:
        self._client.set_tenant(trader_tenant(chain, wallet))
        return self._client.get_reference(f"pos:{uid}") is not None

    def claim_tx_used(self, tx_hash: str) -> bool:
        self._client.set_tenant("claims:tx")
        return self._client.get_reference(f"claimtx:{tx_hash.lower()}") is not None

    def mark_claim_tx(self, tx_hash: str) -> None:
        self._client.set_tenant("claims:tx")
        self._client.set_reference(f"claimtx:{tx_hash.lower()}", {"used": True})

    def save_transfer_pending(self, key: str, body: dict) -> None:
        self._client.set_tenant("claims:pending")
        self._client.set_entity("transfer_pending", key, body)

    def load_transfer_pendings(self) -> list[dict]:
        self._client.set_tenant("claims:pending")
        try:
            ents = self._client.list_entities("transfer_pending")
        except Exception:
            return []
        out = []
        for e in ents or []:
            if isinstance(e, dict):
                out.append({"key": e.get("name", ""), "body": e.get("body", {}) or {}})
        return out

    def delete_transfer_pending(self, key: str) -> None:
        self._client.set_tenant("claims:pending")
        try:
            self._client.delete_entity("transfer_pending", key)
        except Exception:
            pass

    def spent_today_usd(self, chat_id: str) -> float:
        self._client.set_tenant(ledger_tenant(chat_id))
        try:
            events = self._client.read_events(limit=500)
        except Exception:
            return 0.0
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).date().isoformat()
        total = 0.0
        for e in events:
            extra = e.get("extra") or {}
            price = extra.get("price_usd")
            if price is None:
                continue
            at = (e.get("ts") or e.get("created_at") or "")[:10]
            if at == today:
                try:
                    total += float(price)
                except (TypeError, ValueError):
                    continue
        return total

    def incr_ask_count(self, chat_id: str, user_id: str) -> int:
        self._client.set_tenant(group_tenant(chat_id))
        key = f"ask:{user_id}"
        try:
            cur = self._client.get_reference(key)
            body = cur.get("body") if isinstance(cur, dict) else None
            if isinstance(body, str):
                import json as _json

                body = _json.loads(body)
            n = int((body or {}).get("count", 0)) + 1
        except Exception:
            n = 1
        self._client.set_reference(key, {"count": n})
        return n

    def get_ask_count(self, chat_id: str, user_id: str) -> int:
        self._client.set_tenant(group_tenant(chat_id))
        cur = self._client.get_reference(f"ask:{user_id}")
        if not cur:
            return 0
        body = cur.get("body")
        if isinstance(body, str):
            import json as _json

            try:
                body = _json.loads(body)
            except ValueError:
                return 0
        try:
            return int((body or {}).get("count", 0))
        except (TypeError, ValueError):
            return 0

    def search_traders(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        try:
            return self._client.search(query, limit=limit)
        except Exception:
            return []
