#!/bin/sh
#
# build-frostbsd.sh — Stage 0 image builder for FrostBSD.
#
# Produces a bootable UFS/GPT raw image (frostbsd.img) from a stock FreeBSD
# release, plus the Frost overlay and the "Kali-flavor" package set.
#
# RUN THIS ON A FreeBSD HOST (a VM is fine), AS ROOT. It uses FreeBSD-only
# tools: pkg -c (chroot), makefs, mkimg. It will NOT work on Linux/macOS.
#
# Quick start (on FreeBSD):
#   sudo sh build/build-frostbsd.sh
#   # then boot it:
#   qemu-system-x86_64 -m 2048 -drive file=frostbsd.img,format=raw -nographic
#
set -eu

# ---- config (edit these) --------------------------------------------------
FREEBSD_VERSION="${FREEBSD_VERSION:-14.2-RELEASE}"
ARCH="${ARCH:-amd64}"
MIRROR="${MIRROR:-https://download.freebsd.org/releases/${ARCH}/${FREEBSD_VERSION}}"
IMG_SIZE="${IMG_SIZE:-6g}"          # root image size
BUILD_TAG="${BUILD_TAG:-FROSTFORPRESIDENT}"   # stamped into the image + filename
IMG_OUT="${IMG_OUT:-${BUILD_TAG}.img}"
WORK="${WORK:-$(pwd)/work}"
STAGE="${WORK}/stage"
HERE="$(cd "$(dirname "$0")/.." && pwd)"   # repo root (build/..)
PKGLIST="${HERE}/packages/flavor-kali.pkglist"
OVERLAY="${HERE}/overlay"
# ---------------------------------------------------------------------------

log() { printf '\033[38;5;51m>> [frostbsd]\033[0m %s\n' "$*"; }
die() { printf '\033[38;5;196m!! %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "FreeBSD" ] || die "This build runs on FreeBSD only (needs pkg -c, makefs, mkimg). Use a FreeBSD VM."
[ "$(id -u)" = "0" ] || die "Run as root (needs chroot install and device-free image build)."
for t in fetch tar pkg makefs mkimg; do command -v "$t" >/dev/null 2>&1 || die "missing tool: $t"; done

log "FrostBSD ${FREEBSD_VERSION}/${ARCH}  ->  ${IMG_OUT}"
rm -rf "$STAGE"; mkdir -p "$STAGE" "$WORK"

# 1) Fetch and extract the FreeBSD base (+ kernel).
for set in base kernel; do
  if [ ! -f "${WORK}/${set}.txz" ]; then
    log "fetching ${set}.txz"
    fetch -o "${WORK}/${set}.txz" "${MIRROR}/${set}.txz"
  fi
  log "extracting ${set}.txz"
  tar -xpf "${WORK}/${set}.txz" -C "$STAGE"
done

# 2) Prepare the chroot for pkg, then install the flavor toolset.
cp /etc/resolv.conf "${STAGE}/etc/resolv.conf"
mount -t devfs devfs "${STAGE}/dev"
trap 'umount "${STAGE}/dev" 2>/dev/null || true' EXIT

PKGS="$(grep -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' "$PKGLIST" | tr '\n' ' ')"
log "installing packages: ${PKGS}"
env ASSUME_ALWAYS_YES=yes IGNORE_OSVERSION=yes pkg -c "$STAGE" bootstrap -y
# Install best-effort: a single missing port should not abort the whole image.
for p in $PKGS; do
  env ASSUME_ALWAYS_YES=yes pkg -c "$STAGE" install -y "$p" \
    || log "WARN: package not installed (no BSD port?): $p"
done

# 3) Apply the Frost overlay.
log "applying overlay"
cp -R "${OVERLAY}/." "${STAGE}/"
# Make Frost executables runnable and create the Qoin service user (Stage 1).
for f in usr/local/bin/qoind usr/local/bin/qoinctl usr/local/bin/qoin-firstboot \
         etc/rc.d/qoind etc/rc.d/frostfirstboot; do
  [ -f "${STAGE}/${f}" ] && chmod 0755 "${STAGE}/${f}"
done
# Stamp the build tag into the image (release file + MOTD line).
cat > "${STAGE}/etc/frost-release" <<RELEOF
FROSTBSD_TAG="${BUILD_TAG}"
FROSTBSD_BUILT="$(date -u +%FT%TZ)"
FROSTBSD_BASE="FreeBSD ${FREEBSD_VERSION}/${ARCH}"
RELEOF
[ -f "${STAGE}/etc/motd.frost" ] && printf '    build: %s\n' "${BUILD_TAG}" >> "${STAGE}/etc/motd.frost"
pw -R "$STAGE" useradd qoin -c "Qoin core service" -d /var/db/qoin \
  -s /usr/sbin/nologin -w no 2>/dev/null \
  && log "created service user: qoin" \
  || log "service user qoin already present or pw unavailable"
# MOTD + hostname + merge Frost rc.conf defaults.
[ -f "${STAGE}/etc/motd.frost" ] && cp "${STAGE}/etc/motd.frost" "${STAGE}/etc/motd.template"
echo "frostbsd" > "${STAGE}/etc/hostname" 2>/dev/null || true
cat >> "${STAGE}/etc/rc.conf" <<'RCEOF'
# --- FrostBSD defaults (appended by build-frostbsd.sh) ---
hostname="frostbsd"
RCEOF
[ -f "${STAGE}/etc/rc.conf.frost" ] && cat "${STAGE}/etc/rc.conf.frost" >> "${STAGE}/etc/rc.conf"

# Root filesystem + fstab + boot bits.
cat > "${STAGE}/etc/fstab" <<'FSTAB'
# Device        Mountpoint  FStype  Options  Dump  Pass#
/dev/gpt/rootfs  /          ufs     rw       1     1
FSTAB
sysrc -f "${STAGE}/boot/loader.conf" autoboot_delay=3 vfs.root.mountfrom="ufs:/dev/gpt/rootfs" >/dev/null

umount "${STAGE}/dev"; trap - EXIT

# 4) Build the bootable image (UFS root inside a GPT image).
log "building filesystem"
makefs -t ffs -B little -s "$IMG_SIZE" -o label=rootfs \
  "${WORK}/rootfs.ufs" "$STAGE"

log "assembling GPT image"
mkimg -s gpt \
  -b "${STAGE}/boot/pmbr" \
  -p freebsd-boot:="${STAGE}/boot/gptboot" \
  -p freebsd-ufs/rootfs:="${WORK}/rootfs.ufs" \
  -o "${IMG_OUT}"

log "done -> ${IMG_OUT}"
log "boot it:  qemu-system-x86_64 -m 2048 -drive file=${IMG_OUT},format=raw -nographic"
