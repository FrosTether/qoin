# GCII Coin peg design: GCII and Qoin

GCII Coin is the Ethereum Classic side of Qoin. GCII is designed to track Qoin 1:1
by its own rules: each GCII is meant to be minted only against one Qoin locked in
a vault on Frostoise and burned when that Qoin is released. This is not a promise
of value.

| Field | Value |
| --- | --- |
| Name / symbol | GCII Coin / GCII |
| Chain | Ethereum Classic (ERC-20, `src/GCIICoin.sol`) |
| Decimals | 11, matching Frostoise's atomic unit if it keeps Wownero's 11 places |
| Starting supply | 0. GCII is only minted against locked Qoin |
| Vault design | 1 Qoin locked per GCII minted, held in the Frostoise vault |
| Minter | The contract `owner`, which should be the vault operator's multisig |

## Mint (Qoin in, GCII out)

1. The user sends Qoin to the vault address on Frostoise with their ETC address
   in the transaction's payment ID or memo.
2. After 10 confirmations (about 50 minutes at 5-minute blocks), the vault
   operator calls `mint(userEtcAddress, amount)` for the same whole-token amount.
3. The Frostoise transaction hash and the ETC mint transaction hash are logged
   together in the public mint ledger.

## Redeem (GCII in, Qoin out)

1. The user calls `burn(amount)` on GCII Coin and sends the vault operator the
   burn transaction hash plus a Frostoise address.
2. The operator releases the same amount of Qoin from the vault to that address.
3. Both hashes are logged in the public redeem ledger.

## Invariant

The design rule is `GCII.totalSupply() <= Qoin held in the vault`. The vault's
Frostoise view key is published so anyone can check the balance without being
able to spend it. This is the same split as Grayson's Wallet: managers hold the
spend key, everyone else can hold the view key.

## Fees

None at launch. If a fee is added later it is taken in Qoin at mint or redeem
time and is not designed to change the 1:1 mint/redeem ratio.

## Risks

- **Custodial.** Whoever holds the vault spend key and the contract `owner` key
  can break the peg. Use a multisig for both before any real value moves.
- **Owner mint is unlimited.** The contract does not know the vault balance.
  The published ledgers and view key are what let others catch an over-mint.
- **Not a swap.** Minting takes about an hour because of Frostoise confirmations.
- **Legal.** A pegged token can still be treated as a security or as money
  transmission depending on where it is sold. Get counsel before launch.
