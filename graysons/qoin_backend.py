#!/usr/bin/env python3
"""Graysons Wallet + Frostoise miner backend for Qoin.

A local web app (stdlib only) that drives three Qoin binaries built from ~/frostnero:
  qoind                - the node; Frostoise mines through it
  graysons-wallet-rpc  - the wallet engine behind the Graysons Wallet UI
  graysons-wallet-cli  - the command-line wallet (not used here, same wallet files)

Serves the UI on 127.0.0.1 only. Every API call must carry the per-launch token that
is embedded in the page, so other websites open in the browser cannot drive the wallet.
"""
import argparse
import decimal
import hashlib
import http.client
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
QOIN_DIR = Path(os.environ.get("QOIN_DATA_DIR", Path.home() / ".qoin"))
WALLET_DIR = QOIN_DIR / "wallets"
SETTINGS_FILE = QOIN_DIR / "graysons.json"
MINER_CONF = QOIN_DIR / "frostoise.conf"

UI_PORT = 45680
DAEMON_RPC_PORT = 45671
WALLET_RPC_PORT = 45682

ATOMIC = 10 ** 11  # Qoin inherits Wownero's 11 decimal places
DEFAULT_SETTINGS = {
    "peers": [],            # "host:45670" entries passed as --add-peer
    "offline": False,       # run the node with no p2p at all (solo premine)
    "mining_threads": 1,
    "bin_dir": "",
}


# ---------------------------------------------------------------------------
# Keccak-256 (original padding, as used by CryptoNote - not SHA3-256) and sc_reduce32,
# used to check that a wallet's view key is derived from its spend key. The node's
# miner signs blocks assuming view = H(spend); a wallet that breaks that would have
# every block it finds rejected.
_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
        [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M64 = (1 << 64) - 1


def _keccak_f(a):
    for rc in _RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & _M64) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                r = _ROT[x][y]
                v = a[x][y]
                b[y][(2 * x + 3 * y) % 5] = ((v << r) | (v >> (64 - r))) & _M64 if r else v
        a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def keccak256(data: bytes) -> bytes:
    rate = 136
    msg = bytearray(data) + b"\x01"
    msg += b"\x00" * (-len(msg) % rate)
    msg[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(block[i * 8:i * 8 + 8], "little")
        a = _keccak_f(a)
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


_L = 2 ** 252 + 27742317777372353535851937790883648493


def view_key_from_spend(spend_hex: str) -> str:
    h = keccak256(bytes.fromhex(spend_hex))
    return (int.from_bytes(h, "little") % _L).to_bytes(32, "little").hex()


# ---------------------------------------------------------------------------
def fmt_qoin(atomic: int) -> str:
    s = decimal.Decimal(int(atomic)) / ATOMIC
    return f"{s:.11f}".rstrip("0").rstrip(".") if atomic else "0"


def parse_qoin(text: str) -> int:
    try:
        d = decimal.Decimal(str(text).strip())
    except decimal.InvalidOperation:
        raise ApiError("Amount is not a number")
    if d <= 0:
        raise ApiError("Amount must be greater than zero")
    atomic = d * ATOMIC
    if atomic != atomic.to_integral_value():
        raise ApiError("Qoin has at most 11 decimal places")
    return int(atomic)


class ApiError(Exception):
    pass


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        s.update(json.loads(SETTINGS_FILE.read_text()))
    except (OSError, ValueError):
        pass
    return s


def save_settings(s):
    QOIN_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))


