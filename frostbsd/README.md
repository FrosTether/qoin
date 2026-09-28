# FrostBSD (Stage 0 starter)

A FreeBSD-derived OS with a Qoin core service and a Kali-flavored security
userland. This starter builds a **bootable image that boots to a branded login**.
See `docs/FROSTBSD_ARCHITECTURE.md` for the full plan and the honest mapping of
"Qoin as kernel / Kali as flavor / Berkeley-derived image".

## What this is / isn't

- **Is:** a repeatable image build on top of stock FreeBSD, plus the Frost overlay
  (a real `rc.d/qoind` service, MOTD, hardening defaults) and a curated security
  toolset.
- **Isn't (yet):** the `qoind` daemon itself (Stage 3), a hardened daily driver,
  or a Kali port. Kali can't run on a BSD kernel; we reproduce the flavor.

## Requirements

- A **FreeBSD host** to build on (14.x recommended). A FreeBSD VM is fine.
  The build uses `pkg -c`, `makefs`, and `mkimg`, which are FreeBSD-only — it will
  **not** run on Linux or macOS.
- Root, ~8 GB free disk, and network access to a FreeBSD mirror.

## Build

```sh
sudo sh build/build-frostbsd.sh
```

Useful overrides (environment variables):

```sh
# Name the output image whatever you like:
sudo env IMG_OUT=Blockcoin.img sh build/build-frostbsd.sh

# Pin a different release / arch / size:
sudo env FREEBSD_VERSION=14.2-RELEASE ARCH=amd64 IMG_SIZE=8g sh build/build-frostbsd.sh
```

Output: `frostbsd.img` (or your `IMG_OUT`), a GPT + UFS bootable raw image.

## Boot it

```sh
qemu-system-x86_64 -m 2048 -drive file=frostbsd.img,format=raw -nographic
```

You should reach a login with the Frost MOTD. Log in as `root` (no password on the
fresh base image — **set one immediately**, this starter is not hardened for
exposure).

## Turn on the Qoin core (later)

`rc.d/qoind` is shipped and correct, but the daemon is Stage 3. Once
`/usr/local/bin/qoind` exists:

```sh
sysrc qoind_enable=YES
service qoind start
```

Until then it stays disabled and does nothing.

## Legal / ethical

FrostBSD derives from FreeBSD (2-clause BSD license) — keep the base copyright
notices. It is **not** affiliated with the FreeBSD Foundation, Kali Linux, or
Offensive Security. The bundled tools are for testing systems **you own or are
authorized to assess**. Don't ship security claims the build can't back.

## Layout

```
frostbsd/
├── build/build-frostbsd.sh        # the image builder (Stage 0)
├── overlay/
│   └── etc/
│       ├── rc.d/qoind             # Qoin core service (real rc.d, daemon TBD)
│       ├── motd.frost             # Frost login banner
│       └── rc.conf.frost          # service + hardening defaults
├── packages/flavor-kali.pkglist   # curated security toolset (+ gap notes)
└── docs/FROSTBSD_ARCHITECTURE.md   # architecture & roadmap
```
