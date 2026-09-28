# Qoin - build notes

Qoin is a fork of Wownero. This repo builds three programs, and `graysons/` holds the desktop app:

| Program | What it is |
|---|---|
| `qoind` | the Qoin node |
| `graysons-wallet-cli` / `graysons-wallet-rpc` | **Graysons Wallet**, the forked Wownero wallet (command line and RPC engine) |
| `graysons/graysons-wallet` | Graysons Wallet desktop app (runs in your browser, talks to the RPC engine) |
| `graysons/frostoise` | **Frostoise**, the wallet miner: solo-mines Qoin into the open Graysons wallet |
| `graysons/qoinage` | **Qoinage**, the listen-and-earn vault: 13.37 QOIN for five minutes of a 741 Hz sine wave. See [QOINAGE.md](QOINAGE.md) |

## What changed from Wownero

- **Name:** `CRYPTONOTE_NAME` is `qoin`. Data dir is `~/.qoin`. Unit name is `qoin` (sub-units keep Wownero's names). The `donate` command is disabled, since it pointed at Wownero's address.
- **Own network:** new `NETWORK_ID`, `GENESIS_NONCE` 8294, ports 45670 (P2P) / 45671 (RPC) / 45672 (ZMQ), address prefixes 9999 / 19998 / 29997. Wownero's hardcoded seed nodes are removed, so a Qoin node only connects to peers you give it.
- **Reward:** every block pays 1.5x what Wownero's emission curve pays at the same point (`get_block_reward()` in `src/cryptonote_basic/cryptonote_basic_impl.cpp`). The supply cap is unchanged; coins are emitted faster, not more of them.
- **Premine:** block 1 pays exactly **13,370.08241991** QOIN (`QOIN_PREMINE` in `src/cryptonote_config.h`). It goes to whoever mines block 1, so mine it yourself before anyone else connects (Frostoise with the node set to Offline).
- **Block time:** 5 minutes (inherited).
- **Checkpoints removed** (they pinned Wownero block hashes).
- **Upgrade schedule compressed:** `src/hardforks/hardforks.cpp` reaches current rules (v20) by block 65.

## Build

```bash
cd ~/frostnero
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF ..
make -j1 daemon simplewallet wallet_rpc_server
```

`-j1` because this laptop has 3 GB of RAM; parallel C++ jobs can run it out of memory. Binaries land in `build/bin/`.

## Run Graysons Wallet and Frostoise

```bash
~/frostnero/graysons/install-shortcuts.sh   # once: adds both to the app menu, and all three commands to ~/.local/bin
graysons-wallet                              # or: frostoise
```

Each command starts a small local server on 127.0.0.1:45680 and opens it in your browser. It starts `qoind` and `graysons-wallet-rpc` for you and stops them when you press Ctrl+C. Wallet files live in `~/.qoin/wallets/`. They're ordinary wallet files, so `graysons-wallet-cli --wallet-file ~/.qoin/wallets/<name>` opens them too.

### Mining the premine with Frostoise

1. Open Graysons Wallet, create a wallet, and write down the seed.
2. **Node** tab: tick **Offline** and save. Then Stop node and Start node so the setting takes effect.
3. **Frostoise** tab: pick threads, press **Start mining**. Block 1 pays the premine.
4. When you're ready for others to join, untick Offline, add their `host:45670` under peers, and restart the node.

The node only takes the block-signing key at startup. So Start mining restarts the node once with this wallet's spend key. The key goes into `~/.qoin/frostoise.conf` (mode 600), and that file is deleted as soon as the node answers. It never appears on a command line. Frostoise refuses view-only wallets. It also refuses wallets whose view key isn't derived from the spend key, because every block those signed would be rejected.

Coinbase rewards are locked for a number of blocks before they can be spent.

### Spend key as a sine-tone WAV (optional)

`tools/sinekey.py` still works: `python3 tools/sinekey.py new ~/qoin-key.wav` prints a key, and `build/bin/graysons-wallet-cli --generate-from-spend-key ~/.qoin/wallets/<name>` turns it into a wallet that Graysons and Frostoise can open.

### Qoinage and the HUMM lock

`graysons/qoinage --wallet vault` runs the listen-and-earn vault, which pays 13.37 QOIN from a wallet you funded for each five-minute listen. The **Qoinage** tab in Graysons Wallet opens it with your address filled in, and holds the optional HUMM 741 Hz lock for sends. See [QOINAGE.md](QOINAGE.md).

### Number addresses

Every Qoin address can also be written in digits only. Graysons Wallet shows your number address under **Overview** and **Receive** (click it to copy), and takes one anywhere it takes an address. So do Qoinage and the ETC bridge.

    9999 | 155 digits: spend key + view key | 10 digits: checksum      (169 digits)

- It starts with the address prefix: `9999` for a primary address, `29997` for a subaddress, `19998` for an integrated address.
- It holds exactly what the usual address holds, so it converts both ways with no lookup and nobody to trust. The last 10 digits are the usual address's checksum, so a mistyped digit is caught before anything is sent.
- It's long because an address carries two 256-bit keys. Digits are easy to read out and to type on a phone keypad, with no upper and lower case to mix up. Spaces and dashes between digits are fine.
- `qoind` and `graysons-wallet-cli` still take the usual form. Convert either way with `python3 graysons/qoin_number.py <address or number>`.

Tests: `cd graysons && python3 -m unittest test_qoin_number -v` (standard library only).

## Not yet built: the Bitcoin Cash timing oracle

The BCH-driven 159s / 161s / 1s cycle is a separate protocol layer. The phases add up to 321s against the 300s block time; decide whether the block time or the phases change, and it can be specced from there.
