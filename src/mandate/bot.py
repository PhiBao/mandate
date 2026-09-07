from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .cards import CardData, Tier, render_standing, render_unverified_ask
from .claims import (
    build_claim_message,
    claim_digest,
    new_nonce,
    now_iso,
    verify_claim,
)
from .memory import MandateMemory, group_tenant, member_tenant
from .records import Claim
from .tiers import Tier


class Transport(Protocol):
    def send(self, chat_id: str, text: str) -> None: ...


@dataclass
class Update:
    chat_id: str
    user_id: str
    username: str
    text: str


@dataclass
class PendingClaim:
    wallet: str
    nonce: str
    issued_at: str
    message: str


@dataclass
class BotState:
    pending: dict[str, PendingClaim] = field(default_factory=dict)
    ask_counts: dict[str, int] = field(default_factory=dict)
    pending_transfers: dict[str, PendingTransfer] = field(default_factory=dict)


class MandateBot:
    def __init__(
        self,
        mem: MandateMemory,
        transport: Transport,
        *,
        claim_treasury: str = "",
        transfer_checker=None,
    ) -> None:
        self._mem = mem
        self._transport = transport
        self.state = BotState()
        self._claim_treasury = claim_treasury
        # transfer_checker(pending) -> (tx_hash, ts) | None; injectable for tests
        from .transfer_claim import find_matching_transfer

        self._transfer_checker = transfer_checker or find_matching_transfer

    def handle(self, update: Update) -> None:
        self._remember_username(update.chat_id, update.username, update.user_id)
        text = update.text.strip()
        if text.startswith("/claim"):
            self._handle_claim(update, text)
        elif text.startswith("/standing"):
            self._handle_standing(update)
        elif text.startswith("/why"):
            self._handle_why(update)
        elif text.startswith("/search"):
            self._handle_search(update)
        else:
            self._maybe_flag_unverified_call(update)

    def _remember_username(self, chat_id: str, username: str, user_id: str) -> None:
        if not username:
            return
        self._mem.client.set_tenant(group_tenant(chat_id))
        self._mem.client.set_entity("member_map", username, {"user_id": user_id})

    def _resolve_user_id(self, chat_id: str, username: str) -> str:
        self._mem.client.set_tenant(group_tenant(chat_id))
        try:
            ent = self._mem.client.get_entity("member_map", username)
            return ent["body"]["user_id"]
        except Exception:
            return username

    def _handle_claim(self, update: Update, text: str) -> None:
        parts = text.split()
        if len(parts) == 2 and not parts[1].startswith("0x") or len(parts) == 2 and len(parts[1]) < 20:
            self._transport.send(update.chat_id, "Usage: /claim <wallet> — I'll DM you what to sign.")
            return

        if len(parts) == 2:
            wallet = parts[1]
            nonce = new_nonce()
            issued = now_iso()
            message = build_claim_message("hyperliquid", wallet, update.chat_id, update.user_id, nonce, issued)
            self.state.pending[f"{update.chat_id}:{update.user_id}"] = PendingClaim(
                wallet=wallet, nonce=nonce, issued_at=issued, message=message
            )
            reply = (
                "Sign this exact message with the wallet's private key, then:\n"
                f"/claim {wallet} <signature>\n\n"
                f"{message}"
            )
            if self._claim_treasury:
                from .transfer_claim import build_pending, dm_text

                key = f"{update.chat_id}:{update.user_id}"
                pending = build_pending(update.chat_id, update.user_id, update.username, wallet)
                self.state.pending_transfers[key] = pending
                self._mem.save_transfer_pending(key, {
                    "chat_id": pending.chat_id,
                    "user_id": pending.user_id,
                    "username": pending.username,
                    "wallet": pending.wallet,
                    "amount_units": pending.amount_units,
                    "created_at": pending.created_at,
                    "expires_at": pending.expires_at,
                })
                reply = (
                    "EASIEST — send a tiny fee from the wallet you're claiming:\n\n"
                    f"{dm_text(pending, self._claim_treasury)}\n\n"
                    "———— OR ————\n\n"
                    + reply
                )
            self._transport.send(update.chat_id, reply)
            return

        if len(parts) == 3:
            key = f"{update.chat_id}:{update.user_id}"
            pending = self.state.pending.get(key)
            if not pending:
                self._transport.send(update.chat_id, "No pending claim. Start with /claim <wallet>.")
                return
            ok, reason = verify_claim(pending.message, parts[2], pending.wallet)
            if not ok:
                self._transport.send(update.chat_id, f"Claim rejected: {reason}")
                return
            claim = Claim(
                chain="hyperliquid",
                wallet=pending.wallet.lower(),
                group_id=update.chat_id,
                user_id=update.user_id,
                nonce=pending.nonce,
                message=pending.message,
                message_hash=claim_digest(pending.message),
                signature=parts[2],
                claimed_at=now_iso(),
            )
            self._mem.record_claim(claim)
            del self.state.pending[key]
            self._transport.send(
                update.chat_id,
                f"Claim verified and timestamped at {claim.claimed_at}.\n"
                f"Tracking is forward-only from this moment. Digest: {claim.message_hash[:18]}…",
            )
            return

        self._transport.send(update.chat_id, "Usage: /claim <wallet> or /claim <wallet> <signature>")

    async def tick(self) -> None:
        """Called once per polling cycle: settle pending transfer claims."""
        from .transfer_claim import PendingTransfer

        for saved in self._mem.load_transfer_pendings():
            body = saved.get("body", {}) or {}
            key = saved.get("key", "")
            if key and key not in self.state.pending_transfers and body.get("wallet"):
                try:
                    self.state.pending_transfers[key] = PendingTransfer(
                        chat_id=str(body.get("chat_id", "")),
                        user_id=str(body.get("user_id", "")),
                        username=str(body.get("username", "")),
                        wallet=str(body["wallet"]),
                        amount_units=int(body.get("amount_units", 0)),
                        created_at=str(body.get("created_at", "")),
                        expires_at=str(body.get("expires_at", "")),
                    )
                except (TypeError, ValueError):
                    continue
        if not self.state.pending_transfers:
            return
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        from .records import Claim
        from .claims import claim_digest

        for key, pending in list(self.state.pending_transfers.items()):
            expires = datetime.fromisoformat(pending.expires_at)
            if now > expires:
                del self.state.pending_transfers[key]
                self._mem.delete_transfer_pending(key)
                self._transport.send(
                    pending.chat_id,
                    f"Claim request for {pending.wallet} expired (10 min). "
                    "Send /claim <wallet> again to restart.",
                )
                continue
            try:
                found = await self._transfer_checker(
                    self._claim_treasury, pending.wallet, pending.amount_units, pending.created_at
                )
            except Exception:
                continue
            if not found:
                continue
            tx_hash, ts = found
            if self._mem.claim_tx_used(tx_hash):
                continue
            self._mem.mark_claim_tx(tx_hash)
            del self.state.pending_transfers[key]
            self._mem.delete_transfer_pending(key)
            claimed_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            message = (
                "Mandate wallet claim (transfer-proven)\n"
                f"chain: hyperliquid\n"
                f"wallet: {pending.wallet.lower()}\n"
                f"group: {pending.chat_id}\n"
                f"user: {pending.user_id}\n"
                f"nonce: transfer:{tx_hash}\n"
                f"issued_at: {claimed_at}\n"
                "Signing proves control of this wallet for forward-only verification."
            )
            claim = Claim(
                chain="hyperliquid",
                wallet=pending.wallet.lower(),
                group_id=pending.chat_id,
                user_id=pending.user_id,
                nonce=f"transfer:{tx_hash}",
                message=message,
                message_hash="0x" + tx_hash[2:].lower(),
                signature=tx_hash,
                claimed_at=claimed_at,
            )
            self._mem.record_claim(claim)
            self._transport.send(
                pending.chat_id,
                f"Fee received — {pending.wallet} claimed by @{pending.username} and "
                f"timestamped at {claimed_at} (block time, provable onchain).\n"
                "Tracking is forward-only from this moment.",
            )
            break  # one settlement per tick keeps pacing simple

    def _handle_standing(self, update: Update) -> None:
        parts = update.text.split()
        target = parts[1].lstrip("@") if len(parts) > 1 else update.username
        card = self._build_card(update.chat_id, target)
        self._transport.send(update.chat_id, render_standing(card))

    def _handle_why(self, update: Update) -> None:
        parts = update.text.split()
        target = parts[1].lstrip("@") if len(parts) > 1 else update.username
        card = self._build_card(update.chat_id, target)
        derivation = [
            "Wallet claims are signature-verified and timestamped on arrival.",
            "Closed positions are ingested forward from the earliest claim only.",
            "Positions flagged for data quality are excluded, never guessed.",
            "Mean return is bootstrapped (10k resamples) into a 95% CI.",
            "Verdict compares the CI lower bound against zero"
            + (" and the benchmark." if card.benchmark_return is not None else "."),
            "Tier follows deterministically from the verdict; no model in the loop.",
        ]
        from .cards import render_why

        self._transport.send(update.chat_id, render_why(card, derivation))

    def _handle_search(self, update: Update) -> None:
        parts = update.text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""
        if not query:
            self._transport.send(update.chat_id, "Usage: /search <query> — search traders and verdicts")
            return
        try:
            hits = self._mem.search_traders(query, limit=5)
        except Exception:
            hits = []
        if not hits:
            self._transport.send(update.chat_id, f'No matches for "{query}"')
            return
        lines = [f'Peers matching "{query}":']
        for h in hits[:5]:
            snippet = (h.get("text") or h.get("snippet") or str(h))[:120]
            lines.append(f"· {snippet}")
        self._transport.send(update.chat_id, "\n".join(lines))

    def _maybe_flag_unverified_call(self, update: Update) -> None:
        if update.text.startswith("@") or "long" in update.text.lower() or "short" in update.text.lower():
            try:
                n = self._mem.incr_ask_count(update.chat_id, update.user_id)
            except Exception:
                key = f"{update.chat_id}:{update.user_id}"
                self.state.ask_counts[key] = self.state.ask_counts.get(key, 0) + 1
                n = self.state.ask_counts[key]
            identity = self._identity_for(update.chat_id, update.user_id)
            if not identity:
                self._transport.send(
                    update.chat_id,
                    render_unverified_ask(f"@{update.username}", n),
                )

    def _identity_for(self, chat_id: str, user_id: str) -> dict[str, Any] | None:
        self._mem.client.set_tenant(member_tenant(chat_id, user_id))
        try:
            claims = self._mem.client.list_entities("claim")
        except Exception:
            return None
        return {"claims": claims} if claims else None

    def _build_card(self, chat_id: str, username: str) -> CardData:
        resolved = self._resolve_user_id(chat_id, username)
        identity = self._identity_for(chat_id, resolved)
        if not identity:
            try:
                asks = self._mem.get_ask_count(chat_id, resolved)
                if asks == 0 and resolved != username:
                    asks = self._mem.get_ask_count(chat_id, username)
            except Exception:
                asks = self.state.ask_counts.get(f"{chat_id}:{resolved}", 0)
                if asks == 0:
                    asks = self.state.ask_counts.get(f"{chat_id}:{username}", 0)
            return CardData(display_name=f"@{username}", tier=None, unverified_asks=asks)

        first = identity["claims"][0]
        body = first.get("body", {}) if isinstance(first, dict) else {}
        trader_ref = (body.get("trader_ref") if isinstance(body, dict) else None) or f"trader:hyperliquid:{first['name']}"
        _, chain, wallet = trader_ref.split(":", 2)
        stored = self._mem.get_verdict(chain, wallet)
        mandate = self._mem.get_mandate(chain, wallet)
        tier_name = (mandate or {}).get("tier", Tier.UNPROVEN.value)

        if not stored:
            return CardData(display_name=f"@{username}", tier=None, unverified_asks=0)

        return CardData(
            display_name=f"@{username}",
            tier=Tier(tier_name),
            n_trades=stored["n_trades"],
            win_rate=stored["win_rate"],
            mean_return=stored["mean_return"],
            ci_lo=stored["ci_lo"],
            ci_hi=stored["ci_hi"],
            window_days=stored["window_days"],
            benchmark_return=stored.get("benchmark_return"),
            excess_mean=stored.get("excess_mean"),
            max_drawdown=stored["max_drawdown"],
            wallets_claimed=len(identity["claims"]),
            flagged_positions=stored.get("flagged_positions", 0),
        )
