# Mandate — Product Specification (v2)

**One-liner:** An agent that lives in a trading group chat, maintains an unfakeable longitudinal track record for every member, and converts that record into a revocable **Earned Mandate** — memory-derived authority to act.

**Status:** Build window Sep 1–10, 2026. Core engine built and tested (73 tests, premise gate passing). Free Hyperliquid adapter + mandate auto-persist + forward-only filter + idempotent ingest + ask-count persistence all wired; this spec locks remaining scope.

---

## 1. Core User

**Primary — Buyer (holds budget + distribution):** Operator of a paid crypto trading group.

- 200–5,000 members on Telegram, charging $50–500/mo
- 3–10 people making calls that move the room
- Reputation is the entire asset; churn when calls underperform
- Holds the distribution: land one operator, acquire their whole membership (B2B2C)

**Secondary — Beneficiary (experiences value, creates demand):** Paying member deciding whether to act on a call.

**Explicitly not the user:** Solo traders wanting a personal dashboard, developers, quants. They don't pay for verification and don't bring distribution.

**Why this segmentation solves the founder constraint:** User previously noted "no audience." Cold consumer acquisition would be lethal. The operator already has the audience; verification is the missing capability they cannot build themselves.

---

## 2. Job-to-Be-Done

> When someone in my group posts a win, I need to prove or disprove it — before my paying members act on it and churn when it turns out to be noise.

**Current alternatives:** Screenshots (backward-looking, selectively sampled), trust/vibes, executors (BONKbot, Photon, Maestro, Trojan) that assume you already know who to copy.

**Mandate's job:** Turn every call into a checkable claim against a forward-only, timestamped, capital-at-risk record — and make the *absence* of a claim visible.

---

## 3. Main User Journey

| Step | Actor | Action | System |
|------|-------|--------|--------|
| 1 | Operator | Adds bot to group, sets monthly data budget | Bot pins explainer: what gets verified, what stays private |
| 2 | Member | `/claim <wallet>` | Bot returns exact EIP-191 message with nonce; member signs off-band |
| 3 | Member | `/claim <wallet> <sig>` | Bot recovers signer, verifies wallet==signer, expiry, template; writes `Claim` to Sibyl member tenant; optionally anchors hash on Base via `ClaimAnchor`; DMs confirmation with digest |
| 4 | System | Forward-only tracking | Ingests closed positions **from claim timestamp only** via VenueAdapter (Omni $0.005). Quality-flagged positions excluded, counted. Normalizes to return series, window span |
| 5 | System | Verdict + Mandate | Bootstrap 10k resamples → 95% CI. Computes excess vs benchmark, drawdown, win rate. Deterministic tier evaluator (no LLM) writes `Verdict` + `MandateEvent` with reasons, supersession hash |
| 6 | Anyone | Posts a call ("long $HYPE") | Bot attaches **standing card** inline — including for members who never claimed |
| 7 | Anyone | `/standing @alice` / `/why @alice` | Full card + derivation trail |
| 8 | System | Weekly digest | Change report + cost ledger (`spent $0.62, saved $4.10`) |
| 9 | At T3 | Brief | Slippage at member's size (AgentPay $0.010) + perp liquidation risk (Cambrian $0.05) + contrast line, one-tap confirm handoff. Never auto-executes. |

**Claim is permanent and aggregated.** Claiming 5 wallets and promoting the best is impossible — all are bound and all count. Only persistent memory makes this enforceable.

---

## 4. Activation Moment

**Definition:** `≥3 completed signed claims AND ≥1 standing card posted on a live call within 7 days of install.`

Not install. Not first claim. The first time a standing card changes the conversation.

**Critical design: refusal to claim is a first-class signal, not an empty state.**

```
@caller — UNVERIFIED
No wallet claimed. Asked 4 times since Mar 2.
This call cannot be checked against any record.
                                    [Claim a wallet]
```

This de-risks adoption: the product delivers value on day 1 with zero claims (reveals who refuses verification), and visible asymmetry drives claiming via social pressure. Adoption risk becomes growth loop.

