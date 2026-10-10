"""Shared fixtures: EthereumMonero.sol compiled once, deployed fresh per test."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))  # so tests can `import bridge`
SOLC_VERSION = "0.8.24"
XMR = 10**12  # piconero per XMR, and EXMR raw units per EXMR


def _standard_input():
    return {
        "language": "Solidity",
        "sources": {"EthereumMonero.sol": {"content": (PROJECT / "src" / "EthereumMonero.sol").read_text()}},
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "evmVersion": "shanghai",
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
        },
    }


def _run_solc(cmd, std_input):
    out = subprocess.run(cmd, input=json.dumps(std_input), capture_output=True, text=True, timeout=600).stdout
    return json.loads(out[out.find("{"):])  # solcjs prints a notice line before the JSON


def compile_contract():
    """Compile with solc 0.8.24 from PATH, else py-solc-x, else solcjs through npx."""
    std_input = _standard_input()
    solc = shutil.which("solc")
    if solc and SOLC_VERSION in subprocess.run([solc, "--version"], capture_output=True, text=True).stdout:
        out = _run_solc([solc, "--standard-json"], std_input)
    else:
        try:
            import solcx

            solcx.install_solc(SOLC_VERSION)
            out = solcx.compile_standard(std_input, solc_version=SOLC_VERSION)
        except Exception:
            if not shutil.which("npx"):
                pytest.skip("needs solc 0.8.24, py-solc-x, or node/npx")
            out = _run_solc(["npx", "--yes", "--package", f"solc@{SOLC_VERSION}", "solcjs", "--standard-json"], std_input)
    errors = [e["formattedMessage"] for e in out.get("errors", []) if e["severity"] == "error"]
    assert not errors, "\n".join(errors)
    c = out["contracts"]["EthereumMonero.sol"]["EthereumMonero"]
    return {"abi": c["abi"], "bytecode": "0x" + c["evm"]["bytecode"]["object"]}


@pytest.fixture(scope="session")
def artifact():
    return compile_contract()


@pytest.fixture
def chain(artifact):
    """A fresh in-process EVM with EXMR deployed: (w3, token, owner, minter_account, alice, bob).

    The minter is a local key (the relayer signs its own transactions); the rest are
    the tester's unlocked accounts.
    """
    pytest.importorskip("eth_tester")
    from eth_account import Account
    from web3 import EthereumTesterProvider, Web3

    w3 = Web3(EthereumTesterProvider())
    owner, alice, bob = w3.eth.accounts[:3]
    minter = Account.create()
    w3.eth.send_transaction({"from": owner, "to": minter.address, "value": 10**20})
    factory = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    receipt = w3.eth.wait_for_transaction_receipt(
        factory.constructor(minter.address, 100 * XMR).transact({"from": owner})
    )
    token = w3.eth.contract(address=receipt.contractAddress, abi=artifact["abi"])
    return w3, token, owner, minter, alice, bob
