# Mandate — forward-only trader verification with earned mandates

**An agent that lives in a trading group chat, maintains an unfakeable longitudinal track record for every member, and converts that record into a revocable Earned Mandate — memory-derived authority to act.**

> Trading happens anywhere. Reputation settles on Base.

Mandate is a Telegram-native verifier for paid trading groups. Members bind a wallet with an onchain-timestamped claim; closed positions are ingested **forward from the claim timestamp only**; a deterministic statistical engine decides whether the record is skill or luck; tiers gate revocable authority. No custody, no auto-trading, no execution — verification and authorization only.

---

## The problem

Paid trading groups (200–5,000 members, $50–500/mo) run on screenshots: backward-looking, selectively sampled, unfalsifiable. Callers who were wrong quietly stop posting; callers who were lucky post louder. The operator's entire asset is reputation, and they have no instrument to verify it. Executors (BONKbot, Maestro, Photon) copy trades but never ask whether the target trader was any good. Leaderboards (GMGN, Hyperliquid) reward retroactive capital bias. Credibility scores (Cambrian deep42) rank by tweet volume — their formula contains no accuracy term.

Mandate turns every call into a checkable claim against a forward-only, timestamped, capital-at-risk record — and makes the *absence* of a claim visible.

## What it does

1. **Claim.** Member runs `/claim <wallet>` → the bot DMs the exact EIP-191 message → member signs → `/claim <wallet> <sig>` → signature recovered, timestamp checked, claim recorded. The claim binds `wallet ↔ Telegram user ↔ group`, is permanent, and its hash is anchored on Base (`ClaimAnchor` contract or raw calldata self-tx), so claim timing is provable without trusting our database.
2. **Track.** Closed positions are ingested **from `claimed_at` only** through a venue adapter (free public Hyperliquid API by default; paid x402 sources as fallbacks). Positions are deduped by `position_uid`, quality-flagged positions are excluded — counted, never guessed — and normalized into a return series.
3. **Judge.** Bootstrap 10k resamples → 95% CI on mean return. `ci_lo ≤ 0` ⇒ *"not distinguishable from luck"* — the honest line incumbents won't ship. Excess vs benchmark over the identical window prevents beta-as-skill; drawdown and win rate complete the picture.
4. **Mandate.** A deterministic tier engine (no LLM) maps the verdict to `T0_unproven → T1_observed → T2_credible → T3_trusted`, promotes/demotes with persisted reasons, and revokes immediately on risk or drawdown breach.
5. **Show.** Any call in chat gets a standing card — including `UNVERIFIED` for members who never claimed, with a persistent ask counter. `/standing` and `/why` expose the full derivation. A weekly digest and a public credential page are second surfaces.

---

## Where memory is load-bearing (gate)

**Delete Sibyl and the core function breaks structurally, not decoratively:**

- Every `Claim`'s integrity is `claimed_at` being before the outcome. Without memory, every claim is retroactive — the verifier is worthless, not degraded. Forward-only timing cannot be reconstructed after deletion.
- Every `Verdict`, `MandateEvent`, and `Position` journal entry is gone. No mandate can be issued; nothing can be recomputed because the underlying history no longer exists.
- The `UNVERIFIED` pressure loop loses its persisted `ask_counts`; multi-wallet cherry-picking defense (all claims aggregated per trader tenant) is gone.

**A judge can find the critical path in under two minutes:**

| Operation | Location |
|-----------|----------|
| **Claim write** | `src/mandate/memory.py:41` `record_claim()` → `set_entity("claim",…)` + `write_event(kind="claim")` + member_map |
| **Positions journal** | `src/mandate/memory.py:138` `append_position()` → `write_event(extra={kind:"position"…})` |
| **Verdict store + supersession** | `src/mandate/memory.py:77` `save_verdict()` → `set_entity("verdict","current",{…,supersedes:sha256(prev)})` + `write_event(kind="verdict")` |
| **Mandate state** | `src/mandate/memory.py:102` `set_mandate()` → `set_entity("mandate","current")` + `write_event(kind="mandate_event")` |
| **Claim read / verify** | `src/mandate/claims.py:50` `verify_claim()` + `src/mandate/bot.py:71` `_resolve_user_id()` via `group:<chat>` `member_map` |
| **Verdict read (fresh session)** | `src/mandate/memory.py:94` `get_verdict()` + `src/mandate/verdicts.py:54` `evaluate_trader()` — re-opens `MandateMemory(db_path)` cold, no in-memory state |
| **Forward-only cutoff** | `src/mandate/memory.py:192` `get_earliest_claimed_at()` |
| **Budget gate before spend** | `src/mandate/payments.py:75` `X402Payer.authorize()` → `src/mandate/budget.py:18` `authorize_spend()`, called from `fetch()` before any key load or signing; unpriceable 402 requirements deny fail-closed |
| **Ask count (persistent)** | `src/mandate/memory.py:230` `incr_ask_count()` / `:246` `get_ask_count()` — survives restart |
| **Evidence cache + dedup** | `src/mandate/memory.py:173` / `:177`; `verdicts.py:24` dedups ingest via `pos:{uid}` |