def find_binary(name, settings):
    candidates = []
    if settings.get("bin_dir"):
        candidates.append(Path(settings["bin_dir"]).expanduser() / name)
    if os.environ.get("QOIN_BIN_DIR"):
        candidates.append(Path(os.environ["QOIN_BIN_DIR"]) / name)
    candidates.append(HERE.parent / "build" / "bin" / name)
    candidates.append(HERE / "bin" / name)
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    found = shutil.which(name)
    if found:
        return found
    raise ApiError(f"Can't find {name}. Build it first (see QOIN_BUILD.md), or set its folder under Node settings.")


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ---------------------------------------------------------------------------
class JsonRpc:
    """JSON-RPC client with its own HTTP digest auth. epee binds a digest nonce to the
    TCP connection, so the challenge and the authenticated retry must share one socket
    (urllib opens a new connection per request and always gets a stale-nonce 401)."""

    def __init__(self, port, login=None):
        self.port = port
        self.login = login

    def _digest(self, challenge, path):
        nonce = re.search(r'nonce="([^"]*)"', challenge).group(1)
        realm = re.search(r'realm="([^"]*)"', challenge).group(1)
        cnonce = secrets.token_hex(8)
        md5 = lambda x: hashlib.md5(x.encode()).hexdigest()
        ha1 = md5(f"{self.login[0]}:{realm}:{self.login[1]}")
        ha2 = md5(f"POST:{path}")
        resp = md5(f"{ha1}:{nonce}:00000001:{cnonce}:auth:{ha2}")
        return (f'Digest username="{self.login[0]}", realm="{realm}", nonce="{nonce}", uri="{path}", '
                f'algorithm=MD5, response="{resp}", qop=auth, nc=00000001, cnonce="{cnonce}"')

    def _post(self, path, payload, timeout):
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "Connection": "keep-alive"}
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request("POST", path, body, headers)
            r = conn.getresponse()
            data = r.read()
            if r.status == 401 and self.login:
                challenges = r.headers.get_all("WWW-authenticate") or []
                md5 = [c for c in challenges if "algorithm=MD5," in c] or challenges
                if not md5:
                    raise ApiError(f"RPC on port {self.port} wants a login it didn't describe")
                conn.request("POST", path, body, dict(headers, Authorization=self._digest(md5[0], path)))
                r = conn.getresponse()
                data = r.read()
            if r.status == 401:
                raise ApiError(f"RPC on port {self.port} rejected the login")
            if r.status != 200:
                raise ApiError(f"RPC on port {self.port} returned HTTP {r.status}")
            return json.loads(data)
        except (OSError, http.client.HTTPException, ValueError) as e:
            raise ApiError(f"RPC on port {self.port} unreachable: {e}")
        finally:
            conn.close()

    def call(self, method, params=None, timeout=60):
        out = self._post("/json_rpc", {"jsonrpc": "2.0", "id": "0", "method": method, "params": params or {}}, timeout)
        if "error" in out:
            raise ApiError(out["error"].get("message", str(out["error"])))
        return out.get("result", {})

    def other(self, path, params=None, timeout=15):
        return self._post(path, params or {}, timeout)


class Process:
    """A child process we started and are responsible for stopping."""

    def __init__(self, name):
        self.name = name
        self.proc = None
        self.log = QOIN_DIR / f"{name}.log"

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, argv):
        QOIN_DIR.mkdir(parents=True, exist_ok=True)
        out = open(QOIN_DIR / f"{self.name}.stdout.log", "ab")
        self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                     start_new_session=True)

    def stop(self, timeout=30):
        if not self.running:
            return
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


