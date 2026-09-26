# Qoin Maker

Published in [`FrosTether/qoin`](https://github.com/FrosTether/qoin).

Source-available factory for **standard ERC-20 tokens**.

Generate an inspectable Solidity contract plus a Foundry project. No hidden
transfer tax, no honeypot, no blacklist drain. Those patterns are out of scope
on purpose.

**Not affiliated** with Qoin on Base (`qoin.com`), the former Qoin Foundation,
or Post-Quantum Qoin. "Qoin" here is the product name of this generator.

## Why it exists

Most "coin makers" are either:

- closed websites that emit unauditable bytecode, or
- toy gists with no license you can actually sell.

Qoin Maker keeps the generator readable, ships only conservative templates, and
uses a **source-available + paid Production Use** license so the project can
fund itself. See [`LICENSE`](LICENSE), [`PRICING.md`](PRICING.md), and
[`COMMERCIAL_LICENSE.md`](COMMERCIAL_LICENSE.md).

## Install

```bash
python3 -m pip install -e .
qoin-maker --version
```

Python 3.10+ is enough. No runtime dependencies.

## Generate a token project

```bash
qoin-maker generate \
  --name "Harbor Qoin" \
  --symbol HQN \
  --supply 1000000 \
  --decimals 18 \
  --burnable \
  --chain base \
  --out ./harbor-qoin
```

Useful flags:

| Flag | Meaning |
|---|---|
| `--mintable` | Owner can mint whole tokens |
| `--capped --cap 2000000` | Hard cap on raw supply |
| `--burnable` | Holders can burn |
| `--no-ownable` | No owner (ignored if mintable) |
| `--chain base` | README hint only — you still pick the RPC |

Then:

```bash
cd harbor-qoin
# forge build   # if you have Foundry installed
```

`qoin-maker explain ...` prints the normalized spec as JSON without writing files.
`qoin-maker license` and `qoin-maker pricing` print the commercial terms.

## What you get

```
out-token/
  foundry.toml
  README.md
  src/HarborQoin.sol
  script/Deploy.s.sol
```

The contract is a compact ERC-20 written for Solidity `^0.8.24`. It does not
pull OpenZeppelin at generate-time so the output stays copy-pasteable. You can
swap in audited libraries before mainnet — recommended for anything that will
hold real value.

## Licensing (the profitable part)

| Use | Do you pay? |
|---|---|
| Read the source, learn, homework, local experiments | No |
| Tiny production launch under $10k trailing revenue | No |
| Client token launches, agency work, white-label, SaaS factory | **Yes** |
| Embedding the generator in a commercial product | **Yes** |

List prices (2026): Starter **$149** once · Studio **$499/yr** · Agency **$2,490/yr** · Enterprise from **$8,000/yr**.

On **26 September 2030** each published version also becomes available under
Apache-2.0 (the Change License). Until then QMSAL 1.0 + Commercial License
control Production Use.

## Safety and legal

- Generated tokens can still be used poorly (unlocked mint, deployer dumps).
- This tool does **not** make a token legal tender, a security, or "backed".
- Securities, promotions, and AML rules differ by country. Get counsel.
- Have a third party review any contract that will sit on a public chain.

## Web preview

Open `web/index.html` in a browser for a local parameter checklist. It does
not deploy anything and does not replace the CLI.

## Development

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
```

## PAT / publish notes

This repo lives at `https://github.com/FrosTether/qoin`.
If you need to publish from a different account, create a GitHub fine-grained
or classic **Personal Access Token** with `repo` scope and push as usual:

```bash
git remote set-url origin https://<TOKEN>@github.com/FrosTether/qoin.git
git push -u origin main
```

Do not commit the token. Rotate it if it leaks into a shell history.