**Mean time to first value for the demo group (self + clone):** minutes — not weeks. For real groups, the unverified card is minute-one value; the statistical verdict compounds over days.

---

## 5. Retention Loop

```
claim → forward-only tracking → tighter CI → tier change →
new status + authority → peers claim to get status →
richer aggregate record → operator's group more defensible →
more members, less churn
```

**Three compounding mechanics:**

1. **Statistical:** Every closed trade narrows the CI. Informativeness grows monotonically.
2. **Non-portable:** A competitor who wasn't watching cannot reconstruct the forward-only record. Switching cost is *elapsed time* — the one thing money can't buy back.
3. **Status:** T3 is scarce, earned, shareable. Holders advertise the credential (public page), marketing the product.

**Unverified ratio as leading retention signal:** watch `unverified callers / total callers` over time. If it falls, the product is changing behavior.

---

## 6. Product Differentiation

| Category | Example | Optimization | Gap Mandate exploits |
|----------|---------|--------------|----------------------|
| Executors | BONKbot, Banana, Photon, Maestro, Trojan, Cornix, 3Commas | Speed of copying | Never ask if target is good |
| Leaderboards | GMGN, Dexscreener, Hyperliquid leaderboard | $ PnL, arbitrary window | Retroactive, capital-biased, no benchmark, no luck test |
| Social credibility | **Cambrian deep42** | Tweet volume × reach × LLM "alpha" | **Formula contains no accuracy term**; no min-N, no CI |
| Copy platforms | eToro | Curated copy | Closed, not crypto-native, not in chat |
| Reputation registries | ~15 dead agent projects | Generic score | No consequence; no specific user or decision |

**Four things nobody combines:**

1. **Forward-only claims** — `claimed_at` before measured window; retroactive cherry-picking structurally impossible
2. **Honest abstention** — `ci_lo ≤ 0 → "not distinguishable from luck"` — the line incumbents won't ship
3. **Regime adjustment** — excess return vs benchmark over identical window (prevents beta-as-skill in bull)
4. **Attached consequence** — score gates revocable authority (tiers), not a vanity number

**Cambrian contrast as differentiator:** Show both side-by-side — *"Ranks #3 on social credibility. Not distinguishable from luck on capital."* Only our product can say the second sentence.

---

## 7. Interface Model

**Telegram-native cards. No dashboard. No sidebar. No charts. No app.**

**Three commands:** `/claim`, `/standing`, `/why`. Weekly digest pushed automatically.

**Card states (four, all real product states):**

- **UNVERIFIED** — no wallet, ask count, cannot be checked
- **UNPROVEN/OBSERVED (T0/T1)** — tracked, not proven: `n`, win rate, mean, CI, "includes zero"
- **CREDIBLE (T2)** — `n ≥ 30`, CI clears zero, risk PASS
- **TRUSTED (T3)** — `n ≥ 100`, age ≥60d, excess CI clears benchmark, drawdown bounded

**The money-shot card (specimen — this is the demo beat):**

```
@caller — NOT PROVEN (T1)
88 closed trades since Feb 3 · Win rate 61%
Mean return +3.1% — but 95% CI: −1.2% to +7.4%
Interval includes zero. Not distinguishable from luck.

Over the same window: BTC +18%, this wallet +11%.
                                              [Why?]
```

**CREDIBLE specimen:**

```
@alice — CREDIBLE (T2)
47 closed trades since Mar 12 (68 days)
Median mean +4.2% · Excess vs BTC +2.1%
95% CI on excess: +0.8% to +6.4% → skill, not luck
Max drawdown −23% · No risk flags
2 wallets claimed, both counted
                             [Why?] [Full record]
```

**/why** adds derivation trail (claim hash, evidence ids, quality exclusions, CI method, tier reasons).

**Weekly digest** — change-focused, not rank-focused (ranking by return rewards gambling, which this product exposes):

