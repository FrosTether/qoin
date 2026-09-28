# Denero — a labor-time unit

**Draft 0.1 · 28 September 2026 · Jacob Frost**

> A unit of account, defined by time. `1 Denero (DNR) = 5 minutes of work =
> 300 seconds`. This spec defines the unit and, more importantly, resolves the
> one hard question inside it: **how do you prove the work?** Nothing here is
> financial or legal advice, and no model below conjures value from a timer.

## 1. The unit

| | |
|---|---|
| Name / ticker | Denero / **DNR** |
| Definition | 1 DNR = 5 minutes = 300 seconds of work |
| Sub-unit | 1 second = 1/300 DNR ≈ 0.003333 DNR |
| Hour | 12 DNR = 1 hour |
| Epoch | 300 s is the natural accounting epoch — the interval work is *recorded* in, never the interval it is *minted* on |

The last row is the whole ethic: a Denero is **recorded when work is attested**,
not emitted by a clock. A coin that mints itself every 300 seconds is measuring
uptime and calling it labor — don't ship that.

## 2. The hard problem: proving "5 minutes of work"

You cannot verify human labor-time trustlessly. Whatever backs Denero has to
answer "who says the work happened?" Three honest models:

### Model A — Time-bank / mutual credit  *(recommended for a labor unit)*
A Denero is created when a member performs 5 minutes of service **for another
member who co-signs it**. The doer's balance goes **+1 DNR**, the receiver's
**−1 DNR**; the system nets to zero. Deneros are redeemed when the direction
reverses (you later receive service). Backed by **reciprocity + reputation**, not
a mint.
- *Means what it says:* a counterparty vouches, so "5 minutes of work" is real.
- *Voluntary:* no central issuer, no coercion — ancap-clean, and it's how time
  banks already operate.
- *Precedent:* Josiah Warren's labor notes (1827), Owenite labour exchanges,
  Edgar Cahn's Time Banking (1 hour = 1 credit), Ithaca HOURS.

### Model B — Compute proof-of-work  *(honest only if called compute)*
Mint a Denero for verifiable hashing calibrated so a reference machine earns
~1 DNR per 5 minutes. This is the `FrostCrush2` style. It measures **machine
time**, not a person's labor. Fine as a compute coin; **fraud** the moment it's
marketed as "5 minutes of a human's work."

### Model C — Time-dividend  *(honest only if called UBI)*
Every verified human accrues Deneros just by existing — the Qoinchain dividend,
denominated in time. This is a basic income in time units, **not** payment for
work. Honest only if labeled existence/UBI.

**Recommendation:** for a unit literally defined as "5 minutes of *work*," use
**Model A**. Keep B and C as separate, clearly-named things if you want them.

## 3. Collusion — the attack Model A must survive

Two accounts can co-sign fake work for each other and print Deneros. Mitigations,
reusing pieces you already have:
- **Personhood-gate** the ledger (Qoinchain proof-of-personhood): one human, one
  identity, so a ring can't be one person wearing masks.
- **Reputation-weighted credit limits**: new pairs can only net a small DNR
  balance until a history exists; limits widen with diverse, corroborated
  counterparties.
- **Challenge + sampling** (the Qoinchain court): anyone can dispute an
  attestation; a random human panel adjudicates; false attestations slash a bond.
- **Diversity rule**: Deneros earned against a single repeated counterparty are
  discounted versus those spread across many — collusion rings look different from
  real service networks.

No mitigation is perfect; Model A degrades gracefully (fraud dilutes trust in the
fakers' credit, not everyone's balance), which is the point.

## 4. How Denero relates to FTC / Qoin

Keep the layers distinct — hard-pegging human time to a token price recreates the
"backed" fiction the red paper warned about.
- **DNR is a unit of account** for attested labor (mutual credit; nets to zero).
- **FTC / FSZT is a transferable token** with its own fixed supply.
- If you want convertibility, let a **market** set DNR↔FTC, or post a *suggested*
  rate (Ithaca HOURS posted "1 HOUR ≈ $10" as guidance, not a peg). Never mint FTC
  automatically from a Denero timer.
- "Proof of Work of UBI" maps cleanly: **DNR is the *work* side** (what you earn
  by doing), the **dividend is the *UBI* side** (what you get for being a verified
  human). Two units, one honest system.

## 5. What an implementation would be (honest version)

If you want this in `qoind`, it is **not** an auto-minter. It is a local
**attested time-credit ledger**:
- `qoinctl work log --minutes 5 --for <peer>` records a pending entry.
- The peer co-signs (`qoinctl work confirm <id>`); only then does +1/−1 DNR post.
- Balances, history, and reputation live in `/var/db/qoin/denero/`, keys stay
  on-device (§ wallet), nothing auto-mints, nothing is claimed as value it isn't.

That's a real thing I can build for FrostBSD Stage 2 — say the word and pick the
model.

---

*Positions and figures are design, not offers. A labor unit is only as honest as
its proof-of-work; pick a model whose name matches what actually happens.*
