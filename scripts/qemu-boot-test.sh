#!/usr/bin/env bash
# Boot the ISO headless in QEMU and wait for a login prompt on the serial console.
# Usage: qemu-boot-test.sh file.iso    (needs qemu-system-x86_64 and bsdtar)
set -euo pipefail
iso="${1:?usage: qemu-boot-test.sh file.iso}"
timeout_s="${TIMEOUT:-300}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"; [ -n "${qpid:-}" ] && kill "$qpid" 2>/dev/null || true' EXIT

# Boot the kernel directly so we can add a serial console (the stock boot menu has none).
bsdtar -xf "$iso" -C "$tmp" arch/boot/x86_64/vmlinuz-linux arch/boot/x86_64/initramfs-linux.img
log="$tmp/serial.log"
kvm=()
[ -w /dev/kvm ] && kvm=(-enable-kvm)

qemu-system-x86_64 "${kvm[@]}" -m 2048 -no-reboot -display none -monitor none -serial "file:$log" \
  -cdrom "$iso" \
  -kernel "$tmp/arch/boot/x86_64/vmlinuz-linux" \
  -initrd "$tmp/arch/boot/x86_64/initramfs-linux.img" \
  -append "archisobasedir=arch archisolabel=HYBRIDOS console=ttyS0" &
qpid=$!

result=1
for ((t = 0; t < timeout_s; t += 2)); do
  if grep -q 'login:' "$log" 2>/dev/null; then result=0; break; fi
  if grep -q 'Kernel panic' "$log" 2>/dev/null; then break; fi
  kill -0 "$qpid" 2>/dev/null || break
  sleep 2
done

echo "--- last console output ---"
tail -n 25 "$log" || true
[ "$result" -eq 0 ] && echo "PASS: reached login prompt" || echo "FAIL: no login prompt"
exit "$result"
