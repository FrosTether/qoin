#!/usr/bin/env python3
"""Qoinage - listen to five minutes of 741 Hz, earn 13.37 QOIN.

The Qoinage vault is a small web page plus a payout loop. Anyone with a Qoin
address opens the page, listens to a five-minute 741 Hz sine wave (credited to
Fat Productions), and earns 13.37 QOIN. Rewards are paid in batches from a wallet
you funded, such as the one that mined the block-1 premine.

    python3 qoinage.py --wallet vault                   # asks for the vault's password
    python3 qoinage.py --wallet vault --bind 0.0.0.0    # let other devices on your network in

It needs a Qoin node on 127.0.0.1:45671 (Graysons Wallet starts one) and runs its
own graysons-wallet-rpc on 127.0.0.1:45683 for the vault. Use a separate vault
wallet: one wallet file can't be open in Graysons and Qoinage at the same time.

Honest limits:
  * Qoinage doesn't mint. Coins only come from mining; this pays out of the vault
    until the vault is empty.
  * It checks that the listening page stayed open and kept checking in for the whole
    five minutes. It can't tell a person from a script, so each primary address earns
    once a day, each network a few times a day, and the vault has a daily cap.

Stdlib only. Ledger of every reward: ~/.qoin/qoinage/ledger.jsonl
"""
import argparse
import getpass
import json
import math
import os
import re
import secrets
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import qoin_backend as qb

HERE = Path(__file__).resolve().parent
BOOK_FILE = qb.QOIN_DIR / "qoinage" / "ledger.jsonl"
PORT = 45690
VAULT_RPC_PORT = 45683

BEAT_EVERY_S = 15            # the page checks in this often...
MAX_GAP_S = 45               # ...and may miss two check-ins in a row, not more
GRACE_S = 3                  # clock slack when the page claims at the end
SESSION_TTL_S = 900          # an unclaimed session lives this long past its listening time
MAX_SESSIONS_PER_IP = 3
MAX_STARTS_PER_IP_HOUR = 20
BATCH_MAX = 15               # destinations per payout transaction (16 outputs with change)
FEE_RESERVE = 5 * 10 ** 9    # 0.05 QOIN held back for network fees
ADDRESS_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{90,110}")


class VaultUnsure(qb.ApiError):
    """The wallet engine stopped answering mid-payout: the transfer may or may not have gone out."""


def wait_text(seconds):
    minutes = max(1, math.ceil(seconds / 60))
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if h else f"{m} min"


# ---------------------------------------------------------------------------
class Book:
    """Every reward Qoinage has promised and paid, as an append-only JSON-lines file.

    Events: earned (a listen finished), paying (a batch is about to go out), paid (it
    went out, with its txid), retry (it definitely didn't, so back in the queue), unsure
    (the wallet engine went quiet mid-send). A batch that was paying or unsure when
    Qoinage stopped is parked as "unknown" and never re-sent on its own: check the
    vault's history, then start with --requeue-unknown if it really didn't go out.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()    # claims and payouts write from different threads
        self.claims = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    self._apply(json.loads(line))
        for c in self.claims.values():
            if c["status"] == "paying":
                c["status"] = "unknown"

    def _apply(self, ev):
        kind = ev["event"]
        if kind == "earned":
            self.claims[ev["id"]] = {"id": ev["id"], "address": ev["address"], "amount": ev["amount"],
                                     "t": ev["t"], "status": "queued", "txid": ""}
            return
        status = {"paying": "paying", "paid": "paid", "retry": "queued", "unsure": "unknown"}[kind]
        for i in ev["ids"]:
            if i in self.claims:
                self.claims[i]["status"] = status
                if kind == "paid":
                    self.claims[i]["txid"] = ev["txid"]

    def _log(self, ev):
        with self.lock:
            with open(self.path, "a") as f:
                f.write(json.dumps(ev) + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._apply(ev)

    def earn(self, address, amount, now):
        cid = secrets.token_hex(8)
        self._log({"event": "earned", "id": cid, "address": address, "amount": amount, "t": now})
        return cid

    def mark(self, kind, ids, now, **extra):
        self._log(dict({"event": kind, "ids": list(ids), "t": now}, **extra))

    def since(self, t, address=None):
        with self.lock:
            return [c for c in self.claims.values() if c["t"] > t and (address is None or c["address"] == address)]

    def queued(self):
        with self.lock:
            return sorted((dict(c) for c in self.claims.values() if c["status"] == "queued"), key=lambda c: c["t"])

    def owed(self):
        """Promised but not yet sent - still sitting in the vault's balance."""
        with self.lock:
            return sum(c["amount"] for c in self.claims.values() if c["status"] in ("queued", "paying"))

    def unknown(self):
        with self.lock:
            return [dict(c) for c in self.claims.values() if c["status"] == "unknown"]

    def get(self, cid):
        with self.lock:
            c = self.claims.get(cid)
            return dict(c) if c else None


