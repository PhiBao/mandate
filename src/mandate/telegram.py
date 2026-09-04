from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from .bot import MandateBot, Update

API_BASE = "https://api.telegram.org"


class TelegramTransport:
    def __init__(self, token: str, base_url: str = API_BASE) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._a_client = httpx.AsyncClient(timeout=30.0)

    def send(self, chat_id: str, text: str) -> None:
        url = f"{self._base_url}/bot{self._token}/sendMessage"
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json={"chat_id": chat_id, "text": text})
            resp.raise_for_status()

    async def poll_updates(self, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        url = f"{self._base_url}/bot{self._token}/getUpdates"
        resp = await self._a_client.get(url, params={"offset": offset, "timeout": 25})
        resp.raise_for_status()
        data = resp.json()
        updates = data.get("result", [])
        next_offset = updates[-1]["update_id"] + 1 if updates else offset
        return updates, next_offset

    async def close(self) -> None:
        await self._a_client.aclose()


def parse_update(raw: dict[str, Any]) -> Update | None:
    msg = raw.get("message") or raw.get("edited_message")
    if not msg:
        return None
    chat = msg.get("chat", {})
    sender = msg.get("from", {})
    text = msg.get("text") or msg.get("caption") or ""
    if not text:
        return None
    return Update(
        chat_id=str(chat.get("id", "")),
        user_id=str(sender.get("id", "")),
        username=sender.get("username") or sender.get("first_name") or "anon",
        text=text,
    )


class PollingRunner:
    def __init__(self, bot: MandateBot, transport: TelegramTransport) -> None:
        self._bot = bot
        self._transport = transport
        self._offset = 0

    async def run_once(self) -> int:
        raw_updates, self._offset = await self._transport.poll_updates(self._offset)
        for raw in raw_updates:
            upd = parse_update(raw)
            if upd is None:
                continue
            self._bot.handle(upd)
        return len(raw_updates)

    async def run_forever(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                await asyncio.sleep(2.0)


def sync_send(token: str, chat_id: str, text: str) -> None:
    url = f"{API_BASE}/bot{token}/sendMessage"
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, json={"chat_id": chat_id, "text": text})
        resp.raise_for_status()
