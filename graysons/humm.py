#!/usr/bin/env python3
"""humm.py - hears whether a hum is tuned to 741 Hz.

741 Hz is F#5, higher than almost anyone can hum, so every F# counts:
92.6, 185.25, 370.5, 741 or 1482 Hz (that last one is whistling range), each
within a quarter tone (50 cents). A check listens to 1-6 seconds of mono audio in
quarter-second frames and passes when most of the loud frames put at least
45% of their energy on F# partials. A hum on G or F, a semitone off, fails.

    python3 humm.py tone 741 test.wav        # write a 5-second test tone
    python3 humm.py tone 185.25 low.wav 3    # a hummable F#3, 3 seconds
    python3 humm.py check recording.wav      # say what it heard

The hum is a ritual, not a secret. Anyone can play 741 Hz, so Graysons asks for
it as an extra step before a send, never instead of the wallet password.

Pure Python standard library.
"""
import array
import base64
import binascii
import math
import struct
import sys
import wave

TARGET_HZ = 741.0
OCTAVES = (-3, -2, -1, 0, 1)        # 92.6, 185.25, 370.5, 741, 1482 Hz
TOLERANCE_CENTS = 50
RATE = 8000                         # everything is analysed at 8 kHz
FRAME = RATE // 4                   # quarter-second frames, 4 Hz resolution
SCAN_STEP_HZ = 1.5                  # finer than half a bin, so no tone slips between steps
MIN_RMS = 200                       # int16 units (about -44 dBFS); quieter frames are ignored
FRAME_SHARE = 0.45                  # a loud frame is "on F#" at this share of its energy
MIN_LOUD_FRAMES = 6                 # at least 1.5 s of sound
PASS_FRACTION = 0.6                 # and 60% of the loud frames on F#
MIN_SECONDS, MAX_SECONDS = 1.0, 6.0
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class HummError(ValueError):
    pass


def f_sharps():
    return [TARGET_HZ * 2.0 ** k for k in OCTAVES]


def note_name(hz):
    """'F#3 (+12 cents)' style name for a frequency."""
    midi = 69 + 12 * math.log2(hz / 440.0)
    n = round(midi)
    cents = round((midi - n) * 100)
    return f"{NOTES[n % 12]}{n // 12 - 1}", cents


def cents_from_f_sharp(hz):
    """Distance in cents to the nearest F# (any octave). Negative = flat."""
    semis = (12 * math.log2(hz / TARGET_HZ)) % 12
    if semis > 6:
        semis -= 12
    return semis * 100


def goertzel_power(samples, freq, rate=RATE):
    coeff = 2.0 * math.cos(2.0 * math.pi * freq / rate)
    s1 = s2 = 0.0
    for x in samples:
        s1, s2 = x + coeff * s1 - s2, s1
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


def band_peak(frame, energy, center):
    """Largest share of the frame's energy found within +/-50 cents of center, and where."""
    lo = center * 2.0 ** (-TOLERANCE_CENTS / 1200)
    hi = center * 2.0 ** (TOLERANCE_CENTS / 1200)
    steps = max(2, math.ceil((hi - lo) / SCAN_STEP_HZ))
    best, best_f = 0.0, center
    n = len(frame)
    for i in range(steps + 1):
        f = lo + (hi - lo) * i / steps
        share = 2.0 * goertzel_power(frame, f) / (n * energy)
        if share > best:
            best, best_f = share, f
    return min(best, 1.0), best_f


def resample(samples, rate):
    """Bring int16-range samples at any rate to 8 kHz (box-filter down, linear up)."""
    if rate == RATE:
        return [float(s) for s in samples]
    if rate <= 0:
        raise HummError("bad sample rate")
    ratio = rate / RATE
    n_out = int(len(samples) / ratio)
    out = []
    if ratio > 1:
        for j in range(n_out):
            a = int(j * ratio)
            b = max(a + 1, int((j + 1) * ratio))
            chunk = samples[a:b]
            out.append(sum(chunk) / len(chunk))
    else:
        for j in range(n_out):
            x = j * ratio
            a = int(x)
            b = min(a + 1, len(samples) - 1)
            out.append(samples[a] + (samples[b] - samples[a]) * (x - a))
    return out


