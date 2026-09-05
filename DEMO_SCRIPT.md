# Demo runbook — 5:00 video + launch day

One file, whole operation: seed, record, restart, submit. Nothing needs improvising.

The video must answer, in order: **the problem and who has it → the product → how it works → how it uses Sibyl Memory** — with the fresh-session recall beat as one uncut segment.

## Cast

| Role | Account | Purpose |
|------|---------|---------|
| Founder/operator | @kiter9 | Claims the demo wallet, runs /standing, records |
| Peer caller | member 2 | Posts calls, gets UNVERIFIED cards |
| The verifier | @MandateBetaBot (Fly.io, persistent volume) | Everything else |
| Demo wallet (live) | `0x4ba1…1d73` | Real claim, real trade, honest verdict |
| Synthetic wallets | seeded (`demo.db`) | Show the CREDIBLE / NOT PROVEN contrast cleanly |

The **live wallet record is real**: claim timestamped 2026-09-05 02:16:59 UTC, hash anchored on Base (`0xc9344b33…be0f4`), then a real ETH perp roundtrip on Hyperliquid ingested forward-only from the public API → verdict `T0 unproven, n=1, not distinguishable` — because that is the truth. The synthetic wallets exist to show the richer card states without waiting weeks; the video says so explicitly.

## 0. Prep (day before, ~20 min)

**0.1 Discover numeric Telegram IDs.** Both members send `hi` in the group, then (token never printed):

```bash
TOKEN=$(.venv/bin/python -c "
for l in open('.env'):
    l = l.strip()
    if l.startswith('MANDATE_TELEGRAM_TOKEN='):
        print(l.split('=', 1)[1].strip())")
curl -s "https://api.telegram.org/bot$TOKEN/getUpdates" \
  | grep -E '"id"|"username"|"text"' | head -20
```

Note `VET_USER`, `VET_ID`, `ROOKIE_USER`, `ROOKIE_ID`, and the group
`CHAT_ID` (negative, starts with `-100`).

**0.2 Stop the Fly bot** so two pollers don't double-reply during recording:

```bash
export FLY_API_TOKEN=$(.venv/bin/python -c "
for l in open('.env'):
    l = l.strip()
    if l.startswith('FLY_ACCESS_TOKEN='):
        print(l.split('=', 1)[1].strip())")
flyctl machine stop 48e129ec1e99d8 --app mandate
```

**0.3 Seed the demo DB** (mock fills = declared demo evidence path):

```bash
.venv/bin/python scripts/seed_demo.py --db demo.db --group <CHAT_ID> \
  --veteran-user <VET_USER> --veteran-id <VET_ID> \
  --rookie-user <ROOKIE_USER> --rookie-id <ROOKIE_ID>
```

Expect `tier=T2_credible` (n≈57) and `tier=T1_observed` (n≈39).
Keep the local `LIVE_KEY` for the burner-wallet beat off camera.

**0.4 Dry run.** Start the local bot against the seeded DB:

```bash
.venv/bin/python - <<'PY'
import os, sys, asyncio
sys.path.insert(0, "src")
for line in open(".env"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
os.environ["MANDATE_DB_PATH"] = "demo.db"
from mandate.main import run
asyncio.run(run())
PY
```

In Telegram, verify: `/standing @<VET>` → CREDIBLE,
`/standing @<ROOKIE>` → NOT PROVEN, `/why @<VET>` → trail,
any `long $X` from an unclaimed account → UNVERIFIED, and
`/standing @kiter9` → the live wallet's real T0 card.
Ctrl-C the bot when done. Keep this terminal layout for recording:
Telegram left, terminal right.

## 1. Recording — beats and timings (total ≤ 5:00)

Screen shows `git rev-parse --short HEAD` + `date -u` before Beat 5.
No cuts inside Beats 5–6.