# ---------------------------------------------------------------------------
class Qoin:
    def __init__(self):
        QOIN_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(QOIN_DIR, 0o700)
        WALLET_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(WALLET_DIR, 0o700)
        # A stale miner config would put a spend key on disk; it is only ever needed at launch.
        MINER_CONF.unlink(missing_ok=True)
        self.settings = load_settings()
        self.lock = threading.RLock()
        self.daemon = Process("qoind")
        self.walletd = Process("graysons-wallet-rpc")
        self.daemon_key_fp = None       # fingerprint of the spend key the running node was given
        self.daemon_rpc = JsonRpc(DAEMON_RPC_PORT)
        self.wallet_login = ("graysons", secrets.token_hex(16))
        self.wallet_rpc = JsonRpc(WALLET_RPC_PORT, self.wallet_login)
        self.wallet_name = None
        self.pending_tx = {}
        self.last_error = ""

    # ---- node -------------------------------------------------------------
    def daemon_argv(self, with_key_conf):
        argv = [find_binary("qoind", self.settings), "--non-interactive",
                "--data-dir", str(QOIN_DIR / "chain"),
                "--log-file", str(QOIN_DIR / "qoind.log"),
                "--rpc-bind-ip", "127.0.0.1", "--rpc-bind-port", str(DAEMON_RPC_PORT)]
        if self.settings.get("offline"):
            argv.append("--offline")
        for p in self.settings.get("peers", []):
            if p.strip():
                argv += ["--add-peer", p.strip()]
        if with_key_conf:
            argv += ["--config-file", str(MINER_CONF)]
        return argv

    def start_node(self, spend_key=None):
        with self.lock:
            if self.daemon.running:
                return
            if port_open(DAEMON_RPC_PORT):
                if spend_key:
                    raise ApiError("A Qoin node that Graysons didn't start is already running on port "
                                   f"{DAEMON_RPC_PORT}. Stop it so Frostoise can start one with your mining key.")
                return  # use the external node for wallet sync
            if spend_key:
                fd = os.open(MINER_CONF, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(f"spendkey={spend_key}\n")
            try:
                self.daemon.start(self.daemon_argv(bool(spend_key)))
                self.daemon_key_fp = hashlib.sha256(spend_key.encode()).hexdigest() if spend_key else None
                deadline = time.time() + 120
                while time.time() < deadline:
                    if not self.daemon.running:
                        raise ApiError(f"qoind exited during startup - see {QOIN_DIR / 'qoind.log'}")
                    try:
                        self.daemon_rpc.other("/get_height", timeout=3)
                        self.last_error = ""
                        return
                    except ApiError:
                        time.sleep(1)
                raise ApiError("qoind did not answer within 2 minutes")
            finally:
                # qoind has read its config by the time RPC answers (or has died); don't leave the key on disk.
                MINER_CONF.unlink(missing_ok=True)

    def stop_node(self):
        with self.lock:
            self.daemon.stop()
            self.daemon_key_fp = None

    def node_status(self):
        st = {"running": False, "managed": self.daemon.running, "has_mining_key": bool(self.daemon_key_fp)}
        try:
            info = self.daemon_rpc.call("get_info", timeout=4)
        except ApiError:
            return st
        st.update(running=True, height=info.get("height", 0), target_height=info.get("target_height", 0),
                  synced=info.get("synchronized", False), difficulty=info.get("difficulty", 0),
                  peers_in=info.get("incoming_connections_count", 0),
                  peers_out=info.get("outgoing_connections_count", 0),
                  offline=info.get("offline", False), version=info.get("version", ""))
        return st

    # ---- wallet engine ------------------------------------------------------
    def ensure_wallet_rpc(self):
        with self.lock:
            if self.walletd.running:
                return
            if port_open(WALLET_RPC_PORT):
                raise ApiError(f"Port {WALLET_RPC_PORT} is taken by another program; Graysons needs it for its wallet engine.")
            self.walletd.start([
                find_binary("graysons-wallet-rpc", self.settings),
                "--wallet-dir", str(WALLET_DIR),
                "--rpc-bind-ip", "127.0.0.1", "--rpc-bind-port", str(WALLET_RPC_PORT),
                "--rpc-login", f"{self.wallet_login[0]}:{self.wallet_login[1]}",
                "--daemon-address", f"127.0.0.1:{DAEMON_RPC_PORT}", "--trusted-daemon",
                "--log-file", str(QOIN_DIR / "graysons-wallet-rpc.log"),
            ])
            deadline = time.time() + 60
            while time.time() < deadline:
                if not self.walletd.running:
                    raise ApiError(f"graysons-wallet-rpc exited - see {QOIN_DIR / 'graysons-wallet-rpc.log'}")
                try:
                    self.wallet_rpc.call("get_version", timeout=3)
                    return
                except ApiError:
                    time.sleep(0.5)
            raise ApiError("graysons-wallet-rpc did not start")

    def list_wallets(self):
        return sorted(p.name[:-5] for p in WALLET_DIR.glob("*.keys"))

    @staticmethod
    def check_name(name):
        name = (name or "").strip()
        if not name or "/" in name or name.startswith(".") or len(name) > 64:
            raise ApiError("Pick a wallet name without slashes")
        return name

    def create_wallet(self, name, password):
        name = self.check_name(name)
        if (WALLET_DIR / f"{name}.keys").exists():
            raise ApiError("A wallet with that name already exists")
        self.ensure_wallet_rpc()
        self.close_wallet()
        self.wallet_rpc.call("create_wallet", {"filename": name, "password": password, "language": "English"})
        self.wallet_name = name
        return {"seed": self.wallet_rpc.call("query_key", {"key_type": "mnemonic"})["key"]}

    def restore_wallet(self, name, password, seed, height):
        name = self.check_name(name)
        if (WALLET_DIR / f"{name}.keys").exists():
            raise ApiError("A wallet with that name already exists")
        self.ensure_wallet_rpc()
        self.close_wallet()
        self.wallet_rpc.call("restore_deterministic_wallet", {
            "filename": name, "password": password, "seed": " ".join(seed.split()),
            "restore_height": int(height or 0), "language": "English", "autosave_current": True}, timeout=300)
        self.wallet_name = name
        return {}

    def open_wallet(self, name, password):
        name = self.check_name(name)
        self.ensure_wallet_rpc()
        self.close_wallet()
        try:
            self.wallet_rpc.call("open_wallet", {"filename": name, "password": password}, timeout=120)
        except ApiError as e:
            raise ApiError("Wrong password, or the wallet file couldn't be read" if "password" in str(e).lower()
                           or "failed to open" in str(e).lower() else str(e))
        self.wallet_name = name
        return {}

    def close_wallet(self):
        if self.wallet_name and self.walletd.running:
            if self.mining_status().get("active"):
                self.stop_mining()
            try:
                self.wallet_rpc.call("close_wallet", {"autosave_current": True})
            except ApiError:
                pass
        self.wallet_name = None
        self.pending_tx.clear()

    def need_wallet(self):
        if not self.wallet_name:
            raise ApiError("No wallet is open")

    def summary(self):
        self.need_wallet()
        bal = self.wallet_rpc.call("get_balance", {"account_index": 0})
        addr = self.wallet_rpc.call("get_address", {"account_index": 0})
        h = self.wallet_rpc.call("get_height")
        return {"name": self.wallet_name,
                "balance": fmt_qoin(bal["balance"]), "unlocked": fmt_qoin(bal["unlocked_balance"]),
                "blocks_to_unlock": bal.get("blocks_to_unlock", 0),
                "address": addr["address"],
                "addresses": [{"index": a["address_index"], "address": a["address"], "label": a.get("label", ""),
                               "used": a.get("used", False)} for a in addr["addresses"]],
                "wallet_height": h["height"]}

    def new_address(self, label):
        self.need_wallet()
        return self.wallet_rpc.call("create_address", {"account_index": 0, "label": label or ""})

    def history(self):
        self.need_wallet()
        r = self.wallet_rpc.call("get_transfers", {"in": True, "out": True, "pending": True, "failed": True,
                                                   "pool": True, "account_index": 0})
        rows = []
        for kind in ("in", "out", "pending", "failed", "pool"):
            for t in r.get(kind, []):
                rows.append({"kind": kind, "txid": t["txid"], "amount": fmt_qoin(t["amount"]),
                             "fee": fmt_qoin(t.get("fee", 0)), "height": t.get("height", 0),
                             "timestamp": t.get("timestamp", 0), "confirmations": t.get("confirmations", 0),
                             "coinbase": t.get("type") == "block" or t.get("subtype") == "block",
                             "address": t.get("address", "")})
        rows.sort(key=lambda x: (x["timestamp"] or 1e18), reverse=True)
        return {"rows": rows}

    def preview_transfer(self, address, amount, priority):
        self.need_wallet()
        address = (address or "").strip()
        v = self.wallet_rpc.call("validate_address", {"address": address})
        if not v.get("valid"):
            raise ApiError("That isn't a valid Qoin address")
        atomic = parse_qoin(amount)
        r = self.wallet_rpc.call("transfer", {"destinations": [{"address": address, "amount": atomic}],
                                              "account_index": 0, "priority": int(priority or 0),
                                              "do_not_relay": True, "get_tx_metadata": True}, timeout=180)
        pid = secrets.token_hex(8)
        self.pending_tx = {pid: r["tx_metadata"]}
        return {"id": pid, "amount": fmt_qoin(r["amount"]), "fee": fmt_qoin(r["fee"]),
                "total": fmt_qoin(r["amount"] + r["fee"]), "address": address}

    def confirm_transfer(self, pid):
        self.need_wallet()
        meta = self.pending_tx.pop(pid, None)
        if not meta:
            raise ApiError("That transfer expired - review it again")
        r = self.wallet_rpc.call("relay_tx", {"hex": meta}, timeout=120)
        self.wallet_rpc.call("store")
        return {"txid": r.get("tx_hash", "")}

    def reveal_seed(self):
        self.need_wallet()
        return {"seed": self.wallet_rpc.call("query_key", {"key_type": "mnemonic"})["key"]}

    # ---- Frostoise ----------------------------------------------------------
    def mining_status(self):
        st = {"active": False}
        try:
            r = self.daemon_rpc.other("/mining_status", timeout=4)
        except ApiError:
            return st
        st.update(active=r.get("active", False), speed=r.get("speed", 0), threads=r.get("threads_count", 0),
                  address=r.get("address", ""), block_reward=fmt_qoin(r.get("block_reward", 0)),
                  difficulty=r.get("difficulty", 0), block_target=r.get("block_target", 300))
        return st

    def start_mining(self, threads):
        self.need_wallet()
        threads = max(1, min(int(threads or 1), os.cpu_count() or 1))
        address = self.wallet_rpc.call("get_address", {"account_index": 0})["address"]
        spend = self.wallet_rpc.call("query_key", {"key_type": "spend_key"})["key"]
        view = self.wallet_rpc.call("query_key", {"key_type": "view_key"})["key"]
        if int(spend, 16) == 0:
            raise ApiError("This is a view-only wallet. Frostoise needs the spend key to sign blocks.")
        if view_key_from_spend(spend) != view:
            raise ApiError("This wallet's view key isn't derived from its spend key, so blocks it signs would be "
                           "rejected. Mine to a wallet created or restored from a seed.")
        fp = hashlib.sha256(spend.encode()).hexdigest()
        with self.lock:
            if self.daemon.running and self.daemon_key_fp != fp:
                self.stop_node()  # restart the node so it loads this wallet's signing key
            self.start_node(spend_key=spend)
        spend = None
        self.wallet_rpc.call("set_daemon", {"address": f"127.0.0.1:{DAEMON_RPC_PORT}", "trusted": True})
        r = self.daemon_rpc.other("/start_mining", {"miner_address": address, "threads_count": threads,
                                                    "do_background_mining": False, "ignore_battery": True})
        if r.get("status") != "OK":
            raise ApiError(f"Node refused to mine: {r.get('status')}")
        self.settings["mining_threads"] = threads
        save_settings(self.settings)
        return self.mining_status()

    def stop_mining(self):
        r = self.daemon_rpc.other("/stop_mining")
        if r.get("status") not in ("OK", None):
            raise ApiError(r.get("status"))
        return self.mining_status()

    # ---- whole-app state ------------------------------------------------------
    def state(self):
        node = self.node_status()
        return {"node": node, "node_error": "" if node["running"] else self.last_error, "wallet_open": bool(self.wallet_name), "wallet_name": self.wallet_name,
                "wallets": self.list_wallets(), "mining": self.mining_status() if node["running"] else {"active": False},
                "cpu_count": os.cpu_count() or 1, "settings": self.settings}

    def set_settings(self, new):
        s = dict(self.settings)
        if "peers" in new:
            s["peers"] = [p.strip() for p in new["peers"] if p.strip()]
        if "offline" in new:
            s["offline"] = bool(new["offline"])
        if "bin_dir" in new:
            s["bin_dir"] = str(new["bin_dir"]).strip()
        self.settings = s
        save_settings(s)
        return {"settings": s, "note": "Restart the node for peer/offline changes to apply."}

    def shutdown(self):
        try:
            self.close_wallet()
        except Exception:
            pass
        self.walletd.stop()
        self.daemon.stop(timeout=60)


# ---------------------------------------------------------------------------
TOKEN = secrets.token_urlsafe(24)
APP = None


class Handler(BaseHTTPRequestHandler):
    server_version = "Graysons"

    def log_message(self, *a):
        pass

    def _host_ok(self):
        # Blocks DNS-rebinding: only accept requests addressed to our own loopback origin.
        return self.headers.get("Host") in (f"127.0.0.1:{UI_PORT}", f"localhost:{UI_PORT}")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                         "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            html = (HERE / "ui.html").read_text().replace("__GRAYSONS_TOKEN__", TOKEN)
            return self._send(200, html.encode(), "text/html; charset=utf-8")
        if path == "/icon.svg":
            return self._send(200, (HERE / "icon.svg").read_bytes(), "image/svg+xml")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok() or not secrets.compare_digest(self.headers.get("X-Graysons-Token", ""), TOKEN):
            return self._send(403, {"error": "forbidden"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            args = json.loads(self.rfile.read(n) or b"{}")
            routes = {
                "/api/state": lambda: APP.state(),
                "/api/node/start": lambda: (APP.start_node(), APP.node_status())[1],
                "/api/node/stop": lambda: (APP.stop_node(), APP.node_status())[1],
                "/api/settings": lambda: APP.set_settings(args),
                "/api/wallet/create": lambda: APP.create_wallet(args.get("name"), args.get("password", "")),
                "/api/wallet/restore": lambda: APP.restore_wallet(args.get("name"), args.get("password", ""),
                                                                  args.get("seed", ""), args.get("height", 0)),
                "/api/wallet/open": lambda: APP.open_wallet(args.get("name"), args.get("password", "")),
                "/api/wallet/close": lambda: (APP.close_wallet(), {})[1],
                "/api/wallet/summary": lambda: APP.summary(),
                "/api/wallet/new_address": lambda: APP.new_address(args.get("label")),
                "/api/wallet/history": lambda: APP.history(),
                "/api/wallet/preview": lambda: APP.preview_transfer(args.get("address"), args.get("amount"),
                                                                    args.get("priority", 0)),
                "/api/wallet/confirm": lambda: APP.confirm_transfer(args.get("id")),
                "/api/wallet/seed": lambda: APP.reveal_seed(),
                "/api/mine/start": lambda: APP.start_mining(args.get("threads", 1)),
                "/api/mine/stop": lambda: APP.stop_mining(),
            }
            fn = routes.get(self.path)
            if not fn:
                return self._send(404, {"error": "unknown endpoint"})
            self._send(200, fn())
        except ApiError as e:
            self._send(400, {"error": str(e)})
        except Exception as e:  # keep the UI alive and tell the user what broke
            self._send(500, {"error": f"{type(e).__name__}: {e}"})


def already_running():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{UI_PORT}/", timeout=1) as r:
            return r.headers.get("Server", "").startswith("Graysons")
    except Exception:
        return False


def main():
    global APP
    ap = argparse.ArgumentParser(description="Graysons Wallet and Frostoise miner for Qoin")
    ap.add_argument("--page", choices=["wallet", "frostoise"], default="wallet")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    url = f"http://127.0.0.1:{UI_PORT}/" + ("#frostoise" if a.page == "frostoise" else "")
    if already_running():
        print(f"Already running - opening {url}")
        webbrowser.open(url)
        return
    APP = Qoin()
    srv = ThreadingHTTPServer(("127.0.0.1", UI_PORT), Handler)
    srv.daemon_threads = True

    def bye(*_):
        threading.Thread(target=srv.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, bye)
    signal.signal(signal.SIGTERM, bye)
    # Bring the node up in the background so the wallet can sync; mining restarts it with a key when asked.
    def boot():
        try:
            APP.start_node()
        except ApiError as e:
            APP.last_error = str(e)
            print(e, file=sys.stderr)
    threading.Thread(target=boot, daemon=True).start()
    print(f"{'Frostoise' if a.page == 'frostoise' else 'Graysons Wallet'} running at {url}  (Ctrl+C to quit)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    finally:
        print("Shutting down wallet engine and node...")
        APP.shutdown()


if __name__ == "__main__":
    main()
