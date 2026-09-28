#!/usr/bin/env python3
"""
Frostoise <-> ETC bridge for Qoin (Finux).

Runs on your VPS next to frostnerod + the Frostoise wallet RPC.

  Frostoise -> ETC : each ETC user gets their own Frostoise subaddress (labelled with their 0x).
                     Confirmed deposits to it are minted as QOIN to that 0x on Ethereum Classic.
  ETC -> Frostoise : BurnedToFrostoise events on ETC are paid out from the Frostoise vault wallet.

Setup:
  pip install web3==6.* requests
  export BRIDGE_ETC_KEY=0x...      # private key of 0x151f…f3b9 (MetaMask → Account details → Show private key) — keep this machine locked down
  export QOIN_CONTRACT=0x...       # address Remix gives you after deploy
  python3 bridge.py register 0x42FF98C4E85212a5D31358ACbFe76a621b50fC02   # prints that user's deposit subaddress
  python3 bridge.py run                                                   # the loop
"""
import json, os, sys, time
import requests
from web3 import Web3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "graysons"))
import qoin_number   # number addresses: a Frostoise address written in digits only

# ---------- config ----------
ETC_RPC        = os.getenv("ETC_RPC", "https://etc.rivet.link")
WALLET_RPC     = os.getenv("FROSTOISE_WALLET_RPC", "http://127.0.0.1:45673/json_rpc")   # wallet RPC; run it with --rpc-bind-port 45673   
CONTRACT       = os.getenv("QOIN_CONTRACT", "")
ETC_KEY        = os.getenv("BRIDGE_ETC_KEY", "")
FROST_DECIMALS = int(os.getenv("FROSTOISE_DECIMALS", "11"))   # confirmed: CRYPTONOTE_DISPLAY_DECIMAL_POINT 11
FROST_CONFS    = 10     # Frostoise confirmations before minting (~50 min at 5-min blocks)
ETC_CONFS      = 120    # ETC confirmations before paying out a burn (~30 min; ETC has had reorg attacks)
STATE_FILE     = "bridge_state.json"
SCALE          = 10 ** (18 - FROST_DECIMALS)                   # Frostoise atomic -> QOIN wei

ABI = json.loads("""[
 {"type":"function","name":"mintFromFrostoise","stateMutability":"nonpayable",
  "inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"},{"name":"frostoiseTx","type":"bytes32"}],"outputs":[]},
 {"type":"function","name":"processed","stateMutability":"view",
  "inputs":[{"name":"","type":"bytes32"}],"outputs":[{"name":"","type":"bool"}]},
 {"type":"event","name":"BurnedToFrostoise","anonymous":false,
  "inputs":[{"name":"from","type":"address","indexed":true},{"name":"amount","type":"uint256","indexed":false},
            {"name":"frostoiseAddress","type":"string","indexed":false}]}
]""")

# ---------- helpers ----------
def rpc(method, params=None):
    r = requests.post(WALLET_RPC, json={"jsonrpc": "2.0", "id": "0", "method": method, "params": params or {}}, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"{method}: {j['error']}")
    return j["result"]

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"etc_from_block": None, "paid_burns": []}

def save_state(s):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, STATE_FILE)

def w3_and_contract():
    w3 = Web3(Web3.HTTPProvider(ETC_RPC))
    c = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT), abi=ABI)
    acct = w3.eth.account.from_key(ETC_KEY)
    return w3, c, acct

# ---------- register a user ----------
def register(eth_addr):
    eth_addr = eth_addr.removeprefix("FPu")
    eth_addr = Web3.to_checksum_address(eth_addr)
    res = rpc("create_address", {"account_index": 0, "label": eth_addr})
    try:
        number = "\nor its number address:\n" + qoin_number.group(qoin_number.to_number(res["address"]))
    except qoin_number.NumberError:
        number = ""
    print(f"Deposit Frostoise to:\n{res['address']}{number}\n→ minted as QOIN to {eth_addr}")

# ---------- Frostoise -> ETC ----------
def mint_deposits(w3, c, acct):
    subs = rpc("get_address", {"account_index": 0})["addresses"]
    label_of = {a["address_index"]: a.get("label", "") for a in subs}
    height = rpc("get_height")["height"]
    txs = rpc("get_transfers", {"in": True, "account_index": 0}).get("in", [])
    for t in txs:
        idx = t["subaddr_index"]["minor"]
        to = label_of.get(idx, "")
        if idx == 0 or not Web3.is_address(to):
            continue                                   # mining rewards / unlabelled — not a bridge deposit
        if height - t["height"] < FROST_CONFS:
            continue
        txid = bytes.fromhex(t["txid"])
        key = txid if len(txid) == 32 else Web3.keccak(txid)
        if c.functions.processed(key).call():
            continue
        amount = int(t["amount"]) * SCALE
        tx = c.functions.mintFromFrostoise(Web3.to_checksum_address(to), amount, key).build_transaction({
            "from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address), "chainId": 61,
            "gasPrice": w3.eth.gas_price})
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.rawTransaction)
        w3.eth.wait_for_transaction_receipt(h, timeout=600)
        print(f"minted {amount / 1e18} QOIN → {to}  (frostoise tx {t['txid'][:12]}…, etc tx {h.hex()})")

# ---------- ETC -> Frostoise ----------
def pay_burns(w3, c, state):
    head = w3.eth.block_number - ETC_CONFS
    start = state["etc_from_block"] or head
    if head < start:
        return
    for frm in range(start, head + 1, 5000):
        to_blk = min(frm + 4999, head)
        for ev in c.events.BurnedToFrostoise.get_logs(fromBlock=frm, toBlock=to_blk):
            key = f"{ev.transactionHash.hex()}:{ev.logIndex}"
            if key in state["paid_burns"]:
                continue
            atomic = ev.args.amount // SCALE
            try:
                dest = qoin_number.as_address(ev.args.frostoiseAddress)   # a number address works too
            except qoin_number.NumberError:
                dest = ev.args.frostoiseAddress                           # mistyped: validate_address refuses it
            if atomic == 0 or not rpc("validate_address", {"address": dest}).get("valid"):
                print(f"skip burn {key}: bad amount or address {dest!r} — refund by hand")
            else:
                res = rpc("transfer", {"destinations": [{"amount": atomic, "address": dest}], "account_index": 0})
                print(f"paid {atomic / 10**FROST_DECIMALS} Frostoise → {dest[:12]}…  (tx {res['tx_hash'][:12]}…)")
            state["paid_burns"].append(key)
            save_state(state)                           # save after every payout so a crash never double-pays
        state["etc_from_block"] = to_blk + 1
        save_state(state)

def run():
    if not (CONTRACT and ETC_KEY):
        sys.exit("Set QOIN_CONTRACT and BRIDGE_ETC_KEY first.")
    w3, c, acct = w3_and_contract()
    print(f"bridge up · ETC signer {acct.address} · contract {CONTRACT}")
    state = load_state()
    while True:
        try:
            mint_deposits(w3, c, acct)
            pay_burns(w3, c, state)
        except Exception as e:
            print("error:", e)
        time.sleep(60)

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "register":
        register(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "run":
        run()
    else:
        print(__doc__)
