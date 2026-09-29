"""bridge.py end to end: a Monero regtest node, a vault and a user wallet, and EXMR on an in-process EVM.

Needs the Monero CLI (monerod, monero-wallet-rpc) on PATH; skipped otherwise. Takes about a minute.
"""

import json
import os
import shutil
import socket
import subprocess
import time
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("web3")
pytest.importorskip("eth_tester")

import bridge  # noqa: E402

MONEROD, WALLET_RPC = shutil.which("monerod"), shutil.which("monero-wallet-rpc")
pytestmark = pytest.mark.skipif(not (MONEROD and WALLET_RPC), reason="needs monerod and monero-wallet-rpc on PATH")

XMR = 10**12
PENDING, PAID, REFUNDED = 1, 2, 3


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def monero(tmp_path_factory):
    root = tmp_path_factory.mktemp("regtest")
    node_port, vault_port, user_port = free_port(), free_port(), free_port()
    procs = [subprocess.Popen(
        [MONEROD, "--regtest", "--offline", "--fixed-difficulty", "1", "--no-igd", "--non-interactive", "--no-zmq",
         "--data-dir", str(root / "node"), "--p2p-bind-port", str(free_port()), "--rpc-bind-ip", "127.0.0.1",
         "--rpc-bind-port", str(node_port), "--disable-dns-checkpoints", "--check-updates", "disabled", "--log-level", "0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
    for name, port in (("vault", vault_port), ("user", user_port)):
        (root / name).mkdir()
        procs.append(subprocess.Popen(
            [WALLET_RPC, "--wallet-dir", str(root / name), "--daemon-address", f"127.0.0.1:{node_port}",
             "--trusted-daemon", "--allow-mismatched-daemon-version", "--rpc-bind-ip", "127.0.0.1",
             "--rpc-bind-port", str(port), "--disable-rpc-login", "--log-level", "0", "--non-interactive"],
            cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    node, vault, user = (bridge.Wallet(f"http://127.0.0.1:{p}/json_rpc") for p in (node_port, vault_port, user_port))
    try:
        deadline = time.time() + 120
        while True:
            try:
                node("get_info"), vault("get_version"), user("get_version")
                break
            except Exception:
                if time.time() > deadline:
                    raise
                time.sleep(1)
        vault("create_wallet", {"filename": "vault", "language": "English"})
        user("create_wallet", {"filename": "user", "language": "English"})
        user_address = user("get_address")["address"]

        def mine(blocks):
            node("generateblocks", {"amount_of_blocks": blocks, "wallet_address": user_address})
            vault("refresh"), user("refresh")

        mine(140)  # the user's first 80 coinbases unlock; plenty of decoys for ring size 16
        yield SimpleNamespace(vault=vault, user=user, user_address=user_address, mine=mine)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()


def test_round_trip(monero, chain, tmp_path):
    w3, token, owner, minter, alice, bob = chain
    vault, user, mine, user_address = monero.vault, monero.user, monero.mine, monero.user_address
    exmr = w3.eth.contract(address=token.address, abi=bridge.ABI)  # the relayer's own ABI
    state_file = str(tmp_path / "state.json")
    logs = []

    def relayer(**options):
        opts = dict(chain_id=w3.eth.chain_id, etc_confs=2, min_payout=XMR // 100, state_file=state_file, log=logs.append)
        return bridge.Bridge(w3, exmr, vault, minter, **{**opts, **options})

    def minor(address):
        return vault("get_address_index", {"address": address})["index"]["minor"]

    def burn(who, amount, address):
        token.functions.burnToMonero(amount, address).transact({"from": who})
        w3.testing.mine(2)  # ETC_CONFS deep
        return token.functions.burnCount().call() - 1

    def state_of(burn_id):
        return token.functions.burns(burn_id).call()[1]

    def payout_of(burn_id):
        (ev,) = token.events.BurnPaid().get_logs(from_block=0, argument_filters={"burnId": burn_id})
        return vault("get_transfer_by_txid", {"txid": ev.args.moneroTxId.hex()})["transfer"]

    def noted(burn_id):
        sent = vault("get_transfers", {"out": True, "pending": True})
        return [t for t in sent.get("out", []) + sent.get("pending", []) if t.get("note") == f"exmr-burn:{burn_id}"]

    def crash_on_mark_paid(b):
        real_send = b.send

        def send(call):
            if call.fn_name == "markPaid":
                raise RuntimeError("crash")
            return real_send(call)

        b.send = send
        return b

    b = relayer()
    b.check()

    # register: one vault subaddress per ETC address, same one every time
    alice_sub, bob_sub = bridge.register(vault, alice), bridge.register(vault, bob)
    assert bridge.register(vault, alice.lower()) == alice_sub != bob_sub

    # XMR -> EXMR: one Monero transaction paying both users' subaddresses
    deposit = user("transfer", {"destinations": [{"amount": 5 * XMR // 2, "address": alice_sub},
                                                 {"amount": 3 * XMR // 4, "address": bob_sub}]})
    mine(1)
    b.mint_deposits()
    assert token.functions.totalSupply().call() == 0  # 1 confirmation: still locked
    mine(10)
    b.mint_deposits()
    assert token.functions.balanceOf(alice).call() == 5 * XMR // 2
    assert token.functions.balanceOf(bob).call() == 3 * XMR // 4
    txid = bytes.fromhex(deposit["tx_hash"])
    assert token.functions.depositMinted(txid, minor(alice_sub)).call()
    assert token.functions.depositMinted(txid, minor(bob_sub)).call()

    # a relayer that lost its state file checks the chain and mints nothing twice
    os.remove(state_file)
    relayer().mint_deposits()
    assert token.functions.totalSupply().call() == 13 * XMR // 4

    # a deposit above the daily headroom waits until the owner raises the limit
    b = relayer()
    token.functions.setDailyMintLimit(4 * XMR).transact({"from": owner})
    user("transfer", {"destinations": [{"amount": XMR, "address": alice_sub}]})
    mine(11)
    b.mint_deposits()
    assert token.functions.balanceOf(alice).call() == 5 * XMR // 2
    assert any("daily mint limit" in m for m in logs)
    token.functions.setDailyMintLimit(100 * XMR).transact({"from": owner})
    b.mint_deposits()
    assert token.functions.balanceOf(alice).call() == 7 * XMR // 2

    # EXMR -> XMR: waits for ETC_CONFS, pays the burn less the fee, marks it paid on-chain
    token.functions.burnToMonero(XMR, user_address).transact({"from": alice})
    b.settle_burns()
    assert state_of(0) == PENDING
    w3.testing.mine(2)
    b.settle_burns()
    assert state_of(0) == PAID
    paid = payout_of(0)
    assert paid["amount"] + paid["fee"] == XMR  # the vault spends exactly what was burned
    assert paid["note"] == "exmr-burn:0"
    with pytest.raises(SystemExit, match="unconfirmed"):
        b.reserve_proof()  # a payout in flight would skew the proof
    mine(1)
    received = [t for t in user("get_transfers", {"in": True})["in"] if t["txid"] == paid["txid"]]
    assert [t["amount"] for t in received] == [XMR - paid["fee"]]

    # burns the bridge can't pay are refunded as EXMR
    bad_address = user_address[:-1] + ("A" if user_address[-1] != "A" else "B")  # checksum fails
    bad = burn(bob, 3 * XMR // 4, bad_address)
    small = burn(alice, XMR // 1000, user_address)  # under MIN_PAYOUT (0.01)
    b.settle_burns()
    assert (state_of(bad), state_of(small)) == (REFUNDED, REFUNDED)
    assert token.functions.balanceOf(bob).call() == 3 * XMR // 4
    fee_eaten = burn(alice, XMR // 1000, user_address)  # no minimum, but the fee is larger (regtest fees are high)
    relayer(min_payout=1).settle_burns()
    assert state_of(fee_eaten) == REFUNDED
    assert any("does not cover" in m for m in logs)

    # crash after relaying the payout, before markPaid: the retry relays the same tx and pays once
    mine(10)  # unlock the change from the first payout
    half = burn(alice, XMR // 2, user_address)
    with pytest.raises(RuntimeError, match="crash"):
        crash_on_mark_paid(relayer()).settle_burns()
    assert state_of(half) == PENDING and len(noted(half)) == 1
    mine(1)  # the payout is even mined before the relayer comes back
    relayer().settle_burns()
    assert state_of(half) == PAID and len(noted(half)) == 1

    # same crash, and the state file is lost too: the wallet's tx note stops a second payment
    mine(10)
    quarter = burn(alice, XMR // 4, user_address)
    with pytest.raises(RuntimeError, match="crash"):
        crash_on_mark_paid(relayer()).settle_burns()
    os.remove(state_file)
    relayer().settle_burns()
    assert state_of(quarter) == PAID and len(noted(quarter)) == 1
    assert payout_of(quarter)["txid"] == noted(quarter)[0]["txid"]

    # the vault holds what EXMR holders are owed, and a reserve proof shows it
    mine(1)
    status = relayer().status()
    assert Decimal(status["exmr_supply"]) == Decimal("2.5") and Decimal(status["unpaid_burns"]) == 0
    assert Decimal(0) <= Decimal(status["surplus"]) < Decimal("0.001")
    proof = relayer().reserve_proof()
    result = bridge.verify_proof(w3, user, proof)  # checked from a different wallet
    assert result["ok"] and result["signature_good"] and result["etc_block_matches"] and result["supply_matches_chain"]
    assert Decimal(result["reserve_xmr"]) >= Decimal(result["owed_xmr"]) == Decimal("2.5")
    forged = dict(proof, message=proof["message"].replace(" supply ", " supply 1"))
    assert not bridge.verify_proof(w3, user, forged)["ok"]


def test_command_line(monero, chain, tmp_path, monkeypatch, capsys):
    w3, token, _, minter, alice, _ = chain
    monero.vault("create_wallet", {"filename": "vault-cli", "language": "English"})  # a vault with no history
    monkeypatch.setattr(bridge, "w3_from_env", lambda: w3)
    for name, value in {
        "EXMR_CONTRACT": token.address,
        "BRIDGE_ETC_KEY": w3.to_hex(minter.key),
        "ETC_CHAIN_ID": str(w3.eth.chain_id),
        "ETC_CONFS": "0",
        "MONERO_WALLET_RPC": monero.vault.url,
        "STATE_FILE": str(tmp_path / "state.json"),
    }.items():
        monkeypatch.setenv(name, value)

    assert bridge.main(["register", alice]) == 0
    deposit_address = capsys.readouterr().out.splitlines()[1]
    monero.user("transfer", {"destinations": [{"amount": XMR, "address": deposit_address}]})
    monero.mine(11)
    assert bridge.main(["once"]) == 0
    assert token.functions.balanceOf(alice).call() == XMR

    token.functions.burnToMonero(XMR // 2, monero.user_address).transact({"from": alice})
    assert bridge.main(["once"]) == 0
    assert token.functions.burns(0).call()[1] == PAID
    monero.mine(1)

    capsys.readouterr()
    assert bridge.main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert Decimal(status["exmr_supply"]) == Decimal("0.5") and Decimal(status["surplus"]) >= 0

    assert bridge.main(["proof"]) == 0
    proof = tmp_path / "proof.json"
    proof.write_text(capsys.readouterr().out)
    monkeypatch.setenv("MONERO_WALLET_RPC", monero.user.url)  # a verifier's own wallet
    assert bridge.main(["verify", str(proof)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