| Beat | Time | Shot |
|------|------|------|
| 1. Problem & who | 0:00–0:30 | VO over the group chat: "Paid trading groups — 200 to 5,000 members paying $50–500/mo — run on screenshots. When a member posts a win, the operator has no way to check it. If callers are fake, members churn, and the operator's only asset — reputation — burns." |
| 2. UNVERIFIED loop | 0:30–1:10 | Member posts `long $HYPE, targets above` → bot replies **UNVERIFIED, Asked 1 time**. Posts again → **Asked 2 times**. VO: "Day-1 value with zero claims: refusal to verify is a first-class signal, and the counter survives restarts because it's persisted." |
| 3. Live claim + anchor | 1:10–2:10 | Fresh wallet (burner): `/claim <BURNER>` → bot prints the exact EIP-191 message → sign off camera (`scripts/sign_claim.py`, key never on screen) → paste `/claim <wallet> <sig>` → "verified and timestamped". Cut to Basescan: the live wallet's claim hash anchored at tx `0xc9344b33…be0f4`. VO: "The claim's timing is provable on Base, not just in our database." |
| 4. The cards | 2:10–3:10 | `/standing @<VET>` → **CREDIBLE**, 57 trades, CI, benchmark excess. `/standing @<ROOKIE>` → **NOT PROVEN**: linger 5s on "Interval includes zero. Not distinguishable from luck." `/why @<VET>` → derivation trail scroll. VO: "The same engine refuses to flatter the 61%-win-rate wallet." |
| 5. Fresh session (UNCUT) | 3:10–4:10 | New terminal, new `python` process, **no ingest call anywhere**: `MandateMemory(demo.db)` → `get_verdict` + `get_mandate` → same `n`, same `distinguishable`, same tier. Then `/standing @kiter9` → the live wallet's real card: claim 02:16:59 UTC, real trade ingested, honest `T0 unproven, n=1`. VO: "Nothing was recomputed. It remembered. And on the real wallet it refuses to lie about a one-trade record." |
| 6. Deletion (UNCUT) | 4:10–4:40 | Ctrl-C bot. `cp demo.db demo-seed-backup.db && rm demo.db`. Fresh python → `get_verdict` returns `None`. Restart bot → `/standing @<VET>` → **UNVERIFIED**. VO: "Delete the memory and the product doesn't degrade. It ceases — forward-only timing can't be rebuilt retroactively." |
| 7. Settlement + close | 4:40–5:00 | Basescan tx `0xc9344b33…be0f4` on screen (claim hash in calldata). ACP job card in the journal (job #76349, evaluator deliverable). VO: "Claims anchor on Base. Verdicts get second opinions through agent commerce. Reputation settles." End card: landing URL + repo URL. |

Snippet for Beat 5 (paste exactly; `<VET_WALLET>` from seed output, live wallet hardcoded):

```bash
git rev-parse --short HEAD; date -u
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
from mandate.memory import MandateMemory
m = MandateMemory("demo.db")
v = m.get_verdict("hyperliquid", "<VET_WALLET>")
md = m.get_mandate("hyperliquid", "<VET_WALLET>")
print("seeded  -> n:", v["n_trades"], "| distinguishable:", v["distinguishable"], "| tier:", md["tier"])
v2 = m.get_verdict("hyperliquid", "0x4ba1e9e275ef61b56c99532d0066506436201d73")
m2 = m.get_mandate("hyperliquid", "0x4ba1e9e275ef61b56c99532d0066506436201d73")
print("live    -> n:", v2["n_trades"], "| distinguishable:", v2["distinguishable"], "| tier:", m2["tier"])
PY
```

Snippet for Beat 6 recall check:

```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
from mandate.memory import MandateMemory
m = MandateMemory("demo.db")
print(m.get_verdict("hyperliquid", "<VET_WALLET>"))
PY
```

## 2. After recording (~5 min)

```bash
export FLY_API_TOKEN=$(.venv/bin/python -c "
for l in open('.env'):
    l = l.strip()
    if l.startswith('FLY_ACCESS_TOKEN='):
        print(l.split('=', 1)[1].strip())")
flyctl machine start 48e129ec1e99d8 --app mandate
```

Group continues on the Fly volume (real claims from here on; the seeded
`demo.db` stays a local video artifact). `/standing @anyone` → UNVERIFIED
reply proves end-to-end life.

## 3. Submit checklist

- [ ] Public repo (MIT): https://github.com/PhiBao/mandate
- [ ] Demo video 2–5 min: problem+who → product → how → memory; uncut Beats 5–6, commit hash + timestamp visible
- [ ] README: what it does, where memory is load-bearing, partner stacks, "how memory made this possible", Prior Work
- [ ] submission.md: form answers (what breaks / walkthrough / primitives)
- [ ] Post 1 (build log) + Post 2 (demo video) — drafts in section 4
- [ ] Landing page live: https://phibao.github.io/mandate/ (pilot program + validation log)
- [ ] ACP job #76349 completed and journal-recorded

## 4. Launch posts (copy-paste, verify handles before sending)

**Post 1 — build log:**

> Paid trading groups run on screenshots. I built the thing that checks.
>
> Mandate: a Telegram bot that verifies wallet claims (EIP-191 + onchain
> anchor on Base), ingests closed positions FORWARD-ONLY from the claim
> timestamp, and bootstraps a 95% CI on returns. If the interval includes
> zero it says "not distinguishable from luck" — even to a 61% win-rate
> caller. Tier gates a revocable mandate. Delete the memory DB and the
> product ceases, because forward-only time can't be rebuilt.
>
> Built on Sibyl Memory (load-bearing, not a notepad). Live x402 payments
> on Base. Real claim → real trade → honest T0 verdict already in the
> record. 73 tests green.
>
> Repo: github.com/PhiBao/mandate · phibao.github.io/mandate
> @sibylcap @base

**Post 2 — demo video day:**

> Demo: a trading-group bot with unfakeable memory.
> Claim → forward-only track record → CREDIBLE / NOT PROVEN cards.
> New session, one uncut take: it remembers everything.
> Delete the memory DB on camera and every mandate collapses.
> Forgetting is a bug. [video link]
> @sibylcap @base
