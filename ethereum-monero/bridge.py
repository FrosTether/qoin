#!/usr/bin/env python3
"""
Ethereum Monero bridge: XMR <-> EXMR on Ethereum Classic.

Runs next to monerod and a monero-wallet-rpc that has the vault wallet open.

  XMR -> ETC : each ETC user gets a vault subaddress labelled with their 0x address.
               Deposits to it are minted as EXMR to that 0x once they are confirmed and unlocked.
  ETC -> XMR : burns are paid from the vault, less the Monero network fee, then marked paid
               on-chain. A burn that can't be paid (bad address, too small) is refunded as EXMR.

Setup:
  pip install -r requirements.txt
  export EXMR_CONTRACT=0x...   # EthereumMonero address
  export BRIDGE_ETC_KEY=0x...  # private key of the contract's minter; keep the owner key elsewhere
  python3 bridge.py register 0x42FF98C4E85212a5D31358ACbFe76a621b50fC02   # that user's deposit subaddress
  python3 bridge.py run                  # the loop; `once` does a single pass
  python3 bridge.py status               # vault balance against what EXMR holders are owed
  python3 bridge.py proof > proof.json   # Monero reserve proof tied to the EXMR supply
  python3 bridge.py verify proof.json    # anyone can check one (with any wallet open in their wallet RPC)

Other settings (env): ETC_RPC, ETC_CHAIN_ID (61; Mordor testnet is 63), MONERO_WALLET_RPC,
MONERO_WALLET_LOGIN (user:pass if the wallet RPC uses --rpc-login), XMR_CONFS (10),
ETC_CONFS (500), MIN_PAYOUT_XMR (0.001), STATE_FILE, POLL_SECONDS (60).
"""
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from decimal import Decimal

import requests
from requests.auth import HTTPDigestAuth
from web3 import Web3

try:
    import fcntl
except ImportError:  # Windows: no lock file, so make sure only one relayer runs
    fcntl = None

XMR_DECIMALS = 12        # 1 XMR = 10**12 piconero
PENDING = 1              # EthereumMonero.BurnState.Pending
NOTE = "exmr-burn:"      # wallet tx note on every payout, e.g. "exmr-burn:7"
PROOF_MESSAGE = re.compile(
    r"EXMR (0x[0-9a-fA-F]{40}) supply (\d+) unpaid-burns (\d+) at ETC block (\d+) (0x[0-9a-f]{64})"
)

ABI = json.loads("""[
 {"type":"function","name":"decimals","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint8"}]},
 {"type":"function","name":"minter","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"address"}]},
 {"type":"function","name":"totalSupply","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
 {"type":"function","name":"mintHeadroom","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
 {"type":"function","name":"depositMinted","stateMutability":"view","inputs":[{"name":"moneroTxId","type":"bytes32"},{"name":"subaddressIndex","type":"uint32"}],"outputs":[{"name":"","type":"bool"}]},
 {"type":"function","name":"mintFromMonero","stateMutability":"nonpayable","inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"},{"name":"moneroTxId","type":"bytes32"},{"name":"subaddressIndex","type":"uint32"}],"outputs":[]},
 {"type":"function","name":"burnCount","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
 {"type":"function","name":"burns","stateMutability":"view","inputs":[{"name":"","type":"uint256"}],"outputs":[{"name":"from","type":"address"},{"name":"state","type":"uint8"},{"name":"blockNumber","type":"uint64"},{"name":"amount","type":"uint256"},{"name":"moneroAddress","type":"string"}]},
 {"type":"function","name":"markPaid","stateMutability":"nonpayable","inputs":[{"name":"burnId","type":"uint256"},{"name":"moneroTxId","type":"bytes32"}],"outputs":[]},
 {"type":"function","name":"refundBurn","stateMutability":"nonpayable","inputs":[{"name":"burnId","type":"uint256"}],"outputs":[]}
]""")


def xmr(atomic):
    """Piconero as an XMR string."""
    return f"{Decimal(atomic) / 10**XMR_DECIMALS:f}"


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


