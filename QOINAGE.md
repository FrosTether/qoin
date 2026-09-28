# Qoinage

Listen to a five-minute 741 Hz sine wave and earn 13.37 QOIN. Then HUMM 741 Hz to spend.

Qoinage has two parts:

| Part | Files | What it does |
|---|---|---|
| **Qoinage vault** | `graysons/qoinage.py`, `graysons/qoinage.html` | A web page that plays the five-minute sine wave and pays 13.37 QOIN for each finished listen, from a wallet you funded |
| **HUMM lock** | Graysons Wallet, **Qoinage** tab | Optional: every send waits until you hum an F# (741 Hz, or any octave of it) |

The sine wave is credited to **Fat Productions** (change it with `--credit`).

## Run the vault

1. In Graysons Wallet, create a wallet for the vault (for example `vault`) and fund it. The block-1 premine of 13,370.08241991 QOIN covers about 1,000 listens (13.37 × 1,000 = 13,370). Then close that wallet in Graysons, because one wallet file can't be open in two wallet engines at once.
2. Keep a Qoin node running. Graysons Wallet starts one, or run `qoind` yourself.
3. Start the vault. It asks for the vault wallet's password:

   ```bash
   graysons/qoinage --wallet vault
   ```

   It starts its own `graysons-wallet-rpc` on 127.0.0.1:45683, opens the vault wallet in it, and serves the listening page on http://127.0.0.1:45690/.
4. To let phones and other computers on your network listen, add `--bind 0.0.0.0` and open port 45690. For the open internet, put it behind HTTPS (nginx or Caddy) and add `--trust-proxy`.

In Graysons Wallet, **Qoinage → Open Qoinage** opens the listening page with your wallet's address already filled in.

| Option | Default | Meaning |
|---|---|---|
| `--reward` | 13.37 | QOIN per finished listen |
| `--seconds` | 300 | Listening time |
| `--tone` | 741 | Sine wave frequency in Hz |
| `--pulse` | none | Optional slow volume pulse in Hz, for example `7.83` |
| `--credit` | Fat Productions | Credit shown under the sine wave |
| `--per-day` | 1 | Rewards per address per 24 hours |
| `--per-ip` | 5 | Rewards per network (IP address) per 24 hours |
| `--daily-cap` | 100 | Rewards per 24 hours for everyone together |
| `--payout-every` | 60 | Seconds between payout runs |
| `--attach` | off | Use a vault wallet engine that's already running on `--rpc-port` (login from `QOINAGE_RPC_LOGIN=user:pass`) |
| `--requeue-unknown` | off | Put interrupted payouts back in the queue (see below) |

`QOINAGE_PASSWORD` in the environment skips the password prompt, for running it as a service.

## How a listen is checked

- The page asks the vault to start a listen, plays the sine wave with Web Audio, and checks in every 15 seconds. While it plays, it keeps the phone screen on.
- At the end it claims the reward. The vault pays only if five minutes have passed by the vault's own clock, and the page never went quiet for more than 45 seconds.
- Earned rewards wait in a queue. Once a minute the vault sends up to 15 of them in one transaction. After each payout, the vault's change is locked for a few blocks, so a busy vault pays in waves.
- Every reward is written to `~/.qoin/qoinage/ledger.jsonl` before anything is sent. If Qoinage stops in the middle of a payout, those rewards are marked "unknown" and never re-sent automatically. Check the vault's history in Graysons, and if they never went out, restart with `--requeue-unknown`.

## Honest limits

- **Qoinage doesn't mint.** On Qoin, new coins only come from mining. The vault pays out what you put in until it's empty.
- **It can't prove a person listened.** A script can keep the page open. That's why each address earns once a day, each network five times a day, and the whole vault 100 times a day (all adjustable). Only primary addresses can earn, because subaddresses are free to make.
- **The HUMM lock is a ritual, not security.** Anyone can play 741 Hz. Your wallet password still protects your coins. The hum is an extra step on top of it.

## HUMM lock

1. In Graysons Wallet, open the **Qoinage** tab.
2. Press **HUMM 741 Hz** and hum for three seconds. The tuner shows the note you're humming and how far it is from F#.
3. Press **Turn lock on**.

With the lock on, **Send → Review** shows a **HUMM 741 Hz** button, and **Send now** stays disabled until a good hum. Each hum covers one send in the next two minutes. Turning the lock off also takes a hum.

Any F# counts, within a quarter tone (50 cents): 92.6, 185.25, 370.5, 741 or 1482 Hz. Nobody hums as high as 741 Hz, so lower voices usually hum F#3 (185 Hz) and higher voices F#4 (370 Hz). A whistle or a tone app playing 741 Hz works too. A note a semitone off (F or G) doesn't pass.

The three seconds of microphone audio go only to the Graysons backend on 127.0.0.1. It's analysed in memory and not saved.

Test from a terminal:

```bash
python3 graysons/humm.py tone 741 test.wav        # write a test tone
python3 graysons/humm.py check recording.wav      # PASS or FAIL, and the note it heard
```

## Tests

```bash
cd graysons && python3 -m unittest test_qoinage -v
```

36 tests, standard library only. No Qoin binaries needed: a stand-in answers the wallet engine's calls.
