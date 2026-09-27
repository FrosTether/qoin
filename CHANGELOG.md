# Changelog

## Unreleased

- Allow `--supply 0` with `--mintable` for wrapped or pegged tokens; no constructor mint when supply is 0.
- Add `gcii-coin/`: GCII Coin, an ERC-20 pegged 1:1 to Qoin, with `PEG.md` describing the mint/redeem vault.
- Add `frostchain/`: 20 MyDoge.frostchain FLAC containers and `frostchain_fill.py`.

## 0.1.0 — 2026-09-26

- Initial public source-available release.
- CLI: `generate`, `explain`, `license`, `pricing`.
- Templates: standard ERC-20 with optional owner, mint, burn, cap.
- Foundry scaffold (`foundry.toml` + deploy script).
- QMSAL 1.0 + commercial pricing (Starter / Studio / Agency / Enterprise).
