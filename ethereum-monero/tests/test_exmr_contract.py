"""EthereumMonero.sol on an in-process EVM (web3 + eth-tester)."""

import pytest

pytest.importorskip("web3")
pytest.importorskip("eth_tester")

from eth_tester.exceptions import TransactionFailed  # noqa: E402
from web3.exceptions import ContractLogicError  # noqa: E402
from web3.logs import DISCARD  # noqa: E402

XMR = 10**12
TXID = bytes.fromhex("ab" * 32)
XMR_ADDR = "4" + "A" * 94  # length-valid; the relayer checks the real checksum
PENDING, PAID, REFUNDED = 1, 2, 3


def reverts(reason):
    return pytest.raises((ContractLogicError, TransactionFailed), match=reason)


@pytest.fixture
def exmr(chain):
    w3, token, owner, minter, alice, bob = chain
    w3.provider.ethereum_tester.add_account(minter.key.hex())  # let tests transact as the minter
    return w3, token, owner, minter.address, alice, bob


def mint(token, minter, to, amount, txid=TXID, index=1):
    return token.functions.mintFromMonero(to, amount, txid, index).transact({"from": minter})


def receipt(w3, tx_hash):
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def test_metadata(exmr):
    _, token, owner, minter, _, _ = exmr
    f = token.functions
    assert (f.name().call(), f.symbol().call(), f.decimals().call()) == ("Ethereum Monero", "EXMR", 12)
    assert (f.owner().call(), f.minter().call()) == (owner, minter)
    assert f.dailyMintLimit().call() == 100 * XMR
    assert f.totalSupply().call() == 0


