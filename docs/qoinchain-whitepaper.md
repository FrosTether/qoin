# Qoinchain

**Universal basic income as an equation, not a tax**

Draft 0.2 · 29 September 2026 · FrosTether

> **Status:** design proposal for public review. No Qoinchain network, token, or
> sale exists, and nothing in this paper is an offer of anything. Qoinchain is not
> affiliated with Qoin (qoin.com, qoin.world), BPS Financial, the Qoin Association
> or Qoin Foundation, or Post-Quantum Qoin. See [Notices](#notices).
>
> **New in draft 0.2:** Qoin as a universal basic income now depends on the proposed
> Jacob Frost Blockchain Bill Act becoming law. See [The bill](#the-bill).

## Abstract

Anarcho-capitalists reject a state-funded universal basic income (UBI) because it
is paid for by taxation, and taxation is compulsory. But a basic income does not
need a tax. It needs a source of new purchasing power and a rule for dividing it.
Every monetary system already creates new money and hands it to someone first:
under fiat, banks and the state; under Bitcoin, miners. Qoinchain proposes a
voluntary money whose new units go to every participating person in equal shares,
by one equation fixed at genesis:

```math
D = c \cdot \frac{M}{N}
```

Each period, every member receives a dividend D equal to a fixed fraction c of the
money supply M, divided by the number of members N. We show that this rule
(i) redistributes only among people who chose to hold the currency and is balanced
by construction; (ii) is, for its holders, exactly a flat levy on money balances
returned as an equal grant, which is the structure of Friedman's negative income
tax, with no state to administer it; (iii) erases the early-adopter advantage,
because every balance converges toward the average with a half-life of about
7.3 years at c = 10% per year; and (iv) pays a real income of about
ln(1 + c) ≈ 9.5% of the average member's real holdings per year: a share, not a
promised amount. The equation is exact; the head-count N is not. Much of this paper
is therefore about identity: a bonded, challengeable, pseudonymous registry of
persons, the economic condition under which counterfeiting a person does not pay,
and the limits of that design.

> **At a glance**
>
> - **Rule:** each member receives max(D₀, cₑ·M/N) qoin per day, with c = 10% a year, fixed forever.
> - **Issuance:** the dividend is the only way qoin is created. No premine, team allocation, treasury, or admin keys.
> - **Fairness over time:** a newcomer's gap to the founders halves every 7.3 years.
> - **Real value:** the dividend is worth about 9.5% of the average member's real qoin holdings per year.
> - **Hardest problem:** counting people honestly ([Section 6](#6-counting-people-the-hard-part)).

## Contents

1. [The realization](#1-the-realization)
2. [Who gets new money?](#2-who-gets-new-money)
3. [The equation](#3-the-equation)
4. [What the equation implies](#4-what-the-equation-implies)
5. [Why this is anarcho-capitalist](#5-why-this-is-anarcho-capitalist)
6. [Counting people: the hard part](#6-counting-people-the-hard-part)
7. [Protocol design](#7-protocol-design)
8. [What the dividend is actually worth](#8-what-the-dividend-is-actually-worth)
9. [Related systems](#9-related-systems)
10. [Risks and open questions](#10-risks-and-open-questions)
11. [Roadmap](#11-roadmap)
12. [Conclusion](#12-conclusion)
- [The bill](#the-bill)
- [Appendix A. Proofs](#appendix-a-proofs)
- [Appendix B. Proposed genesis parameters](#appendix-b-proposed-genesis-parameters)
- [Appendix C. Reference accounting](#appendix-c-reference-accounting)
- [References](#references)
- [Notices](#notices)

## 1. The realization

The anarcho-capitalist case against universal basic income is not that people
should not have money. It is that a state UBI is financed by taxation, taxation is
collected under threat of force, and a good cause does not make a forced transfer
legitimate. Work incentives, bureaucracy, and cost all matter, but they come second
to that objection.

Most UBI proposals run into it because they answer the funding question with the
state. Thomas Paine's *Agrarian Justice* (1797) proposed paying fifteen pounds to
every person at 21 and ten pounds a year from age 50, funded by a levy on
inheritances that he justified as ground rent owed by landowners [1]. Milton
Friedman's negative income tax (1962) runs through the income tax [2]. Alaska's
Permanent Fund Dividend, paid every year since 1982, comes from the earnings of a
state investment fund built from oil royalties [3]. Each is financed by a state
levy or by a state-owned asset.

Take the objection seriously and remove the state. What is left of UBI?

Two things: a rule (divide something equally among people) and a source (the
something). The rule is easy. The source is the problem. Under voluntary exchange,
you can give someone purchasing power only by taking it from someone who has it, or
by creating new money.

Money is the exception. New units of a money can be created by rule, and creating
them takes nothing from anyone who has not chosen to hold that money. Anyone who
does choose to hold it can read the rule first. Every monetary system already
creates money and hands it to someone first. So if people freely adopt a money
whose rule says *new units go to every participant in equal shares*, the result is
a basic income that nobody was forced to fund.

That is the realization this paper is built on: **a universal basic income does not
need a state. It needs an equation, and a money that people choose.**

Since draft 0.2 the plan also depends on one law: the proposed Jacob Frost
Blockchain Bill Act ([The bill](#the-bill)).

The equation is D = c·M/N. That is the whole policy. No agency administers it; no
legislature can raise it before an election or cut it after one; no one is
means-tested. The rest of this paper examines what that one line does, why it is
consistent with the non-aggression principle, and what it takes to keep N honest,
which is the hard part.

## 2. Who gets new money?

The money supply grows in almost every monetary system. The design question is not
whether new money is created but who receives it first. The value of newly created
money, its *seigniorage*, always goes to someone.

- **Fiat money.** New money enters through bank credit and government spending.
  Richard Cantillon observed in the eighteenth century that the first recipients of
  new money spend it before prices adjust, and so gain at the expense of those who
  receive it last [4]. Today the first recipients are banks, their borrowers, and
  the state. Using fiat money is not fully voluntary: taxes must be paid in it, and
  legal-tender laws privilege it.
- **Bitcoin.** New bitcoin goes to miners on a fixed, halving schedule [5]. No
  authority can change that rule, which was a real advance. But issuance is
  front-loaded by design: the 20-millionth bitcoin was mined in March 2026, so
  about 95% of all bitcoin that will ever exist was issued in its first 17 years.
  Anyone who arrives later has to buy their share from those who came earlier.
- **A third answer.** Give new money to everyone who uses it, equally, by a rule
  fixed in advance. Stéphane Laborde formalized this as the *universal dividend* in
  his *Relative Theory of Money* (2010) [6], and the Ğ1 currency has run a version
  of it since 2017 [7]. Qoinchain adopts his equation.

What Qoinchain contributes is not the formula. It is (a) a justification from
anarcho-capitalist premises, (b) a stricter stance on immutability and exit, (c) an
explicit analysis of the economics of counting people, and (d) an implementation
path on existing EVM chains using the conservative contract conventions of Qoin
Maker.

## 3. The equation

### 3.1 Definitions

| Symbol | Meaning |
|---|---|
| t | Epoch index; one epoch is one day |
| N(t) | Members in good standing at the start of epoch t ([Section 6](#6-counting-people-the-hard-part)) |
| M(t) | Monetary mass at the start of epoch t: every qoin ever issued, including dividends accrued but not yet claimed |
| c | Annual issuance rate, fixed at genesis; proposed 10% |
| cₑ | Per-epoch rate, (1 + c)^(1/365.25) − 1 ≈ 0.0261% per day |
| D₀ | Bootstrap floor, fixed at genesis; proposed 1 qoin per member per day |
| D(t) | Dividend credited to each member for epoch t |
| bᵢ(t) | Balance of account i |

The unit is provisionally called the *qoin* (plural *qoin*). No ticker has been
chosen.

### 3.2 The rule

```math
D(t) = \max\left(D_0,\ c_e \cdot \frac{M(t)}{N(t)}\right)
```

```math
M(t+1) = M(t) + N(t) \cdot D(t)
```

The D = c·M/N of the abstract is this rule without the floor, with c stated per
period.

Nothing else creates qoin. There is no premine, no founder or team allocation, no
treasury, no validator or staking reward, and no owner-controlled mint. Anyone can
hold and send qoin. Only members receive the dividend.

### 3.3 Two regimes

**Relative regime.** Once cₑ·M/N ≥ D₀, the second term governs, and the money
supply grows at exactly cₑ per epoch, however many members there are:

```math
M(t+1) = M(t) + N(t) \cdot c_e \frac{M(t)}{N(t)} = (1 + c_e)\, M(t)
```

**Bootstrap regime.** M starts at zero, so the floor pays D₀ per member per epoch
until the relative term catches up. With constant membership that takes 1/cₑ
epochs: **about 10.5 years at c = 10%, whatever the value of D₀**
([Appendix A.5](#appendix-a-proofs)). Through that decade the nominal dividend is
flat, and nominal supply growth falls as roughly 1/T per year after T years: 50%
at two years, 20% at five, and about 10% at ten, where it joins the relative
regime without a jump. Faster membership growth lengthens the bootstrap. The
absolute size of D₀ is arbitrary; only ratios matter.

Ğ1 bridges the same gap differently, with the smoothed recurrence
DU(t+1) = DU(t) + c²·M(t)/N(t+1), which converges to the same ratio D = c·M/N [7].
Qoinchain uses the floor instead, so that once the bootstrap ends the equation
holds exactly rather than asymptotically.

### 3.4 The dividend as the unit of account

In the relative regime, D ÷ (M/N) = cₑ at every epoch. Each member receives the
same fraction of the average balance, whatever the size of the network. So the
natural way to measure qoin is in dividends. Following Laborde, we define
**1 DU as the current dividend D(t)** and recommend that wallets show balances and
prices in DU alongside nominal qoin. Measured in DU:

- every member receives exactly 1 DU per day;
- the average balance is always 1/cₑ ≈ 3,832 DU (about 10.5 years of dividends),
  and a member who neither spends nor earns converges to it;
- prices are stable whenever real money demand per member is stable, whatever the
  nominal inflation rate ([Appendix A.6](#appendix-a-proofs)).

### 3.5 Choosing c

Two independent arguments put c near 10% per year:

1. **Laborde's temporal symmetry.** The *Relative Theory of Money* chooses c so
   that each generation co-creates an equal share of the money over its lifetime,
   which gives c = ln(ev/2) ÷ (ev/2) for life expectancy ev [6]. At ev = 80 years,
   c ≈ 9.2% per year.
2. **Convergence within a generation.** Under the rule, any gap between a balance
   and the average shrinks by a factor of 1/(1 + c) per year (Proposition 4).
   Requiring 90% of a founder's head start to disappear within one 25-year
   generation gives c = 10^(1/25) − 1 ≈ 9.65%.

Qoinchain proposes c = 10%, fixed forever.
[Section 8.2](#82-why-not-a-larger-c) explains why a larger c would not produce a
proportionally larger dividend.

## 4. What the equation implies

Proofs are in [Appendix A](#appendix-a-proofs). Propositions 2 to 4 assume the
relative regime, a constant N, and no trading, which isolates what the rule itself
does. Trading moves balances by voluntary exchange, which is the point of money.

**Proposition 1: predictable supply.** In the relative regime M grows at exactly c
per year, independent of N. Outside the bootstrap, supply growth does not depend
on membership at all.

**Proposition 2: balanced by construction.** Let sᵢ = bᵢ/M be account i's share of
all qoin. For a member, one epoch changes it by

```math
s_i(t+1) - s_i(t) = \frac{c_e}{1 + c_e}\left(\frac{1}{N} - s_i(t)\right)
```

Members holding less than the average M/N gain share. Members holding more lose
share. An average holder is unaffected. The changes across all holders sum to
exactly zero. Holders who are not members, such as companies, exchanges, and people
who never registered, lose share at c/(1 + c) ≈ 9.1% per year and receive nothing:
they use the currency without taking part in its dividend.

**Proposition 3: a negative income tax without a state.** Rescale units after each
epoch so that the supply stays the same. Then one epoch of the rule is exactly

```math
b_i' = (1 - \tau)\, b_i + \tau \cdot \frac{M}{N}, \qquad \tau = \frac{c_e}{1 + c_e}
```

That is a flat levy τ on every qoin balance, with all the proceeds returned as an
equal grant to each person. It is the structure of Friedman's negative income tax,
and of a basic income funded by a flat tax [2], applied to money balances instead
of income, and to willing holders instead of taxpayers. Over a year the levy is
c/(1 + c) ≈ 9.1%. The equation is not a metaphor for redistribution. It is
redistribution with the coercion removed.

**Proposition 4: no permanent early-adopter premium.** Let rᵢ = bᵢ ÷ (M/N) be a
balance relative to the average. For an account that only receives dividends,

```math
r_i(t) - 1 = \big(r_i(0) - 1\big)\,(1 + c_e)^{-t}
```

Every relative balance converges geometrically to the average. At c = 10%, a
newcomer who starts with nothing closes half the gap to a founder in **7.3 years**
and 90% of it in **24.2 years**. Under a fixed-supply money, a share acquired early
is kept forever, absent trade. Under Qoinchain it fades toward the average within a
generation.

**Proposition 5: fraud degrades gracefully.** If a fraction f of counted members
are fake, each honest member receives (1 − f) of the dividend an honest count would
give them, and the fakes take the rest. Fraud leaks value in proportion to its
prevalence. It does not break the system. That makes f the key security number,
and [Section 6](#6-counting-people-the-hard-part) is about keeping it small.

**Proposition 6: two views of one equation.** Measured in qoin, the currency
inflates at c. Measured in DU, it is a demurrage currency: each member receives
1 DU per epoch and every balance shrinks by a factor of 1/(1 + cₑ) per epoch, about
9.1% per year. Gesell's stamp scrip [8] and Circles [9] use the second form
directly. They are the same equation in different units.

## 5. Why this is anarcho-capitalist

### 5.1 The argument

1. A transfer is legitimate if it is voluntary. Initiating force against persons or
   property is not (the non-aggression principle).
2. A state UBI is financed by taxation, which is not voluntary [10].
3. Creating money always transfers purchasing power to whoever receives the new
   money ([Section 2](#2-who-gets-new-money)).
4. In a free market for money, with no legal-tender privilege and no monopoly
   issuer, people may use whichever money has the rules they prefer [11].
5. A money whose issuance rule gives each participating person an equal share of new
   units, fixed before anyone joins and adopted freely, moves purchasing power only
   among people who accepted that rule.
6. So a UBI implemented as the issuance rule of a voluntary money is consistent with
   the non-aggression principle. It is not a policy imposed on people but a property
   of a product they choose.

### 5.2 Contract, not policy

A qoin holder is party to a public, immutable contract whose terms are the equation
and the genesis parameters. Like a mutual society's rules, or an issuance schedule
written into a company's charter, the terms are accepted by acquiring the
instrument, can be read in full beforehand, and cannot be changed afterward by
anyone: not the authors, not a majority, not a foundation. Nobody outside the
contract is bound by it, and it touches no property outside the ledger.

### 5.3 Exit, not voice

Qoinchain has no on-chain governance and no parameter votes. Albert Hirschman
described two responses to an organization you disagree with: voice, meaning working
to change it, and exit, meaning leaving it [12]. Qoinchain relies on exit. If c is
wrong or the registry turns out to be weak, the remedy is a competing currency or a
fork with different parameters, and holders moving to it. This is Hayek's
competition in currencies [11] applied to the rules themselves: the market, not a
committee, finds the right dividend.

### 5.4 Compared with a state UBI

| | State UBI | Qoinchain dividend |
|---|---|---|
| Funded by | Taxation (compulsory) | Dilution of holders who opted in |
| Pays | A promised amount of currency | A share: 1 DU per day, whose real value the market sets |
| Administered by | An agency and eligibility rules | One equation; no administrator |
| Political risk | Raised or cut by legislatures | None; changing it requires a new currency |
| Means test | Common, creating poverty traps | None; earning more never reduces the dividend |
| Who can receive it | Citizens of one state | Any person on Earth who can be counted |
| Guarantee | The state's power to tax | None; a dividend in a money nobody wants is worthless |

The last row is the honest price of the first. A state can promise an amount
because it can take money to pay it. Qoinchain takes nothing, so it can promise only
a share.

### 5.5 Objections from the right

**"Inflation is theft."** Theft is taking without consent. The objection has real
force against monopoly fiat money, whose issuers can change the rules and whose
users cannot easily leave [10]. Qoin's issuance is disclosed in advance, can never
change, and applies only to people who chose to hold qoin. It is closer to a
membership fee paid in dilution than to debasement.

**"Sound money shouldn't inflate."** Then do not hold your savings in qoin. It is
designed as a medium of exchange that pays a dividend, not as a store of value; keep
savings in gold, bitcoin, land, or equities. If the market wants non-inflating
money for everything, qoin will fail, and it should.

**"It pays people not to work."** The dividend is not taken from anyone's wages or
property. It comes from the relative dilution of above-average qoin balances, held
by people who chose to hold them. A merchant who accepts qoin does so because a
network of customers with a steady income is worth more to them than the holding
cost, and remains free to price that cost in or to refuse qoin.

**"Counting people requires an authority."** Only for receiving the dividend.
Holding and sending qoin require no identity at all. The registry has no central
gatekeeper, is pseudonymous, and answers one question only: is this a unique, living
person? It cannot touch anyone's balance ([Section 7.1](#71-invariants)).

**"Why not charity?"** Charity is voluntary and admirable, but it is discretionary
and personal. The dividend is neither: it is unconditional, identical for every
member, and involves no donor or recipient. The two complement each other.

## 6. Counting people: the hard part

The equation is exact; N is not. Anyone who can register a second identity collects
a second dividend, taken from every honest member (Proposition 5). Every UBI
currency to date has found proof of personhood harder than monetary design, and
Qoinchain will too.

### 6.1 Requirements

The member registry must be:

1. **Unique:** one living person, one membership.
2. **Live:** memberships lapse when people die or leave, so N tracks living people.
3. **Open:** anyone can join without a central gatekeeper, a state ID, or a
   biometric database.
4. **Private:** membership does not reveal legal identity, and eventually dividend
   claims cannot be linked to vouching relationships.
5. **Unprofitable to cheat:** a fake identity costs more to create and keep than it
   collects.

No known system meets all five. Qoinchain meets the first four by design and aims to
meet the fifth at the margin.

### 6.2 Prior approaches

- **Web of trust (Ğ1):** membership requires certifications from five existing
  members [7]. It is decentralized and costs nothing to use, but collusion rings are
  hard to detect, and certifying a fake puts nothing at stake.
- **Personal currencies and trust graphs (Circles):** every person mints their own
  token at 1 CRC per hour, and trust relationships decide which tokens are
  interchangeable, so a fake identity's tokens are worth only what its trusters
  will accept [9].
- **Vouching with adjudication (Proof of Humanity):** a video submission, vouching
  by registered humans, and challenges decided by the Kleros court. Its UBI token,
  launched in March 2021, streamed 1 UBI per hour to each registered human [13].
- **Synchronous ceremonies (pseudonym parties, Idena):** one person can only be in
  one place at one time. Ford and Strauss proposed in-person pseudonym parties in
  2008 [14]. Idena launched in 2019 with online validation ceremonies built on
  human-solvable puzzles [15].
- **Biometrics (such as iris scans):** strong uniqueness, bought with biometric data
  collection, special hardware, and a central point of trust. Qoinchain does not
  require biometrics.

### 6.3 Qoinchain's registry

**Admission.** A candidate becomes a member when k = 5 members in good standing
vouch for them. Each voucher locks a bond of B DU (proposed: 150 DU, about five
months of dividends) for as long as the vouch is active. Each member may issue at
most one new vouch every seven days.

**Challenges.** Anyone may challenge any membership by posting a deposit and
evidence that the member is a duplicate, fictitious, or dead. The case goes to a
juror panel drawn uniformly at random from members who have opted in to serve and
posted a juror deposit. Jurors who vote with the final majority are paid from the
deposits of those who do not; this is the Schelling-point design pioneered by
Kleros [13]. Decisions can be appealed to larger panels. Unlike Kleros, Qoinchain
draws jurors per person, not per coin staked, so holding qoin does not buy influence
over the court.

**Outcomes.** If a challenge succeeds, the membership is revoked, the vouchers'
bonds are slashed and paid to the challenger as a bounty, and the vouchers lose the
right to vouch for a period. If it fails, the challenger's deposit goes to the
challenged member and the jurors. Revocation stops future dividends. **It never
freezes, seizes, or reverses a balance.** The protocol has no blacklist.

**Renewal.** Members renew once a year by signing with their key while holding at
least k active vouches. A vouch expires after two years unless renewed. A person who
dies or loses their key stops being counted within a year. Their existing balance
remains property, available to whoever holds the key.

**Evidence, not authorities.** Members may attach optional attestations from other
personhood systems, such as attendance at a pseudonym party or a validation from
another registry, to strengthen their defense against a challenge. No particular
attestation is ever required, and neither is a state ID.

### 6.4 When faking a person doesn't pay

Measured in DU, a fake identity collects 365.25 DU a year, by definition. Let λ be
the rate per year at which the challenge market exposes fakes, so a fake survives
1/λ years on average. When a fake is exposed, its k vouchers lose k·B between them.
Colluding vouchers profit from a fake only if the dividends it is expected to
collect exceed the slashing they expect, so faking is unprofitable when

```math
\lambda \cdot k \cdot B \ \ge\ 365.25\ \text{DU per year}
```

With k = 5 and B = 150 DU, this holds whenever λ ≥ 0.49 per year, that is, when a
typical fake is exposed within about two years. The bond each voucher needs for
other combinations:

| Vouches k | λ = 0.25 per year | λ = 0.5 per year | λ = 0.75 per year |
|---|---|---|---|
| 5 | 292 DU | 146 DU | 97 DU |
| 10 | 146 DU | 73 DU | 49 DU |

Because every quantity is in DU, the condition is scale-free: it works the same way
whatever the size of the network or the nominal supply. It also puts a number on
what honest identity costs. In the relative regime the average balance is exactly
1/cₑ DU ([Section 3.4](#34-the-dividend-as-the-unit-of-account)), so the share of
all qoin that must sit in bonds is

```math
\frac{k \cdot B}{1/c_e} \ \ge\ \frac{365.25 \cdot c_e}{\lambda} \ \approx\ \frac{\ln(1 + c)}{\lambda}
```

That is about 19% of the supply at λ = 0.5 per year and about 10% at λ = 1. This is
the registry's security budget, paid in locked-up capital rather than in new
issuance.

### 6.5 Known weaknesses

- **The young network is the weak network.** In the bootstrap years, balances are
  too small to fund 150-DU bonds. The proposal is to ramp B linearly from zero
  across the bootstrap decade. That keeps about 20% of the supply bonded throughout,
  but it means full economic deterrence arrives only when the bootstrap ends. Until
  then, admission should lean on in-person verification (a genesis pseudonym party)
  and tighter rate limits.
- **Bonds favor capital.** People with little qoin cannot vouch much, which cuts
  against the purpose of a UBI. Underwriting markets, where third parties post bonds
  for vouchers and price the risk, fit the design and could help, but the tension is
  real.
- **Court capture.** Fakes that get in are also drawn as jurors. Random sampling and
  escalating appeals work only while honest members are a clear majority of those
  who serve.
- **Sold or coerced identities.** A real person can sell their membership key or be
  forced to hand it over. No registry can see this. Renewal and challenges only
  limit how long it pays.

These are the design's main unsolved problems.
[Section 10](#10-risks-and-open-questions) lists them with the rest.

## 7. Protocol design

### 7.1 Invariants

The reference implementation must enforce the following, and audits should check
them:

1. **One source of issuance.** The dividend is the only code path that creates
   qoin.
2. **Conservation.** At every epoch boundary, M equals the sum of all balances, all
   escrowed bonds and deposits, and all accrued but unclaimed dividends.
3. **Determinism.** D(t) is a pure function of M(t), N(t), and the genesis
   constants.
4. **No privileged keys.** The ledger and the dividend engine have no owner, admin,
   pause switch, blacklist, upgrade proxy, or fee switch.
5. **Separation.** The registry decides who counts in N. It can never move, freeze,
   or reduce a balance, except to slash bonds and deposits that members locked
   voluntarily under published rules.
6. **Immutability.** c, D₀, the epoch length, and the registry rules are constants
   fixed at genesis.

These extend the conventions Qoin Maker already applies to the token contracts it
generates: plain, readable contracts with no hidden transfer tax, no honeypot, no
blacklist drain, and no upgrade proxy.

### 7.2 Components

- **Ledger.** An ERC-20-compatible balance and transfer contract, so existing
  wallets and exchanges can hold qoin without special integration. Anyone can hold
  and transfer qoin.
- **Dividend engine.** Epoch accounting and claims. Dividends accrue to each member
  automatically; claiming mints them into the member's balance. Accrued but
  unclaimed dividends count toward M, so the dividend never depends on how often
  people claim. Claims can be sponsored by third parties through
  account-abstraction paymasters, so members do not need to hold the host chain's
  gas token. [Appendix C](#appendix-c-reference-accounting) gives constant-time
  accounting.
- **Registry.** Vouches, bonds, renewals, and revocations. N(t) is the number of
  members in good standing at the start of epoch t.
- **Court.** Challenge deposits, juror selection, votes, appeals, and payouts.

### 7.3 Why Qoinchain doesn't start as a chain

Despite the name, Qoinchain does not begin as its own blockchain. A new layer-1
needs validators, validators need to be paid, and paying them in new qoin would
break invariant 1. Fee-only security is weak while transaction volume is low. So
Qoinchain launches as contracts on an existing EVM chain whose security is already
paid for, the same environment Qoin Maker targets. "Qoinchain" names the protocol
and, if volume ever justifies it, a dedicated rollup to host it, with operators paid
from transaction fees and never from issuance.

### 7.4 Bugs and upgrades

The core contracts are immutable, so bugs cannot be patched in place. The
mitigations are a small and simple core, independent audits, formal verification of
the dividend arithmetic, and a public bug bounty before genesis. If a critical flaw
is found anyway, the remedy is exit: a corrected version is deployed with a
voluntary, one-way, one-for-one migration contract. No one can force holders to
migrate, and no one can migrate them without their signature.

### 7.5 Privacy

Qoin transfers are as public as the host chain's. The vouch graph is public but
pseudonymous. A later phase will let members claim dividends with a zero-knowledge
proof of membership and a per-epoch nullifier, in the style of Semaphore [16], so
the address that receives dividends cannot be linked to the identity that was
vouched for.

## 8. What the dividend is actually worth

### 8.1 A share, not an amount

Let V be the real market value of all qoin, for example in dollars of constant
purchasing power. If real demand for qoin is steady, each member's dividends over a
year are worth, when received,

```math
d_{\text{real}} \ \approx\ \ln(1 + c) \cdot \frac{V}{N} \ \approx\ 0.095 \cdot \frac{V}{N}\ \text{per year}
```

**The real basic income is about 9.5% of the average member's real qoin holdings per
year.** The equation guarantees the share. The market decides what the share is
worth.

| Average qoin held per member (real value) | Real dividend per member per year |
|---|---|
| $10 | $0.95 |
| $100 | $9.53 |
| $1,000 | $95 |
| $10,000 | $953 |
| $50,000 | $4,766 |

A dividend that matters requires people to hold substantial balances in qoin, which
happens only if qoin is useful as everyday money. **No promise of real value is made
or implied.** Qoin has no peg, no backing, no buyback, and no treasury. Members who
sell their dividends as they arrive create steady selling pressure, and the price
settles wherever buyers are willing to hold qoin.

### 8.2 Why not a larger c?

Raising c does not raise the dividend without limit. The costlier a money is to
hold, the less of it people hold, so the real dividend is c times a real money demand
that shrinks as c grows. Cagan and Bailey analyzed this trade-off, since nicknamed
the seigniorage Laffer curve, in 1956 for national currencies with captive users
[17, 18]. Qoin has no captive users and many close substitutes, so its demand is
probably far more sensitive to c, and the dividend-maximizing rate may be well below
anything seen in national currencies. Qoinchain sets c for fairness between
generations ([Section 3.5](#35-choosing-c)), not to maximize the dividend. Whether
holders will tolerate 10% is for the market to decide.

### 8.3 Prices

If the velocity of money is constant, prices in qoin rise at roughly c minus the
growth rate of real demand for qoin. Measured in DU, prices depend only on real
money demand per member ([Appendix A.6](#appendix-a-proofs)). That is why wallets
should show DU: someone whose everyday prices hold steady in DU has a stable basic
income, whatever the nominal numbers do.

### 8.4 Demand is the real bottleneck

The equation does not create demand. Ğ1, the longest-running universal-dividend
currency, reached a peak of 8,685 members in July 2024 and had 7,675 on
8 September 2025, after eight years in operation, according to a community report
[19]. Qoinchain's bet is that a money whose every user has a steady income is
attractive to merchants as a network of customers. Whether that bet is right is an
empirical question this paper does not claim to have answered.

## 9. Related systems

| System | New units go to | Issuance rule | Counting people | Holding cost |
|---|---|---|---|---|
| Fiat money | Banks, borrowers, the state | Discretionary | Not applicable | Inflation set by policy |
| Bitcoin (2009) | Miners | Fixed halving schedule, 21M cap | Not applicable | Under 1% a year and falling; none after the cap |
| Ğ1 (2017) | Members, equally | DU(t+1) = DU(t) + c²·M(t)/N(t+1), c = 4.88% per half-year | Web of trust, 5 certifications | About 9.1% a year dilution |
| UBI token, Proof of Humanity (2021) | Registered humans | 1 UBI per hour, streamed | Video, vouching, Kleros disputes | Dilution from per-person issuance |
| Circles 2.0 (2025) | Each person mints their own | 1 CRC per hour | Trust graph | 7% a year demurrage |
| **Qoinchain (proposed)** | **Members, equally** | **max(D₀, cₑ·M/N) daily; c = 10% a year** | **Bonded vouching, challenge court, yearly renewal** | **About 9.1% a year dilution** |

## 10. Risks and open questions

1. **Identity at scale.** Can bonded vouching plus a challenge market keep f small
   against organized collusion, identity markets, and coercion? This is the central
   open problem ([Section 6.5](#65-known-weaknesses)).
2. **Bonds versus inclusion.** k, B, and the bond ramp trade Sybil resistance
   against access for people without capital. They should be fixed only after
   adversarial testnet games.
3. **Registry rigidity.** Immutable registry rules cannot adapt to new attacks
   without a new version and a migration. A narrow, long-timelocked upgrade path for
   the registry alone might be worth its capture risk. That is unresolved.
4. **Demand.** Whether enough people will hold enough qoin for the dividend to
   matter ([Section 8.4](#84-demand-is-the-real-bottleneck)).
5. **Bootstrap length.** About a decade of flat nominal dividends before the
   relative regime, longer if membership grows quickly.
6. **Legal and tax treatment.** Dividends may be taxable income for recipients in
   some jurisdictions, and front-ends, wallets, and exchanges may be regulated as
   money transmitters or under AML rules. The design avoids features commonly
   associated with investment offerings (no sale, premine, team allocation, or
   promised return), but that is a design choice, not a legal conclusion.
7. **Smart-contract risk.** Immutable code has to be right the first time.
8. **Children.** A universal income arguably should count children. Whether
   guardians could hold memberships for minors without opening a Sybil channel is
   unresolved.
9. **Licensing.** Qoin Maker is source-available under QMSAL 1.0, which restricts
   production use; each version also becomes available under Apache-2.0 on
   26 September 2030. A currency's credibility depends on anyone being able to
   verify and fork its rules ([Section 5.3](#53-exit-not-voice)). The license for
   Qoinchain's reference contracts is an open decision.
10. **The bill.** Qoin as a universal basic income depends on the proposed Jacob
    Frost Blockchain Bill Act becoming law ([The bill](#the-bill)). Until it passes,
    the dividend described here is a design, not an income.

## 11. Roadmap

No dates are promised. Each phase begins only when the previous one is complete.

- **Phase 0: paper.** Public review of this design, and a reference simulation of
  the dividend and registry economics.
- **Phase 1: testnet.** Reference contracts on a public testnet, and adversarial
  Sybil games with real stakes, funded by bounties rather than issuance, to
  calibrate k, B, and the challenge process.
- **Phase 2: audit and genesis.** At least two independent audits, then genesis on
  an existing EVM chain with a founding cohort verified at an in-person event. No
  sale, no premine, and no allocation to anyone, the authors included, beyond the
  dividend every member receives.
- **Phase 3: privacy and scale.** Zero-knowledge dividend claims, and a dedicated
  rollup only if volume justifies one.
- **The bill.** Qoin as a universal basic income depends on the proposed Jacob
  Frost Blockchain Bill Act becoming law ([The bill](#the-bill)).

## 12. Conclusion

Every money has a rule for who gets new units. Fiat's rule favors whoever stands
closest to the source of new money. Bitcoin's rule favors whoever came first.
Qoinchain's rule is that every person who chooses the currency gets an equal share,
forever, by an equation nobody can change.

For an anarcho-capitalist, the problem with basic income was never that people
receive money. It was the tax collector standing behind the transfer. Take the tax
collector away and what remains is an equation, D = c·M/N, and a question only the
market can answer: will people choose a money that shares its seigniorage with
everyone? Qoinchain is a proposal to find out.

## The bill

Qoin as a universal basic income depends on the proposed **Jacob Frost Blockchain
Bill Act** becoming law. It is a proposal, not law.

- **Video:** [the bill on YouTube](https://www.youtube.com/shorts/s5TBYt0H9oU), on
  the channel [@frostforcongress](https://www.youtube.com/@frostforcongress).
- **Text:** not published in this repository yet. When it is, this section will
  summarize what the bill does and how it fits the design above.

## Appendix A. Proofs

Unless stated otherwise, each proof assumes the relative regime (D = cₑ·M/N), a
constant N, and no trading.

**A.1 Supply growth.** M(t+1) = M(t) + N·cₑ·M(t)/N = (1 + cₑ)·M(t). Over a year,
(1 + cₑ)^365.25 = 1 + c. ∎

**A.2 Shares.** A member's balance becomes b + cₑM/N while M becomes (1 + cₑ)M, so
s′ = (s + cₑ/N)/(1 + cₑ) and s′ − s = cₑ(1/N − s)/(1 + cₑ). A non-member's share
becomes s/(1 + cₑ). If members hold total share S, the members' new shares sum to
(S + cₑ)/(1 + cₑ) and the non-members' to (1 − S)/(1 + cₑ), which together make 1.
Shares are conserved. ∎

**A.3 Levy and grant.** Divide every balance by (1 + cₑ) after the epoch, so the
supply returns to M. Then b′ = (b + cₑM/N)/(1 + cₑ) = (1 − τ)b + τ·M/N, because
1/(1 + cₑ) = 1 − τ and cₑ/(1 + cₑ) = τ. Compounded over a year, the levy is
1 − (1 + c)⁻¹ = c/(1 + c). ∎

**A.4 Convergence.** With r = b ÷ (M/N): r′ = (b + cₑM/N) ÷ ((1 + cₑ)M/N) =
(r + cₑ)/(1 + cₑ), so r′ − 1 = (r − 1)/(1 + cₑ). Iterating gives the result. The gap
halves after ln 2 ÷ ln(1 + c) = 7.27 years and shrinks by 90% after
ln 10 ÷ ln(1 + c) = 24.16 years. ∎

**A.5 Bootstrap length.** Starting from M(0) = 0 with constant N, the floor pays D₀
per member per epoch, so M(t) = N·D₀·t. The relative term reaches the floor when
cₑ·D₀·t = D₀, at t* = 1/cₑ epochs, which is 1/(365.25·cₑ) = 10.49 years at
c = 10%. D₀ cancels. At T years into the bootstrap, annual supply growth is
365.25·N·D₀/M = 1/T. ∎

**A.6 Prices in DU.** Let m be real money demand (the real value of all qoin) and
P = M/m the price level. In the relative regime a price expressed in DU is
P/D = (M/m) ÷ (cₑM/N) = 1/(cₑ·m/N), which depends only on real money demand per
member. ∎

**A.7 Real dividend.** With m constant, a member's real dividend per epoch is
D/P = (cₑM/N)·(m/M) = cₑ·m/N. Over a year that is 365.25·cₑ·m/N ≈ ln(1 + c)·m/N
≈ 0.0953·m/N. ∎

**A.8 Fraud.** With H honest and F fake members, f = F/(H + F). Each identity
receives cₑM/(H + F), where an honest count would give cₑM/H. The ratio is
H/(H + F) = 1 − f. ∎

**A.9 The DU view.** Let x = b/D. For a member, b′ = b + D and D′ = (1 + cₑ)D (by
A.1, with constant N), so x′ = (x + 1)/(1 + cₑ): one DU is added, then the balance
decays by the factor 1/(1 + cₑ). The fixed point is x* = 1/cₑ ≈ 3,832 DU. ∎

**A.10 Registry security.** Ignore discounting and assume the vouchers' bonds stay
at risk for the fake's whole life. A fake then collects 365.25 DU per year for an
expected 1/λ years, and its exposure costs its vouchers k·B DU. Faking is
unprofitable if and only if λ·k·B ≥ 365.25. At the smallest such bond, the bonded
share of supply in the relative regime is k·B·cₑ = 365.25·cₑ/λ ≈ ln(1 + c)/λ. ∎

## Appendix B. Proposed genesis parameters

| Parameter | Proposed value | Notes |
|---|---|---|
| Annual rate c | 10% | Fixed forever ([Section 3.5](#35-choosing-c)) |
| Epoch length | 1 day (86,400 s) | |
| Per-epoch rate cₑ | 1.1^(1/365.25) − 1 ≈ 0.000261 | |
| Bootstrap floor D₀ | 1 qoin per member per epoch | The absolute value is arbitrary |
| Decimals | 18 | ERC-20 convention |
| Vouches to join or renew (k) | 5 | Calibrate on testnet |
| Bond per vouch (B) | 150 DU | Ramps linearly from 0 over the bootstrap; calibrate on testnet |
| New vouches per member | At most 1 every 7 days | |
| Vouch lifetime | 2 years, renewable | |
| Membership renewal | Every 365 days | |
| Challenge deposit | 30 DU | Calibrate on testnet |
| Juror selection | Uniform over opted-in members | Per person, not per coin |
| Premine, allocations, treasury | None | |
| Admin keys | None | |

Values marked for calibration are fixed only after the Phase 1 games. After genesis,
none of these values can change.

## Appendix C. Reference accounting

Dividends accrue through a global cumulative index, so no transaction ever has to
loop over members.

```text
constants: c_e, D0
state:     M          # monetary mass, including accrued but unclaimed dividends
           N          # members in good standing
           index      # cumulative dividend per member since genesis
           last       # last finalized epoch
           member[a] = { active, checkpoint, owed }

finalize():                                # runs at the start of every call
    while last < current_epoch():
        last += 1
        if N > 0:
            D      = max(D0, c_e * M / N)  # dividend for epoch `last`
            M     += N * D
            index += D

join(a):                                   # after k vouches are recorded
    finalize()
    member[a] = { active: true, checkpoint: index, owed: 0 }
    N += 1                                 # first dividend: next epoch

lapse_or_revoke(a):
    finalize()
    member[a].owed      += index - member[a].checkpoint
    member[a].checkpoint = index
    member[a].active     = false
    N -= 1                                 # balances are never touched

claim(a):
    finalize()
    if member[a].active:
        member[a].owed      += index - member[a].checkpoint
        member[a].checkpoint = index
    mint(a, member[a].owed)                # M already counts this amount
    member[a].owed = 0
```

When no one joins or leaves between two calls, the loop has a closed form. In the
relative regime, M is multiplied by (1 + cₑ)^k over k epochs and the index grows by
(M/N)·((1 + cₑ)^k − 1). In the bootstrap regime both grow linearly, and the epoch at
which the regime switches can be computed directly. Finalization therefore costs
O(1) however long the network was idle. Rounding always favors under-issuance, and M
is increased by exactly the amounts credited to the index, so conservation
(invariant 2) holds exactly.

## References

1. Paine, T. (1797). *Agrarian Justice.* https://www.ssa.gov/history/paine4.html
2. Friedman, M. (1962). *Capitalism and Freedom*, ch. 12, "The Alleviation of
   Poverty." University of Chicago Press.
3. Alaska Department of Revenue, Permanent Fund Dividend Division.
   https://pfd.alaska.gov/
4. Cantillon, R. (1755). *Essai sur la nature du commerce en général.*
5. Nakamoto, S. (2008). "Bitcoin: A Peer-to-Peer Electronic Cash System."
   https://bitcoin.org/bitcoin.pdf. Under the issuance schedule, cumulative supply
   reaches 20 million at block 939,999, which was mined in March 2026.
6. Laborde, S. (2010). *Théorie Relative de la Monnaie* (Relative Theory of Money).
   https://trm.creationmonetaire.info/
7. Duniter and the Ğ1 currency, launched 8 March 2017 with 59 members.
   https://duniter.org/
8. Gesell, S. (1916). *Die natürliche Wirtschaftsordnung* (The Natural Economic
   Order). The stamp scrip of Wörgl, Austria (1932–33) applied his demurrage idea.
9. Circles. Gnosis, "Gnosis Launches Circles 2.0" (21 May 2025),
   https://www.businesswire.com/news/home/20250521225718/en/Gnosis-Launches-Circles-2.0-A-Trust-Based-Digital-Currency-Where-Users-Issue-Their-Own-Tokens-Over-Time;
   contracts: https://github.com/aboutcircles/circles-contracts-v2
10. Rothbard, M. N. (1963). *What Has Government Done to Our Money?* and (1982).
    *The Ethics of Liberty.*
11. Hayek, F. A. (1976). *Denationalisation of Money.* Institute of Economic
    Affairs.
12. Hirschman, A. O. (1970). *Exit, Voice, and Loyalty.* Harvard University Press.
13. Kleros (2021). "Introducing UBI: Universal Basic Income for Humans."
    https://blog.kleros.io/introducing-ubi-universal-basic-income-for-humans/;
    Proof of Humanity documentation:
    https://docs.kleros.io/products/proof-of-humanity
14. Ford, B., and Strauss, J. (2008). "An Offline Foundation for Online Accountable
    Pseudonyms." SocialNets 2008. https://bford.info/pub/net/sybil.pdf
15. Idena (2019). *Idena Concept Paper.* https://www.idena.io/IdenaConceptPaper.pdf
16. Semaphore, Privacy & Scaling Explorations. https://docs.semaphore.pse.dev/
17. Cagan, P. (1956). "The Monetary Dynamics of Hyperinflation." In M. Friedman
    (ed.), *Studies in the Quantity Theory of Money.* University of Chicago Press.
18. Bailey, M. J. (1956). "The Welfare Cost of Inflationary Finance." *Journal of
    Political Economy* 64(2).
19. Monnaie Libre et Transitions (13 September 2025). "Évolution de la toile de
    confiance en 2025."
    https://www.mlet.fr/2025/09/13/evolution-de-la-toile-de-confiance-en-2025/

## Notices

- **Not affiliated.** Qoinchain and Qoin Maker are not affiliated with Qoin
  (qoin.com, qoin.world), BPS Financial Pty Ltd, the Qoin Association or Qoin
  Foundation, or Post-Quantum Qoin. Here "Qoin" is the name of this project's
  software and proposed protocol.
- **No offer.** No Qoinchain network, token, or sale exists. Nothing in this paper is
  an offer or solicitation to buy, sell, or hold any asset, and nothing in it
  promises value or returns.
- **Not advice.** Nothing here is legal, tax, investment, or financial advice.
  Monetary, securities, AML/CTF, consumer-protection, and tax law differ by
  jurisdiction; get qualified counsel.
- **Proposals, not commitments.** Parameters, mechanisms, and phases are proposals
  that may change before genesis. By design, they cannot change after it.
- **Copyright.** © 2026 FrosTether and contributors. Distributed with the
  FrosTether/qoin repository under its [LICENSE](../LICENSE).
