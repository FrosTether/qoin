#!/usr/bin/env python3
"""Fill MyDoge.frostchain containers 01-20 with FLAC payloads.

Usage:
    python3 frostchain_fill.py <folder_with_flac_files> [containers_folder]

Takes the FLAC files in the folder (sorted by name), puts the first 20 into
container_01 ... container_20, and records each file's name, SHA-256, size,
sample rate, channels, bit depth and duration. Nothing is changed in the
audio files. Pure Python, no installs needed.
"""
import hashlib
import json
import sys
from pathlib import Path


def flac_info(path):
    """Read the STREAMINFO block from a FLAC header."""
    with open(path, "rb") as f:
        if f.read(4) != b"fLaC":
            raise ValueError(f"{path.name} is not a FLAC file")
        header = f.read(4)
        if header[0] & 0x7F != 0:
            raise ValueError(f"{path.name}: first metadata block is not STREAMINFO")
        si = f.read(34)
    bits = int.from_bytes(si[10:18], "big")
    sample_rate = bits >> 44
    channels = ((bits >> 41) & 0x7) + 1
    bits_per_sample = ((bits >> 36) & 0x1F) + 1
    total_samples = bits & 0xFFFFFFFFF
    duration = total_samples / sample_rate if sample_rate else None
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "bits_per_sample": bits_per_sample,
        "duration_seconds": round(duration, 3) if duration else None,
        "audio_md5": si[18:34].hex(),
    }


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    flac_dir = Path(sys.argv[1])
    box_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent
    flacs = sorted(p for p in flac_dir.iterdir() if p.suffix.lower() == ".flac")
    if not flacs:
        sys.exit(f"No .flac files found in {flac_dir}")
    if len(flacs) > 20:
        print(f"Found {len(flacs)} FLAC files; using the first 20 by name.")

    for i, flac in enumerate(flacs[:20], start=1):
        box_path = box_dir / f"container_{i:02d}.frostchain"
        box = json.loads(box_path.read_text())
        box.pop("container_sha256", None)
        box["payload"] = {
            "type": "audio/flac",
            "filename": flac.name,
            "sha256": sha256_file(flac),
            "size_bytes": flac.stat().st_size,
            **flac_info(flac),
        }
        body = json.dumps(box, indent=2, sort_keys=True)
        box["container_sha256"] = hashlib.sha256(body.encode()).hexdigest()
        box_path.write_text(json.dumps(box, indent=2))
        print(f"{box_path.name}  <-  {flac.name}  ({box['payload']['duration_seconds']} s)")

    if len(flacs) < 20:
        print(f"Only {len(flacs)} FLAC files; containers {len(flacs)+1:02d}-20 stay empty.")


if __name__ == "__main__":
    main()