def test_mint_from_monero(exmr):
    w3, token, _, minter, alice, _ = exmr
    rc = receipt(w3, mint(token, minter, alice, 3 * XMR // 2, index=7))
    assert token.functions.balanceOf(alice).call() == 3 * XMR // 2
    assert token.functions.totalSupply().call() == 3 * XMR // 2
    assert token.functions.depositMinted(TXID, 7).call()
    assert not token.functions.depositMinted(TXID, 8).call()
    (ev,) = token.events.MintedFromMonero().process_receipt(rc, errors=DISCARD)
    assert dict(ev.args) == {"to": alice, "amount": 3 * XMR // 2, "moneroTxId": TXID, "subaddressIndex": 7}


def test_each_deposit_mints_once(exmr):
    _, token, _, minter, alice, _ = exmr
    mint(token, minter, alice, XMR, index=7)
    with reverts("deposit already minted"):
        mint(token, minter, alice, XMR, index=7)
    mint(token, minter, alice, XMR, index=8)  # same tx, another user's subaddress
    assert token.functions.balanceOf(alice).call() == 2 * XMR


def test_only_minter_mints(exmr):
    _, token, owner, _, alice, _ = exmr
    for who in (owner, alice):
        with reverts("not minter"):
            mint(token, who, alice, XMR)


def test_zero_mint_rejected(exmr):
    _, token, _, minter, alice, _ = exmr
    with reverts("zero amount"):
        mint(token, minter, alice, 0)


def test_daily_mint_limit(exmr):
    w3, token, _, minter, alice, _ = exmr
    mint(token, minter, alice, 60 * XMR, index=1)
    with reverts("daily mint limit"):
        mint(token, minter, alice, 50 * XMR, index=2)
    assert token.functions.mintHeadroom().call() == 40 * XMR
    mint(token, minter, alice, 40 * XMR, index=3)
    assert token.functions.mintHeadroom().call() == 0

    start = token.functions.mintWindowStart().call()
    w3.testing.timeTravel(start + 24 * 3600)
    w3.testing.mine()
    assert token.functions.mintHeadroom().call() == 100 * XMR
    mint(token, minter, alice, 50 * XMR, index=2)  # the deposit that waited
    assert token.functions.balanceOf(alice).call() == 150 * XMR


def test_owner_controls(exmr):
    _, token, owner, minter, alice, bob = exmr
    for fn in (
        token.functions.setMinter(alice),
        token.functions.setDailyMintLimit(0),
        token.functions.transferOwnership(alice),
    ):
        with reverts("not owner"):
            fn.transact({"from": minter})

    token.functions.setDailyMintLimit(5 * XMR).transact({"from": owner})
    with reverts("daily mint limit"):
        mint(token, minter, alice, 6 * XMR)

    token.functions.setMinter("0x" + "00" * 20).transact({"from": owner})
    with reverts("not minter"):
        mint(token, minter, alice, XMR)

    with reverts("zero owner"):
        token.functions.transferOwnership("0x" + "00" * 20).transact({"from": owner})
    token.functions.transferOwnership(bob).transact({"from": owner})
    assert token.functions.owner().call() == bob
    with reverts("not owner"):
        token.functions.setMinter(owner).transact({"from": owner})


def test_burn_to_monero(exmr):
    w3, token, _, minter, alice, _ = exmr
    mint(token, minter, alice, 2 * XMR)
    rc = receipt(w3, token.functions.burnToMonero(XMR, XMR_ADDR).transact({"from": alice}))
    assert token.functions.balanceOf(alice).call() == XMR
    assert token.functions.totalSupply().call() == XMR
    assert token.functions.burnCount().call() == 1
    assert token.functions.burns(0).call() == [alice, PENDING, rc.blockNumber, XMR, XMR_ADDR]
    (ev,) = token.events.BurnedToMonero().process_receipt(rc, errors=DISCARD)
    assert dict(ev.args) == {"burnId": 0, "from": alice, "amount": XMR, "moneroAddress": XMR_ADDR}


@pytest.mark.parametrize(
    "address",
    ["", "0x" + "11" * 20, XMR_ADDR[:-1], XMR_ADDR + "B", "4" * 107]  # wrong length
    + ["4" + c * 94 for c in "0OIl +"],  # not base58
)
def test_burn_rejects_non_monero_address(exmr, address):
    _, token, _, minter, alice, _ = exmr
    mint(token, minter, alice, XMR)
    with reverts("not a monero address"):
        token.functions.burnToMonero(XMR, address).transact({"from": alice})


def test_burn_rejects_bytes_that_are_not_utf8(exmr):
    # Solidity doesn't check UTF-8 in calldata strings; such a burn record would break
    # every ABI decoder that reads it, and with it the relayer's queue.
    from eth_abi import encode
    from web3 import Web3

    w3, token, _, minter, alice, _ = exmr
    mint(token, minter, alice, XMR)
    data = Web3.keccak(text="burnToMonero(uint256,string)")[:4] + encode(["uint256", "bytes"], [XMR, b"\xff" * 95])
    with reverts("not a monero address"):
        w3.eth.send_transaction({"from": alice, "to": token.address, "data": data})


def test_burn_accepts_integrated_address(exmr):
    _, token, _, minter, alice, _ = exmr
    mint(token, minter, alice, XMR)
    token.functions.burnToMonero(XMR, "4" + "C" * 105).transact({"from": alice})
    assert token.functions.burnCount().call() == 1


def test_burn_needs_balance_and_amount(exmr):
    _, token, _, minter, alice, bob = exmr
    mint(token, minter, alice, XMR)
    with reverts("balance"):
        token.functions.burnToMonero(XMR, XMR_ADDR).transact({"from": bob})
    with reverts("zero amount"):
        token.functions.burnToMonero(0, XMR_ADDR).transact({"from": alice})


def test_mark_paid(exmr):
    w3, token, _, minter, alice, _ = exmr
    mint(token, minter, alice, XMR)
    token.functions.burnToMonero(XMR, XMR_ADDR).transact({"from": alice})
    payout = bytes.fromhex("cd" * 32)
    with reverts("not minter"):
        token.functions.markPaid(0, payout).transact({"from": alice})
    with reverts("no such burn"):
        token.functions.markPaid(1, payout).transact({"from": minter})
    rc = receipt(w3, token.functions.markPaid(0, payout).transact({"from": minter}))
    assert token.functions.burns(0).call()[1] == PAID
    (ev,) = token.events.BurnPaid().process_receipt(rc)
    assert dict(ev.args) == {"burnId": 0, "moneroTxId": payout}
    with reverts("not pending"):
        token.functions.markPaid(0, payout).transact({"from": minter})
    with reverts("not pending"):
        token.functions.refundBurn(0).transact({"from": minter})
    assert token.functions.balanceOf(alice).call() == 0


def test_refund_burn(exmr):
    w3, token, owner, minter, alice, _ = exmr
    mint(token, minter, alice, 2 * XMR)
    token.functions.burnToMonero(XMR, XMR_ADDR).transact({"from": alice})
    token.functions.setDailyMintLimit(0).transact({"from": owner})  # refunds are not new mints
    with reverts("not minter"):
        token.functions.refundBurn(0).transact({"from": alice})
    rc = receipt(w3, token.functions.refundBurn(0).transact({"from": minter}))
    assert token.functions.balanceOf(alice).call() == 2 * XMR
    assert token.functions.totalSupply().call() == 2 * XMR
    assert token.functions.burns(0).call()[1] == REFUNDED
    (ev,) = token.events.BurnRefunded().process_receipt(rc, errors=DISCARD)
    assert dict(ev.args) == {"burnId": 0, "to": alice, "amount": XMR}
    with reverts("not pending"):
        token.functions.refundBurn(0).transact({"from": minter})
    with reverts("not pending"):
        token.functions.markPaid(0, b"\x00" * 32).transact({"from": minter})


def test_erc20_transfer_and_allowance(exmr):
    _, token, _, minter, alice, bob = exmr
    mint(token, minter, alice, 10 * XMR)
    token.functions.transfer(bob, 3 * XMR).transact({"from": alice})
    assert token.functions.balanceOf(bob).call() == 3 * XMR
    with reverts("zero to"):
        token.functions.transfer("0x" + "00" * 20, 1).transact({"from": alice})

    token.functions.approve(bob, 2 * XMR).transact({"from": alice})
    with reverts("allowance"):
        token.functions.transferFrom(alice, bob, 3 * XMR).transact({"from": bob})
    token.functions.transferFrom(alice, bob, 2 * XMR).transact({"from": bob})
    assert token.functions.allowance(alice, bob).call() == 0

    unlimited = 2**256 - 1
    token.functions.approve(bob, unlimited).transact({"from": alice})
    token.functions.transferFrom(alice, bob, XMR).transact({"from": bob})
    assert token.functions.allowance(alice, bob).call() == unlimited
    assert token.functions.balanceOf(alice).call() == 4 * XMR
    assert token.functions.balanceOf(bob).call() == 6 * XMR