```
This week in <group>
↑ @alice → TRUSTED (T3) — 104 trades, CI now clears BTC
↓ @bob  → OBSERVED — drawdown −41% breached limit
· @carl still unverified after 6 asks
· New claims: @dana, @erin
Data spend: $0.62 (cache saved $4.10)
```

**Second surface:** Public read-only credential page per verified trader (shareable proof, opt-in).

---

## 8. MVP Scope and Non-Goals

### In scope (10-day build)

- Telegram bot: 3 commands, 4 card states including UNVERIFIED, `/why` trail
- Signature-verified claims (EIP-191, expiry, template check) + forward-only timestamp
- Base `ClaimAnchor` contract (event-only, no storage) + raw-calldata anchoring for prep-window demo wallets + verification path
- Evidence pipeline: VenueAdapter abstraction, `HyperliquidAdapter` (Omni $0.005) as beachhead, mock source for tests/demo, evidence cache with staleness labels, budget gate enforced before signing
- Normalization → closed-position return series with quality abstention
- Statistical core: bootstrap CI (10k, stdlib-only), min-N gates (T1 10, T2 30, T3 100), benchmark excess, drawdown
- Mandate engine: T0–T3, promotion/demotion/revocation, persisted reasons, supersession
- Standing cards + `/why` + weekly digest + credential page data
- Cambrian contrast line (`influencer-credibility` $0.05) + `perp-risk-engine` for T3 leverage brief
- ACP second-opinion job on T2/T3 promotion (CLI via subprocess, not Python SDK)
- Cost ledger (spent vs saved-by-cache) + cold-start recall path + memory-wipe failure mode
- Tests: 52 and growing, including Day-4 premise gate (lucky vs skilled synthetic separation)

### Explicit non-goals (not in v1 — ever or until validated)

- ❌ Autonomous trading, order execution, custody of user funds
- ❌ Trade advice — bot verifies *people*, not *trades*
- ❌ Return-ranked leaderboard
- ❌ Price prediction, sentiment, TA, backtesting
- ❌ Web/mobile/member-facing billing
- ❌ Multi-venue breadth — Hyperliquid done properly; `BaseAdapter` only as Day-7 stretch
- ❌ Token, NFT credentials, points
- ❌ General chat AI / copilot
- ❌ Discord (Telegram only)

---

## 9. Architecture

### Stack table — "how the agent operates" vs "what the agent looks at"

Hyperliquid is a **value** passed to a VenueAdapter, not a layer.

| Layer | Tech | Role | Scoring |
|-------|------|------|---------|
| Memory substrate | Sibyl SDK 0.6.1, SQLite, FTS5 | Tenancy, append-only journal, verdict/tier history, evidence cache | Gate + 40 |
| Settlement & trust | Base 8453, `ClaimAnchor.sol` | Claim anchoring, payment settlement | +15 |
| Payments | x402 v2, USDC `0x8335…2913`, `x402` 2.19 + `eth-account` | Budget gate before signing (`X402Payer.authorize` → `authorize_spend`), fail-closed on unpriceable 402s, settlement tx decoded from `PAYMENT-RESPONSE` | (same) |
| Agent commerce | Virtuals ACP CLI via subprocess | Hire evaluator on promotion; register own service | +10 |
| Evidence | Omni $0.005, CoinGecko $0.005, LionX402 $0.001, AgentPay $0.010, Cambrian $0.05 | All x402-paid on Base | — |
| Surface | Telegram Bot API over `httpx` | 3 commands, 4 states | 15 |
| Runtime | Python 3.14, stdlib-only stats | Pure-Python bootstrap, no numpy | 20 |
| Authority path | Deterministic arithmetic, no LLM | Prompt-injection defense + auditability | — |

### Sibyl tenancy — coordination pattern (tops the 40-point band)

```
group:<chat_id>              config, budget, roster, digest, member_map (username→user_id)
member:<chat_id>:<user_id>   per-member claim entities
trader:<chain>:<wallet>      identity, claims aggregate, evidence cache (REFERENCE), positions (journal), verdicts, mandate
(planned) specialist:normalizer|variance|risk   working memory + ACP job records
ledger:<chat_id>             cost journal, tx hashes
```