**Tenancy model** (`src/mandate/memory.py:12-25`): `group:<chat>`, `member:<chat>:<user>`, `trader:<chain>:<wallet>`, `ledger:<chat>` — a coordination pattern, not a notepad. Dynamic storage: verdict supersession chains, `pos:{uid}` dedup, `ev:{key}` evidence cache (REFERENCE tier), `ask:{user}` pressure counters.

**Fresh-session recall (required unedited demo segment):** a new `python` process opens `MandateMemory(db_path)` cold and `get_verdict()` returns the identical verdict — no ingest in that process, commit hash + timestamp on screen. `tests/test_pipeline.py:TestEndToEndPipeline.test_verdict_survives_fresh_process` proves it in CI.

**Deletion test:** `rm ~/.mandate/memory.db` → every `get_verdict()` returns `None`, all `/standing` collapse to `UNVERIFIED`, the bot refuses mandates fail-closed. The loss is permanent — the forward-only timeline cannot be re-derived retroactively.

---

## Which partner stacks, and where

**Base — settlement & trust (live, verified on Basescan):**

- **Claim anchoring (wallet op):** claim hash in calldata of a self-tx; block timestamp proves the claim existed before the outcome.
  - Live demo wallet claim (2026-09-05): [`0xc9344b33…8be0f4`](https://basescan.org/tx/0xc9344b33a6ea5b5cea2ea30612a3b5e8bd43f1999afc11507c736b2fca8be0f4) — block `50258124`-family, gas `22280`. Code path: `src/mandate/anchor.py:25`, `contracts/ClaimAnchor.sol` (event-only `anchor(bytes32,venue)` + `anchorBatch`).
  - Prep-window demo claims: [`0xe4555aae…5943b0`](https://basescan.org/tx/0xe4555aae22aef955232e8ffdcdce48b014638a596e70615ee5313128745943b0) — block `50258124`.
- **x402 payment (live USDC on Base):** `src/mandate/payments.py:66` `X402Payer` (`x402HttpxClient` + `EthAccountSigner` + `register_exact_evm_client`) on `eip155:8453`, USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`. A probe fetched `BTC 78051` from a 402-gated endpoint; settlement proof is the onchain USDC delta (`1.345200 → 1.340200`), decoded from the `PAYMENT-RESPONSE` header into `PaymentReceipt.tx_hash`. The budget gate (`authorize_spend`) runs **before** the key is loaded; unpriceable requirements deny fail-closed. T0 wallets get one memory-tracked discovery fetch per trader, enforced at `src/mandate/budget.py:30`.

**Virtuals — agent commerce (live ACP):**

- ACP agent **`mandate-verifier`** registered on Virtuals (wallet `0xc0a1374c…172e`), funded on Base USDC, restricted-policy signer, **live provider offering** `verdict_verification` ($0.01 fixed, 15-min SLA) — forward-only verification purchasable by any ACP agent.
- **ACP job #76381** (`evaluate_trading`): **completed onchain** — `job.created → budget.set (0.99 USDC) → job.funded (escrow on Base 8453) → job.submitted → job.completed`, escrow released. Full happy-path ACP v2 lifecycle.
- Three further funded jobs (#76354, #76369, #76375) exercised the evaluator-controlled path: each deliverable came back `insufficientData` (the evaluator's index does not cover agents created this week) and was **honestly rejected with refunds** rather than paid for — evaluation cuts both ways.
- Job #76376 (ExecutionProof `verifySwapExecution`, $0.01) requests independent onchain verification of real swap `0x8f7474e6…d7f8` (WETH→USDC, min-out honored); open with the provider.
- All job lifecycles are journaled in Sibyl (`kind: acp_job`, cost ledger) — agent commerce is part of the persistent record, not a side demo.

**Sibyl — mandatory, never a multiplier:** `sibyl-memory-client` 0.6.1 (SQLite/FTS5, `MemoryClient.local(path)`), file-based, zero embeddings, zero vector DB.

---

## How memory made this possible

- **Forward-only is time, not cryptography.** The Base block timestamp + `claimed_at` in Sibyl together prove the claim existed before the outcome — the one thing screenshots cannot do.
- **Statistical honesty requires history.** Bootstrap CI, min-N gates, benchmark excess, and drawdown all need N observations accumulated over time. One session produces zero value — which is the definition of load-bearing.
- **Supersession needs durable storage.** Every recomputation appends a new verdict and supersedes the old one; the derivation trail survives restarts because it lives in Sibyl, not process state.
- **Multi-wallet aggregation is enforceable only with persistent memory.** Without it, a trader claims 5 wallets and promotes the winner; with it, `trader:<chain>:<wallet>` aggregates all claims permanently and the card shows `2 wallets claimed, both counted`.
- **Refusal is a signal only if remembered.** The `UNVERIFIED — Asked 4 times` card is the product's day-1 value, and it only works because ask counts survive restarts.

---

## Live evidence (this build, this window)

| What | Proof |
|------|-------|
| Demo wallet claim timestamped | Sibyl journal, `claimed_at 2026-09-05T02:16:59Z`, anchored at [`0xc9344b33…`](https://basescan.org/tx/0xc9344b33a6ea5b5cea2ea30612a3b5e8bd43f1999afc11507c736b2fca8be0f4) |
| Real perp trade, after the claim | long 0.0043 ETH @ $2451.4 → closed @ $2451.3 on Hyperliquid, fills `536629282544` / `536629444865` |
| Real ingest → verdict on the live bot DB | free public-API adapter, forward-only since claim; `T0_unproven, n=1, distinguishable=False` |
| x402 paid fetch with settlement | 402 probe → USDC delta −$0.005 on Base |
| Real Base swap (this window) | `0x8f7474e6…d7f8` — WETH→USDC via Uniswap V3, 0.737472 USDC out vs 0.70 min, block 50900413 |
| ACP job lifecycle (Virtuals) | **#76381 completed** (created→funded→submitted→completed, escrow released); #76354/#76369/#76375 funded + honest rejects with refund; #76376 swap verification open; `verdict_verification` offering live |

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .[dev]
pytest -q                      # 73 tests, premise gate included
```

Live Telegram + Base:

```bash
cp .env.example .env
# edit .env: MANDATE_TELEGRAM_TOKEN, MANDATE_EVM_PRIVATE_KEY (0x…), optional MANDATE_CLAIM_ANCHOR
python -m mandate.main         # polling runner: getUpdates → MandateBot → Sibyl
```

Demo wallets (deterministic, paper):

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

## Validation

- **73 tests:** `pytest -q` — statistical premise gate (`tests/test_stats.py:TestPremiseGate`: synthetic skilled separates, lucky does not), tier ladder, claim EIP-191, budget gates incl. fail-closed price discovery, ingest idempotency + mandate auto-persist + forward-only + ask-count persistence, Sibyl round-trip + supersession + fresh-process recall, bot 5-state flows, anchor/digest.
- **Live verification performed:** Base anchor tx mined; x402 settlement verified by USDC balance delta; real HL trade ingested into the live bot DB and evaluated.

## Security

- EIP-191 `recover_message` check, `issued_at` expiry (1h, 5m future grace), template validation, per-claim nonce.
- Tier is deterministic arithmetic — no LLM in the authority path; stored evidence never carries instruction authority.
- Budget caps (`daily_cap`, `per_call_cap`) enforced before the key is even loaded; unpriceable 402 requirements deny fail-closed; T0 spend limited to one memory-tracked discovery fetch per trader.
- `.env` never committed; hot EOA with a small float; **never holds user keys — no custody by design**; fail-closed on memory outage; abstains on data-quality flags.

## Prior Work Declaration

- **Authorship disclosure:** the core engine (stats, tier ladder, claim verification, Sibyl persistence) was written during the prep window before Sep 1; the first commits predate the build window. Declared explicitly rather than letting commit dates imply otherwise. Build-window commits (Sep 1+) cover the Telegram surface, live Base/x402 paths, adapters, docs, and this submission.
- **Prep-window wallet ops (before Sep 1):** raw self-txs anchoring demo claim hashes (e.g. `0xe4555a…5943b0`) — wallet activity, not project code.
- **Live dependencies probed, not vendored:** Sibyl SDK, x402 SDK, Base RPC, CoinGecko/Nansen/Cambrian 402 pricing, public Hyperliquid API. No private Sibyl data used.

## License

MIT — see `LICENSE`.
