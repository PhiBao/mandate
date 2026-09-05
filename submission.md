# Mandate — Sibyl Labs Hackathon Submission

## What breaks when memory is deleted?

Without memory, Mandate forgets when each wallet claim was made — so every claim becomes retroactive, and a forward-only track record is structurally impossible to rebuild. The product becomes another screenshot-based trust game: every verdict, mandate, and ask count is unrecoverable, and the bot has no basis to authorize anything.

*(Verification path for judges: `rm` the memory DB → every `get_verdict()`/`get_mandate()` returns `None`, all `/standing` cards collapse to `UNVERIFIED`, and mandates are refused fail-closed. Forward-only claim timing cannot be reconstructed retroactively — the loss is permanent, not a cache miss.)*

## Memory walkthrough (judges score the 40% from this)

- **What you persist:** Signature-verified wallet claims with their timestamp (`Claim`), every closed position as an append-only journal entry (`Position`), every verdict with its full derivation and a supersession hash (`Verdict`), every tier change with reasons (`MandateEvent`), per-member ask counts, the evidence cache, and the cost ledger — all in Sibyl's entity/reference tiers plus the event journal.
- **How a fresh session recalls it:** A new process opens `MandateMemory(db_path)` cold and calls `get_verdict()` / `get_mandate()` — no in-process state exists; `/standing` and `/why` re-derive from Sibyl on every call. The demo video shows this in one uncut segment: a fresh Python process, on-screen commit hash, zero ingest calls, same verdict returned.
- **What it changes:** `claimed_at` is the forward-only cutoff that makes retroactive cherry-picking structurally impossible; persisted verdicts and supersession chains determine which tier — and therefore which authority — a member holds right now; aggregated multi-wallet claims defeat cherry-picked best-of-5 wallets; persisted ask counts turn refusal-to-verify into a first-class product signal.

## Memory primitives you used

- **entities** — `claim` per member tenant, `identity/current` per trader tenant, `verdict/current` (with `supersedes: sha256(prev)`), `mandate/current`
- **recall** — fresh-process cold recall of verdicts, mandates, claims, and ask counts; the entire demo hinges on it
- **semantic search** — `/search` over the trader corpus via Sibyl FTS5 (`search_traders()`)
- **temporal / time-travel** — forward-only ingest cut at `claimed_at`; verdict supersession chains preserve the full history of what was believed when
- **references (dynamic storage)** — `ev:{key}` evidence cache with 6h TTL and staleness labels, `pos:{uid}` position dedup, `ask:{user}` pressure counters, cost ledger
- **journal** — every claim, verdict, mandate change, and position is an append-only event with evaluated/acted/forward fields

*(Summarization / reflection / consolidation are not used by design: authority comes from deterministic arithmetic over exact financial records, not from model-generated memory. Stored evidence never gains instruction authority.)*

---

## Where memory is load-bearing (critical path map)

| Operation | Location |
|-----------|----------|
| Claim write | `src/mandate/memory.py:41` `record_claim()` |
| Positions journal | `src/mandate/memory.py:138` `append_position()` |
| Verdict store + supersession | `src/mandate/memory.py:77` `save_verdict()` |
| Mandate state | `src/mandate/memory.py:102` `set_mandate()` |
| Verdict read (fresh session) | `src/mandate/memory.py:94` `get_verdict()` ← `src/mandate/verdicts.py:54` `evaluate_trader()` re-opens memory cold |
| Forward-only cutoff | `src/mandate/memory.py:192` `get_earliest_claimed_at()` |
| Ask count (persistent) | `src/mandate/memory.py:230` / `:246` |
| Evidence cache + dedup | `src/mandate/memory.py:173` / `verdicts.py:24` (`pos:{uid}` dedup) |
| Cost ledger | `src/mandate/memory.py:129` `append_ledger()` |

## Partner stacks and where

- **Base (verified, live):** claim-hash anchor transactions with on-block timestamps (`0xc9344b33…8be0f4` for the live demo wallet claim, `0xe4555aae…5943b0` prep-window); x402 v2 USDC payments for data with a fail-closed budget gate before any signing (`src/mandate/payments.py:75` → `src/mandate/budget.py:18`), settlement tx decoded from the `PAYMENT-RESPONSE` header.
- **Virtuals (see submission video/README for current state):** ACP agent `mandate-verifier` registered on Virtuals; an ACP job exercises the second-opinion path on tier promotion.
- **Sibyl (mandatory):** `sibyl-memory-client` — file-based SQLite/FTS5, zero embeddings.

## Live evidence for this build

- Claim anchor (wallet op, self-tx, claim hash in calldata): https://basescan.org/tx/0xc9344b33a6ea5b5cea2ea30612a3b5e8bd43f1999afc11507c736b2fca8be0f4 — block 50892642
- Real perp trade after the claim timestamp: long 0.0043 ETH @ $2451.4 → closed @ $2451.3 on Hyperliquid (fills `536629282544` / `536629444865`), verified through the free public API adapter and recorded into Sibyl.
- x402 paid data fetch with onchain settlement: USDC balance `1.345200 → 1.340200` at `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`.
