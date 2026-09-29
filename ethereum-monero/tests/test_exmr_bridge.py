"""bridge.py without a Monero node: embedded ABI, startup checks, proof parsing, CLI."""

import pytest

pytest.importorskip("web3")
pytest.importorskip("eth_tester")

from eth_account import Account  # noqa: E402

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
