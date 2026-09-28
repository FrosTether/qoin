# FrostBSD — Stage 1

**frostcoin.io · finux.tech**

Stage 0 booted a branded FreeBSD base. **Stage 1 makes the Qoin core service
real**: it starts on boot, persists to `/var/db/qoin`, and is observable — while
staying honest about what it does not yet do.

## What Stage 1 adds

| File | What it does |
|---|---|
| `overlay/usr/local/bin/qoind` | The Qoin core daemon. Creates the data dir + a node identity, then heartbeats every `qoind_interval` seconds. Dependency-free (base `sh` + utils). |
| `overlay/usr/local/bin/qoinctl` | Operator CLI: `qoinctl status \| start \| stop \| restart \| id`. |
| `build/smoke-test.sh` | Boots the image in QEMU and asserts it reaches a login prompt with the Frost banner. |
| `overlay/etc/rc.conf.frost` | `qoind_enable="YES"` now that the daemon ships. |
| `overlay/etc/motd.frost` | Banner now shows `frostcoin.io · finux.tech` and the `qoinctl status` hint. |
| `build/build-frostbsd.sh` | Now creates the `qoin` service user and marks the Frost binaries executable. |

## What `qoind` honestly is (and isn't)

**Is:** a supervised, boot-time service that owns the Qoin data directory
(`/var/db/qoin`), generates a stable node id (`state/node.id`), and writes a
heartbeat (`state/heartbeat`) so `rc.d`/`daemon(8)` can supervise and restart it.

**Isn't (yet):** it does not talk to peers, run consensus, mine, or issue any
coin. That is Stage 3. Nothing in Stage 1 creates value — it's the skeleton the
real node slots into without re-architecting. Keeping this line bright is the
whole point: a security OS that fakes capability discredits itself.

## Try it (on a FreeBSD host or the built image)

```sh
# build with Stage 1 included
sudo sh build/build-frostbsd.sh          # or: sudo env IMG_OUT=Blockcoin.img sh build/build-frostbsd.sh

# smoke-test the image boots
sh build/smoke-test.sh frostbsd.img

# inside the running system:
service qoind start        # rc.conf already enables it on boot
qoinctl status
#   qoind  0.1.0-stage1
#   node   FROST-9F2A...
#   beat   2026-09-28T...Z
#   state  scaffold running — no network/consensus yet (Stage 3)
```

## Stage 1 → Stage 2 (next)

- Drop `qoind` from root to the `qoin` user (privilege separation).
- Autologin-on-serial + an `expect` smoke test that asserts `qoinctl status`.
- ZFS-root build variant; a live/installer image.
- Frost theme: shell prompt, default editor/WM, `frostcoin.io`/`finux.tech`
  first-boot page.

## Note on the names

`frostcoin.io` and `finux.tech` are used here as project/coin URLs (branding in
the banner and `qoind --version`). This scaffold does not register domains, serve
them, or claim they are live — wire them up yourself when you're ready.