def analyze(samples, rate=RATE):
    """Decide whether this audio is a hum on F#. samples are int16-range numbers."""
    samples = resample(samples, rate)
    seconds = len(samples) / RATE
    if seconds < MIN_SECONDS:
        raise HummError("Recording too short - hum for about three seconds")
    if seconds > MAX_SECONDS:
        raise HummError("Recording too long - three seconds is plenty")
    targets = f_sharps()
    loud = on = 0
    shares, hits = [], []
    frames = []
    for start in range(0, len(samples) - FRAME + 1, FRAME):
        frame = samples[start:start + FRAME]
        mean = sum(frame) / FRAME
        frame = [x - mean for x in frame]
        energy = sum(x * x for x in frame)
        if math.sqrt(energy / FRAME) < MIN_RMS:
            continue
        loud += 1
        frames.append((energy, frame))
        total, strongest = 0.0, (0.0, 0.0)
        for t in targets:
            share, f = band_peak(frame, energy, t)
            total += share
            if share > strongest[0]:
                strongest = (share, f)
        total = min(total, 1.0)
        shares.append(total)
        if total >= FRAME_SHARE:
            on += 1
            hits.append(strongest[1])

    passed = loud >= MIN_LOUD_FRAMES and on >= PASS_FRACTION * loud
    result = {"passed": passed, "loud_frames": loud, "on_frames": on,
              "share": round(sorted(shares)[len(shares) // 2], 3) if shares else 0.0}
    if passed:
        hz = sorted(hits)[len(hits) // 2]
        name, _ = note_name(hz)
        off = round(cents_from_f_sharp(hz))
        result.update(hz=round(hz, 1), note=name, cents=off,
                      message=f"Heard {name} at {hz:.1f} Hz, {abs(off)} cents {'flat' if off < 0 else 'sharp'}. Tuned.")
        return result
    if loud < MIN_LOUD_FRAMES:
        result["message"] = "Too quiet - hum louder or closer to the mic"
        return result
    hz = strongest_note(frames)
    if hz:
        name, _ = note_name(hz)
        result.update(hz=round(hz, 1), note=name)
        result["message"] = (f"Heard about {name} ({hz:.0f} Hz), not F#. "
                             "Aim for 92.6, 185, 370 or 741 Hz.")
    else:
        result["message"] = "Heard sound but no steady note. Hum one long, steady F#."
    return result


def rough_pitch(frame):
    """Autocorrelation pitch of one frame, 80-1600 Hz, or None if it isn't a steady note."""
    lo, hi = RATE // 1600, RATE // 80
    n = min(len(frame), 1200) - hi - 1
    a = frame[:n]
    e1 = sum(x * x for x in a)
    corr = [0.0] * (hi + 2)
    for lag in range(lo - 1, hi + 2):
        b = frame[lag:lag + n]
        e2 = sum(y * y for y in b)
        corr[lag] = sum(x * y for x, y in zip(a, b)) / math.sqrt(e1 * e2) if e1 and e2 else 0.0
    peak = max(corr[lo:hi + 1])
    if peak < 0.5:
        return None
    for lag in range(lo, hi + 1):
        if corr[lag] >= 0.9 * peak and corr[lag] >= corr[lag - 1] and corr[lag] >= corr[lag + 1]:
            p, q, r = corr[lag - 1], corr[lag], corr[lag + 1]
            d = p - 2 * q + r
            return RATE / (lag + (0.5 * (p - r) / d if d else 0.0))
    return None


def strongest_note(frames):
    """Median pitch of the loudest few frames, for telling someone what they hummed instead."""
    loudest = sorted(frames, key=lambda ef: -ef[0])[:4]
    pitches = sorted(p for p in (rough_pitch(fr) for _, fr in loudest) if p)
    return pitches[len(pitches) // 2] if len(pitches) >= 2 else None


def decode_pcm16(b64, rate):
    """Base64 little-endian int16 mono, as sent by the Graysons page."""
    try:
        raw = base64.b64decode(b64 or "", validate=True)
    except (binascii.Error, ValueError):
        raise HummError("That recording didn't arrive intact")
    try:
        rate = int(rate)
    except (TypeError, ValueError):
        raise HummError("bad sample rate")
    if not 3000 <= rate <= 192000:
        raise HummError("bad sample rate")
    if len(raw) % 2 or len(raw) > 2 * rate * MAX_SECONDS + 4096:
        raise HummError("That recording is the wrong size")
    a = array.array("h")
    a.frombytes(raw)
    if sys.byteorder == "big":
        a.byteswap()
    return list(a), rate


def check_base64(b64, rate):
    samples, rate = decode_pcm16(b64, rate)
    return analyze(samples, rate)


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise HummError("Use a 16-bit WAV")
        ch, rate = w.getnchannels(), w.getframerate()
        raw = w.readframes(w.getnframes())
    a = array.array("h")
    a.frombytes(raw)
    if sys.byteorder == "big":
        a.byteswap()
    samples = list(a)
    if ch > 1:
        samples = [sum(samples[i:i + ch]) / ch for i in range(0, len(samples), ch)]
    return samples, rate


def write_tone(path, hz, seconds=5.0, rate=RATE, amplitude=0.5):
    n = int(seconds * rate)
    fade = int(0.05 * rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(
            struct.pack("<h", int(32767 * amplitude * min(1.0, i / fade, (n - 1 - i) / fade)
                                  * math.sin(2 * math.pi * hz * i / rate)))
            for i in range(n)))


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "tone":
        secs = float(sys.argv[4]) if len(sys.argv) > 4 else 5.0
        write_tone(sys.argv[3], float(sys.argv[2]), secs)
        print(f"wrote {sys.argv[3]}: {float(sys.argv[2])} Hz for {secs:g} s")
    elif len(sys.argv) == 3 and sys.argv[1] == "check":
        samples, rate = read_wav(sys.argv[2])
        take = samples[:int(rate * 3)] if len(samples) > rate * MAX_SECONDS else samples
        try:
            r = analyze(take, rate)
        except HummError as e:
            sys.exit(str(e))
        print(("PASS  " if r["passed"] else "FAIL  ") + r["message"])
        sys.exit(0 if r["passed"] else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
