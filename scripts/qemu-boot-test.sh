#!/usr/bin/env bash
# Boot the ISO headless in QEMU and wait for a login prompt on the serial console.
# Usage: qemu-boot-test.sh file.iso      (needs qemu-system-x86_64 and bsdtar)
# Env:   TIMEOUT (seconds, default 600)   SERIAL_LOG (keep the console log at this path)
set -euo pipefail

iso="${1:?usage: qemu-boot-test.sh file.iso}"
timeout_s="${TIMEOUT:-600}"
tmp="$(mktemp -d)"
qpid=""
cleanup() { [ -n "$qpid" ] && kill "$qpid" 2>/dev/null || true; rm -rf "$tmp"; }
trap cleanup EXIT

log="${SERIAL_LOG:-$tmp/serial.log}"
: > "$log"

# The archiso initramfs finds the boot medium by the ISO's volume label, so read it from the ISO.
label="$(dd if="$iso" bs=1 skip=32808 count=32 2>/dev/null | tr -d '\0' | sed 's/ *$//')"
[ -n "$label" ] || { echo "could not read the ISO volume label" >&2; exit 1; }

if ! bsdtar -xf "$iso" -C "$tmp" arch/boot/x86_64/vmlinuz-linux arch/boot/x86_64/initramfs-linux.img; then
  echo "could not extract kernel and initramfs; ISO contents:" >&2
  bsdtar -tf "$iso" | head -40 >&2
  exit 1
fi

kvm=()
if [ -w /dev/kvm ]; then kvm=(-enable-kvm); echo "KVM available: hardware acceleration on"
else echo "no KVM: software emulation, expect a slow boot"; fi
cmdline="archisobasedir=arch archisolabel=${label} console=ttyS0,115200"
echo "ISO: $iso  label: $label"
echo "kernel command line: $cmdline"

qemu-system-x86_64 "${kvm[@]}" -m 2048 -no-reboot -display none -monitor none -serial "file:$log" \
  -cdrom "$iso" \
  -kernel "$tmp/arch/boot/x86_64/vmlinuz-linux" \
  -initrd "$tmp/arch/boot/x86_64/initramfs-linux.img" \
  -append "$cmdline" &
qpid=$!

result=1
for ((t = 0; t < timeout_s; t += 2)); do
  if grep -q 'login:' "$log" 2>/dev/null; then result=0; break; fi
  if grep -q 'Kernel panic' "$log" 2>/dev/null; then echo "kernel panic detected"; break; fi
  kill -0 "$qpid" 2>/dev/null || { echo "QEMU exited early"; break; }
  [ $((t % 30)) -eq 0 ] && [ "$t" -gt 0 ] && echo "still waiting (${t}s)..."
  sleep 2
done

echo "--- last console output ---"
tail -n 80 "$log" || true
if [ "$result" -eq 0 ]; then
  echo "PASS: reached a login prompt"
else
  echo "FAIL: no login prompt within ${timeout_s}s"
  if [ ! -s "$log" ]; then echo "hint: no serial output at all, so the kernel did not start or the console is not ttyS0"
  elif grep -qi 'label\|not found\|timed out waiting for device' "$log"; then echo "hint: the initramfs may not have found the boot medium by label '$label'"; fi
fi
exit "$result"