class WalletError(RuntimeError):
    pass


class Wallet:
    """monero-wallet-rpc JSON-RPC client."""

    def __init__(self, url, login=""):
        self.url = url
        self.auth = HTTPDigestAuth(*login.split(":", 1)) if login else None

    def __call__(self, method, params=None):
        r = requests.post(self.url, json={"jsonrpc": "2.0", "id": "0", "method": method, "params": params or {}},
                          auth=self.auth, timeout=300)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise WalletError(f"{method}: {j['error'].get('message', j['error'])}")
        return j["result"]


def mint_target(label):
    """The ETC address a vault subaddress label names, or None if it isn't a bridge deposit address."""
    if not Web3.is_address(label) or int(label, 16) == 0:
        return None
    return Web3.to_checksum_address(label)


def register(wallet, eth_address):
    """The vault subaddress whose deposits mint to eth_address; created on first use."""
    eth_address = mint_target(eth_address)
    if eth_address is None:
        raise ValueError("not an ETC address that can receive EXMR")
    for a in wallet("get_address", {"account_index": 0})["addresses"]:
        if a["address_index"] != 0 and a.get("label") == eth_address:
            return a["address"]
    return wallet("create_address", {"account_index": 0, "label": eth_address})["address"]


class Bridge:
    def __init__(self, w3, token, wallet, account=None, *, chain_id=61, xmr_confs=10, etc_confs=500,
                 min_payout=10**9, state_file="exmr_bridge_state.json", log=log):
        self.w3, self.token, self.wallet, self.account = w3, token, wallet, account
        self.chain_id, self.xmr_confs, self.etc_confs = chain_id, xmr_confs, etc_confs
        self.min_payout, self.state_file, self.log = min_payout, state_file, log
        self.scale = 10 ** (token.functions.decimals().call() - XMR_DECIMALS)  # EXMR raw units per piconero
        self.state = self._load()

    # ---------- state ----------
    def _load(self):
        try:
            with open(self.state_file) as f:
                saved = json.load(f)
        except FileNotFoundError:
            saved = {}
        return {"minted": saved.get("minted", []), "next_burn": saved.get("next_burn", 0),
                "payouts": saved.get("payouts", {})}

    def save(self):
        tmp = self.state_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.state_file)

    # ---------- ETC ----------
    def check(self):
        """Refuse to sign on the wrong chain or with a key that is not the minter."""
        chain = self.w3.eth.chain_id
        if chain != self.chain_id:
            sys.exit(f"ETC_RPC is chain {chain}, expected {self.chain_id} (set ETC_CHAIN_ID)")
        minter = self.token.functions.minter().call()
        if minter != self.account.address:
            sys.exit(f"BRIDGE_ETC_KEY is {self.account.address}, but the contract's minter is {minter}")

    def send(self, call):
        """Sign a legacy gasPrice transaction (ETC has no EIP-1559), send it, and wait for it."""
        tx = call.build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "chainId": self.chain_id,
            "gasPrice": self.w3.eth.gas_price,
        })
        tx_hash = self.w3.eth.send_raw_transaction(self.account.sign_transaction(tx).raw_transaction)
        if self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600).status != 1:
            raise RuntimeError(f"ETC transaction {Web3.to_hex(tx_hash)} failed")
        return Web3.to_hex(tx_hash)

    # ---------- XMR -> ETC ----------
    def mint_deposits(self):
        """Mint EXMR for confirmed, unlocked deposits to labelled subaddresses, oldest first."""
        self.wallet("refresh")
        labels = {a["address_index"]: a.get("label", "")
                  for a in self.wallet("get_address", {"account_index": 0})["addresses"]}
        done = set(self.state["minted"])
        deposits = self.wallet("get_transfers", {"in": True, "account_index": 0}).get("in", [])
        for t in sorted(deposits, key=lambda t: t["height"]):
            minor = t["subaddr_index"]["minor"]
            to = mint_target(labels.get(minor, ""))
            key = f"{t['txid']}:{minor}"
            if key in done or minor == 0 or to is None or t["amount"] == 0:
                continue                               # minted already, or not a bridge deposit
            if t.get("confirmations", 0) < self.xmr_confs or t.get("locked", t.get("unlock_time", 0) != 0):
                continue                               # not final or not spendable yet
            txid = bytes.fromhex(t["txid"])
            if not self.token.functions.depositMinted(txid, minor).call():
                amount = t["amount"] * self.scale
                if amount > self.token.functions.mintHeadroom().call():
                    self.log(f"daily mint limit reached; deposit {key} waits for the next window")
                    return
                etc_tx = self.send(self.token.functions.mintFromMonero(to, amount, txid, minor))
                self.log(f"minted {xmr(t['amount'])} EXMR to {to} (xmr {t['txid']}, etc {etc_tx})")
            self.state["minted"].append(key)
            done.add(key)
            self.save()

    # ---------- ETC -> XMR ----------
    def settle_burns(self):
        """Pay or refund every burn that is ETC_CONFS deep, in burn order."""
        head = self.w3.eth.block_number
        count = self.token.functions.burnCount().call()
        noted = None
        while self.state["next_burn"] < count:
            burn_id = self.state["next_burn"]
            frm, state, block, amount, address = self.token.functions.burns(burn_id).call()
            if state == PENDING:
                if head - block < self.etc_confs:
                    return                             # this burn and every later one are too recent
                if noted is None:
                    noted = self._noted_payouts()
                self._settle(burn_id, frm, amount, address, noted)
            self.state["payouts"].pop(str(burn_id), None)
            self.state["next_burn"] = burn_id + 1
            self.save()

    def _settle(self, burn_id, frm, amount, address, noted):
        payout = self.state["payouts"].get(str(burn_id)) or noted.get(burn_id)
        if payout is None:
            payout, problem = self._new_payout(burn_id, amount // self.scale, address)
            if problem:
                etc_tx = self.send(self.token.functions.refundBurn(burn_id))
                self.log(f"refunded burn {burn_id} to {frm}: {problem} (etc {etc_tx})")
                return
        self._relay(burn_id, payout)
        etc_tx = self.send(self.token.functions.markPaid(burn_id, bytes.fromhex(payout["tx_hash"])))
        self.wallet("store")
        self.log(f"paid burn {burn_id}: {xmr(payout['amount'])} XMR to {address} "
                 f"(xmr {payout['tx_hash']}, etc {etc_tx})")

    def _new_payout(self, burn_id, atomic, address):
        """Build, but don't relay, a payout of `atomic` less its own fee. Returns (payout, problem)."""
        if not self.wallet("validate_address", {"address": address}).get("valid"):
            return None, f"{address!r} is not a Monero address on this wallet's network"
        if atomic < self.min_payout:
            return None, f"{xmr(atomic)} XMR is below the {xmr(self.min_payout)} XMR minimum"
        params = {"destinations": [{"amount": atomic, "address": address}], "account_index": 0,
                  "subtract_fee_from_outputs": [0], "do_not_relay": True, "get_tx_metadata": True}
        tx = self.wallet("transfer", params)
        if tx["amount"] + tx["fee"] > atomic:          # this wallet RPC ignored subtract_fee_from_outputs
            if tx["fee"] >= atomic:
                return None, f"{xmr(atomic)} XMR does not cover the {xmr(tx['fee'])} XMR fee"
            params["destinations"][0]["amount"] = atomic - tx["fee"]
            tx = self.wallet("transfer", params)
            if tx["amount"] + tx["fee"] > atomic:
                raise RuntimeError(f"burn {burn_id}: the Monero fee went up while building; retrying")
        self.wallet("set_tx_notes", {"txids": [tx["tx_hash"]], "notes": [f"{NOTE}{burn_id}"]})
        payout = {k: tx[k] for k in ("tx_hash", "tx_metadata", "amount", "fee")}
        self.state["payouts"][str(burn_id)] = payout
        self.save()                                    # saved before relaying, so a crash can't pay twice
        return payout, None

    def _relay(self, burn_id, payout):
        """Relay a saved payout, unless the wallet already sent it (before a crash, say).

        Relaying a tx that is already mined makes the wallet list it as pending a second time.
        """
        if "tx_metadata" not in payout or self._sent(payout["tx_hash"]):
            return
        try:
            self.wallet("relay_tx", {"hex": payout["tx_metadata"]})
        except WalletError as e:
            if not self._sent(payout["tx_hash"]):
                raise RuntimeError(f"burn {burn_id}: payout {payout['tx_hash']} was not accepted ({e}); check the "
                                   f"wallet, then delete payouts[{burn_id}] from {self.state_file} to retry") from e

    def _sent(self, txid):
        try:
            return self.wallet("get_transfer_by_txid", {"txid": txid})["transfer"]["type"] in ("out", "pending")
        except WalletError:
            return False                               # the wallet has never seen it

    def _noted_payouts(self):
        """Payouts the wallet already sent, by burn id, from their tx notes (survives a lost state file)."""
        found = {}
        sent = self.wallet("get_transfers", {"out": True, "pending": True, "account_index": 0})
        for t in sent.get("out", []) + sent.get("pending", []):
            burn_id = t.get("note", "").removeprefix(NOTE)
            if t.get("note", "").startswith(NOTE) and burn_id.isdigit():
                found[int(burn_id)] = {"tx_hash": t["txid"], "amount": t["amount"], "fee": t["fee"]}
        return found

    # ---------- loop ----------
    def run_once(self):
        """One pass in each direction. False if either hit an error (the next pass retries)."""
        ok = True
        for step in (self.mint_deposits, self.settle_burns):
            try:
                step()
            except Exception as e:  # keep the relayer alive
                self.log(f"{step.__name__}: {e}")
                ok = False
        return ok

    def run(self, poll=60):
        self.log(f"bridge up · minter {self.account.address} · EXMR {self.token.address}")
        while True:
            self.run_once()
            time.sleep(poll)

    # ---------- reserves ----------
    def unpaid_burns(self, block="latest"):
        """EXMR burned but not yet paid or refunded (the vault still owes it)."""
        total = 0
        for burn_id in range(self.token.functions.burnCount().call(block_identifier=block)):
            _, state, _, amount, _ = self.token.functions.burns(burn_id).call(block_identifier=block)
            if state == PENDING:
                total += amount
        return total

    def status(self):
        balance = self.wallet("get_balance", {"account_index": 0})
        supply = self.token.functions.totalSupply().call()
        unpaid = self.unpaid_burns()
        return {
            "exmr_supply": xmr(supply // self.scale),
            "unpaid_burns": xmr(unpaid // self.scale),
            "vault_balance": xmr(balance["balance"]),
            "vault_unlocked": xmr(balance["unlocked_balance"]),
            "surplus": xmr(balance["balance"] - (supply + unpaid) // self.scale),
            "mint_headroom": xmr(self.token.functions.mintHeadroom().call() // self.scale),
        }

    def reserve_proof(self):
        """Monero reserve proof over the whole vault, signed over what EXMR holders are owed."""
        self.wallet("refresh")
        if self.wallet("get_transfers", {"pending": True, "account_index": 0}).get("pending"):
            sys.exit("A payout is still unconfirmed; make the proof once it is mined.")
        block = self.w3.eth.get_block("latest")
        supply = self.token.functions.totalSupply().call(block_identifier=block.number)
        unpaid = self.unpaid_burns(block.number)
        message = (f"EXMR {self.token.address} supply {supply} unpaid-burns {unpaid} "
                   f"at ETC block {block.number} {Web3.to_hex(block.hash)}")
        return {
            "address": self.wallet("get_address", {"account_index": 0})["address"],
            "message": message,
            "signature": self.wallet("get_reserve_proof", {"all": True, "message": message})["signature"],
        }


def verify_proof(w3, wallet, proof):
    """Check a reserve proof: Monero signature, reserve >= owed, and the claims against ETC."""
    m = PROOF_MESSAGE.fullmatch(proof["message"])
    if not m:
        return {"ok": False, "error": "not an EXMR reserve proof message"}
    contract, supply, unpaid, number, block_hash = m[1], int(m[2]), int(m[3]), int(m[4]), m[5]
    check = wallet("check_reserve_proof", {k: proof[k] for k in ("address", "message", "signature")})
    token = w3.eth.contract(address=Web3.to_checksum_address(contract), abi=ABI)
    scale = 10 ** (token.functions.decimals().call() - XMR_DECIMALS)
    reserve, owed = check["total"] - check["spent"], (supply + unpaid) // scale
    block_ok = Web3.to_hex(w3.eth.get_block(number).hash) == block_hash
    try:
        supply_ok = token.functions.totalSupply().call(block_identifier=number) == supply
    except Exception:
        supply_ok = None                               # this node keeps no state that old; try an archive RPC
    return {
        "ok": bool(check["good"]) and reserve >= owed and block_ok and supply_ok is not False,
        "signature_good": check["good"],
        "reserve_xmr": xmr(reserve),
        "owed_xmr": xmr(owed),
        "etc_block": number,
        "etc_block_matches": block_ok,
        "supply_matches_chain": supply_ok,
    }


# ---------- command line ----------
def wallet_from_env():
    return Wallet(os.getenv("MONERO_WALLET_RPC", "http://127.0.0.1:18083/json_rpc"), os.getenv("MONERO_WALLET_LOGIN", ""))


def w3_from_env():
    return Web3(Web3.HTTPProvider(os.getenv("ETC_RPC", "https://etc.rivet.link")))


def bridge_from_env():
    contract = os.getenv("EXMR_CONTRACT", "")
    if not contract:
        sys.exit("Set EXMR_CONTRACT first.")
    w3 = w3_from_env()
    key = os.getenv("BRIDGE_ETC_KEY", "")
    return Bridge(
        w3,
        w3.eth.contract(address=Web3.to_checksum_address(contract), abi=ABI),
        wallet_from_env(),
        w3.eth.account.from_key(key) if key else None,
        chain_id=int(os.getenv("ETC_CHAIN_ID", "61")),
        xmr_confs=int(os.getenv("XMR_CONFS", "10")),
        etc_confs=int(os.getenv("ETC_CONFS", "500")),
        min_payout=int(Decimal(os.getenv("MIN_PAYOUT_XMR", "0.001")) * 10**XMR_DECIMALS),
        state_file=os.getenv("STATE_FILE", "exmr_bridge_state.json"),
    )


@contextmanager
def single_instance(state_file):
    """Keep a second relayer on this machine from paying the same burns."""
    if fcntl is None:
        yield
        return
    with open(state_file + ".lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit(f"Another bridge.py is already running with {state_file}.")
        yield


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    cmd = args[0] if args else ""
    if cmd == "register" and len(args) == 2:
        print(f"Deposit XMR to:\n{register(wallet_from_env(), args[1])}\n"
              f"-> minted as EXMR to {Web3.to_checksum_address(args[1])}")
    elif cmd in ("run", "once") and len(args) == 1:
        bridge = bridge_from_env()
        if bridge.account is None:
            sys.exit("Set BRIDGE_ETC_KEY first.")
        with single_instance(bridge.state_file):
            bridge.check()
            if cmd == "once":
                return 0 if bridge.run_once() else 1
            bridge.run(int(os.getenv("POLL_SECONDS", "60")))
    elif cmd == "status" and len(args) == 1:
        print(json.dumps(bridge_from_env().status(), indent=2))
    elif cmd == "proof" and len(args) == 1:
        print(json.dumps(bridge_from_env().reserve_proof(), indent=2))
    elif cmd == "verify" and len(args) == 2:
        with open(args[1]) as f:
            result = verify_proof(w3_from_env(), wallet_from_env(), json.load(f))
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
