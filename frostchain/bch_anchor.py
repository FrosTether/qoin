#!/usr/bin/env python3
"""Build a frostchain block record and the Bitcoin Cash OP_RETURN that anchors it.

Usage:
    python3 bch_anchor.py <height> <container_file> [--time "1991-08-24T00:00:00"] [--prev <hash>]

Writes block_<height>.json next to the container and prints the OP_RETURN hex.
Block times are local America/New_York time, not UTC. Nothing is broadcast:
put the printed hex in an OP_RETURN output from your own BCH wallet, then
write the txid and BCH block height into the record's "anchor" slot.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("America/New_York")
MAGIC = b"FROSTCHAIN"
VERSION = 1


def block_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k not in ("block_hash", "anchor")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def op_return_hex(height: int, bhash: str) -> str:
    payload = MAGIC + bytes([VERSION]) + height.to_bytes(4, "big") + bytes.fromhex(bhash)
    return payload.hex()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("height", type=int)
    ap.add_argument("container", type=Path)
    ap.add_argument("--time", default=None, help="local ISO time, e.g. 1991-08-24T00:00:00")
    ap.add_argument("--prev", default="0" * 64, help="previous block hash (default: none)")
    a = ap.parse_args()

    box = json.loads(a.container.read_text())
    when = datetime.fromisoformat(a.time).replace(tzinfo=ZONE) if a.time else datetime.now(ZONE)

    record = {
        "chain": "frostchain",
        "height": a.height,
        "time": {"local": when.isoformat(), "zone": "America/New_York", "epoch": int(when.timestamp())},
        "prev_hash": a.prev,
        "container": box["container"],
        "container_sha256": box["container_sha256"],
        "payload_sha256": box["payload"].get("sha256"),
        "owner": box["owner"],
    }
    record["block_hash"] = block_hash(record)
    record["anchor"] = {
        "chain": "bitcoin-cash",
        "op_return_hex": op_return_hex(a.height, record["block_hash"]),
        "txid": None,
        "block_height": None,
    }

    out = a.container.parent / f"block_{a.height:04d}.json"
    out.write_text(json.dumps(record, indent=2))
    print(f"wrote {out}")
    print(f"block_hash   {record['block_hash']}")
    print(f"OP_RETURN    {record['anchor']['op_return_hex']}")


if __name__ == "__main__":
    main()
