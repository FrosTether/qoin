"""bridge.py without a Monero node: embedded ABI, startup checks, proof parsing, CLI."""

import pytest

pytest.importorskip("web3")
pytest.importorskip("eth_tester")

from eth_account import Account  # noqa: E402
from web3 import Web3  # noqa: E402

import bridge  # noqa: E402


def relayer(chain, tmp_path, account=None, **kw):
    w3, token, _, minter, _, _ = chain
    exmr = w3.eth.contract(address=token.address, abi=bridge.ABI)
    return bridge.Bridge(w3, exmr, None, account or minter, state_file=str(tmp_path / "state.json"),
                         log=lambda msg: None, **kw)


def test_embedded_abi_matches_contract(artifact):
    compiled = {e["name"]: e for e in artifact["abi"] if e["type"] == "function"}
    for entry in bridge.ABI:
        c = compiled[entry["name"]]
        assert entry["stateMutability"] == c["stateMutability"], entry["name"]
        for side in ("inputs", "outputs"):
            assert [(i["name"], i["type"]) for i in entry[side]] == [(i["name"], i["type"]) for i in c[side]]


def test_check_accepts_the_minter(chain, tmp_path):
    relayer(chain, tmp_path, chain_id=chain[0].eth.chain_id).check()


def test_check_refuses_wrong_chain(chain, tmp_path):
    with pytest.raises(SystemExit, match="expected 61"):
        relayer(chain, tmp_path, chain_id=61).check()


def test_check_refuses_a_key_that_is_not_the_minter(chain, tmp_path):
    with pytest.raises(SystemExit, match="minter is"):
        relayer(chain, tmp_path, account=Account.create(), chain_id=chain[0].eth.chain_id).check()


def test_verify_rejects_other_messages(chain):
    result = bridge.verify_proof(chain[0], None, {"address": "4", "message": "hello", "signature": "x"})
    assert result == {"ok": False, "error": "not an EXMR reserve proof message"}


def test_mint_target():
    alice = "0x42FF98C4E85212a5D31358ACbFe76a621b50fC02"
    assert bridge.mint_target(alice.lower()) == alice
    for label in ("", "Primary account", "0x" + "00" * 20, "0x42FF98C4"):
        assert bridge.mint_target(label) is None


def test_register_refuses_the_zero_address():
    with pytest.raises(ValueError, match="can receive EXMR"):
        bridge.register(None, "0x" + "00" * 20)


def test_xmr_formatting():
    assert bridge.xmr(1) == "0.000000000001"
    assert bridge.xmr(10**12) == "1"
    assert bridge.xmr(1_234_500_000_000) == "1.2345"


def test_cli_prints_usage(capsys):
    assert bridge.main([]) == 2
    assert "python3 bridge.py register" in capsys.readouterr().out


class FakeWallet:
    """Just enough monero-wallet-rpc for one call path."""

    def __init__(self, **results):
        self.results = results

    def __call__(self, method, params=None):
        return self.results.get(method, {})


def as_minter(chain):
    w3, token, _, minter, _, _ = chain
    w3.provider.ethereum_tester.add_account(minter.key.hex())
    return minter.address


def test_deposit_over_the_whole_limit_does_not_block_the_queue(chain, tmp_path):
    w3, token, owner, _, alice, bob = chain
    XMR = 10**12
    deposits = [{"txid": "aa" * 32, "subaddr_index": {"minor": 1}, "amount": 150 * XMR, "height": 1,
                 "confirmations": 20, "locked": False},
                {"txid": "bb" * 32, "subaddr_index": {"minor": 2}, "amount": XMR, "height": 2,
                 "confirmations": 20, "locked": False}]
    wallet = FakeWallet(get_address={"addresses": [{"address_index": 1, "label": alice},
                                                   {"address_index": 2, "label": bob}]},
                        get_transfers={"in": deposits})
    logs = []
    b = relayer(chain, tmp_path, chain_id=w3.eth.chain_id)
    b.wallet, b.log = wallet, logs.append
    b.mint_deposits()
    assert token.functions.balanceOf(alice).call() == 0      # 150 XMR is over the 100 XMR limit
    assert token.functions.balanceOf(bob).call() == XMR      # the deposit behind it still mints
    assert any("over the whole daily mint limit" in m for m in logs)
    token.functions.setDailyMintLimit(200 * XMR).transact({"from": owner})
    b.mint_deposits()
    assert token.functions.balanceOf(alice).call() == 150 * XMR
    assert token.functions.balanceOf(bob).call() == XMR


def test_verify_checks_unpaid_burns_against_the_chain(chain):
    w3, token, _, _, alice, _ = chain
    XMR = 10**12
    minter = as_minter(chain)
    token.functions.mintFromMonero(alice, 2 * XMR, b"\x01" * 32, 1).transact({"from": minter})
    token.functions.burnToMonero(XMR, "4" + "A" * 94).transact({"from": alice})
    block = w3.eth.get_block("latest")
    wallet = FakeWallet(check_reserve_proof={"good": True, "total": 2 * XMR, "spent": 0})

    def proof(unpaid):
        return {"address": "4", "signature": "x", "message": f"EXMR {token.address} supply {XMR} unpaid-burns "
                f"{unpaid} at ETC block {block.number} {Web3.to_hex(block.hash)}"}

    honest = bridge.verify_proof(w3, wallet, proof(XMR))
    assert honest["ok"] and honest["unpaid_burns_match_chain"]
    hidden = bridge.verify_proof(w3, wallet, proof(0))       # a signed proof that leaves out the pending burn
    assert not hidden["ok"] and hidden["unpaid_burns_match_chain"] is False
