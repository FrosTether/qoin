"""Tests for Qoinage (listen and earn), humm.py and the Graysons HUMM lock.

    cd graysons && python3 -m unittest test_qoinage -v

No Qoin binaries needed: the wallet engine is replaced by a stand-in that answers
the same JSON-RPC calls (get_balance, validate_address, transfer, relay_tx...).
"""
import base64
import json
import math
import os
import random
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from array import array
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["QOIN_DATA_DIR"] = tempfile.mkdtemp(prefix="qoin-test-")   # never touch the real ~/.qoin

import humm                  # noqa: E402
import qoin_backend as qb    # noqa: E402
import qoinage               # noqa: E402

REWARD = 1337 * 10 ** 9      # 13.37 QOIN
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def addr(i):
    return "Qo" + B58[i % 58] + B58[(i // 58) % 58] + "x" * 93


class Clock:
    def __init__(self):
        self.t, self.w = 1000.0, 1_790_000_000.0

    def mono(self):
        return self.t

    def wall(self):
        return self.w

    def advance(self, s):
        self.t += s
        self.w += s


class VaultRpc:
    """Stands in for graysons-wallet-rpc with the vault wallet open."""

    def __init__(self, qoin=13370):
        self.balance = self.unlocked = qoin * qb.ATOMIC
        self.calls, self.fail, self.n = [], None, 0

    def call(self, method, params=None, timeout=60):
        self.calls.append((method, params))
        if method == "get_balance":
            return {"balance": self.balance, "unlocked_balance": self.unlocked}
        if method == "validate_address":
            a = params["address"]
            return {"valid": a.startswith("Qo"), "subaddress": a.startswith("Qos"), "integrated": False}
        if method == "transfer":
            if self.fail:
                raise self.fail
            self.n += 1
            amount = sum(d["amount"] for d in params["destinations"])
            self.balance -= amount + 10 ** 8
            self.unlocked = 0          # change comes back locked, like the real chain
            return {"tx_hash": f"tx{self.n}", "fee": 10 ** 8, "amount": amount}
        if method == "store":
            return {}
        if method == "get_address":
            return {"address": "Qovault"}
        raise AssertionError(f"unexpected RPC {method}")

    def transfers(self):
        return [p for m, p in self.calls if m == "transfer"]


def tone(hz, secs=3.0, rate=8000, amp=8000, harmonics=(1.0,), noise=0.0, seed=1):
    rnd = random.Random(seed)
    return [amp * sum(a * math.sin(2 * math.pi * hz * (k + 1) * i / rate) for k, a in enumerate(harmonics))
            + (rnd.gauss(0, noise) if noise else 0.0) for i in range(int(secs * rate))]


def pcm64(samples):
    a = array("h", (max(-32768, min(32767, int(s))) for s in samples))
    if sys.byteorder == "big":
        a.byteswap()
    return base64.b64encode(a.tobytes()).decode()


HUM = (1.0, 0.5, 0.3, 0.2, 0.1)


# ---------------------------------------------------------------------------
class HummTest(unittest.TestCase):
    def check(self, samples, rate=8000):
        return humm.analyze(samples, rate)["passed"]

    def test_f_sharp_in_every_octave_passes(self):
        for hz in (92.625, 185.25, 370.5, 741.0, 1482.0):
            self.assertTrue(self.check(tone(hz, harmonics=HUM if hz < 400 else (1.0,), noise=400)), hz)

    def test_within_a_quarter_tone_passes(self):
        self.assertTrue(self.check(tone(741 * 2 ** (-45 / 1200))))
        self.assertTrue(self.check(tone(741 * 2 ** (45 / 1200))))

    def test_other_notes_fail(self):
        for hz in (174.61, 196.0, 246.94, 700.0, 741 * 2 ** (70 / 1200)):
            self.assertFalse(self.check(tone(hz, harmonics=HUM, noise=400)), hz)

    def test_noise_and_silence_fail(self):
        rnd = random.Random(2)
        self.assertFalse(self.check([rnd.gauss(0, 5000) for _ in range(24000)]))
        r = humm.analyze([rnd.gauss(0, 20) for _ in range(24000)])
        self.assertFalse(r["passed"])
        self.assertIn("quiet", r["message"])

    def test_says_what_it_heard(self):
        r = humm.analyze(tone(196.0, harmonics=HUM, noise=300))
        self.assertEqual(r["note"], "G3")
        r = humm.analyze(tone(185.25, harmonics=HUM, noise=300))
        self.assertEqual(r["note"], "F#3")
        self.assertIn("Tuned", r["message"])

    def test_other_sample_rates(self):
        self.assertTrue(self.check(tone(741, rate=48000), rate=48000))
        self.assertTrue(self.check(tone(185.25, rate=44100, harmonics=HUM), rate=44100))

    def test_length_limits(self):
        with self.assertRaises(humm.HummError):
            humm.analyze(tone(741, secs=0.5))
        with self.assertRaises(humm.HummError):
            humm.analyze(tone(741, secs=7))

    def test_base64_roundtrip_and_garbage(self):
        self.assertTrue(humm.check_base64(pcm64(tone(370.5)), 8000)["passed"])
        with self.assertRaises(humm.HummError):
            humm.check_base64("not base64!!", 8000)
        with self.assertRaises(humm.HummError):
            humm.check_base64(base64.b64encode(b"\x01\x02\x03").decode(), 8000)
        with self.assertRaises(humm.HummError):
            humm.check_base64(pcm64(tone(741)), 99)


# ---------------------------------------------------------------------------
class QoinageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ledger.jsonl"
        self.rpc = VaultRpc()
        self.clock = Clock()
        self.q = self.make()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, **kw):
        kw.setdefault("reward", REWARD)
        return qoinage.Qoinage(qoinage.Vault(self.rpc), qoinage.Book(self.path),
                               clock=self.clock.mono, wall=self.clock.wall, **kw)

    def listen(self, address, ip="10.0.0.1", q=None, beats=True):
        q = q or self.q
        sid = q.start(address, ip)["session"]
        for _ in range(q.seconds // qoinage.BEAT_EVERY_S):
            self.clock.advance(qoinage.BEAT_EVERY_S)
            if beats:
                q.beat(sid)
        return sid

    def test_full_listen_earns_then_pays_13_37(self):
        r = self.q.claim(self.listen(addr(1)))
        self.assertEqual((r["status"], r["reward"]), ("earned", "13.37"))
        self.assertEqual(self.q.payout(r["id"])["status"], "queued")
        self.assertIn("paid 1 x 13.37 QOIN", self.q.pay_queued())
        (t,) = self.rpc.transfers()
        self.assertEqual(t["destinations"], [{"address": addr(1), "amount": 1_337_000_000_000}])
        p = self.q.payout(r["id"])
        self.assertEqual((p["status"], p["txid"], p["amount"]), ("paid", "tx1", "13.37"))

    def test_claiming_early_says_how_long_to_wait(self):
        sid = self.q.start(addr(1), "10.0.0.1")["session"]
        for _ in range(13):
            self.clock.advance(15)
            self.q.beat(sid)
        self.assertEqual(self.q.claim(sid), {"status": "early", "wait": 105})

    def test_page_that_went_quiet_earns_nothing(self):
        sid = self.listen(addr(1), beats=False)
        with self.assertRaisesRegex(qb.ApiError, "went quiet"):
            self.q.claim(sid)
        self.assertEqual(self.q.book.claims, {})

    def test_one_reward_per_address_per_day(self):
        self.q.claim(self.listen(addr(1)))
        with self.assertRaisesRegex(qb.ApiError, r"already earned today. Come back in 24 h 0 min"):
            self.q.start(addr(1), "10.0.0.2")
        self.clock.advance(86400)
        self.q.start(addr(1), "10.0.0.2")

    def test_daily_cap_for_everyone(self):
        q = self.make(daily_cap=2, per_ip=10)
        q.claim(self.listen(addr(1), q=q))
        q.claim(self.listen(addr(2), q=q))
        with self.assertRaisesRegex(qb.ApiError, "paid its 2 listens"):
            q.start(addr(3), "10.0.0.9")
        self.assertEqual(q.status()["vault"], "resting")

    def test_per_network_limit(self):
        q = self.make(per_ip=2)
        q.claim(self.listen(addr(1), q=q))
        q.claim(self.listen(addr(2), q=q))
        with self.assertRaisesRegex(qb.ApiError, "network has earned 2 times"):
            q.start(addr(3), "10.0.0.1")
        q.start(addr(3), "10.0.0.7")

    def test_primary_addresses_only(self):
        with self.assertRaisesRegex(qb.ApiError, "primary address"):
            self.q.start("Qos" + "s" * 95, "10.0.0.1")
        with self.assertRaisesRegex(qb.ApiError, "doesn't look like"):
            self.q.start("hello", "10.0.0.1")
        with self.assertRaisesRegex(qb.ApiError, "isn't a valid"):
            self.q.start("Zz" + "x" * 95, "10.0.0.1")

    def test_empty_vault_turns_listeners_away_before_they_listen(self):
        self.rpc.balance = self.rpc.unlocked = 13 * qb.ATOMIC
        with self.assertRaisesRegex(qb.ApiError, "empty"):
            self.q.start(addr(1), "10.0.0.1")
        self.assertEqual(self.q.status()["vault"], "empty")

    def test_last_rewards_are_held_for_people_listening(self):
        self.rpc.balance = self.rpc.unlocked = 2 * REWARD + qoinage.FEE_RESERVE
        self.q.start(addr(1), "10.0.0.1")
        self.q.start(addr(2), "10.0.0.2")
        with self.assertRaisesRegex(qb.ApiError, "taken by people listening"):
            self.q.start(addr(3), "10.0.0.3")

    def test_starting_again_replaces_the_old_listen(self):
        old = self.q.start(addr(1), "10.0.0.1")["session"]
        self.q.start(addr(1), "10.0.0.1")
        with self.assertRaisesRegex(qb.ApiError, "ended"):
            self.q.beat(old)

    def test_claim_twice_is_one_reward(self):
        sid = self.listen(addr(1))
        a, b = self.q.claim(sid), self.q.claim(sid)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(self.q.book.claims), 1)

    def test_waits_for_locked_change_then_pays(self):
        self.q.claim(self.listen(addr(1)))
        self.q.pay_queued()                     # vault change is now locked
        self.q.claim(self.listen(addr(2), ip="10.0.0.2"))
        self.assertIn("waiting for 13.37 QOIN to unlock", self.q.pay_queued())
        self.assertEqual(len(self.rpc.transfers()), 1)
        self.rpc.unlocked = self.rpc.balance
        self.assertIn("paid 1", self.q.pay_queued())

    def test_batches_of_fifteen(self):
        q = self.make(daily_cap=50, per_ip=50)
        for i in range(20):
            q.claim(self.listen(addr(i), q=q))
        self.assertIn("paid 15", q.pay_queued())
        self.rpc.unlocked = self.rpc.balance
        self.assertIn("paid 5", q.pay_queued())
        self.assertEqual([len(t["destinations"]) for t in self.rpc.transfers()], [15, 5])
        self.assertIsNone(q.pay_queued())

    def test_wallet_refusal_goes_back_in_the_queue(self):
        r = self.q.claim(self.listen(addr(1)))
        self.rpc.fail = qb.ApiError("not enough unlocked money")
        self.assertIn("will retry", self.q.pay_queued())
        self.assertEqual(self.q.payout(r["id"])["status"], "queued")
        self.rpc.fail = None
        self.assertIn("paid 1", self.q.pay_queued())

    def test_unsure_payout_is_never_resent(self):
        r = self.q.claim(self.listen(addr(1)))
        self.rpc.fail = qb.ApiError("RPC on port 45683 unreachable: timed out")
        self.assertIn("UNSURE", self.q.pay_queued())
        self.rpc.fail = None
        self.assertIsNone(self.q.pay_queued())
        self.assertEqual(self.q.payout(r["id"])["status"], "unknown")
        book = qoinage.Book(self.path)          # still parked after a restart
        self.assertEqual([c["id"] for c in book.unknown()], [r["id"]])

    def test_ledger_survives_restart_and_parks_half_sent_batches(self):
        r = self.q.claim(self.listen(addr(1)))
        self.q.pay_queued()
        r2 = self.q.claim(self.listen(addr(2), ip="10.0.0.2"))
        self.q.book.mark("paying", [r2["id"]], self.clock.wall())   # then the power went out
        book = qoinage.Book(self.path)
        self.assertEqual((book.claims[r["id"]]["status"], book.claims[r["id"]]["txid"]), ("paid", "tx1"))
        self.assertEqual(book.claims[r2["id"]]["status"], "unknown")
        q = qoinage.Qoinage(qoinage.Vault(self.rpc), book, reward=REWARD, clock=self.clock.mono, wall=self.clock.wall)
        with self.assertRaisesRegex(qb.ApiError, "already earned today"):
            q.start(addr(1), "10.0.0.5")

    def test_claims_do_not_wait_for_a_slow_payout(self):
        self.q.claim(self.listen(addr(1)))
        gate, real = threading.Event(), self.rpc.call

        def slow(method, params=None, timeout=60):
            if method == "transfer":
                gate.wait(5)                    # a transfer that takes a while to build
            return real(method, params, timeout)
        self.rpc.call = slow
        payout = threading.Thread(target=self.q.pay_queued)
        payout.start()
        time.sleep(0.2)
        sid = self.listen(addr(2), ip="10.0.0.2")
        t0 = time.monotonic()
        r = self.q.claim(sid)
        took = time.monotonic() - t0
        gate.set()
        payout.join(5)
        self.assertEqual(r["status"], "earned")
        self.assertLess(took, 1.0)
        self.assertEqual(self.q.payout(r["id"])["status"], "queued")

    def test_status_counts_listens_left(self):
        st = self.q.status()
        self.assertEqual((st["vault"], st["listens_left"], st["reward"], st["seconds"]), ("open", 999, "13.37", 300))
        self.assertEqual((st["tone"], st["pulse"], st["credit"]), (741.0, 0.0, "Fat Productions"))
        self.q.claim(self.listen(addr(1)))
        self.assertEqual((self.q.status()["listens_left"], self.q.status()["today"]), (998, 1))


# ---------------------------------------------------------------------------
class QoinageHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rpc = VaultRpc()
        qoinage.Q = qoinage.Qoinage(qoinage.Vault(cls.rpc), qoinage.Book(Path(cls.tmp.name) / "l.jsonl"), reward=REWARD)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), qoinage.Handler)
        cls.port = cls.srv.server_address[1]
        qoinage.CONF.update(port=cls.port, loopback=True, trust_proxy=False)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def req(self, path, body=None, ctype="application/json", host=None):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                   data=None if body is None else json.dumps(body).encode(),
                                   headers={"Content-Type": ctype, **({"Host": host} if host else {})})
        try:
            with urllib.request.urlopen(r, timeout=5) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_page_status_and_start(self):
        code, page = self.req("/")
        self.assertEqual(code, 200)
        self.assertIn(b"Earn", page)
        code, st = self.req("/api/status")
        self.assertEqual(json.loads(st)["reward"], "13.37")
        code, r = self.req("/api/start", {"address": addr(7)})
        self.assertEqual(code, 200)
        sid = json.loads(r)["session"]
        code, r = self.req("/api/beat", {"session": sid})
        self.assertEqual((code, json.loads(r)["left"]), (200, 300))
        code, r = self.req("/api/claim", {"session": sid})
        self.assertEqual(json.loads(r)["status"], "early")

    def test_refuses_foreign_hosts_and_non_json(self):
        self.assertEqual(self.req("/api/status", host="evil.example:80")[0], 403)
        self.assertEqual(self.req("/api/start", {"address": addr(8)}, ctype="text/plain")[0], 415)
        code, r = self.req("/api/start", {"address": "nope"})
        self.assertEqual((code, json.loads(r)["error"]), (400, "That doesn't look like a Qoin address"))