### Records — append-only, supersession never mutation

```python
Claim         {chain, wallet, group_id, user_id, nonce, message, message_hash, sig, claimed_at, anchor_tx, block_time}
Position      {open_at, close_at, asset, direction, entry, exit, return_pct, notional, quality, source_ids}
Verdict       {computed_at, n, window_days, mean, ci_lo, ci_hi, benchmark, excess, drawdown, win_rate, distinguishable, abstain, flagged, reasons, evidence_ids, supersedes}
MandateEvent  {at, trader_ref, from_tier, to_tier, reason, verdict_hash}
```

Current verdict is entity `verdict/current` with `supersedes: sha256(prev)`. Full history is journal.

### VenueAdapter abstraction

```python
class VenueAdapter(Protocol):
    venue: str
    async def fetch_closed_positions(self, wallet: str, *, since_iso: str | None) -> EvidenceBatch: ...
```

- `MockHyperliquidSource` — synthetic, for tests/demo
- `OmniHyperliquidAdapter` — primary beachhead (reconciled PnL + quality flags)
- `BaseAdapter` (Nansen) — Day-7 stretch; same interface

### Payments — gate before signing

Implemented: `X402Payer.authorize()` calls `authorize_spend()` against the probed price before the key is loaded or any payment is signed; a 402 whose requirements cannot be priced for `eip155:8453` denies fail-closed (`parse_payment_required`). Settlement is decoded from the `PAYMENT-RESPONSE` header into `PaymentReceipt.tx_hash`. T0 wallets get one memory-tracked discovery fetch per trader.

Planned: SDK payment hooks writing attempts to the Sibyl journal, and an evidence cache keyed on request params checked before any spend.

### On anchoring — two paths

- **Prep-window demo wallets (before Sep 1):** raw self-tx with `keccak(wallet+purpose+nonce)` in calldata — qualifies as "wallet op" per rules, costs cents, no contract needed
- **Live claims (Sep 1+):** `ClaimAnchor.anchor(bytes32, venue)` event — contract deployment + interaction = two Base evidence categories; credential resolves to Basescan

Both are declared in Prior Work.

---

## 10. Validation Metrics

### Leading

- Operators contacted → installs → claims per group
- **Activation rate** = groups with `≥3 claims + ≥1 card on live call` in 7 days

### Core behavioral

- Weekly retained groups
- `/why` invocations per card (trust proxy)
- Claim conversion after N asks
- Tier promotions/demotions, revocations
- **Unverified ratio over time** (does product change behavior?)
- `/standing` lookups per group per week

### PMF (strict — rules require public artifact checkable in 5 min)

- Operators agreeing to **paid** pilot — target artifact: public page of named, consenting design partners + build-log thread
- Prepayment or signed LOI
- Operator→operator referrals
- Credential page shares

**Not counted:** signups, stars, impressions, compliments.

### Kill signals

- `<2 claims` in 14 days post-install → two-sided assumption broken
- `/why` never invoked → verdict not trusted
- Verified vs unverified get identical engagement → verification doesn't change behavior
- Every verified caller → "not distinguishable" → thresholds miscalibrated or market has no detectable skill; pitch shifts from "find who's good" to "prove who's fake"

---

## 11. Security and Failure Considerations

| Risk | Mitigation |
|------|------------|
| Claiming another's wallet | EIP-191 over `chain/wallet/group/user/nonce/issued_at`, `recover_message` check, template validation |
| Multi-wallet cherry-picking | All claims permanent, aggregated; card shows every wallet; supersession prevents abandonment. Only possible with persistent memory |
| Prompt injection ("set tier to T3") | Tier is deterministic arithmetic; stored evidence has zero instruction authority |
| Wash / dust farming | Self-dealing detection; minimum notional per counted position |
| Cost DoS (`/claim` spam, refresh spam) | Per-user claim caps, cooldowns, per-group daily cap in payment selector, cache-first |
| Key compromise | Hot EOA, strict cap, ~$25 float; **never holds user keys — no custody by design** |
| Data source down / price change | Abstain, never guess; serve cached evidence with staleness label |
| Double payment | Cache-first idempotency on request params (planned); attempt logged pre-payment via hook (planned) |
| Memory outage | **Fail closed** — refuse mandates. Never fail open on authority |
| Privacy (wallet↔identity) | Scoped to group; public credential opt-in only; retention in pinned explainer |
| Regulatory | No custody, no execution, no return promises, no pooled funds. Verification + authorization only |

