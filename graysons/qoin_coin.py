#!/usr/bin/env python3
"""Qoin coins: an address drawn as a coin, and read back from a picture of one.

    python3 qoin_coin.py <address or number address> [coin.svg] [--dark]

A coin carries what the number address carries (which kind of address, both
public keys and the 4-byte checksum) as 552 spots on 4 rings. It comes light
(bronze on gold) or dark (gold on near-black), and either reads the same way.

  * The spot in the middle and the ring around it let a reader find the coin at
    any size, anywhere in a picture.
  * The axis, a bar from the middle up to the rim, shows which way is up, so a
    coin reads at any angle, and mirrored.
  * Each spot sits just inside its ring for a 0 or just outside it for a 1.
    Bits run clockwise from the axis, inner ring first, XORed with a fixed
    pattern so the spots look evenly scattered.

Only primary addresses and subaddresses make coins. The checksum catches a
misread spot, so a damaged picture is refused, never read as a different
address. Graysons Wallet shows coins under Receive and reads them under Send.
Stdlib only.
"""
import hashlib
import math
import re
import sys
from pathlib import Path

import qoin_number

# Geometry, in units of a SIZE x SIZE picture with the coin's middle at (C, C).
SIZE = 1000
C = SIZE / 2
COIN_R, RIM_R = 480, 452            # the rim is a dark band from 452 out to 480
BULL = 32                           # middle spot radius; then light out to 64, dark ring out to 96
AXIS_FROM, AXIS_W = 118, 14         # the axis runs straight up from r=118 to the rim
RINGS = ((190, 86), (265, 121), (340, 155), (415, 190))   # (radius, spots): 552 spots, a bit each
TRACK = 16                          # a spot sits TRACK inside its ring (0) or outside it (1)
SPOT_R = 5.5
GAP = 34                            # arc kept clear around the axis in every ring
LIGHT = ("#3a2a06", "#f6dc8f", "#ffffff")   # ink, face, paper: dark bronze on gold
DARK = ("#f2c14e", "#15181b", "#1e2226")    # gold on near-black, a dark coin (paper = Graysons' dark card)

HEADER = 0x10                       # version 1 in the high nibble, kind in the low one
KINDS = {9999: 0, 29997: 1}         # primary address, subaddress
PAYLOAD = 1 + 64 + 4                # header, spend + view keys, checksum: 69 bytes = 552 bits
_MASK = b"".join(hashlib.sha256(b"qoin coin %d" % i).digest() for i in range(3))


class CoinError(ValueError):
    pass


def _slots():
    """(radius, angle clockwise from the axis) of every spot, in bit order."""
    out = []
    for r, n in RINGS:
        gap = GAP / r
        step = (2 * math.pi - gap) / n
        out += [(r, gap / 2 + (i + 0.5) * step) for i in range(n)]
    return out


SLOTS = _slots()
assert len(SLOTS) == 8 * PAYLOAD


# ---------------------------------------------------------------------------
def bits(address: str) -> list:
    """The 552 bits a coin shows for an address (usual or number form)."""
    prefix, body, check = qoin_number.unpack(qoin_number.as_address(address))
    if prefix not in KINDS:
        raise CoinError("Coins are for primary addresses and subaddresses")
    data = bytes(a ^ b for a, b in zip(bytes([HEADER | KINDS[prefix]]) + body + check, _MASK))
    return [(byte >> (7 - i)) & 1 for byte in data for i in range(8)]


def _address(spots: list):
    """The address 552 bits spell, or None if they don't make one (a misread spot)."""
    data = bytes(sum(b << (7 - i) for i, b in enumerate(spots[8 * n:8 * n + 8])) ^ _MASK[n]
                 for n in range(PAYLOAD))
    prefix = {v: k for k, v in KINDS.items()}.get(data[0] ^ HEADER)
    if prefix is None:
        return None
    try:
        return qoin_number.pack(prefix, data[1:65], data[65:])
    except qoin_number.NumberError:
        return None


