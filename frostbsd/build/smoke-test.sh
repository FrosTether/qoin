#!/bin/sh
#
# smoke-test.sh — boot the FrostBSD image in QEMU and confirm it reaches a
# login prompt with the Frost banner. Requires qemu-system-x86_64.
#
# This is a boot check, not a full integration test: it verifies the image is
# bootable and branded. Logging in to assert `qoinctl status` needs an expect
# or SSH step (Stage 2). Run on any host with QEMU (Linux or FreeBSD).
#
#   usage: sh build/smoke-test.sh [image]     (default: frostbsd.img)
#
set -eu

IMG="${1:-frostbsd.img}"
TIMEOUT="${TIMEOUT:-180}"
LOG="$(mktemp -t frostbsd-smoke.XXXXXX)"

[ -f "$IMG" ] || { echo "smoke-test: no image at '$IMG'" >&2; exit 1; }
command -v qemu-system-x86_64 >/dev/null 2>&1 || { echo "smoke-test: need qemu-system-x86_64" >&2; exit 1; }

echo ">> booting $IMG (timeout ${TIMEOUT}s); serial log -> $LOG"
qemu-system-x86_64 -m 2048 -drive file="$IMG",format=raw -nographic > "$LOG" 2>&1 &
qpid=$!

reached_login=1
i=0
while [ "$i" -lt "$TIMEOUT" ]; do
	if grep -q "login:" "$LOG" 2>/dev/null; then reached_login=0; break; fi
	kill -0 "$qpid" 2>/dev/null || { echo ">> qemu exited early"; break; }
	i=$((i + 2)); sleep 2
done

kill "$qpid" 2>/dev/null || true
wait "$qpid" 2>/dev/null || true

rc=0
if [ "$reached_login" -eq 0 ]; then
	echo ">> PASS: reached login prompt"
	if grep -qi "FrostBSD" "$LOG"; then echo ">> PASS: Frost banner present"; else echo ">> WARN: Frost banner not seen in serial log"; fi
else
	echo ">> FAIL: no login prompt within ${TIMEOUT}s"
	echo ">> last serial lines:"; tail -n 20 "$LOG" || true
	rc=1
fi
echo ">> serial log kept at $LOG"
exit "$rc"
