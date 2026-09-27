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
