"""Tests for Qoin coins (qoin_coin.py): drawing an address as a coin and reading it back.

    cd graysons && python3 -m unittest test_qoin_coin -v

The pictures here are painted from the same shapes the SVG is made of, turned,
shrunk, blurred and speckled the way a shared picture gets. Standard library only.
"""
import base64
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["QOIN_DATA_DIR"] = tempfile.mkdtemp(prefix="qoin-test-")   # never touch the real ~/.qoin

import qoin_backend as qb    # noqa: E402
import qoin_coin             # noqa: E402
import qoin_number as qn     # noqa: E402
from test_qoin_number import INTEGRATED, PRIMARY, PRIMARY_NUM, SUB   # noqa: E402


# ---------------------------------------------------------------------------
# A small painter: greyscale pictures of a coin, from qoin_coin's shapes.
def luma(colour):
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return round(0.299 * r + 0.587 * g + 0.114 * b)


def fill_disk(img, w, h, cx, cy, r, v):
    if r > 12:                          # big disks: whole-row spans
        for y in range(max(0, int(cy - r)), min(h, int(cy + r) + 1)):
            dy = y + 0.5 - cy
            if abs(dy) < r:
                half = math.sqrt(r * r - dy * dy)
                x0, x1 = max(0, round(cx - half)), min(w, round(cx + half))
                if x1 > x0:
                    img[y * w + x0:y * w + x1] = bytes([v]) * (x1 - x0)
        return
    for y in range(max(0, int(cy - r - 1)), min(h, int(cy + r + 2))):      # spots: soft edges
        for x in range(max(0, int(cx - r - 1)), min(w, int(cx + r + 2))):
            cover = r + 0.5 - math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if cover >= 1:
                img[y * w + x] = v
            elif cover > 0:
                img[y * w + x] = round(img[y * w + x] * (1 - cover) + v * cover)


def fill_polygon(img, w, h, pts, v):
    ys = [p[1] for p in pts]
    for y in range(max(0, int(min(ys))), min(h, int(max(ys)) + 1)):
        yc, xs = y + 0.5, []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                xs.append(x1 + (yc - y1) * (x2 - x1) / (y2 - y1))
        if len(xs) >= 2:
            x0, x1 = max(0, round(min(xs))), min(w, round(max(xs)))
            if x1 > x0:
                img[y * w + x0:y * w + x1] = bytes([v]) * (x1 - x0)


def paint(shapes, size=500, turn=0.0, mirror=False, canvas=None, at=(0, 0), paper=255):
    """The coin size px across, turned `turn` degrees clockwise, maybe mirrored, at `at` on a canvas."""
    w, h = canvas or (size, size)
    img = bytearray([paper]) * (w * h)
    k, c, s = size / qoin_coin.SIZE, math.cos(math.radians(turn)), math.sin(math.radians(turn))

    def place(x, y):
        dx, dy = (qoin_coin.C - x if mirror else x - qoin_coin.C), y - qoin_coin.C
        return at[0] + (qoin_coin.C + dx * c - dy * s) * k, at[1] + (qoin_coin.C + dx * s + dy * c) * k

    for kind, *v in shapes:
        if kind == "rect":
            x, y, rw, rh, colour = v
            fill_polygon(img, w, h, [place(x, y), place(x + rw, y), place(x + rw, y + rh), place(x, y + rh)],
                         luma(colour))
        else:
            x, y, r, colour = v
            fill_disk(img, w, h, *place(x, y), r * k, luma(colour))
    return img, w, h