# ---------------------------------------------------------------------------
class Vault:
    """The funded wallet Qoinage pays from, behind its own graysons-wallet-rpc."""

    def __init__(self, rpc, proc=None):
        self.rpc = rpc
        self.proc = proc
        self.lock = threading.Lock()
        self._bal = None
        self._bal_t = -1e9

    @classmethod
    def launch(cls, wallet, password, daemon, port):
        if qb.port_open(port):
            raise qb.ApiError(f"Port {port} is already in use. Pick another with --rpc-port, "
                              "or use --attach if a vault wallet engine is already running there.")
        login = ("qoinage", secrets.token_hex(16))
        proc = qb.Process("qoinage-wallet-rpc")
        proc.start([qb.find_binary("graysons-wallet-rpc", qb.load_settings()),
                    "--wallet-dir", str(qb.WALLET_DIR),
                    "--rpc-bind-ip", "127.0.0.1", "--rpc-bind-port", str(port),
                    "--rpc-login", f"{login[0]}:{login[1]}",
                    "--daemon-address", daemon, "--trusted-daemon",
                    "--log-file", str(qb.QOIN_DIR / "qoinage-wallet-rpc.log")])
        rpc = qb.JsonRpc(port, login)
        deadline = time.time() + 60
        while True:
            if not proc.running:
                raise qb.ApiError(f"graysons-wallet-rpc exited - see {qb.QOIN_DIR / 'qoinage-wallet-rpc.log'}")
            try:
                rpc.call("get_version", timeout=3)
                break
            except qb.ApiError:
                if time.time() > deadline:
                    proc.stop()
                    raise qb.ApiError("graysons-wallet-rpc did not start")
                time.sleep(0.5)
        try:
            rpc.call("open_wallet", {"filename": wallet, "password": password}, timeout=120)
        except qb.ApiError as e:
            proc.stop()
            raise qb.ApiError(f"Couldn't open the vault wallet '{wallet}': {e}")
        return cls(rpc, proc)

    def balance(self, fresh=False):
        """(total, unlocked) in atomic units, or None if the wallet engine isn't answering."""
        with self.lock:
            if fresh or time.monotonic() - self._bal_t > 15:
                try:
                    b = self.rpc.call("get_balance", {"account_index": 0}, timeout=10)
                    self._bal = (int(b["balance"]), int(b["unlocked_balance"]))
                except (qb.ApiError, KeyError, ValueError, TypeError):
                    self._bal = None
                self._bal_t = time.monotonic()
            return self._bal

    def validate(self, address):
        return self.rpc.call("validate_address", {"address": address}, timeout=10)

    def address(self):
        return self.rpc.call("get_address", {"account_index": 0})["address"]

    def pay(self, dests):
        try:
            r = self.rpc.call("transfer", {"destinations": [{"address": a, "amount": n} for a, n in dests],
                                           "account_index": 0, "priority": 0}, timeout=180)
        except qb.ApiError as e:
            if str(e).startswith("RPC on port"):   # timeout, dropped connection, HTTP error
                raise VaultUnsure(str(e))
            raise                                   # the wallet said no: nothing was sent
        try:
            self.rpc.call("store", timeout=60)
        except qb.ApiError:
            pass
        with self.lock:
            self._bal_t = -1e9
        return r.get("tx_hash", ""), int(r.get("fee", 0))

    def close(self):
        if self.proc:
            try:
                self.rpc.call("close_wallet", {"autosave_current": True}, timeout=60)
            except qb.ApiError:
                pass
            self.proc.stop()


