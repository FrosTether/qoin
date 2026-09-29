# FrostBSD on a Windows laptop — quickstart (FreeBSD)

Try FrostBSD safely on Windows by running it inside a free virtual machine, then
applying the Frost overlay to a stock FreeBSD install. Nothing here touches your
Windows install or your files.

> **What FrostBSD is right now:** an early **console** system (Stage 1–2). It
> boots to a login, runs the Qoin core service (`qoind`), and has the security
> toolset available via `pkg`. It is **not** a polished desktop yet, so a VM is
> the right way to try it. Do **not** install it over Windows yet (see the last
> section).

## 1. Install VirtualBox (Windows)

Download and install VirtualBox: <https://www.virtualbox.org>

## 2. Create a FreeBSD VM

1. Get the FreeBSD **14.x amd64 disc1 ISO** from <https://www.freebsd.org/where/>
   (the "disc1" installer image).
2. In VirtualBox: **New** → Type **BSD**, Version **FreeBSD (64-bit)**, 2–4 GB
   RAM, 20 GB disk.
3. Attach the ISO to the VM's optical drive and **Start** it.
4. Run the FreeBSD installer (`bsdinstall`): accept defaults, set a **root
   password**, enable `dhclient` networking, finish, and reboot.
5. Log in as **root**.

## 3. Apply the Frost overlay + start the Qoin core

Paste these in the VM as root:

```sh
pkg install -y git openssl
git clone https://github.com/FrosTether/qoin
cd qoin && git checkout claude/qoinchain-white-paper-iu8yep
cd frostbsd

# install the Frost binaries, services, banner, and defaults
cp -R overlay/usr /
cp overlay/etc/rc.d/qoind overlay/etc/rc.d/frostfirstboot /etc/rc.d/
cp overlay/etc/motd.frost /etc/motd
cat overlay/etc/rc.conf.frost >> /etc/rc.conf
pw useradd qoin -d /var/db/qoin -s /usr/sbin/nologin -w no

# start it
service qoind start
qoinctl status
```

You should see something like:

```
qoind   0.1.0-stage1
node    FROST-....
wallet  FROST-....
beat    2026-...Z
state   scaffold running — no network/consensus yet (Stage 3)
```

On first start `qoind` generates your wallet **on this VM**, from the OS random
generator. The private key is at `/var/db/qoin/keys/spend.pem` (mode `0600`).

## 4. Back up your key (important)

`spend.pem` is the **only copy** of your identity. Copy it off the VM to
somewhere offline:

```sh
# example: print the public fingerprint (safe to share); NEVER share spend.pem
qoind wallet address
# then move spend.pem to a USB/offline backup via a VirtualBox shared folder or scp
```

If you lose it, the identity is gone — that is the cost of self-custody.

## 5. (Optional) Build the tagged image

To produce the distributable image inside the VM:

```sh
sudo sh build/build-frostbsd.sh        #  ->  FROSTFORPRESIDENT.img
```

Boot the image with QEMU (also inside the VM):

```sh
pkg install -y qemu
qemu-system-x86_64 -m 2048 -drive file=FROSTFORPRESIDENT.img,format=raw -nographic
```

## Security tools (the Kali-flavor set)

Install the curated toolset when you want it:

```sh
pkg install -y $(grep -v '^#' packages/flavor-kali.pkglist | tr '\n' ' ')
```

Some Kali tools have no FreeBSD port (Metasploit, Burp) — see the notes at the
bottom of `packages/flavor-kali.pkglist`.

## On the laptop's real hardware

Build `FROSTFORPRESIDENT.img`, write it to a USB stick (8 GB or more) with
**balenaEtcher** or **Rufus** (in Rufus, pick DD image mode), and boot the laptop
from the stick. That erases only the stick: Windows stays as it was. The one real
danger is choosing the laptop's own drive as the target, which **erases Windows
and your files**, so check the target twice.

Turn off **Secure Boot** in the laptop's firmware settings first; FreeBSD's boot
loader isn't signed for it. The image boots on UEFI and older BIOS laptops. Full
steps: `frostbsd/README.md` → *On your laptop*. It's still a console scaffold, so
keep Windows as your daily OS for now.

## Troubleshooting

- `pkg install` fails: the VM needs networking. Check `ping freebsd.org`; in
  VirtualBox, NAT networking is on by default.
- `qoinctl status` says "not running": run `service qoind start` and check
  `/var/log/messages` for `qoind` lines.
- `wallet not provisioned`: install `openssl` (`pkg install -y openssl`), then
  `qoind wallet init`.

---

Not affiliated with the FreeBSD Foundation or Kali Linux. The security tools are
for systems you own or are authorized to test.
