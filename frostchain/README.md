# MyDoge.frostchain containers

Twenty `.frostchain` containers (`container_01` to `container_20`) for FLAC audio,
owned by the MyDoge profile [frostcoin](https://mydoge.com/frostcoin).

Each container is JSON with a `payload` slot (FLAC file name, SHA-256, size,
sample rate, channels, bit depth, duration), an `anchor` slot (chain, txid,
block height), and a `container_sha256` over the rest of the file.

## Fill with FLAC files

```bash
python3 frostchain/frostchain_fill.py <folder_with_flac_files> frostchain/
```

Files are sorted by name; the first 20 fill containers 01 to 20. Audio files are
read, never changed. Pure Python, no dependencies.

## Anchor on-chain

Send a Doge transaction carrying a container's `container_sha256`, then write
the txid and block height into that container's `anchor` slot.

## Block records and the BCH anchor

`bch_anchor.py` turns a container into a frostchain block record and prints the
Bitcoin Cash OP_RETURN that anchors it. Block times are America/New_York, not UTC.

```bash
python3 frostchain/bch_anchor.py 1 frostchain/container_01.frostchain --time 1991-08-24T00:00:00
```

The OP_RETURN payload is `FROSTCHAIN` + version byte + 4-byte height + the
32-byte block hash (47 bytes). Broadcast it from your own BCH wallet, then write
the txid and BCH block height into the record's `anchor` slot. Re-run the
script if the container changes after anchoring; the hash must match.

`block_0001.json` is block 1, dated 1991-08-24 00:00 Eastern, anchoring
`MyDoge.frostchain/01`.