# ---------------------------------------------------------------------------
class Qoinage:
    def __init__(self, vault, book, reward=1337 * 10 ** 9, seconds=300, per_day=1, per_ip=5,
                 daily_cap=100, tone=741.0, pulse=0.0, credit="Fat Productions",
                 clock=time.monotonic, wall=time.time):
        self.vault, self.book = vault, book
        self.reward, self.seconds = int(reward), int(seconds)
        self.per_day, self.per_ip, self.daily_cap = per_day, per_ip, daily_cap
        self.tone, self.pulse, self.credit = tone, pulse, credit
        self.clock, self.wall = clock, wall
        self.lock = threading.RLock()        # sessions and counters
        self.claim_lock = threading.Lock()   # one claim at a time, so limits can't be raced
        self.pay_lock = threading.Lock()     # one payout at a time (claims don't wait for it)
        self.sessions = {}
        self.starts = {}                     # ip -> recent session start times
        self.ip_claims = {}                  # ip -> times it earned (memory only)
        self.wake = threading.Event()
        self.last_payout = ""

    # ---- listening --------------------------------------------------------------
    def status(self):
        now = self.wall()
        today = len(self.book.since(now - 86400))
        st = {"reward": qb.fmt_qoin(self.reward), "seconds": self.seconds, "tone": self.tone,
              "pulse": self.pulse, "credit": self.credit, "beat": BEAT_EVERY_S, "per_day": self.per_day,
              "today": today, "cap": self.daily_cap}
        bal = self.vault.balance()
        if bal is None:
            st.update(vault="offline", listens_left=0)
            return st
        left = max(0, (bal[0] - self.book.owed() - FEE_RESERVE) // self.reward)
        st.update(listens_left=int(left),
                  vault="resting" if today >= self.daily_cap else ("open" if left > 0 else "empty"))
        return st

    def _limits(self, address, ip, now):
        day = now - 86400
        mine = self.book.since(day, address)
        if len(mine) >= self.per_day:
            raise qb.ApiError("This address already earned today. Come back in "
                              f"{wait_text(min(c['t'] for c in mine) + 86400 - now)}.")
        everyone = self.book.since(day)
        if len(everyone) >= self.daily_cap:
            raise qb.ApiError(f"The vault has paid its {self.daily_cap} listens for today. Come back in "
                              f"{wait_text(min(c['t'] for c in everyone) + 86400 - now)}.")
        net = [t for t in self.ip_claims.get(ip, []) if t > day]
        if len(net) >= self.per_ip:
            raise qb.ApiError(f"This network has earned {self.per_ip} times today. Come back in "
                              f"{wait_text(min(net) + 86400 - now)}.")

    def _spare(self):
        bal = self.vault.balance()
        if bal is None:
            raise qb.ApiError("The vault is offline right now. Try again in a few minutes.")
        return bal[0] - self.book.owed() - FEE_RESERVE

    def _expire(self, t):
        for sid, s in list(self.sessions.items()):
            if t - s["start"] > self.seconds + SESSION_TTL_S:
                del self.sessions[sid]
        for ip in list(self.starts):
            self.starts[ip] = [x for x in self.starts[ip] if t - x < 3600]
            if not self.starts[ip]:
                del self.starts[ip]

    def start(self, address, ip):
        address = (address or "").strip()
        if not ADDRESS_RE.fullmatch(address):
            raise qb.ApiError("That doesn't look like a Qoin address")
        t, now = self.clock(), self.wall()
        with self.lock:
            self._expire(t)
            if len(self.starts.get(ip, [])) >= MAX_STARTS_PER_IP_HOUR:
                raise qb.ApiError("Too many listens started from here in the last hour. Try again later.")
            self._limits(address, ip, now)
        info = self.vault.validate(address)
        if not info.get("valid"):
            raise qb.ApiError("That isn't a valid Qoin address")
        if info.get("subaddress") or info.get("integrated"):
            raise qb.ApiError("Use your wallet's primary address, not a subaddress or integrated address")
        spare = self._spare()
        with self.lock:
            others = [sid for sid, s in self.sessions.items() if s["address"] == address]
            for sid in others:                       # starting again replaces your earlier listen
                del self.sessions[sid]
            running = sum(1 for s in self.sessions.values() if not s["done"])
            if spare < self.reward * (running + 1):
                raise qb.ApiError("The vault is empty right now." if spare < self.reward
                                  else "Every reward left in the vault is taken by people listening now. Try again soon.")
            if sum(1 for s in self.sessions.values() if s["ip"] == ip and not s["done"]) >= MAX_SESSIONS_PER_IP:
                raise qb.ApiError(f"{MAX_SESSIONS_PER_IP} listens are already running from here")
            sid = secrets.token_urlsafe(18)
            self.sessions[sid] = {"address": address, "ip": ip, "start": t, "beats": [], "done": False, "claim": ""}
            self.starts.setdefault(ip, []).append(t)
        return {"session": sid, "seconds": self.seconds, "tone": self.tone, "pulse": self.pulse,
                "beat": BEAT_EVERY_S, "reward": qb.fmt_qoin(self.reward)}

    def beat(self, sid):
        t = self.clock()
        with self.lock:
            s = self.sessions.get(sid or "")
            if not s or s["done"]:
                raise qb.ApiError("That listen has ended. Start again.")
            if len(s["beats"]) < 400:
                s["beats"].append(t)
            return {"left": max(0, math.ceil(self.seconds - (t - s["start"])))}

    def claim(self, sid):
        with self.claim_lock:
            t, now = self.clock(), self.wall()
            with self.lock:
                s = self.sessions.get(sid or "")
                if not s:
                    raise qb.ApiError("That listen has ended. Start again.")
                if s["done"]:
                    return {"status": "earned", "id": s["claim"], "reward": qb.fmt_qoin(self.reward)}
                elapsed = t - s["start"]
                if elapsed < self.seconds - GRACE_S:
                    return {"status": "early", "wait": math.ceil(self.seconds - elapsed)}
                marks = [s["start"]] + s["beats"] + [t]
                gap = max(b - a for a, b in zip(marks, marks[1:]))
                if gap > MAX_GAP_S:
                    del self.sessions[sid]
                    raise qb.ApiError(f"The page went quiet for {int(gap)} seconds, so this listen doesn't count. "
                                      "Keep it open and playing the whole time, then try again.")
                self._limits(s["address"], s["ip"], now)
            if self._spare() < self.reward:
                raise qb.ApiError("The vault ran out before you finished. Sorry - nothing was sent.")
            cid = self.book.earn(s["address"], self.reward, now)
            with self.lock:
                s["done"], s["claim"] = True, cid
                self.ip_claims.setdefault(s["ip"], []).append(now)
        self.wake.set()
        return {"status": "earned", "id": cid, "reward": qb.fmt_qoin(self.reward)}

    def payout(self, cid):
        c = self.book.get(cid or "")
        if not c:
            raise qb.ApiError("No such reward")
        return {"status": c["status"], "txid": c["txid"], "amount": qb.fmt_qoin(c["amount"])}

    # ---- paying -------------------------------------------------------------------
    def pay_queued(self):
        """Send what's waiting, up to 15 addresses per transaction. Returns what happened."""
        with self.pay_lock:
            batch = self.book.queued()[:BATCH_MAX]
            if not batch:
                return None
            total = sum(c["amount"] for c in batch)
            bal = self.vault.balance(fresh=True)
            if bal is None:
                return "vault offline"
            if bal[1] < total + FEE_RESERVE:
                # Change from the last payout stays locked for a few blocks; try again later.
                return f"waiting for {qb.fmt_qoin(total)} QOIN to unlock ({qb.fmt_qoin(bal[1])} spendable)"
            ids = [c["id"] for c in batch]
            now = self.wall()
            self.book.mark("paying", ids, now)
            try:
                txid, fee = self.vault.pay([(c["address"], c["amount"]) for c in batch])
            except VaultUnsure as e:
                self.book.mark("unsure", ids, now, error=str(e))
                return f"UNSURE whether {len(ids)} payouts went out ({e}). Check the vault history."
            except qb.ApiError as e:
                self.book.mark("retry", ids, now, error=str(e))
                return f"payout failed, will retry: {e}"
            self.book.mark("paid", ids, self.wall(), txid=txid, fee=fee)
            self.last_payout = txid
            return f"paid {len(ids)} x {qb.fmt_qoin(self.reward)} QOIN in {txid}"

    def payout_loop(self, every, stop):
        while not stop.is_set():
            try:
                r = self.pay_queued()
                if r:
                    print(time.strftime("%H:%M:%S"), r, flush=True)
            except Exception as e:  # keep paying later; say why now
                print(time.strftime("%H:%M:%S"), f"payout error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            self.wake.wait(every)
            self.wake.clear()


# ---------------------------------------------------------------------------
Q = None
CONF = {"port": PORT, "loopback": True, "trust_proxy": False}


class Handler(BaseHTTPRequestHandler):
    server_version = "Qoinage"

    def log_message(self, *a):
        pass

    def _ip(self):
        if CONF["trust_proxy"]:
            fwd = self.headers.get("X-Forwarded-For", "")
            if fwd.strip():
                return fwd.split(",")[0].strip()
        return self.client_address[0]

    def _host_ok(self):
        # On loopback, only answer our own origin (blocks DNS rebinding). Public binds take any Host.
        return not CONF["loopback"] or self.headers.get("Host") in (f"127.0.0.1:{CONF['port']}", f"localhost:{CONF['port']}")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                         "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        u = urlparse(self.path)
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (HERE / "qoinage.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/icon.svg":
                return self._send(200, (HERE / "icon.svg").read_bytes(), "image/svg+xml")
            if u.path == "/api/status":
                return self._send(200, Q.status())
            if u.path == "/api/payout":
                return self._send(200, Q.payout(parse_qs(u.query).get("id", [""])[0]))
        except qb.ApiError as e:
            return self._send(400, {"error": str(e)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._send(415, {"error": "send JSON"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > 4096:
                return self._send(413, {"error": "request too large"})
            args = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(args, dict):
                raise qb.ApiError("send a JSON object")
            routes = {
                "/api/start": lambda: Q.start(args.get("address"), self._ip()),
                "/api/beat": lambda: Q.beat(args.get("session")),
                "/api/claim": lambda: Q.claim(args.get("session")),
            }
            fn = routes.get(self.path)
            if not fn:
                return self._send(404, {"error": "unknown endpoint"})
            self._send(200, fn())
        except qb.ApiError as e:
            self._send(400, {"error": str(e)})
        except ValueError:
            self._send(400, {"error": "bad request"})
        except Exception as e:
            self._send(500, {"error": f"{type(e).__name__}: {e}"})


def main():
    global Q
    ap = argparse.ArgumentParser(description="Qoinage: listen to 741 Hz for five minutes, earn 13.37 QOIN.")
    ap.add_argument("--wallet", help="vault wallet name in ~/.qoin/wallets (Qoinage opens it in its own wallet engine)")
    ap.add_argument("--attach", action="store_true",
                    help="use a graysons-wallet-rpc already running on --rpc-port with the vault open "
                         "(set QOINAGE_RPC_LOGIN=user:pass if it has a login)")
    ap.add_argument("--rpc-port", type=int, default=VAULT_RPC_PORT, help="vault wallet engine port (default 45683)")
    ap.add_argument("--daemon", default=f"127.0.0.1:{qb.DAEMON_RPC_PORT}", help="Qoin node RPC (default 127.0.0.1:45671)")
    ap.add_argument("--bind", default="127.0.0.1", help="address for the listening page (0.0.0.0 = every network)")
    ap.add_argument("--port", type=int, default=PORT, help="port for the listening page (default 45690)")
    ap.add_argument("--reward", default="13.37", help="QOIN per listen (default 13.37)")
    ap.add_argument("--seconds", type=int, default=300, help="listening time (default 300)")
    ap.add_argument("--tone", type=float, default=741.0, help="tone in Hz (default 741)")
    ap.add_argument("--pulse", type=float, default=0.0, help="optional soft volume pulse in Hz, e.g. 7.83 (default: none, a pure sine)")
    ap.add_argument("--credit", default="Fat Productions", help="who the sine wave is credited to (default: Fat Productions)")
    ap.add_argument("--per-day", type=int, default=1, help="rewards per address per 24 h (default 1)")
    ap.add_argument("--per-ip", type=int, default=5, help="rewards per network per 24 h (default 5)")
    ap.add_argument("--daily-cap", type=int, default=100, help="rewards per 24 h for everyone together (default 100)")
    ap.add_argument("--payout-every", type=int, default=60, help="seconds between payout runs (default 60)")
    ap.add_argument("--trust-proxy", action="store_true", help="take the client IP from X-Forwarded-For (behind nginx/caddy)")
    ap.add_argument("--requeue-unknown", action="store_true",
                    help="put interrupted payouts back in the queue (only after checking they never went out)")
    ap.add_argument("--book", default=str(BOOK_FILE), help=argparse.SUPPRESS)
    a = ap.parse_args()

    try:
        reward = qb.parse_qoin(a.reward)
    except qb.ApiError as e:
        sys.exit(f"--reward: {e}")
    if a.seconds < 10:
        sys.exit("--seconds must be at least 10")
    if not 20 <= a.tone <= 20000 or not 0 <= a.pulse <= 40:
        sys.exit("--tone must be 20-20000 Hz and --pulse 0-40 Hz")
    a.credit = " ".join(a.credit.split())[:80]
    if min(a.per_day, a.per_ip, a.daily_cap) < 1 or a.payout_every < 5:
        sys.exit("limits must be at least 1, and --payout-every at least 5")

    book = Book(a.book)
    stuck = book.unknown()
    if stuck and a.requeue_unknown:
        book.mark("retry", [c["id"] for c in stuck], time.time())
        print(f"Put {len(stuck)} interrupted payouts back in the queue.")
    elif stuck:
        print(f"Note: {len(stuck)} payouts were interrupted mid-send and are on hold. Check the vault's history; "
              "if they never went out, restart with --requeue-unknown.", file=sys.stderr)

    try:
        if a.attach:
            login = os.environ.get("QOINAGE_RPC_LOGIN")
            vault = Vault(qb.JsonRpc(a.rpc_port, tuple(login.split(":", 1)) if login else None))
            vault.rpc.call("get_version", timeout=5)
        else:
            if not a.wallet:
                sys.exit("Name the vault wallet: --wallet <name>  (or --attach to an already-running wallet engine)")
            password = os.environ.get("QOINAGE_PASSWORD")
            if password is None:
                password = getpass.getpass(f"Password for vault wallet '{a.wallet}': ")
            vault = Vault.launch(a.wallet, password, a.daemon, a.rpc_port)
            password = None
        vault_address = vault.address()
    except qb.ApiError as e:
        sys.exit(str(e))

    Q = Qoinage(vault, book, reward=reward, seconds=a.seconds, per_day=a.per_day, per_ip=a.per_ip,
                daily_cap=a.daily_cap, tone=a.tone, pulse=a.pulse, credit=a.credit)
    CONF.update(port=a.port, loopback=a.bind in ("127.0.0.1", "localhost", "::1"), trust_proxy=a.trust_proxy)
    try:
        srv = ThreadingHTTPServer((a.bind, a.port), Handler)
    except OSError as e:
        vault.close()
        sys.exit(f"Can't listen on {a.bind}:{a.port}: {e}")
    srv.daemon_threads = True
    stop = threading.Event()

    def bye(*_):
        stop.set()
        Q.wake.set()
        threading.Thread(target=srv.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, bye)
    signal.signal(signal.SIGTERM, bye)
    threading.Thread(target=Q.payout_loop, args=(a.payout_every, stop), daemon=True).start()

    st = Q.status()
    host = "127.0.0.1" if CONF["loopback"] else a.bind
    print(f"Qoinage vault {vault_address[:12]}…{vault_address[-8:]}")
    print(f"  {st['reward']} QOIN per {a.seconds // 60}:{a.seconds % 60:02d} of {a.tone:g} Hz sine"
          + (f" (pulse {a.pulse:g} Hz)" if a.pulse else "") + (f" - {a.credit}" if a.credit else ""))
    print(f"  vault: {st['vault']}, about {st['listens_left']} listens left")
    print(f"  listening page: http://{host}:{a.port}/   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    finally:
        stop.set()
        print("Closing the vault…")
        vault.close()


if __name__ == "__main__":
    main()
