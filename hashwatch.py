#!/usr/bin/env python3
"""
hashwatch — Frostoise miner H/s on your Wear OS watch.

Reads the miner speed from your Frostoise daemon (frostnerod) and pushes it to
the ntfy app on your phone. Wear OS mirrors the notification to your watch.

Setup (once):
  1. Phone: install "ntfy" from the Play Store → + → subscribe to your topic name (below).
  2. Phone: Wear OS / Galaxy Wearable app → Notifications → make sure ntfy is allowed on the watch.
  3. Computer that mines:  pip install requests   then   python3 hashwatch.py

Pick a long, unguessable topic — anyone who knows it can read your pushes.
"""
import os, time, requests

DAEMON = os.getenv("FROSTOISE_DAEMON", "http://127.0.0.1:45671")   # Frostoise mainnet RPC (cryptonote_config.h)
TOPIC  = os.getenv("NTFY_TOPIC", "frostoise-hash-jtf-7831")        # change this to your own
NTFY   = f"https://ntfy.sh/{TOPIC}"
EVERY  = int(os.getenv("EVERY_MIN", "5")) * 60                     # push interval in seconds

def fmt(hs):
    for unit, div in (("MH/s", 1e6), ("kH/s", 1e3)):
        if hs >= div:
            return f"{hs / div:.2f} {unit}"
    return f"{hs:.0f} H/s"

def status():
    m = requests.post(f"{DAEMON}/mining_status", timeout=10).json()
    info = requests.post(f"{DAEMON}/json_rpc",
                         json={"jsonrpc": "2.0", "id": "0", "method": "get_info"}, timeout=10).json()["result"]
    return bool(m.get("active")), float(m.get("speed", 0)), int(m.get("threads_count", 0)), int(info["height"])

def push(title, body, priority="low", tags="pick"):
    requests.post(NTFY, data=body.encode(), timeout=10,
                  headers={"Title": title, "Priority": priority, "Tags": tags})

was_mining = None
while True:
    try:
        active, hs, threads, height = status()
        if active and hs > 0:
            push(f"⛏ {fmt(hs)}", f"Frostoise · block {height:,} · {threads} threads")
            if was_mining is False:
                push("Miner back up", f"{fmt(hs)} at block {height:,}", "high", "white_check_mark")
        elif was_mining is not False:
            push("Miner stopped", f"0 H/s at block {height:,}", "high", "warning")   # buzzes the watch
        was_mining = active and hs > 0
    except Exception as e:
        if was_mining is not None:
            push("Node unreachable", str(e)[:120], "high", "warning")
        was_mining = None
    time.sleep(EVERY)
