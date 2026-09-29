# Ethereum Monero (`EXMR`)

Monero on Ethereum Classic: an ERC-20 where **1 EXMR = 1 XMR** held in a bridge vault.
Deposit XMR and get EXMR on ETC; burn EXMR and get the XMR back.

**Not affiliated** with the Monero Project, Ethereum Classic, or the Ethereum
Foundation. EXMR is a claim on XMR held by whoever runs the vault. Read
[`PEG.md`](PEG.md) for how the peg works and what can break it.

| Field | Value |
|---|---|
| Name / symbol | Ethereum Monero / EXMR |
| Chain | Ethereum Classic (chain 61); Mordor testnet (63) for trials |
| Decimals | 12, same as XMR, so 1 raw unit is exactly 1 piconero |
| Supply | Starts at 0. Minted only against XMR deposits, burned on redemption |
| Contract | `src/EthereumMonero.sol` (Solidity 0.8.24, EVM `shanghai`) |
| Relayer | `bridge.py`: monero-wallet-rpc on one side, ETC on the other |

It has the same shape as the Frostoise ↔ ETC bridge for Qoin (`bridge.py` on
`master`). On top of that, burns are recorded on-chain, and anyone can check
the reserve with a Monero reserve proof.

## Files

| File | What it is |
|---|---|
| `src/EthereumMonero.sol` | The token. ERC-20 core from the Qoin Maker template, plus bridge mint, burn, pay and refund |
| `bridge.py` | The relayer: mints for deposits, pays burns, makes and checks reserve proofs |
| `script/Deploy.s.sol` | Foundry deploy script |
| `tests/` | Contract tests (in-process EVM), relayer tests, and an end-to-end test on a Monero regtest node |
| `PEG.md` | Mint and redeem flows, the invariant, limits, fees, risks |

## Keys

| Key | Holds | Keep it |
|---|---|---|
| Owner (deployer) | Can replace the minter and set the daily mint limit | Cold, or a multisig |
| Minter (`BRIDGE_ETC_KEY`) | Mints for deposits, marks burns paid, refunds burns | Hot, on the relayer host |
| Vault wallet | The XMR itself (spend key) | On the relayer host, backed up |

The owner can't mint or touch balances. Nobody can freeze, seize, or tax EXMR.

## Deploy

With Foundry. ETC has no EIP-1559, hence `--legacy`:

```bash
forge install --no-git foundry-rs/forge-std
export PRIVATE_KEY=0x...            # owner
export EXMR_MINTER=0x...            # the relayer's address
export EXMR_DAILY_LIMIT_XMR=100     # most XMR the relayer can mint per 24 h
export ETC_RPC_URL=https://etc.rivet.link
forge script script/Deploy.s.sol --rpc-url etc --broadcast --legacy
```

With Remix: compile `src/EthereumMonero.sol` with 0.8.24, **EVM version
`shanghai`** (ETC has no Cancun opcodes) and optimization at 200 runs. Then
deploy from MetaMask on Ethereum Classic with `minter_` set to the relayer's
address and `dailyMintLimit_` in piconero (100 XMR = `100000000000000`).

Try it on Mordor first (`--rpc-url mordor`, `ETC_CHAIN_ID=63`, with a stagenet
or testnet Monero wallet).

## Run the relayer

Next to a synced `monerod`, open the vault in `monero-wallet-rpc`. Bind it to
loopback and give it a login:

```bash
monero-wallet-rpc --wallet-file ~/exmr-vault --password-file ~/exmr-vault.pass \
  --daemon-address 127.0.0.1:18081 --rpc-bind-ip 127.0.0.1 --rpc-bind-port 18083 \
  --rpc-login bridge:CHANGE_ME

pip install -r requirements.txt
export EXMR_CONTRACT=0x...  BRIDGE_ETC_KEY=0x...  MONERO_WALLET_LOGIN=bridge:CHANGE_ME
python3 bridge.py run
```

| Setting | Default | Meaning |
|---|---|---|
| `ETC_RPC` | `https://etc.rivet.link` | ETC JSON-RPC |
| `ETC_CHAIN_ID` | `61` | The relayer refuses to sign for any other chain |
| `MONERO_WALLET_RPC` | `http://127.0.0.1:18083/json_rpc` | The vault's wallet RPC |
| `MONERO_WALLET_LOGIN` | none | `user:pass` from `--rpc-login` |
| `XMR_CONFS` | `10` | Monero confirmations before minting (about 20 min) |
| `ETC_CONFS` | `500` | ETC confirmations before paying a burn (about 1 h 50 min) |
| `MIN_PAYOUT_XMR` | `0.001` | Smaller burns are refunded |
| `STATE_FILE` | `exmr_bridge_state.json` | Relayer state; the chain and wallet notes can rebuild it |
| `POLL_SECONDS` | `60` | Time between passes |

`python3 bridge.py once` does a single pass. `python3 bridge.py status`
compares the vault's balance with what EXMR holders are owed.

Leave a little XMR of your own in the vault (0.01 is plenty). Some wallet RPCs
ignore `subtract_fee_from_outputs` (0.18.3.1 does). With those, the relayer
measures each payout's fee with a trial build, which needs the fee on top of the
payout.

## Use it

**XMR to EXMR.** `python3 bridge.py register 0xYourEtcAddress` prints your own
Monero deposit subaddress (the same one every time). Send XMR to it. After 10
Monero confirmations the same amount of EXMR arrives at that ETC address.

**EXMR to XMR.** Call `burnToMonero(amount, "4...")` on the contract (Remix or
Blockscout "Write contract"). The amount is in raw units:
1 EXMR = `1000000000000`. After `ETC_CONFS` the XMR arrives, less the Monero
network fee. The burn shows as paid on-chain, with the Monero txid.
If the address isn't valid Monero, or the amount is under `MIN_PAYOUT_XMR`, you
get the EXMR back instead.

To see EXMR in MetaMask, add the contract address as a token (symbol `EXMR`, 12 decimals).

## Prove the reserve

```bash
python3 bridge.py proof > proof.json      # the operator
python3 bridge.py verify proof.json       # anyone: needs an ETC RPC and any wallet open in monero-wallet-rpc
```

The proof is a Monero reserve proof over every vault output. It's signed over
the EXMR supply and unpaid burns at a named ETC block, so each proof speaks for
one moment. See [`PEG.md`](PEG.md#check-it-yourself).

## Tests

```bash
pip install -r requirements.txt "web3[tester]" pytest
python3 -m pytest -q tests
```

The contract tests compile with solc 0.8.24, taken from `PATH`, from py-solc-x,
or via `npx solc@0.8.24`. `tests/test_exmr_regtest.py` starts its own
`monerod --regtest` and two `monero-wallet-rpc` processes, then runs the whole
bridge. That covers deposits, the daily limit, payouts, refunds, crash recovery
and a reserve proof. It is skipped if the Monero CLI isn't on `PATH`
(`apt install monero` on Ubuntu 24.04 gives 0.18.3.1).

## Safety

- This is a custodial bridge. Its safety is the safety of the vault host, the
  minter key and the owner key. Use a multisig for the owner before real value
  moves.
- Get the contract reviewed before mainnet. Run on Mordor and Monero stagenet first.
- Running a bridge for other people may be money transmission where you are. Get counsel.
