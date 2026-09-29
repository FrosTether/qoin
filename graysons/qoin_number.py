#!/usr/bin/env python3
"""Qoin number addresses: any Qoin address, written in digits only.

    python3 qoin_number.py <address>     # prints its number address
    python3 qoin_number.py <number>      # prints the usual address back

A number address holds exactly what the usual address holds, so it converts both
ways with no lookup, no registry and nobody to trust:

    9999 | 155 digits: spend key + view key | 10 digits: checksum     (169 digits)

It starts with the address prefix: 9999 for a primary address, 29997 for a
subaddress, 19998 for an integrated address (whose middle part is 174 digits,
because it also carries the payment ID). The last 10 digits are the same 4-byte
checksum the usual address ends with, so a mistyped digit is caught. It's long
because an address carries two 256-bit keys; digits spell them out in a way you
can read aloud or type on a phone keypad, with no upper and lower case to mix up.

Graysons Wallet shows your number address and takes one anywhere it takes an
address, and so does Qoinage. qoind and graysons-wallet-cli still take the usual
form: convert with this script. Stdlib only.
"""
import re
import sys

# address prefix -> bytes between the prefix and the checksum (prefixes: src/cryptonote_config.h)
BODY_BYTES = {
    9999: 64,       # primary address: spend + view public keys
    29997: 64,      # subaddress
    19998: 72,      # integrated address: the keys + an 8-byte payment ID
}
CHECK_DIGITS = 10   # the 4-byte checksum, 0 to 4294967295

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_BLOCK = [0, 2, 3, 5, 6, 7, 9, 10, 11]   # base58 characters for a block of 0-8 bytes
_NUMBER_RE = re.compile(r"[0-9][0-9\s-]*")    # digits, optionally grouped with spaces or dashes
TYPO = "That number address has a typo: its last 10 digits don't match the rest. Copy it again."


class NumberError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Keccak-256 (original padding, as used by CryptoNote - not SHA3-256): the address
# checksum, and Graysons' check that a wallet's view key comes from its spend key.
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


# ---------------------------------------------------------------------------
# CryptoNote base58: 8-byte blocks, each written as 11 characters (a shorter last block
# gets fewer), and a varint prefix. Same as src/common/base58.cpp.
def b58encode(raw: bytes) -> str:
    out = []
    for i in range(0, len(raw), 8):
        block = raw[i:i + 8]
        n, chars = int.from_bytes(block, "big"), []
        for _ in range(_B58_BLOCK[len(block)]):
            n, r = divmod(n, 58)
            chars.append(_B58[r])
        out.append("".join(reversed(chars)))
    return "".join(out)


def b58decode(text: str) -> bytes:
    out = bytearray()
    for i in range(0, len(text), 11):
        chunk = text[i:i + 11]
        if len(chunk) not in _B58_BLOCK:
            raise NumberError("not base58")
        size = _B58_BLOCK.index(len(chunk))
        n = 0
        for ch in chunk:
            d = _B58.find(ch)
            if d < 0:
                raise NumberError("not base58")
            n = n * 58 + d
        if n >> (8 * size):
            raise NumberError("not base58")
        out += n.to_bytes(size, "big")
    return bytes(out)


def _varint(n: int) -> bytes:
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def _width(size: int) -> int:
    """Digits needed to write any size-byte number: 155 for 64 bytes, 174 for 72."""
    return len(str(256 ** size - 1))


# ---------------------------------------------------------------------------
def unpack(address: str):
    """(prefix, body, checksum) of a usual Qoin address, with the checksum checked."""
    address = (address or "").strip()
    try:
        raw = b58decode(address)
    except NumberError:
        raise NumberError("That isn't a Qoin address") from None
    if len(raw) < 5 or keccak256(raw[:-4])[:4] != raw[-4:]:
        raise NumberError("That isn't a Qoin address")
    for prefix, size in BODY_BYTES.items():
        tag = _varint(prefix)
        if raw.startswith(tag) and len(raw) == len(tag) + size + 4:
            return prefix, raw[len(tag):-4], raw[-4:]
    raise NumberError("That isn't a Qoin address")


def pack(prefix: int, body: bytes, check: bytes) -> str:
    """The usual Qoin address for a prefix, body and checksum. NumberError if the checksum doesn't match."""
    raw = _varint(prefix) + body
    if keccak256(raw)[:4] != check:
        raise NumberError(TYPO)
    return b58encode(raw + check)


def to_number(address: str) -> str:
    """The number address (digits only) for a usual Qoin address."""
    prefix, body, check = unpack(address)
    return (f"{prefix}{int.from_bytes(body, 'big'):0{_width(len(body))}d}"
            f"{int.from_bytes(check, 'big'):0{CHECK_DIGITS}d}")


def _split(number: str):
    """(prefix, body size in bytes, digits) for a number address, or NumberError."""
    text = (number or "").strip()
    if not _NUMBER_RE.fullmatch(text):
        raise NumberError("A number address is digits only")
    digits = re.sub(r"[\s-]", "", text)
    for prefix, size in BODY_BYTES.items():
        p = str(prefix)
        if digits.startswith(p) and len(digits) == len(p) + _width(size) + CHECK_DIGITS:
            return prefix, size, digits
    raise NumberError(f"A Qoin number address starts with 9999 and has 169 digits (170 for a subaddress, "
                      f"which starts with 29997). This one has {len(digits)}.")


def from_number(number: str) -> str:
    """The usual Qoin address for a number address. Spaces and dashes between digits are fine."""
    prefix, size, digits = _split(number)
    p = len(str(prefix))
    body = int(digits[p:-CHECK_DIGITS])
    check = int(digits[-CHECK_DIGITS:])
    if body >> (8 * size) or check >> 32:
        raise NumberError(TYPO)
    return pack(prefix, body.to_bytes(size, "big"), check.to_bytes(4, "big"))


def group(number: str) -> str:
    """9999 01234 56789 ... : the prefix, then blocks of five, for reading and writing down."""
    prefix, _, digits = _split(number)
    p = len(str(prefix))
    return " ".join([digits[:p]] + [digits[i:i + 5] for i in range(p, len(digits), 5)])


def is_number(text: str) -> bool:
    return bool(_NUMBER_RE.fullmatch((text or "").strip()))


def as_address(text: str) -> str:
    """The usual Qoin address for text written either way. Anything that isn't a number
    address comes back trimmed but otherwise untouched, for the wallet engine to judge."""
    text = (text or "").strip()
    return from_number(text) if is_number(text) else text


def main():
    text = " ".join(sys.argv[1:]).strip()
    if not text or text in ("-h", "--help"):
        sys.exit(__doc__)
    try:
        print(from_number(text) if is_number(text) else group(to_number(text)))
    except NumberError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
