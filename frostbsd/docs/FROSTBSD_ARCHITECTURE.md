# FrostBSD — architecture & build plan

**Draft 0.1 · 28 September 2026 · Jacob Frost**

FrostBSD is a **FreeBSD-derived** operating system with a **Qoin core service**
baked into the base and a **Kali-flavored** security/privacy userland, shipped as
a bootable image. This document is the honest, buildable version of "Finux/Frost
BSD, ground up, Qoin as kernel, Kali as flavor, Berkeley-derived image."

---

## 1. The honest mapping

| You said | What it means technically | What FrostBSD does |
|---|---|---|
| "Berkeley-derived image" | BSD = Berkeley Software Distribution | Derive from **FreeBSD** (its kernel, base system, and release tooling). This is "ground up" in the sane sense: a custom distro, not a hand-written kernel. |
| "Qoin as the kernel" | A token can't be an OS kernel | Qoin becomes the **core identity/economic service** — a `qoind` daemon integrated into the base system and `rc.d`, present on every boot. The kernel stays the FreeBSD kernel. |
| "Kali as the flavor" | Kali is Debian/Linux, not BSD | Reproduce the *flavor*: a curated security toolset from FreeBSD `pkg` + theming. Not a Kali port (impossible on a BSD kernel). |
| "Finux / FrostBSD" | The product | A branded FreeBSD spin: base + Qoin core + security userland + Frost theming. |

Why FreeBSD and not OpenBSD/NetBSD: FreeBSD has the most mature **image/release
pipeline** (`release(7)`, `poudriere`, `makefs`, `mkimg`), the largest ports tree
for the security toolset, and a Linux compat layer (`linuxulator`) for the few
tools with no native port. If the priority is maximum hardening over tooling
breadth, **HardenedBSD** (a FreeBSD fork) is the drop-in alternative base.

---

## 2. System layers

```
┌────────────────────────────────────────────────────────┐
│  Frost userland / theme   MOTD, shell, WM, branding      │  ← identity
├────────────────────────────────────────────────────────┤
│  Kali-flavor toolset      nmap, wireshark, hydra, …      │  ← "flavor"
│                           (FreeBSD pkg; gaps noted)      │
├────────────────────────────────────────────────────────┤
│  Qoin core service        qoind: wallet / personhood /   │  ← "Qoin as core"
│                           dividend, wired into rc.d      │
├────────────────────────────────────────────────────────┤
│  FreeBSD base system      libc, rc, pkg, jails, ZFS      │  ← Berkeley-derived
├────────────────────────────────────────────────────────┤
│  FreeBSD kernel           amd64 (arm64 later)            │  ← the real kernel
└────────────────────────────────────────────────────────┘
```

The **Qoin core** is what makes this FrostBSD and not "FreeBSD with tools." It is
a base-integrated service, not an afterthought app:
- `qoind` — a Qoin/Qoinchain node + wallet daemon, started by `rc.d/qoind`.
- Identity: a user's Qoinchain personhood key can back local login / signing.
- Economics: the machine can run the universal-dividend logic from the Qoinchain
  white paper as a first-class service, not a downloaded app.

> `qoind` does not exist yet — it's Stage 3 work. The `rc.d` wiring, packaging
> slot, and data directory are real now, so the daemon drops in later without
> re-architecting.

---

## 3. Build pipeline

FrostBSD is produced by a repeatable image build on a **FreeBSD host** (a VM is
fine). The starter script `build/build-frostbsd.sh` does the minimal real path:

1. **Fetch base** — download `base.txz` (+ `kernel.txz`) for a pinned FreeBSD
   release, extract into a staging root.
2. **Install the flavor** — `pkg -c <stage> install` the curated toolset from
   `packages/flavor-kali.pkglist`.
3. **Apply the overlay** — drop `overlay/` over the stage: `rc.d/qoind`, a Frost
   `motd`, `rc.conf` service enables, `loader.conf` branding.
4. **Make it bootable** — build a UFS root with `makefs`, wrap it in a GPT image
   with `mkimg` (`efi` + `freebsd-boot` + `freebsd-ufs`, so it boots on UEFI and
   BIOS machines), output `FROSTFORPRESIDENT.img`.
5. **Test** — boot the image in QEMU.

For production later, graduate to FreeBSD's `release(7)` (`make release`) with a
`poudriere` package repo and a signed `pkgbase`, which also yields ISO + memstick
+ cloud images and reproducible builds.

---

## 4. Roadmap (realistic milestones)

Each stage produces something that actually boots or runs.

- **Stage 0 — Boot a branded base.** Run `build-frostbsd.sh`, get a `FROSTFORPRESIDENT.img`
  that boots to a login with the Frost MOTD in QEMU. *This is where the starter
  gets you.*
- **Stage 1 — The flavor.** Curated security toolset installs cleanly; document
  the Kali→BSD tool gaps and the `linuxulator` fallbacks.
- **Stage 2 — Frost identity.** Theming, default shell/WM, a hardened `rc.conf`,
  ZFS root option, a live/installer image.
- **Stage 3 — Qoin core.** Ship `qoind` (start from the safe FSZT/Qoin node
  work), wire personhood-key login and the dividend service, persist to
  `/var/db/qoin`.
- **Stage 4 — Release engineering.** `poudriere` repo, signed images, ISO +
  memstick + arm64, update channel.

---

## 5. Honest constraints

- **This is a real project, not a one-shot.** The starter boots a branded base;
  a daily-driver secure OS is stages of work. That's normal for a distro.
- **The build runs on FreeBSD, not on a generic Linux box** (it uses `makefs`,
  `mkimg`, `pkg -c`). Use a FreeBSD VM as the build host.
- **Tool parity with Kali is partial.** Many tools have native ports (below);
  some don't and need `linuxulator` or have no BSD equivalent — the pkglist marks
  these.
- **Naming.** "FrostBSD" appears unused among active BSD spins (GhostBSD,
  HardenedBSD, MidnightBSD, NomadBSD exist); confirm before you brand publicly.
  FreeBSD's license (2-clause BSD) lets you derive and rebrand freely; keep the
  base copyright notices.
- **Security posture is a promise you have to keep.** A "security OS" that ships
  the red-paper habits (fake displays, unbacked claims) undermines itself. Ship
  what's real.

---

## 6. What ships in the starter

| Path | Purpose |
|---|---|
| `build/build-frostbsd.sh` | The image builder (Stage 0). Runs on a FreeBSD host. |
| `overlay/etc/rc.d/qoind` | Real FreeBSD service script for the future Qoin daemon. |
| `overlay/etc/motd.frost` | Frost login banner. |
| `overlay/etc/rc.conf.frost` | Service enables + hardening defaults to merge into `rc.conf`. |
| `packages/flavor-kali.pkglist` | Curated security toolset (FreeBSD pkg names) with gap notes. |
| `README.md` | How to run the build and boot it in QEMU. |
