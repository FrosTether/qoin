"""Tests for Qoin number addresses (qoin_number.py) and where Graysons and Qoinage take them.

    cd graysons && python3 -m unittest test_qoin_number -v

The addresses below were made by Qoin's own C++ encoder (src/common/base58.cpp) from
known keys, so these tests pin the real format. Standard library only.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["QOIN_DATA_DIR"] = tempfile.mkdtemp(prefix="qoin-test-")   # never touch the real ~/.qoin

import qoin_backend as qb    # noqa: E402
import qoin_number as qn     # noqa: E402
import qoinage               # noqa: E402

# keys = bytes 0..63 / 64..127, and 128..199 for the integrated address (keys + payment ID)
PRIMARY = "QyEdUS7VFgQ21UVT1p34Di3MPXQQ9NRfr4hJZMnUho7z63DbKAp3Aa87P8dGZ9NY2G8j3fDwUhuUQA4xhBKp3GvY1XzrBDWQw"
SUB = "W6BhUSZVi4KCb3t6RSHqtoDvxv3omdDLwFGsx1C6xao5GcnyxaSHxFDHxi1uxmdKhMKJd3sM6xh9VLeY5pjSJ4bd5kq4QR8MsB"
INTEGRATED = ("TXiAuhHw1xXPLN9jW6xoVuQgHBgtSJAx3S2CDeGmdYQBTN7Fbf6xurKUi2HZ3SJHJTW3wKWRmdekbXPrMTp6y2CjYjmPRC"
              "SJPes8VheetTPHY")
PRIMARY_NUM = ("9999000002061946625135347497050984236556070146478948992017284640941724174351674591322344786897"
               "635416865344625557867260005611080485006364138707661660351195541111413726688")
SUB_NUM = ("2999703365303086883400649936911372483162086068292649871410262480988024959368100497198926695630"
           "7638659289633729951550551578444595788869107847745958591862426497274273033702")
INTEGRATED_NUM = ("1999812415396592823691036168954692198852641194498063841069844882633162519428411691359748260357"
                  "78091508532334557107730348758812113480366752274701199642298912863497726407020331516871828643959")
MONERO = "44AFFq5kSiGBoZ4NMDwYtN18obc8AemS33DBLWs3H7otXft3XjrpDtQGv7SqSsaBYBb98uNbr2VBBEt7f2wfn3RVGQBEP3A"


def make_address(prefix, body):
    raw = qn._varint(prefix) + body
    return qn.b58encode(raw + qn.keccak256(raw)[:4])


# ---------------------------------------------------------------------------
class CodecTest(unittest.TestCase):
    def test_keccak(self):
        self.assertEqual(qn.keccak256(b"").hex(), "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(qn.keccak256(b"abc").hex(), "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45")

    def test_known_addresses(self):
        for address, number, prefix in ((PRIMARY, PRIMARY_NUM, "9999"), (SUB, SUB_NUM, "29997"),
                                        (INTEGRATED, INTEGRATED_NUM, "19998")):
            self.assertEqual(qn.to_number(address), number)
            self.assertEqual(qn.from_number(number), address)
            self.assertTrue(number.startswith(prefix))
        self.assertEqual([len(PRIMARY_NUM), len(SUB_NUM), len(INTEGRATED_NUM)], [169, 170, 189])
        self.assertEqual(make_address(9999, bytes(range(64))), PRIMARY)

    def test_round_trip(self):
        rnd = random.Random(1991)
        for prefix, size in qn.BODY_BYTES.items():
            bodies = [bytes(size), b"\xff" * size, b"\x00" * 9 + b"\x01" * (size - 9)]
            bodies += [bytes(rnd.randrange(256) for _ in range(size)) for _ in range(40)]
            for body in bodies:
                address = make_address(prefix, body)
                number = qn.to_number(address)
                self.assertEqual(len(number), len(str(prefix)) + qn._width(size) + qn.CHECK_DIGITS)
                self.assertTrue(number.isdigit())
                self.assertEqual(qn.from_number(number), address)
                self.assertEqual(qn.from_number(qn.group(number)), address)

    def test_group(self):
        g = qn.group(PRIMARY_NUM)
        blocks = g.split(" ")
        self.assertEqual(blocks[:3], ["9999", "00000", "20619"])
        self.assertEqual((len(blocks), {len(b) for b in blocks[1:]}), (34, {5}))
        self.assertEqual(qn.group(SUB_NUM).split(" ")[0], "29997")
        self.assertEqual(g.replace(" ", ""), PRIMARY_NUM)

    def test_spaces_dashes_and_line_breaks_are_fine(self):
        g = qn.group(PRIMARY_NUM)
        for text in (g, g.replace(" ", "-"), g.replace(" ", "\n"), "  " + PRIMARY_NUM + "\n", g.replace(" ", " ")):
            self.assertEqual(qn.from_number(text), PRIMARY)

    def test_every_mistyped_digit_is_caught(self):
        for number in (PRIMARY_NUM, SUB_NUM):
            for i, d in enumerate(number):
                with self.assertRaises(qn.NumberError):
                    qn.from_number(number[:i] + str((int(d) + 1) % 10) + number[i + 1:])

    def test_swapped_digits_are_caught(self):
        for i in range(len(PRIMARY_NUM) - 1):
            a, b = PRIMARY_NUM[i], PRIMARY_NUM[i + 1]
            if a != b:
                with self.assertRaises(qn.NumberError):
                    qn.from_number(PRIMARY_NUM[:i] + b + a + PRIMARY_NUM[i + 2:])

    def test_wrong_length_says_what_it_expects(self):
        for text in (PRIMARY_NUM[:-1], PRIMARY_NUM + "7", "12", "8888" + PRIMARY_NUM[4:]):
            with self.assertRaisesRegex(qn.NumberError, "starts with 9999 and has 169 digits"):
                qn.from_number(text)

    def test_out_of_range_digits(self):
        with self.assertRaisesRegex(qn.NumberError, "typo"):
            qn.from_number("9999" + "9" * 155 + PRIMARY_NUM[-10:])
        with self.assertRaisesRegex(qn.NumberError, "typo"):
            qn.from_number(PRIMARY_NUM[:-10] + "9999999999")

    def test_only_ascii_digits(self):
        arabic = PRIMARY_NUM.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
        self.assertFalse(qn.is_number(arabic))
        with self.assertRaises(qn.NumberError):
            qn.from_number(arabic)
        with self.assertRaises(qn.NumberError):
            qn.from_number("9999 abc")

    def test_to_number_refuses_what_isnt_a_qoin_address(self):
        bad_char = PRIMARY[:40] + ("A" if PRIMARY[40] != "A" else "B") + PRIMARY[41:]
        for text in (MONERO, bad_char, PRIMARY[:-1], "hello", "", "0" * 97):
            with self.assertRaisesRegex(qn.NumberError, "isn't a Qoin address"):
                qn.to_number(text)

    def test_as_address(self):
        self.assertEqual(qn.as_address(PRIMARY_NUM), PRIMARY)
        self.assertEqual(qn.as_address(" " + qn.group(SUB_NUM) + " "), SUB)
        self.assertEqual(qn.as_address("  " + PRIMARY + "\n"), PRIMARY)
        self.assertEqual(qn.as_address("not an address"), "not an address")   # left for the wallet engine
        self.assertEqual(qn.as_address(None), "")
        with self.assertRaises(qn.NumberError):
            qn.as_address(PRIMARY_NUM[:-1] + "0")

    def test_command_line(self):
        run = lambda *args: subprocess.run([sys.executable, str(HERE / "qoin_number.py"), *args],
                                           capture_output=True, text=True, timeout=30)
        r = run(PRIMARY)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, qn.group(PRIMARY_NUM)))
        r = run(*qn.group(PRIMARY_NUM).split(" "))              # pasted without quotes
        self.assertEqual((r.returncode, r.stdout.strip()), (0, PRIMARY))
        r = run(PRIMARY_NUM[:-1] + "0")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("typo", r.stderr)


# ---------------------------------------------------------------------------
class WalletRpc:
    """Stands in for graysons-wallet-rpc, and judges addresses the way the real one does."""

    def __init__(self):
        self.calls = []

    def call(self, method, params=None, timeout=60):
        self.calls.append((method, params))
        if method == "validate_address":
            try:
                n = qn.to_number(params["address"])
            except qn.NumberError:
                return {"valid": False}
            return {"valid": True, "subaddress": n.startswith("29997"), "integrated": n.startswith("19998")}
        if method == "get_balance":
            return {"balance": 13370 * qb.ATOMIC, "unlocked_balance": 13370 * qb.ATOMIC, "blocks_to_unlock": 0}
        if method == "get_address":
            return {"address": PRIMARY,
                    "addresses": [{"address_index": 0, "address": PRIMARY, "label": "Primary account", "used": True},
                                  {"address_index": 1, "address": SUB, "label": "shop", "used": False}]}
        if method == "get_height":
            return {"height": 42}
        if method == "transfer":
            amount = sum(d["amount"] for d in params["destinations"])
            return {"amount": amount, "fee": 10 ** 8, "tx_metadata": "meta", "tx_hash": "tx1"}
        raise AssertionError(f"unexpected RPC {method}")

    def sent_to(self):
        return [d["address"] for m, p in self.calls if m == "transfer" for d in p["destinations"]]


class GraysonsTest(unittest.TestCase):
    def setUp(self):
        self.app = qb.Qoin()
        self.app.settings = dict(qb.DEFAULT_SETTINGS)
        self.app.wallet_rpc = WalletRpc()
        self.app.wallet_name = "test"

    def test_summary_shows_number_addresses(self):
        s = self.app.summary()
        self.assertEqual(s["number"], qn.group(PRIMARY_NUM))
        self.assertEqual([a["number"] for a in s["addresses"]], [qn.group(PRIMARY_NUM), qn.group(SUB_NUM)])

    def test_send_to_a_number_address(self):
        r = self.app.preview_transfer(qn.group(SUB_NUM), "1.5", 0)
        self.assertEqual(self.app.wallet_rpc.sent_to(), [SUB])
        self.assertEqual((r["address"], r["number"], r["amount"]), (SUB, qn.group(SUB_NUM), "1.5"))

    def test_send_to_a_usual_address_as_before(self):
        r = self.app.preview_transfer("  " + PRIMARY + " ", "2", 0)
        self.assertEqual(self.app.wallet_rpc.sent_to(), [PRIMARY])
        self.assertEqual((r["address"], r["number"]), (PRIMARY, qn.group(PRIMARY_NUM)))

    def test_mistyped_number_sends_nothing(self):
        with self.assertRaisesRegex(qb.ApiError, "typo"):
            self.app.preview_transfer(PRIMARY_NUM[:-1] + "0", "1", 0)
        self.assertEqual(self.app.wallet_rpc.calls, [])

    def test_number_address_helper(self):
        self.assertEqual(qb.number_address(PRIMARY), qn.group(PRIMARY_NUM))
        self.assertEqual(qb.number_address(MONERO), "")


class QoinageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = 1000.0
        self.q = qoinage.Qoinage(qoinage.Vault(WalletRpc()), qoinage.Book(Path(self.tmp.name) / "ledger.jsonl"),
                                 clock=lambda: self.t, wall=lambda: 1_790_000_000.0 + self.t)

    def tearDown(self):
        self.tmp.cleanup()

    def listen(self, address, ip="10.0.0.1"):
        sid = self.q.start(address, ip)["session"]
        for _ in range(self.q.seconds // qoinage.BEAT_EVERY_S):
            self.t += qoinage.BEAT_EVERY_S
            self.q.beat(sid)
        return self.q.claim(sid)

    def test_listen_with_a_number_address(self):
        r = self.listen(qn.group(PRIMARY_NUM))
        self.assertEqual(self.q.book.get(r["id"])["address"], PRIMARY)   # the ledger keeps the usual form

    def test_both_forms_share_one_daily_limit(self):
        self.listen(PRIMARY_NUM)
        with self.assertRaisesRegex(qb.ApiError, "already earned today"):
            self.q.start(PRIMARY, "10.0.0.2")
        with self.assertRaisesRegex(qb.ApiError, "already earned today"):
            self.q.start(qn.group(PRIMARY_NUM), "10.0.0.3")

    def test_mistyped_or_subaddress_numbers_are_refused(self):
        with self.assertRaisesRegex(qb.ApiError, "typo"):
            self.q.start(PRIMARY_NUM[:-1] + "0", "10.0.0.1")
        with self.assertRaisesRegex(qb.ApiError, "starts with 9999"):
            self.q.start("1234", "10.0.0.1")
        with self.assertRaisesRegex(qb.ApiError, "primary address"):
            self.q.start(SUB_NUM, "10.0.0.1")


if __name__ == "__main__":
    unittest.main()
