# Demo runbook — 5:00 video + launch day

Group is live: two members + `@MandateBetaBot`. This file is the whole
operation: seed, record, restart, submit. Nothing here needs improvising.

## 0. Prep (day before, ~20 min)

**0.1 Discover numeric Telegram IDs.** Have both members send `hi` in the
group, then (token never printed):

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
`CHAT_ID` (negative number, starts with `-100`).

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
Save the printed `LIVE_KEY` to a local env var, **off camera**:

```bash
export LIVE_KEY=<burner key>
```

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
any `long $X` from an unclaimed account → UNVERIFIED.
Ctrl-C the bot when done. Keep this terminal layout for recording:
Telegram left, terminal right.

## 1. Recording — beats and timings (total ≤ 5:00)

Screen shows `git rev-parse --short HEAD` + `date -u` output at the top
of the terminal before Beat 4. No cuts inside Beats 4–5.

| Beat | Time | Shot |
|------|------|------|
| 1. Problem | 0:00–0:25 | VO over the group chat: paid groups run on screenshots. "When someone posts a win, who checks?" |
| 2. UNVERIFIED loop | 0:25–1:10 | Member posts `long $HYPE, targets above` → bot replies **UNVERIFIED, Asked 1 time**. Posts again → **Asked 2 times**. VO: "Refusal to verify is a first-class signal." (If tight on time, cut the second call.) |
| 3. Live claim | 1:10–2:10 | Founder (third account or member slot) runs `/claim <BURNER>` → bot prints the exact EIP-191 message → sign **off camera** (`scripts/sign_claim.py`, key never on screen) → paste `/claim <wallet> <sig>` → "verified and timestamped". Then `/standing` → **UNPROVEN, 0 trades**: "New claim. No history yet. The system says so honestly." |
| 4. The cards | 2:10–3:10 | `/standing @<VET>` → **CREDIBLE**, 57 trades, CI. `/standing @<ROOKIE>` → **NOT PROVEN**: linger 5s on "Interval includes zero. Not distinguishable from luck." `/why @<VET>` → derivation trail scroll. |
| 5. Fresh session (UNCUT) | 3:10–4:10 | New terminal, new `python` process, **no ingest call anywhere**: `MandateMemory("demo.db")` → `get_verdict` + `get_mandate` → same `n`, same `distinguishable`, same tier. VO: "Nothing was recomputed. It remembered." |
| 6. Deletion (UNCUT) | 4:10–4:40 | Ctrl-C bot. `cp demo.db demo-seed-backup.db && rm demo.db`. Fresh python → `get_verdict` returns `None`. Restart bot → `/standing @<VET>` → **UNVERIFIED**. VO: "Delete memory and the product doesn't degrade. It ceases." |
| 7. Settlement + close | 4:40–5:00 | Basescan tx `0xe4555a…5943b0` on screen (block 50258124, claim hash in calldata). VO: "Claims anchor on Base. Reputation settles there." End card: landing URL + repo URL. |

Snippet for Beat 5 (paste exactly; `<VET_WALLET>` from seed output):

```bash
git rev-parse --short HEAD; date -u
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
from mandate.memory import MandateMemory
m = MandateMemory("demo.db")
v = m.get_verdict("hyperliquid", "<VET_WALLET>")
md = m.get_mandate("hyperliquid", "<VET_WALLET>")
print("n:", v["n_trades"], "| distinguishable:", v["distinguishable"], "| tier:", md["tier"])
PY
```

Snippet for Beat 6 recall check:

```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
from mandate.memory import MandateMemory
print(MandateMemory("demo.db").get_verdict("hyperliquid", "<VET_WALLET>"))
PY
```

## 2. After recording (~5 min)

```bash
flyctl machine start 48e129ec1e99d8 --app mandate
```

Group continues on the fresh Fly DB (real claims from here on; the
seeded `demo.db` stays a local video artifact). Message the bot
`/standing @anyone` → UNVERIFIED reply proves end-to-end life.

## 3. Submit checklist

- [ ] Public repo (MIT): https://github.com/PhiBao/mandate
- [ ] Demo video 2–5 min, uncut Beats 5–6, commit hash + timestamp visible
- [ ] README gate table + Prior Work current
- [ ] Post 1 (build log) + Post 2 (demo video), drafts below
- [ ] Landing page live: https://phibao.github.io/mandate/

## 4. Launch posts (copy-paste, verify handles before sending)

**Post 1 — build log:**

> Paid trading groups run on screenshots. I built the thing that checks:
> Mandate verifies wallet claims (EIP-191), tracks forward-only, and
> says "not distinguishable from luck" when the math says so.
> 73 tests green. Live on Base + Telegram.
> Repo: github.com/PhiBao/mandate
> @sibylcap @base

**Post 2 — demo video day:**

> Demo: a trading-group bot with unfakeable memory.
> Claim → forward-only track record → CREDIBLE / NOT PROVEN cards.
> Delete the memory DB on camera and every mandate collapses.
> Forgetting is a bug. [video link]
> @sibylcap @base