def _shapes(spots: list, dark=False) -> list:
    """What a coin is drawn from, painted in order: ("rect", x, y, w, h, colour),
    ("disk", x, y, r, colour) and ("spot", x, y, r, colour)."""
    ink, face, paper = DARK if dark else LIGHT
    out = [("rect", 0, 0, SIZE, SIZE, paper), ("disk", C, C, COIN_R, ink), ("disk", C, C, RIM_R, face),
           ("rect", C - AXIS_W / 2, C - RIM_R, AXIS_W, RIM_R - AXIS_FROM, ink),
           ("disk", C, C, 3 * BULL, ink), ("disk", C, C, 2 * BULL, face), ("disk", C, C, BULL, ink)]
    for (r, a), bit in zip(SLOTS, spots):
        r += TRACK if bit else -TRACK
        out.append(("spot", C + r * math.sin(a), C - r * math.cos(a), SPOT_R, ink))
    return out


def shapes(address: str, dark=False) -> list:
    return _shapes(bits(address), dark)


def svg(address: str, dark=False) -> str:
    """The coin for an address (usual or number form), as an SVG picture. dark: gold on near-black."""
    address = qoin_number.as_address(address)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">'
           f"<title>Qoin coin {address}</title>"]
    spots = []
    for kind, *v in shapes(address, dark):
        if kind == "rect":
            out.append('<rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>' % tuple(v))
        elif kind == "disk":
            out.append('<circle cx="%g" cy="%g" r="%g" fill="%s"/>' % tuple(v))
        else:
            spots.append('<circle cx="%.1f" cy="%.1f" r="%g"/>' % tuple(v[:3]))
    out.append(f'<g fill="{(DARK if dark else LIGHT)[0]}">' + "".join(spots) + "</g></svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# Reading a coin from a picture: 8-bit greyscale, row by row.
class _Picture:
    def __init__(self, gray, width, height):
        self.g, self.w, self.h = gray, width, height
        hist = [gray.count(v) for v in range(256)]
        self.thr = _otsu(hist)
        self.dark_table = bytes(1 if v <= self.thr else 0 for v in range(256))

    def at(self, x, y):
        """Grey level at (x, y), between pixels too. Outside the picture reads as white."""
        if not (0 <= x < self.w - 1 and 0 <= y < self.h - 1):
            return 255.0
        x0, y0 = int(x), int(y)
        fx, fy = x - x0, y - y0
        g, i, w = self.g, y0 * self.w + x0, self.w
        top = g[i] + (g[i + 1] - g[i]) * fx
        return top + (g[i + w] + (g[i + w + 1] - g[i + w]) * fx - top) * fy

    def dark(self, x, y):
        xi, yi = int(x + 0.5), int(y + 0.5)
        return 0 <= xi < self.w and 0 <= yi < self.h and self.g[yi * self.w + xi] <= self.thr


def _otsu(hist):
    """The grey level that best splits the picture into dark and light."""
    total = sum(hist)
    everything = sum(v * n for v, n in enumerate(hist))
    best, thr, n0, s0 = -1.0, 127, 0, 0
    for t in range(255):
        n0 += hist[t]
        s0 += t * hist[t]
        if n0 == 0 or n0 == total:
            continue
        m0, m1 = s0 / n0, (everything - s0) / (total - n0)
        between = n0 * (total - n0) * (m0 - m1) ** 2
        if between > best:
            best, thr = between, t
    return thr


_RUNS = re.compile(rb"\x00+|\x01+")


def _ratios_ok(lens, unit):
    """Dark, light, dark, light, dark in the middle spot's proportions 1:1:2:1:1."""
    return all(abs(n - k * unit) <= (0.75 if k == 2 else 0.5) * unit for n, k in zip(lens, (1, 1, 2, 1, 1)))


def _arm(pic, x, y, dx, dy, limit):
    """Going out from (x, y), inside the middle spot: the lengths of the dark, light and dark runs met."""
    lens, want, n = [], True, 0
    for i in range(int(limit)):
        if pic.dark(x + dx * i, y + dy * i) == want:
            n += 1
        else:
            lens.append(n)
            if len(lens) == 3:
                return lens
            want, n = not want, 1
    return None


def _across(pic, x, y, dx, dy, unit):
    """The middle-spot pattern through (x, y) along (dx, dy): its (centre x, centre y, unit), or None."""
    a = _arm(pic, x, y, dx, dy, 5 * unit)
    b = _arm(pic, x, y, -dx, -dy, 5 * unit)
    if not a or not b:
        return None
    lens = [a[2], a[1], a[0] + b[0] - 1, b[1], b[2]]
    u = sum(lens) / 6
    if u < 2 or not _ratios_ok(lens, u):
        return None
    shift = (a[0] - b[0]) / 2
    return x + dx * shift, y + dy * shift, u


def _centres(pic):
    """Places that look like a coin's middle spot, as (x, y, BULL in pixels), most often seen first."""
    w, g = pic.w, pic.g
    hits = []
    for y in range(pic.h):
        row = g[y * w:(y + 1) * w].translate(pic.dark_table)
        runs = [m.span() for m in _RUNS.finditer(row)]
        for j in range(len(runs) - 4):
            if not row[runs[j][0]]:
                continue
            lens = [end - start for start, end in runs[j:j + 5]]
            unit = sum(lens) / 6
            if unit < 4 or not _ratios_ok(lens, unit):      # under 4 px, a coin is too small to read anyway
                continue
            v = _across(pic, (runs[j + 2][0] + runs[j + 2][1] - 1) / 2, y, 0, 1, unit)
            hv = v and _across(pic, v[0], v[1], 1, 0, v[2])
            if hv:
                hits.append((hv[0], hv[1], (unit + v[2] + hv[2]) / 3))
    groups = []
    for x, y, u in hits:
        for grp in groups:
            n = grp[3]
            if (x - grp[0] / n) ** 2 + (y - grp[1] / n) ** 2 <= (grp[2] / n) ** 2:
                grp[0] += x
                grp[1] += y
                grp[2] += u
                grp[3] += 1
                break
        else:
            groups.append([x, y, u, 1])
    groups.sort(key=lambda grp: -grp[3])
    return [(x / n, y / n, u / n) for x, y, u, n in groups]


def _circle(pts):
    """Least-squares circle through points: (x, y, r)."""
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    suu = svv = suv = a = b = 0.0
    for x, y in pts:
        u, v = x - mx, y - my
        suu += u * u
        svv += v * v
        suv += u * v
        a += u * (u * u + v * v)
        b += v * (u * u + v * v)
    det = suu * svv - suv * suv
    if abs(det) < 1e-9:
        return None
    uc = 0.5 * (a * svv - b * suv) / det
    vc = 0.5 * (b * suu - a * suv) / det
    return mx + uc, my + vc, math.sqrt(uc * uc + vc * vc + (suu + svv) / n)


def _rim(pic, cx, cy, unit):
    """The coin's centre and size from its rim's outer edge: (x, y, pixels per unit), or None."""
    s = unit / BULL
    lo, hi, step = 0.88 * COIN_R * s, 1.06 * COIN_R * s, 0.5
    thin, thick = 0.5 * (COIN_R - RIM_R) * s, 2.5 * (COIN_R - RIM_R) * s   # the axis joins the rim: 2x
    pts = []
    for k in range(120):
        dx, dy = math.sin(k * math.pi / 60), -math.cos(k * math.pi / 60)
        edge, start, prev, r = None, None, 0.0, lo
        while r <= hi:
            v = pic.at(cx + dx * r, cy + dy * r)
            if v <= pic.thr:
                if start is None:
                    start = r
            elif start is not None:
                if thin <= r - start <= thick:      # a dark band as thick as the rim: its outer edge, between samples
                    edge = r - step + step * (pic.thr - prev) / (v - prev)
                start = None
            prev, r = v, r + step
        if edge is not None:
            pts.append((cx + dx * edge, cy + dy * edge))
    if len(pts) < 80:
        return None
    fit = _circle(pts)
    if fit:
        good = [p for p in pts if abs(math.hypot(p[0] - fit[0], p[1] - fit[1]) - fit[2]) <= max(1.5, 0.01 * fit[2])]
        fit = _circle(good) if len(good) >= 80 else None   # most of the rim, all on one circle
    if not fit or abs(fit[2] / (COIN_R * s) - 1) > 0.15:
        return None
    return fit[0], fit[1], fit[2] / COIN_R


def _axis(pic, cx, cy, s):
    """Which way the axis points, clockwise from straight up (radians), or None if there's no bar."""
    radii = [r * s for r in (130, 140, 150, 160)]    # clear of everything but the axis
    grey = []
    for k in range(720):
        dx, dy = math.sin(k * math.pi / 360), -math.cos(k * math.pi / 360)
        grey.append(sum(pic.at(cx + dx * r, cy + dy * r) for r in radii) / len(radii))
    peak = min(range(720), key=grey.__getitem__)
    face = sorted(grey)[360]
    if face < pic.thr + 20 or grey[peak] > pic.thr or face - grey[peak] < 40:   # light face, one dark bar
        return None
    half = (face + grey[peak]) / 2
    num = den = 0.0
    for off in range(-40, 41):
        v = half - grey[(peak + off) % 720]
        if v > 0:
            num += v * off
            den += v
    return (peak + num / den) * math.pi / 360


def _read_spots(pic, cx, cy, s, axis, mirror):
    """The address the spots spell, lined up on the axis; None if they don't spell one."""
    turn = -1 if mirror else 1

    def points(da, grow):
        for r, a in SLOTS:
            t = axis + turn * a + da
            dx, dy = math.sin(t), -math.cos(t)
            ri, ro = (r - TRACK) * s * grow, (r + TRACK) * s * grow
            yield cx + dx * ri, cy + dy * ri, cx + dx * ro, cy + dy * ro

    def contrast(da, grow):
        return sum(abs(pic.at(xi, yi) - pic.at(xo, yo)) for xi, yi, xo, yo in points(da, grow))

    # Line up to within a fraction of a spot: the right turn and size make the rings' in/out steps sharpest.
    _, da, grow = max((contrast(math.radians(0.15 * k), 1 + g), math.radians(0.15 * k), 1 + g)
                      for k in range(-4, 5) for g in (-0.008, 0.0, 0.008))
    q = 0.4 * SPOT_R * s

    def spot(x, y):
        return pic.at(x, y) + pic.at(x + q, y) + pic.at(x - q, y) + pic.at(x, y + q) + pic.at(x, y - q)

    return _address([1 if spot(xo, yo) < spot(xi, yi) else 0 for xi, yi, xo, yo in points(da, grow)])


_NEGATIVE = bytes(range(255, -1, -1))


def read(gray, width: int, height: int) -> str:
    """The address on a Qoin coin in a picture (8-bit greyscale, row by row). CoinError if there isn't one."""
    if width < 64 or height < 64 or len(gray) != width * height:
        raise CoinError("That picture is too small to hold a coin")
    gray = bytes(gray)
    found = False
    for g in (gray, gray.translate(_NEGATIVE)):     # a light coin, or a dark one: its negative is a light coin
        pic = _Picture(g, width, height)
        for cx, cy, unit in _centres(pic)[:12]:
            rim = _rim(pic, cx, cy, unit)
            axis = rim and _axis(pic, *rim)
            if axis is None:
                continue
            found = True
            for mirror in (False, True):
                address = _read_spots(pic, *rim, axis, mirror)
                if address:
                    return address
    if found:
        raise CoinError("Found a coin but couldn't read every spot. Try a sharper copy of the picture.")
    raise CoinError("No Qoin coin found in that picture")


def main():
    args = sys.argv[1:]
    dark = "--dark" in args
    args = [a for a in args if a != "--dark"]
    if not args or args[0] in ("-h", "--help"):
        sys.exit(__doc__)
    out = Path(args.pop()) if len(args) > 1 and args[-1].lower().endswith(".svg") else Path("qoin-coin.svg")
    try:
        picture = svg(" ".join(args), dark)
    except (qoin_number.NumberError, CoinError) as e:
        sys.exit(str(e))
    out.write_text(picture)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
