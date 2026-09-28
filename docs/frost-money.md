# Frost Money — reconciled

**Draft 0.1 · 28 September 2026 · Jacob Frost**

Your units were fighting because several of them were pegged to *each other and*
to the dollar *and* to bitcoin at the same time. A currency can have **one
anchor, not five.** Pick the anchor, define everything else in it or let it
float, and the math closes. Here it is with **labor-time** as the anchor — the
one that fits "1 Denero = 5 minutes of work / Proof of Work of UBI."

> All figures below are computed and checked. Dollar values are a **suggested
> reference**, not a peg or a promise.

## The one rule

**Everything is measured in Denero (labor-time). Nothing is pegged to two things.**
Each unit is exactly one of:
- **the anchor** — Denero,
- **defined in Denero** — the UBI dividend,
- **floating vs Denero by the market** — FTC, Blockcoin, the dollar.

That's the whole fix.

## 1. The anchor — Denero (DNR) = attested labor-time

`1 DNR = 5 minutes = 300 seconds of attested work.`

| Work | Denero |
|---|---|
| 1 hour | **12 DNR** |
| 1 day (8 h) | 96 DNR |
| 1 week (40 h) | 480 DNR |
| 1 month (173.3 h) | 2,080 DNR |
| 1 year (2,080 h) | 24,960 DNR |

This is exact and self-consistent — it's just time. (Denero is mutual credit:
issued when a counterparty co-signs your work, nets to zero across the system.
See `DENERO.md`.)

## 2. The dollar as a *reference*, not a peg

Your $60/hour, carried through the anchor:

| | Value |
|---|---|
| $ per hour | $60.00 |
| **$ per Denero** | **$5.00** |
| $ per minute | $1.00 |
| a workday (96 DNR) | ~ $480 |
| a workweek (480 DNR) | ~ $2,400 |
| a work-year (24,960 DNR) | ~ $124,800 |

Posted as *guidance* (the way Ithaca HOURS posted "1 HOUR ≈ $10"), never enforced.
No reserve backs it, so it can't be a peg — it's a suggested wage.

## 3. Why "$60/hr UBI" was breaking the math

$60/hour paid **unconditionally, 24/7**, is **$525,960 per person per year**. That
can't be a basic income. So $60/hr is a **wage for work** — it lives on the
**Denero (work) rail**, not the UBI rail. That single reclassification removes the
biggest contradiction.

## 4. Two rails — this is "Proof of Work of UBI"

| Rail | Unit | What earns it | Value |
|---|---|---|---|
| **Work** | Denero | doing 5 min of attested work | anchored: 1 DNR = 5 min (~$5 reference) |
| **UBI** | the dividend | being a verified human | a **share**: ~9.53%/yr of the average member's *real* holdings, paid in DNR |

The UBI is a *share*, never a promised $/hr. That's the honest split you were
reaching for: **work is priced (Denero); existence pays a dividend (a share).**

## 5. Tokens float — they don't hold the peg

FTC / FSZT are **fixed-supply** transferable tokens. A fixed supply means the
price **floats** against the anchor; it is set by the market, not declared:

| FTC price | Network value (100M supply) | at $5/DNR reference |
|---|---|---|
| 0.2 DNR | 20,000,000 DNR | ~$100M |
| 1.0 DNR | 100,000,000 DNR | ~$500M |
| 5.0 DNR | 500,000,000 DNR | ~$2.5B |

You **cannot** also fix FTC's price to $5/DNR — fixed supply and a hard price
can't both be true without a reserve. Let it float.

**Blockcoin** as "one bitcoin unit" (say 1 satoshi) is an **external reference**
that floats too — e.g. at BTC $100,000, 1 sat = $0.001 = 0.0002 DNR. It's a
bridge/reference asset, not an anchor.

## 6. The reconciliation, one table

| Unit | Role | Anchored / backed by | Relation to Denero |
|---|---|---|---|
| **Denero (DNR)** | unit of account | **labor-time (the anchor)** | 1 DNR = 5 min |
| **Dividend** | UBI | defined in DNR | a share (~9.5%/yr of avg real holdings) |
| **FTC / FSZT** | transferable token | fixed supply (no peg) | floats, market-set |
| **Blockcoin** | external reference | bitcoin | floats, market-set |
| **US dollar** | external reference | — | guidance rate ($5/DNR) |
| ~~"USDTether"~~ | — | needs real $ reserves | **don't issue** unless audited & reserved |

## 7. What was breaking, precisely

1. `$60/hr = UBI` → it's a **wage** (work rail), not UBI. Fixed.
2. `fixed-supply token = $ price` → impossible without reserves; **float** it. Fixed.
3. `Blockcoin = bitcoin` **and** `= $5/DNR` → two anchors; make it a **reference** that floats. Fixed.
4. `USDTether = a dollar` → a dollar claim needs dollars in the bank; **don't mint** one. Fixed.

Every break was the same mistake: two anchors on one unit. One anchor fixes all four.

## 8. Guardrails (so it stays honest)

- Denero only means "5 minutes of work" if a counterparty **attests** it —
  personhood-gate + challenge court, or it's just a timer.
- $5/DNR is **guidance**, printed as such, never enforced or promised.
- Tokens **float**; never claim a token holds a dollar or a Denero price.
- No "backed"/"stable"/"USD" unit without audited reserves.
- The dividend is a **share**, not an income figure.

## 9. Burn & supply (honest)

A **burn** permanently removes tokens from supply. It lives on the **token rail**
(FTC / FSZT) — never on Denero, which is mutual credit that nets to zero, so there
is nothing there to burn.

- **The real burn:** `FrostEther.burn(amount)` destroys the caller's *own* tokens
  and decrements `totalSupply` on-chain. Anyone can verify the supply dropped. No
  admin can burn someone else's balance.
- **A burn address has no key, by design.** Sending to `0x…dEaD` also removes
  tokens, but the address has **no private key** — that's what makes it a burn.
  There is nothing to generate: if a tool asks you to create a "burn key," it's
  wrong.
- **Effect on the math:** burning is deflationary on a *floating* token — fewer
  tokens, so the market price per token drifts up. It changes neither the Denero
  anchor nor the dividend rule.
- **Say it straight:** a burn is not a buyback and returns no value; don't imply
  it does. Never burn from an address you don't control.

---

*All arithmetic here is computed and checked. Values in dollars are a suggested
reference only — not an offer, a peg, or a forecast.*
