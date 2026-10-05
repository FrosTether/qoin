# EXMR peg: 1 EXMR = 1 XMR

Ethereum Monero is XMR you can hold and move on Ethereum Classic. Every EXMR is
backed by one XMR in the bridge vault, a Monero wallet run by the bridge
operator. EXMR is minted only when XMR arrives there, and XMR leaves only when
EXMR is burned.

| Field | Value |
| --- | --- |
| Name / symbol | Ethereum Monero / EXMR |
| Chain | Ethereum Classic (ERC-20, `src/EthereumMonero.sol`) |
| Decimals | 12, Monero's, so amounts map 1:1 with no rounding |
| Starting supply | 0 |
| Backing | 1 XMR per EXMR, in the vault wallet |
| Minter | The relayer's hot key, capped by a daily mint limit |
| Owner | Cold key or multisig. Sets the minter and the limit, nothing else |

## Mint (XMR in, EXMR out)

1. The user's ETC address gets its own vault subaddress, labelled with that
   address (`bridge.py register 0x...`).
2. The user sends XMR to that subaddress.
3. Once the deposit has 10 confirmations (about 20 minutes) and the wallet
   counts it as unlocked, the relayer calls
   `mintFromMonero(to, amount, moneroTxId, subaddressIndex)`.
   Each (transaction, subaddress) pair mints once. The contract rejects a
   repeat, so one Monero transaction can pay several users, each exactly once.
4. The `MintedFromMonero` event names the Monero txid behind every mint.

## Redeem (EXMR in, XMR out)

1. The user calls `burnToMonero(amount, moneroAddress)`. The EXMR is destroyed,
   and a burn record (id, burner, amount, address, ETC block) is stored on-chain.
   The contract only accepts 95 or 106 base58 characters, so pasting an 0x
   address fails before anything is burned.
2. After `ETC_CONFS` blocks (500, about 1 h 50 min), the relayer checks the
   address with the vault wallet. It then pays the amount **less the Monero
   network fee of the payout**.
3. It records the payout on-chain: `markPaid(burnId, moneroTxId)`.
4. If the address is not valid on the vault's network, or the amount is under
   `MIN_PAYOUT_XMR` (0.001) or doesn't cover the fee, the relayer calls
   `refundBurn(burnId)` instead. The contract sends a refund only to the burner,
   only for the burned amount, and only once.

## Invariant

`XMR in the vault >= EXMR totalSupply + burns not yet paid`, at all times.

The relayer keeps it this way:

- **It mints only final deposits**: confirmed and unlocked, so a far-future
  `unlock_time` can't mint EXMR the vault can't spend yet.
- **The vault spends exactly what was burned.** The payout's fee comes out of
  the payout. Wallets that honor `subtract_fee_from_outputs` do this directly.
  monero-wallet-rpc 0.18.3.1 ignores that option, so the relayer notices and
  rebuilds the payout with the fee taken off. The first, trial build needs the
  fee on top, so keep a small float of your own XMR in the vault.
- **It never pays a burn twice.** Each payout is built unrelayed, saved, then
  relayed. It also carries the wallet note `exmr-burn:<id>`. After a crash, the
  relayer finishes the saved payout. If the state file is lost too, the note
  tells it the burn was already paid, so it only marks it paid on-chain.

### Check it yourself

A published view key is **not** enough for Monero: it shows incoming outputs
but can't see which were spent. Use a reserve proof instead:

- `bridge.py proof` signs a Monero reserve proof (`get_reserve_proof`, all
  outputs) over the message
  `EXMR <contract> supply <n> unpaid-burns <n> at ETC block <n> <hash>`.
  It refuses while a payout is unconfirmed, because an in-flight payout skews the proof.
- `bridge.py verify proof.json` checks four things:
  1. The signature (`check_reserve_proof`).
  2. The reserve (total minus spent) is at least supply plus unpaid burns.
  3. The block hash is really that ETC block.
  4. The supply and the unpaid burns match the chain at that block. This needs
     a node that still has that block's state; an archive RPC always does.

Every mint names its Monero txid, and every burn is on-chain with its payout
txid or its refund. So the whole history can be audited.

## Limits

- **Daily mint limit.** The owner sets `dailyMintLimit`, the most the minter
  can mint in each 24-hour window. Deposits over the remaining headroom wait
  for the next window (`mintHeadroom()` shows it). A single deposit larger than
  the whole limit waits until the owner raises it, without holding up the
  deposits behind it. If the hot key leaks, this is the most it can mint a day.
- **Kill switch.** `setMinter(address(0))` stops all minting and settling at
  once. Burns stay pending on-chain until a minter settles them.

## Fees

No bridge fee. Depositors pay their own Monero fee. Redeemers receive the
burned amount less the Monero fee of their payout. On ETC, users pay gas for
`burnToMonero`, and the relayer pays gas for mints, `markPaid` and refunds.

## Recovery

- The relayer can be stopped and restarted at any time. Pending burns wait
  on-chain, and deposits wait in the vault.
- If the state file is lost, the relayer rebuilds from the chain: deposits
  already minted are marked on-chain, and burns carry their state. It also
  uses the vault's tx notes (payouts already sent).
- If a payout is rejected by the network, the relayer stops on that burn
  rather than risk paying twice. Check the wallet, then delete that entry from
  `payouts` in the state file to retry.
- To refund a stuck burn by hand, stop the relayer, then call
  `refundBurn(burnId)` from the minter account.

## Risks

- **Custodial.** The vault spend key can take the XMR. The owner key can
  appoint a minter, and the minter can mint up to the daily limit without a
  deposit. Reserve proofs and the on-chain history let others catch that;
  they can't prevent it. Use a multisig for the owner, and lock down the vault host.
- **ETC reorgs.** Ethereum Classic has had 51% attacks. If a burn is paid and
  then reorged away, XMR left the vault without EXMR being burned.
  `ETC_CONFS` is the defense; raise it for large redemptions.
- **Monero reorgs** deeper than 10 blocks could undo a deposit after it was
  minted. 10 blocks is also Monero's own spend lock.
- **Relayer downtime** delays mints and payouts. It doesn't lose them.
- **Privacy.** EXMR on ETC is fully public. Each mint publishes the Monero txid
  it came from, which publicly ties that deposit transaction to the ETC address.
  The sender stays hidden, as in any Monero transaction. The operator can also
  link each ETC address to its deposit subaddress.
- **Legal.** A pegged, custodial token can be treated as a security or as money
  transmission, depending on where it is offered. Get counsel before launch.
