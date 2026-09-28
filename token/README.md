# FSZT — safe fixed-supply token + Merkle airdrop

This is the "let others hold FrosTether safely" path. It replaces the old
`FrosTether.sol` (which did not compile — a function sat after the contract's
closing brace) with a token that **cannot be inflated or frozen**, plus a claim
contract so a fixed list of people can receive it fairly.

It closes the airdrop-relevant findings from the Finux red paper: no free mint
(C2/C3), no payment-verification bypass (C1), and no central mint/freeze on the
holders' token (H1).

## Files

| File | What it is |
|---|---|
| `contracts/FrostEther.sol` | FSZT token. Fixed 25,000,000 supply minted once to a treasury. No mint, no owner, no pause. Holders can `burn`. |
| `contracts/FrostAirdrop.sol` | Merkle claim. Distributes a pre-funded pool; each address claims once; unclaimed sweeps to the treasury after a deadline. Cannot mint. |
| `scripts/build_airdrop.mjs` | Builds the Merkle root + per-address proofs from a CSV. |
| `allowlist.csv.example` | The CSV format: `address,amount_in_wei`, one per line. |

## Why holders are safe

- **Fixed supply.** The whole supply is created at deployment. There is no
  `mint` function anywhere, so no key — not even the deployer's — can dilute it.
- **No freeze / no pause / no blacklist.** The token cannot stop or reverse a
  transfer. What someone holds is theirs.
- **The airdrop can only give away what it already has.** It never mints; it
  transfers from a pool you fund. Each address claims exactly its listed amount,
  exactly once.
- **No open door.** No `X-Dev-Mode` bypass, no permissionless `surgeMint`. The
  only privileged outcome is that unclaimed tokens go to one fixed `treasury`
  address after the deadline, and nowhere else.

## Burn & supply

`FrostEther.burn(uint256)` lets a holder destroy their **own** tokens: it lowers
`totalSupply` and emits `Transfer(holder, address(0), value)`, so the burn is
verifiable on-chain. This is the honest burn — it actually reduces supply, unlike
"sending to a dead address," which only parks tokens at `0x…dEaD` (an address with
**no private key by design**).

- No admin can burn someone else's balance — only the holder burns their own.
- Burning is **deflationary**; it is **not** a buyback and returns no value. Don't
  imply it does.
- There is no "burn key" to hold or generate — a burn address is *defined* by
  having no key. Never derive a key from anything guessable (a birthday, a name);
  keys must be full-entropy random, generated on the device (see `qoind`).

## Deploy order

1. **Deploy `FrostEther`** with `treasury` = the wallet that will fund the drop.
   It receives all 25,000,000 FSZT. (Edit `INITIAL_SUPPLY` first if you want a
   different fixed total.)
2. **Make the allowlist.** Put recipients in `allowlist.csv`
   (`address,amount_in_wei`), then:
   ```bash
   npm init -y && npm i @openzeppelin/merkle-tree
   node scripts/build_airdrop.mjs allowlist.csv
   ```
   This prints the **merkle root** and writes `airdrop-claims.json` (the proofs
   your claim page will serve).
3. **Deploy `FrostAirdrop`** with `(token, merkleRoot, claimWindowSeconds, treasury)`.
   Example window: `2592000` = 30 days.
4. **Fund it.** Transfer the total pool of FSZT (the script prints the total)
   from the treasury to the `FrostAirdrop` address.
5. **Let people claim.** Each recipient (or you, on their behalf) calls
   `claim(account, amount, proof)`. Tokens always go to `account`.
6. After the window, anyone can call `sweepUnclaimed()` to return the remainder
   to the treasury.

## Verified

Both contracts compile clean with `solc 0.8.24 --optimize` (no warnings). The
build script was run end-to-end against a sample allowlist; its leaf encoding
(`["address","uint256"]`, OpenZeppelin StandardMerkleTree) matches
`FrostAirdrop._verify`.

## Before mainnet — honest notes

- **Get an independent audit.** This is sound, minimal code, but real money
  deserves a second set of eyes. Test on a public testnet first.
- **Claim gas.** Recipients pay gas to claim unless you relay it. You can submit
  `claim` for them (tokens still go to them), or add an account-abstraction
  paymaster.
- **No value is promised.** FSZT has no backing, peg, buyback, or treasury
  reserve, and receiving it is not an investment or a return. Say that plainly
  wherever you announce it, and don't state or imply a price.
- **Naming.** "FrosTether" reads like "Tether/USDT". It isn't a stablecoin and
  isn't affiliated with Tether — using that likeness invites a trademark
  dispute and "backed/stable" confusion. Consider a name that doesn't borrow it.
- I did **not** write launch/marketing or an "X listing" — promoting a token is
  where holders get hurt if the claims outrun the code. The contracts above are
  the part I can stand behind.
