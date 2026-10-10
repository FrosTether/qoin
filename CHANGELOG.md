# Changelog

## Unreleased

- Add `ethereum-monero/`: Ethereum Monero (EXMR), XMR bridged 1:1 to Ethereum Classic. `EthereumMonero.sol` records every mint's Monero txid and every burn on-chain; `bridge.py` relays between monero-wallet-rpc and ETC and makes and checks reserve proofs. Tested against a Monero regtest node.
- Add `frostchain/bch_anchor.py` and `block_0001.json`: frostchain block 1 (1991-08-24 Eastern) with its Bitcoin Cash OP_RETURN anchor.
- Allow `--supply 0` with `--mintable` for wrapped or pegged tokens; no constructor mint when supply is 0.
- Add `gcii-coin/`: GCII Coin, an ERC-20 pegged 1:1 to Qoin, with `PEG.md` describing the mint/redeem vault.
- Add `frostchain/`: 20 MyDoge.frostchain FLAC containers and `frostchain_fill.py`.

## 0.1.0 — 2026-09-26

- Initial public source-available release.
- CLI: `generate`, `explain`, `license`, `pricing`.
- Templates: standard ERC-20 with optional owner, mint, burn, cap.
- Foundry scaffold (`foundry.toml` + deploy script).
- QMSAL 1.0 + commercial pricing (Starter / Studio / Agency / Enterprise).
