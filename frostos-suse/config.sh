#!/bin/bash
#
# config.sh — KIWI runs this inside the image root after packages install.
# Wires the Frost overlay in: services, Qoin user/dirs, MOTD, hardening.
#
set -euxo pipefail

#======================================
# systemd services
#--------------------------------------
systemctl enable qoind.service || true
systemctl enable NetworkManager.service || true
systemctl enable sshd.service || true            # off-by-default posture: mask if you prefer
# A security workstation shouldn't advertise sshd; uncomment to disable by default:
# systemctl disable sshd.service || true

#======================================
# Qoin core: user + data dir (the daemon also mkdir's this, belt & suspenders)
#--------------------------------------
getent group qoin  >/dev/null 2>&1 || groupadd -r qoin
getent passwd qoin >/dev/null 2>&1 || useradd -r -g qoin -d /var/lib/qoin -s /usr/sbin/nologin qoin
install -d -o qoin -g qoin -m 0750 /var/lib/qoin

#======================================
# Frost branding
#--------------------------------------
if [ -f /etc/motd.frost ]; then
    cp /etc/motd.frost /etc/motd
fi

#======================================
# Do NOT ship a known root password. Force a reset on first console login.
#--------------------------------------
passwd -l root || true
if command -v chage >/dev/null 2>&1; then
    chage -d 0 root || true
fi

#======================================
# clean up to shrink the image
#--------------------------------------
zypper clean -a || true
rm -rf /var/log/zypp /var/cache/zypp/* || true

exit 0