# ---------------------------------------------------------------------------
class WalletStub:
    def __init__(self):
        self.calls = []

    def call(self, method, params=None, timeout=60):
        self.calls.append(method)
        if method == "relay_tx":
            return {"tx_hash": "abc123"}
        if method == "store":
            return {}
        raise AssertionError(method)


class HummLockTest(unittest.TestCase):
    def setUp(self):
        self.app = qb.Qoin()
        self.app.settings = dict(qb.DEFAULT_SETTINGS)
        self.app.wallet_rpc = WalletStub()
        self.app.wallet_name = "test"
        self.good = pcm64(tone(185.25, harmonics=HUM, noise=300))
        self.bad = pcm64(tone(196.0, harmonics=HUM, noise=300))

    def send(self, pid="p1"):
        self.app.pending_tx[pid] = "meta-" + pid
        return self.app.confirm_transfer(pid)

    def test_lock_off_sends_as_before(self):
        self.assertEqual(self.send(), {"txid": "abc123"})

    def test_lock_on_needs_one_hum_per_send(self):
        self.app.set_humm_lock(True)
        with self.assertRaisesRegex(qb.ApiError, "HUMM lock is on"):
            self.send()
        self.assertIn("p1", self.app.pending_tx)            # the reviewed transfer is kept
        self.assertTrue(self.app.check_humm(self.good, 8000)["passed"])
        self.assertEqual(self.app.confirm_transfer("p1"), {"txid": "abc123"})
        with self.assertRaisesRegex(qb.ApiError, "HUMM lock is on"):
            self.send("p2")                                 # that hum is spent

    def test_wrong_note_does_not_unlock(self):
        self.app.set_humm_lock(True)
        self.assertFalse(self.app.check_humm(self.bad, 8000)["passed"])
        with self.assertRaisesRegex(qb.ApiError, "HUMM lock is on"):
            self.send()

    def test_old_hum_expires(self):
        self.app.set_humm_lock(True)
        self.app.check_humm(self.good, 8000)
        self.app.humm_until -= qb.HUMM_VALID_S + 1
        with self.assertRaisesRegex(qb.ApiError, "HUMM lock is on"):
            self.send()

    def test_turning_the_lock_off_takes_a_hum(self):
        self.app.set_humm_lock(True)
        with self.assertRaisesRegex(qb.ApiError, "HUMM 741 Hz first"):
            self.app.set_humm_lock(False)
        self.app.check_humm(self.good, 8000)
        self.assertEqual(self.app.set_humm_lock(False), {"humm_lock": False})
        self.assertFalse(qb.load_settings()["humm_lock"])

    def test_expired_review_does_not_eat_the_hum(self):
        self.app.set_humm_lock(True)
        self.app.check_humm(self.good, 8000)
        with self.assertRaisesRegex(qb.ApiError, "expired"):
            self.app.confirm_transfer("gone")
        self.assertEqual(self.send(), {"txid": "abc123"})

    def test_qoinage_url_setting(self):
        with self.assertRaises(qb.ApiError):
            self.app.set_settings({"qoinage_url": "javascript:alert(1)"})
        self.app.set_settings({"qoinage_url": "http://10.0.0.5:45690/"})
        self.assertEqual(self.app.settings["qoinage_url"], "http://10.0.0.5:45690")
        self.app.set_settings({"qoinage_url": ""})
        self.assertEqual(self.app.settings["qoinage_url"], "http://127.0.0.1:45690")

    def test_garbage_recording_is_an_error_not_a_crash(self):
        with self.assertRaises(qb.ApiError):
            self.app.check_humm("%%%", 8000)


if __name__ == "__main__":
    unittest.main()