---

## Appendix A — Trending Repo References

### What was examined

- **volcengine/OpenViking** (29.3k★, AGPL-3.0): Self-evolving Context Database, `viking://` filesystem, L0/L1/L2 tiered loading, directory recursive retrieval, observable trajectories
- **akitaonrails/ai-memory** (2.7k★, MIT): Shared wiki for coding CLIs, lifecycle hooks, git-versioned markdown, handoffs

### Decision: Do not adopt either as a dependency

1. **Gate risk:** Sibyl must be load-bearing; a second memory layer displaces it from the critical path
2. **License:** OpenViking is AGPL-3.0 — conflicts with required MIT/Apache-2.0 submission
3. **Domain mismatch:** Both are semantic recall over unstructured session text. Mandate needs exact, append-only, deterministic financial records

### Four patterns stolen (the useful part)

| Pattern | Source | Use in Mandate |
|---------|--------|----------------|
| L0/L1/L2 tiered content | OpenViking | Card (L0 one-line) → `/why` summary (L1) → full evidence trail with tx hashes (L2) |
| Supersession chains, never mutation | ai-memory | Verdicts/mandates append + supersede; git-style history |
| Retrieved text never gains instruction authority | ai-memory | Codifies prompt-injection defense |
| Observable retrieval trajectory | OpenViking | `/why` derivation path, not just conclusion |

---

## Appendix B — Cambrian as Verification Layer

**Question:** Can Cambrian be the verification layer?

**Answer: Not as the primary wallet verification. As two real, scoped roles — yes.**

**Probed live (402 responses decoded, Base USDC):** All Cambrian endpoints support x402 v2 on `x402.cambrian.org`, same SDK shape (`x402HttpxClient` + `register_exact_evm_client`), $0.05/req, 5–10× Nansen/Omni. Cache hard.

**Limitation:** EVM surface has **no per-wallet trade history**. Endpoints `wallet-balance-history`, `token-transactions`, `traders/leaderboard` are **Solana-only**. EVM has lending, pools, `tvl/status` (balances), `price-hour` (capped 1000h ≈41d, short of 60d T3 window). Cannot replace Nansen/Omni for EVM wallet verification.

**Assigned roles:**

1. **`risk/perp-risk-engine`** — Monte Carlo liquidation probability for leveraged positions. Strong fit for T3 pre-trade brief (now that beachhead is Hyperliquid perps).
2. **`deep42/social-data/influencer-credibility`** — contrast signal + market evidence. Sample of top-10 by their credibility: **all tiered "unproven,"** most with negative 30d avg return; their formula ` (views/50K)*10 + (alpha/10)*5 + ...` contains **no accuracy term**, no min-N, no CI. Our line: *"The incumbent score doesn't include whether you were right. Ours is only whether you were right, with capital at risk, adjusted for the market."* One extra $0.05 call, highest-ROI differentiator.
3. **Primary source if beachhead were Solana** — rich wallet coverage, but reconciliation hardest (partial fills, dust, rugged tokens). Not chosen.

**Cambrian is a premium source that makes our statistical honesty visible by contrast.**

---

## Appendix C — Build Plan

### Prep window (now → Aug 31) — founder hands required

