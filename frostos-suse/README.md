# FrostOS (SUSE variant)

A SUSE-based FrostOS: **openSUSE Leap** base + the **Qoin core service** +
a **Kali-flavored** security userland, built with **KIWI** into a bootable image.
This is the Linux/systemd sibling of the FreeBSD build in `../frostbsd/`.

## Why openSUSE Leap, not SLED

SLED (SUSE Linux Enterprise Desktop) is a paid, subscription-gated product; its
ISOs aren't freely redistributable. **openSUSE Leap is built from the same SLE
sources** and is free to use and redistribute — same enterprise base, no license
problem. You also don't download any ISO: KIWI pulls packages from repos at build
time from the image description.

## Requirements

- An **openSUSE host** to build on (Leap or Tumbleweed). A VM is fine.
- `kiwi-ng`, root, and a few GB of disk.
- This will **not** build in a generic Linux cloud container (KIWI needs
  privileged mounts and pulls a full package set).

## Build

```sh
sudo zypper install kiwi-ng
sudo kiwi-ng system build --description . --target-dir /tmp/frostos-build
```

Output: a hybrid, USB-writable ISO under `/tmp/frostos-build`. Boot it in QEMU:

```sh
qemu-system-x86_64 -m 4096 -cdrom /tmp/frostos-build/FrostOS.*.iso -boot d
```

For a raw disk image instead of an ISO, change the `<type image="iso" .../>` line
in `FrostOS.kiwi` to `image="oem"`.

To share the ISO on your home network, then the internet, use FrostBSD's
`finux-share`: `../frostbsd/share/finux-share lan /tmp/frostos-build`. See
[Share it](../frostbsd/README.md#share-it-home-network-first-then-the-internet).

## What ships

| Path | Purpose |
|---|---|
| `FrostOS.kiwi` | KIWI image description: base, repos, package set, users. |
| `config.sh` | In-image setup: enable `qoind`, create the `qoin` user + `/var/lib/qoin`, MOTD, lock root for first-boot reset. |
| `root/usr/local/bin/qoind` | The Qoin core daemon (same portable script as FrostBSD; runs on Linux). |
| `root/usr/local/bin/qoinctl` | Operator CLI; uses `systemctl` on Linux. |
| `root/etc/systemd/system/qoind.service` | Hardened systemd unit (runs as `qoin`, datadir `/var/lib/qoin`). |
| `root/etc/motd.frost` | Frost login banner. |

## Verify after boot

```sh
systemctl status qoind
qoinctl status
#   qoind  0.1.0-stage1
#   node   FROST-....
#   beat   2026-...Z
#   state  scaffold running — no network/consensus yet (Stage 3)
```

## Honest constraints

- `qoind` still does **not** network, mine, or issue coins — it owns its data dir
  and heartbeats (Stage 3 is the real node). Same honesty line as the BSD build.
- Package names are openSUSE names; verify with `zypper se <name>` and pin the
  repo to your Leap version. Some Kali tools have no openSUSE package and need a
  manual install (e.g. Metasploit, Burp).
- Don't ship a known root password: `config.sh` locks root and forces a reset at
  first login. Set your own before real use.
- Not affiliated with SUSE, the openSUSE project, or Kali Linux.

## FreeBSD vs SUSE

You now have two FrostOS variants that share `qoind` and the Frost identity:
- `../frostbsd/` — FreeBSD (Berkeley-derived), `rc.d`, `mkimg` image.
- `./` (this) — openSUSE, `systemd`, KIWI image.

Pick one to carry forward, or keep both. The Qoin core is identical across them.
