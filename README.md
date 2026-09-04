# Mandate — forward-only trader verification with earned mandates

**An agent that lives in a trading group chat, maintains an unfakeable longitudinal track record for every member, and converts that record into a revocable Earned Mandate — memory-derived authority to act.**

> Trading happens anywhere. Reputation settles on Base.

Live proof of Base minimal-real:

- **Wallet op (claim hash anchoring):** [`0xe4555aae22aef955232e8ffdcdce48b014638a596e70615ee5313128745943b0`](https://basescan.org/tx/0xe4555aae22aef955232e8ffdcdce48b014638a596e70615ee5313128745943b0) — block `50258124`, status `1`, `gasUsed 22280`. Input `0x5bb4c84b…` is `keccak(claim message)` — forward-only claim before outcome. Verifiable on Basescan without trusting our DB.
- **x402 payment (live USDC on Base):** `CoinGecko price`, USDC balance `1.345200 → 1.340200` at `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`. The `-0.005000` balance delta is the settlement proof; the `settled` field in `PaymentReceipt` was an unconditional literal in this run and proves nothing on its own. Probe returned `402` with a `1180`-byte requirements header; body `BTC 78051`. Second probe confirmed Nansen `$0.010` and Cambrian `$0.05` pricing; Omni `trader-profile` returns `500 internal_error`, so the Omni adapter is unexercised and the mock source is the working evidence path.

---

## What it does

A Telegram-native verifier for paid trading groups:

1. Member runs `/claim <wallet>` → bot DMs exact EIP-191 message with `nonce`+`issued_at` → member signs → `/claim <wallet> <sig>` → `recover_message` verifies signer==wallet, timestamp checked. Claim is **permanently timestamped** and binds `wallet ↔ Telegram user ↔ group`.
2. System ingests **closed positions forward from `claimed_at` only** (`HyperliquidFreeAdapter` free public API + `Omni` paid `$0.005` + `Mock` synthetic). Deduped by `position_uid` via `pos:{hash}` refs; quality-flagged excluded, counted. Normalizes to return series + window span.
3. **Bootstrap 10k resamples → 95% CI** on mean return. Compares `ci_lo` against `0` and `benchmark`, computes win rate, drawdown. If `ci_lo ≤ 0` → `"not distinguishable from luck"` — the honest line incumbents won't ship.
4. **Deterministic tier engine (no LLM):** `T0_unproven → T1_observed (≥10) → T2_credible (≥30 + distinguishable + risk PASS) → T3_trusted (≥100 + 60d + excess CI + drawdown)`. Immediate revocation on risk `WARN/BLOCK` or drawdown breach. Every promotion/demotion persisted with reasons.
5. Any call in chat gets a **standing card** — including `UNVERIFIED` (no wallet, ask count) which *is the first product signal*. `/standing` and `/why` show full derivation. Weekly digest + public credential page are second surfaces.

No custody. No auto-trading. No execution. Verification + authorization only.

Full product thesis, market, and build plan: [`SPEC.md`](SPEC.md) (23K, 11-point spec + 4 appendices).

---

## Where memory is load-bearing (gate)

**Delete Sibyl and the core function breaks structurally, not decoratively:**

- Every `Claim`'s integrity is `claimed_at` being before the outcome. Without memory, every claim is retroactive — the verifier is worthless, not degraded.
- Every `Verdict` + `MandateEvent` + `Position` journal entry is gone. No mandate can be issued; nothing can be recomputed because the underlying history no longer exists.
- `UNVERIFIED` pressure loop loses its `ask_counts`; multi-wallet cherry-picking defense (all claims aggregated) is gone.

**A judge can find the critical path in <2 minutes:**

| Operation | Location |
|-----------|----------|
| **Claim write** | `src/mandate/memory.py:41` `record_claim()` → `set_entity("claim",…)` + `write_event(kind="claim")` + `member_map` |
| **Positions journal** | `src/mandate/memory.py:138` `append_position()` → `write_event(extra={kind:"position"…})` |
| **Verdict store + supersession** | `src/mandate/memory.py:77` `save_verdict()` → `set_entity("verdict","current",{…,supersedes:sha256(prev)})` + `write_event(kind="verdict")` |
| **Mandate state** | `src/mandate/memory.py:102` `set_mandate()` → `set_entity("mandate","current")` + `write_event(kind="mandate_event")` |
| **Claim read / verify** | `src/mandate/claims.py:50` `verify_claim()` + `src/mandate/bot.py:71` `_resolve_user_id()` via `group:<chat>` `member_map` |
| **Verdict read (fresh session)** | `src/mandate/memory.py:94` `get_verdict()` + `src/mandate/verdicts.py:54` `evaluate_trader()` — re-opens `MandateMemory(db_path)` cold, no in-memory state |
| **Budget gate before spend** | `src/mandate/payments.py:75` `X402Payer.authorize()` → `src/mandate/budget.py:18` `authorize_spend()`, called from `fetch()` (`payments.py:97`) before any key load or signing; price-discovery failure denies fail-closed (`payments.py:37` `parse_payment_required`) |
| **Ask count (persistent)** | `src/mandate/memory.py:230` `incr_ask_count()` / `:246` `get_ask_count()` via `group:<chat>` `ask:{user_id}` refs — survives restart |
| **Evidence cache + dedup** | `src/mandate/evidence/hyperliquid_free.py:95` + `omni.py:27` fetch via `get_cached_evidence()` before network; `verdicts.py:24` dedups ingest via `pos:{uid}` (`records.py:110`) |
| **Mandate auto-persist** | `src/mandate/verdicts.py:109` `evaluate_trader()` calls `set_mandate()` on tier change — no manual step |

Tenancy (`src/mandate/memory.py:12-25`): `group:<chat>`, `member:<chat>:<user>`, `trader:<chain>:<wallet>`, `ledger:<chat>` — coordination pattern that tops the 40-point band; dynamic storage is `Verdict` supersession + `pos:{uid}` dedup + `ev:{key}` cache (REFERENCE tier).

**Cold-start recall demo (required unedited segment):** Run `tests/test_pipeline.py:TestEndToEndPipeline.test_verdict_survives_fresh_process` — writes with one `MandateMemory`, re-opens with a new `MandateMemory(db_path)` in a fresh process, `get_verdict()` returns the same `distinguishable=True`. For the video: start a new `python` process, `MandateMemory("~/.mandate/memory.db")`, `/standing @alice` shows `CREDIBLE` without any prior `ingest` in that process. Show commit hash + timestamp on screen.

**Deletion test to run:** `rm ~/.mandate/memory.db` (or truncate the DB file) → every `get_verdict()` returns `None`, `get_mandate()` `None`, all `/standing` → `UNVERIFIED`, bot refuses mandates. The loss is permanent: forward-only claim timing cannot be reconstructed retroactively, so no amount of re-ingestion rebuilds the record.

---

## Memory wiring status

All core memory paths are now exercised — either via tests or live code. One ledger path remains opt-in.

| Component | Location | Status |
|-----------|----------|--------|
| Evidence cache | `src/mandate/memory.py:173` / `:177` | **Wired**: `hyperliquid_free.py:95` + `omni.py:27` check `get_cached_evidence()` before fetch, write via `cache_evidence()` with 6h TTL; verified in `tests/test_fixes.py` |
| Position dedup | `src/mandate/memory.py:203` + `verdicts.py:24` | **Wired**: ingest skips duplicate `pos:{uid}` refs; `position_uid` in `records.py:110` |
| Cost ledger | `src/mandate/memory.py:129` | **Wired (opt-in)**: `X402Payer.fetch(ledger_chat_id=…) -> append_ledger()` (`payments.py:138`); adapter threads it when caller supplies `ledger_chat_id` |
| Bootstrap spend flag | `src/mandate/memory.py:120` / `:124` | **Wired**: `X402Payer(mem=…)` read in `authorize()` (`payments.py:88`) + mark after paid T0 fetch (`:137`) |
| Ask counts | `src/mandate/memory.py:230` / `:246` | **Wired**: `bot.py:177` `incr_ask_count()` survives restart; `tests/test_fixes.py` proves fresh `MandateMemory(db_path)` sees same count |
| Search | `src/mandate/memory.py:264` `search_traders()` | **Wired**: `bot.py:155` `/search` command surfaces FTS5 hits |

---

## Which partner stacks and where

**Base — settlement & trust (live, minimal-real):**

- **Wallet op (live):** `0xe4555a…5943b0` block `50258124` — `claim hash` in calldata, self-tx `to==from`. Qualifies as `wallet operation` per `rules:Base`. Proves claim timing without trusting DB. Also `anchor_calldata()` in `src/mandate/anchor.py:25` and `contracts/ClaimAnchor.sol:10` (event-only; `anchor(bytes32,venue)` at `:12`, `anchorBatch` at `:16`).
- **x402 payment (live):** `src/mandate/payments.py:66` `X402Payer` (`x402HttpxClient` + `EthAccountSigner` + `register_exact_evm_client`) on `eip155:8453` USDC `0x8335…2913`. Budget gate runs before any signing: `authorize()` (`payments.py:75`) calls `authorize_spend()` (`budget.py:18`) against the probed price, and unpriceable 402 requirements deny fail-closed (`parse_payment_required`, `payments.py:37`). Settlement proof is decoded from the `PAYMENT-RESPONSE` header into `PaymentReceipt.tx_hash` (`payments.py:156`). T0 wallets get one memory-tracked discovery fetch per trader (`memory.py:120`), enforced at `budget.py:30`. Evidence now prefers `HyperliquidFreeAdapter` (`evidence/hyperliquid_free.py:73`, free `https://api.hyperliquid.xyz/info`, cached via `ev:hl_free:*` + `pos:{uid}` dedup); `OmniHyperliquidAdapter` (`evidence/omni.py:19`, `$0.005`) is the paid fallback — currently `500 internal_error`, so `MockHyperliquidSource` is the demo fallback.
- **How to verify:** Basescan tx + grep `"x402"` in `src/mandate/payments.py` + run live probe script below.

**Virtuals — not integrated (declared stretch):**

- No ACP code exists in `src/` yet. `@virtuals-protocol/acp-cli` `1.0.32` is installed and OAuth setup is blocked at `NO_ACTIVE_AGENT` (`acp configure → agent create → add-signer → wallet topup`). Plan: hire a second-opinion evaluator on `T2→T3` promotion and register this verifier as a purchasable ACP service (`SPEC.md:Appendix C`). Until then this submission claims Base only.

**Sibyl — mandatory, never a multiplier:** `sibyl-memory-client 0.6.1` SQLite/FTS5, `MemoryClient.local(path)` — file-based, zero embeddings.

---

## How memory made this possible

- **Forward-only is time, not cryptography.** The block timestamp (Base) + `claimed_at` in Sibyl together prove the claim existed before the outcome — the one thing screenshots cannot do.
- **Statistical honesty requires history.** Bootstrap CI, min-N gates, benchmark excess, drawdown all need *N observations over time*. One session produces zero value — the definition of load-bearing.
- **Supersession needs durable storage.** Every recomputation appends a new verdict and supersedes the old one (`memory.py:77`); the derivation trail survives restarts because it lives in Sibyl, not process state.
- **Multi-wallet aggregation is enforceable only with persistent memory.** Without it, a trader claims 5 wallets and promotes the winner — with it, `trader:<chain>:<wallet>` aggregates all claims permanently and the card shows `2 wallets claimed, both counted`.

---

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .[dev]          # or pip install sibyl-memory-client eth-account httpx "x402[httpx,evm]" pytest
pytest -q                      # 73 tests, premise gate included
```

Live Telegram + Base (minimal-real):

```bash
cp .env.example .env
# edit .env: MANDATE_TELEGRAM_TOKEN (from @BotFather), MANDATE_EVM_PRIVATE_KEY (0x…), optional MANDATE_CLAIM_ANCHOR
python -m mandate.main         # polling runner: getUpdates → MandateBot → Sibyl
```

Live x402 probe (free) and paid fetch (requires USDC on Base):

```bash
python - <<'PY'
import asyncio, os
os.environ["MANDATE_EVM_PRIVATE_KEY"] = open(".env").read().split("MANDATE_EVM_PRIVATE_KEY=")[1].split()[0].strip()
from mandate.payments import X402Payer
import asyncio
async def f():
    r = await X402Payer().fetch("https://coingecko.use.x402atlas.com/price?ids=bitcoin&vs_currencies=usd", spent_today_usd=0.0, tier_rank=2)
    print(r.price_usd, r.body)
asyncio.run(f())
PY
```

Demo wallets (paper by default, deterministic):

```python
from mandate.evidence.mock import MockHyperliquidSource
from mandate.verdicts import VerdictService
from mandate.memory import MandateMemory
mem = MandateMemory("~/.mandate/memory.db")
svc = VerdictService(mem)
w = "0x" + "ab"*20
svc.ingest("hyperliquid", w, MockHyperliquidSource(w, mean=0.03, sd=0.08, n=60, seed=7).fetch_closed_positions())
ev = svc.evaluate_trader("hyperliquid", w, risk_screen="pass", seed=42)
print(ev.tier, ev.verdict.distinguishable)
```

---

## Prior Work Declaration

- **Authorship disclosure:** the core engine (stats, tier ladder, claim verification, Sibyl persistence) was written during the prep window before Sep 1; commits in this repo began in the prep window and continue through the build window. Flagging this explicitly rather than letting commit dates imply otherwise.
- **Prep-window wallet ops (before Sep 1):** raw self-txs anchoring demo claim hashes in calldata (wallet activity, not project code) — e.g. `0xe4555a…5943b0`.
- **Live dependencies probed, not vendored:** Sibyl SDK, x402 SDK, Base RPC, CoinGecko/Nansen/Cambrian 402 pricing. No private Sibyl data used.

---

## Validation

- **73 tests:** `pytest -q` — core statistical premise (`tests/test_stats.py:TestPremiseGate`), tier ladder, claim EIP-191, budget gates incl. fail-closed price discovery and bootstrap wiring (`tests/test_payments_gate.py`), ingest idempotency + mandate auto-persist + forward-only + ask-count persistence + Hyperliquid free cache (`tests/test_fixes.py`), Sibyl round-trip + supersession + fresh-process recall, bot 5-state flows incl. `/search`, anchor/digest.
- **The premise gate test** is `tests/test_stats.py:TestPremiseGate` — synthetic skilled (`mean 0.03 sd 0.08 n 60`) must be `distinguishable`, lucky (`0.02 sd 0.45 n 40`) must not.
- **Live verification performed:** Base wallet `0x4Ba1…1D73` `0.000247 ETH` + `1.340200 USDC`, wallet op mined, x402 `$0.005` settlement verified with USDC deduction.

---

## Security

- EIP-191 `recover_message` check, `issued_at` expiry (1h, 5m future grace), template validation, nonce per claim.
- Tier is deterministic arithmetic — no LLM in authority path; stored evidence never carries instruction authority.
- Budget caps (`daily_cap`, `per_call_cap`) enforced before the key is even loaded — `authorize()` runs before `_require_key()`; unpriceable 402 requirements deny fail-closed; T0 spend limited to one memory-tracked discovery fetch per trader.
- `.env` never committed (`.gitignore`), hot EOA only, no user keys held, fail-closed on memory outage, abstain on data-quality flags.

See `SPEC.md` for full 11-point spec, threat model, and 10-day build plan.

## License

MIT — see `LICENSE`.