1. **Today/tomorrow: Open and onchain-anchor 2–4 Hyperliquid demo wallets** ($100–500 each is enough — percentage returns don't care about capital). Use raw calldata self-tx; every day delayed is unrecoverable track record. Also trade one wallet to look good but be noise (61% win rate, high variance, benchmark-tracking) for the honest "not distinguishable" demo.
2. Register team (closes Aug 31 23:59 UTC — build-page link is submission mechanism)
3. Clear ACP OAuth chain (`configure` → `agent create` → `add-signer` → `topup` ~$20)
4. Probe Omni on 3–5 public Hyperliquid traders — confirm closed-position reconstruction works *before* Sep 1 (premise test; fallback exists if it fails)
5. Fund EOA ~$25 USDC + gas ETH on Base
6. 10 operator interviews, public consent where offered; daily trading of demo wallets
7. Public repo + Discord

**No project code committed during prep is declared as spike; real commits Sep 1–10 for clean Prior Work.**

### Build window (Sep 1–10)

| Day | Milestone | Risk retired |
|-----|-----------|--------------|
| 1 | Skeleton ✓ + Spons tenancy + signed claims + ClaimAnchor deploy | Claim integrity |
| 2 | x402 payer + budget gate + hooks audit + cache; **first real Base payment** | Base bonus |
| 3 | Evidence normalizer → closed-position return series; quality abstention | Premise |
| 4 | **Statistical core** ✓ + verdict service ✓ — synthetic lucky vs skilled must separate | **The moat** |
| 5 | Mandate engine ✓ + tiers persisted with reasons | Authority correctness |
| 6 | Telegram surface: 4 card states ✓ + `/why` + unverified pressure loop | Product legibility |
| 7 | ACP second-opinion + Cambrian contrast + T3 brief (slippage + perp risk) | Both multipliers |
| 8 | Weekly digest + credential page + cost ledger + cold-start recall + memory-wipe failure mode | Gate |
| 9 | Hardening; README with `file:line` memory pointers; record demo (single unbroken take) | Gate |
| 10 | Final cut, submit, second build-log post | Submission |

**Day-4 gate:** If synthetic lucky vs skilled don't separate, fall back to narrower claim (*verified forward-only record, no skill verdict*) rather than dishonest score. Day-7 `BaseAdapter` is stretch — cut if behind; Base bonus already earned via anchor + payments.

### Demo beat order (2–5 min, one unbroken take for gate)

1. Unverified caller → visible ask count
2. Signed claim timestamped + Base anchor tx
3. Real x402 payment with tx hash
4. **"Not distinguishable from luck" on a 61%-win-rate wallet** — proof of honesty
5. ACP second-opinion job on promotion
6. **Fresh session, one continuous take, on-screen commit hash** — recall of claim date, record, tier
7. **Wipe memory → every mandate collapses to T0, cost ledger explodes**

---

## Appendix D — Risks and Honest Score Estimate

**Top risks:**

1. Agent reputation is a 15-project graveyard — generic scores with no consequence. Our gap (specific group, specific decision, real authority) must be *real by Day 6* or we're #16.
2. Statistical honesty is the moat — fake rigor = another gameable score. Cut scope elsewhere, never here.
3. No custody / no advice is the correct legal posture; verification + authorization only.
4. DEX swap reconciliation is genuinely hard — scoped to perps + Omni quality flags; abstain rather than guess.
5. ACP OAuth single point of failure — if not cleared in prep, multiplier drops ×1.25→×1.15.

| Criterion | Est. | Reasoning |
|-----------|------|-----------|
| Memory load-bearing 40 | 34–38 | Coordination + dynamic storage + structurally required forward-only record |
| Innovation 25 | 20–22 | Verifier not executor; earned mandate; honest abstention |
| Execution 20 | 14–17 | Solo, 10 days, real mainnet |
| Pitch 15 | 13–14 | Deletion test unusually legible |
| PMF bonus 10 | 0 or 5–10 | Binary on public artifact |
| Multiplier | ×1.25 | Both stacks real |
| **Realistic** | **103–120 / 137.5** | Competitive, not guaranteed; PMF + ACP are swing factors |

Real ceiling: (100+10)×1.25 = 137.5. The product is designed to be *useful on day 1 with zero claims* and to become *unreplaceable over weeks* — the retention mechanic the hackathon is explicitly rewarding.