def blur(img, w, h):
    out = bytearray(img)
    for y in range(h):
        r = img[y * w:(y + 1) * w]
        out[y * w + 1:(y + 1) * w - 1] = bytes((r[i - 1] + r[i] + r[i + 1]) // 3 for i in range(1, w - 1))
    rows = bytes(out)
    for x in range(w):
        col = rows[x::w]
        out[x + w:x + (h - 1) * w:w] = bytes((col[i - 1] + col[i] + col[i + 1]) // 3 for i in range(1, h - 1))
    return out


def speckle(img, amount, seed=1):
    rnd = random.Random(seed)
    return bytearray(min(255, max(0, v + rnd.randint(-amount, amount))) for v in img)


# ---------------------------------------------------------------------------
class CoinTest(unittest.TestCase):
    def reads(self, want, img, w, h):
        self.assertEqual(qoin_coin.read(img, w, h), want)

    def test_reads_back_what_it_draws(self):
        for address in (PRIMARY, SUB):
            self.reads(address, *paint(qoin_coin.shapes(address), 600))

    def test_any_angle_and_mirrored(self):
        shapes = qoin_coin.shapes(PRIMARY)
        for turn, mirror in ((37.3, False), (90, False), (200, True), (301.5, False)):
            self.reads(PRIMARY, *paint(shapes, 450, turn, mirror))

    def test_small_and_large(self):
        shapes = qoin_coin.shapes(PRIMARY)
        for size in (230, 340, 1000):
            self.reads(PRIMARY, *paint(shapes, size, 45))

    def test_dark_coin(self):
        self.reads(SUB, *paint(qoin_coin.shapes(SUB, dark=True), 420, 128))
        self.reads(PRIMARY, *paint(qoin_coin.shapes(PRIMARY, dark=True), 300, 301))

    def test_blurred_and_speckled(self):
        img, w, h = paint(qoin_coin.shapes(PRIMARY), 500, 23)
        self.reads(PRIMARY, speckle(blur(img, w, h), 30), w, h)

    def test_found_anywhere_in_a_bigger_picture(self):
        self.reads(SUB, *paint(qoin_coin.shapes(SUB), 520, 12, canvas=(1400, 900), at=(610, 190), paper=30))

    def test_a_misread_spot_is_refused_not_misread(self):
        rnd = random.Random(7)
        for _ in range(3):
            spots = qoin_coin.bits(PRIMARY)
            spots[rnd.randrange(len(spots))] ^= 1
            with self.assertRaisesRegex(qoin_coin.CoinError, "couldn't read every spot"):
                qoin_coin.read(*paint(qoin_coin._shapes(spots), 500))

    def test_no_coin(self):
        rnd = random.Random(3)
        for img, w, h in ((bytearray(rnd.randrange(256) for _ in range(400 * 400)), 400, 400),
                          (bytearray([255]) * (300 * 300), 300, 300)):
            with self.assertRaisesRegex(qoin_coin.CoinError, "No Qoin coin"):
                qoin_coin.read(img, w, h)
        with self.assertRaisesRegex(qoin_coin.CoinError, "too small"):
            qoin_coin.read(bytearray(40 * 40), 40, 40)

    def test_bits(self):
        blank = qn.pack(9999, bytes(64), qn.keccak256(qn._varint(9999) + bytes(64))[:4])
        for address in (PRIMARY, SUB, blank):
            b = qoin_coin.bits(address)
            self.assertEqual(len(b), 552)
            self.assertEqual(qoin_coin._address(b), address)
        self.assertTrue(200 < sum(qoin_coin.bits(blank)) < 352)     # all-zero keys still look scattered
        self.assertEqual(qoin_coin.bits(PRIMARY_NUM), qoin_coin.bits(PRIMARY))

    def test_svg(self):
        picture = qoin_coin.svg(PRIMARY)
        self.assertTrue(picture.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"'))
        self.assertIn(f"<title>Qoin coin {PRIMARY}</title>", picture)
        self.assertEqual(len(re.findall(r'<circle cx="[\d.]+" cy="[\d.]+" r="5.5"/>', picture)), 552)
        self.assertEqual(qoin_coin.svg(qn.group(PRIMARY_NUM)), picture)
        self.assertIn('fill="#f2c14e"', qoin_coin.svg(PRIMARY, dark=True))
        with self.assertRaisesRegex(qoin_coin.CoinError, "primary addresses and subaddresses"):
            qoin_coin.svg(INTEGRATED)
        with self.assertRaises(qn.NumberError):
            qoin_coin.svg("hello")

    def test_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "mine.svg"
            r = subprocess.run([sys.executable, str(HERE / "qoin_coin.py"), *qn.group(PRIMARY_NUM).split(), str(out),
                                "--dark"], capture_output=True, text=True, timeout=30)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, f"Wrote {out}"))
            self.assertEqual(out.read_text(), qoin_coin.svg(PRIMARY, dark=True))


class GraysonsCoinTest(unittest.TestCase):
    def setUp(self):
        self.app = qb.Qoin()

    def send(self, img, w, h):
        return self.app.read_coin(w, h, base64.b64encode(zlib.compress(bytes(img))).decode())

    def test_coin_picture_for_an_address(self):
        self.assertEqual(self.app.coin(PRIMARY)["svg"], qoin_coin.svg(PRIMARY))
        self.assertEqual(self.app.coin(qn.group(PRIMARY_NUM), dark=True)["svg"], qoin_coin.svg(PRIMARY, dark=True))
        with self.assertRaisesRegex(qb.ApiError, "primary addresses and subaddresses"):
            self.app.coin(INTEGRATED)

    def test_read_a_coin_picture(self):
        r = self.send(*paint(qoin_coin.shapes(SUB), 400, 77))
        self.assertEqual(r, {"address": SUB, "number": qb.number_address(SUB)})

    def test_bad_pictures(self):
        img, w, h = paint(qoin_coin.shapes(SUB), 300)
        for args in ((w, h, "not base64!"), (w, h + 1, base64.b64encode(zlib.compress(bytes(img))).decode()),
                     (5000, 10, ""), ("x", h, ""), (w, h, base64.b64encode(b"not deflated").decode())):
            with self.assertRaisesRegex(qb.ApiError, "couldn't open that picture"):
                self.app.read_coin(*args)
        with self.assertRaisesRegex(qb.ApiError, "No Qoin coin"):
            self.send(bytearray([255]) * (200 * 200), 200, 200)


if __name__ == "__main__":
    unittest.main()
