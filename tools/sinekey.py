#!/usr/bin/env python3
"""
sinekey.py - store a Qoin private spend key as a 5-minute sine-tone WAV file.

    python3 sinekey.py new   mykey.wav          # make a brand-new random key + its WAV
    python3 sinekey.py encode <64-hex-key> mykey.wav
    python3 sinekey.py decode mykey.wav         # prints the key back out

How it works: the 32-byte spend key plus a 4-byte SHA-256 checksum becomes
72 hex digits. Each digit is played as one pure sine tone (16 possible
pitches, 400-1900 Hz) for 300/72 = 4.17 seconds. Total length: exactly
5 minutes. Decoding measures which of the 16 pitches is loudest in each
slot, then checks the checksum so a damaged file is refused, not silently
turned into the wrong key.

WARNING: this WAV *is* your private key. Anyone who gets a copy of it,
or records it being played, can spend your coins. Treat it like a seed
phrase: don't play it out loud, don't upload it, keep an offline backup.

Pure Python standard library - no installs needed.
"""
import hashlib
import math
import os
import struct
import sys
import wave

SAMPLE_RATE = 8000
DURATION_S = 300                      # 5 minutes
N_SYMBOLS = 72                        # 64 key digits + 8 checksum digits
SYMBOL_S = DURATION_S / N_SYMBOLS     # ~4.1667 s per tone
FREQS = [400 + 100 * n for n in range(16)]   # one pitch per hex digit 0-f
AMPLITUDE = 0.6
FADE_S = 0.05                         # soft edges so tones don't click

# ed25519 group order - a valid Monero/Wownero-family spend key is < L
L = 2**252 + 27742317777372353535851937790883648493


def reduce_scalar(key: bytes) -> bytes:
    """Make 32 bytes into a valid spend key, same as Monero's sc_reduce32."""
    return (int.from_bytes(key, "little") % L).to_bytes(32, "little")


def key_to_digits(key: bytes) -> list:
    checksum = hashlib.sha256(key).digest()[:4]
    return [int(c, 16) for c in (key + checksum).hex()]


def encode(key: bytes, path: str) -> None:
    if len(key) != 32:
        sys.exit("key must be exactly 32 bytes (64 hex characters)")
    if int.from_bytes(key, "little") >= L:
        sys.exit("that isn't a valid spend key (not reduced mod L)")
    digits = key_to_digits(key)
    total = int(DURATION_S * SAMPLE_RATE)
    fade = int(FADE_S * SAMPLE_RATE)
    frames = bytearray()
    for i in range(total):
        slot = min(int(i / (SYMBOL_S * SAMPLE_RATE)), N_SYMBOLS - 1)
        start = int(slot * SYMBOL_S * SAMPLE_RATE)
        end = int((slot + 1) * SYMBOL_S * SAMPLE_RATE) if slot < N_SYMBOLS - 1 else total
        env = min(1.0, (i - start) / fade, (end - 1 - i) / fade)
        env = max(env, 0.0)
        s = AMPLITUDE * env * math.sin(2 * math.pi * FREQS[digits[slot]] * i / SAMPLE_RATE)
        frames += struct.pack("<h", int(s * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))


def goertzel_power(samples, freq):
    coeff = 2 * math.cos(2 * math.pi * freq / SAMPLE_RATE)
    s1 = s2 = 0.0
    for x in samples:
        s0 = x + coeff * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


def decode(path: str) -> bytes:
    with wave.open(path, "rb") as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            sys.exit("not a sinekey WAV (expected 8000 Hz mono 16-bit)")
        raw = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(raw) // 2), raw)
    digits = []
    for slot in range(N_SYMBOLS):
        mid = int((slot + 0.5) * SYMBOL_S * SAMPLE_RATE)
        window = samples[mid - SAMPLE_RATE // 2: mid + SAMPLE_RATE // 2]   # middle 1 s of each tone
        powers = [goertzel_power(window, f) for f in FREQS]
        digits.append(powers.index(max(powers)))
    data = bytes.fromhex("".join("%x" % d for d in digits))
    key, checksum = data[:32], data[32:]
    if hashlib.sha256(key).digest()[:4] != checksum:
        sys.exit("checksum mismatch - this WAV is damaged or isn't a sinekey file")
    return key


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "new":
        key = reduce_scalar(os.urandom(32))
        encode(key, sys.argv[2])
        print("wrote", sys.argv[2])
        print("spend key (import it with: frostoise-wallet-cli --generate-from-spend-key <walletname>):")
        print(key.hex())
    elif cmd == "encode" and len(sys.argv) == 4:
        encode(bytes.fromhex(sys.argv[2]), sys.argv[3])
        print("wrote", sys.argv[3])
    elif cmd == "decode":
        print(decode(sys.argv[2]).hex())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
