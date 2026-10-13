#!/usr/bin/env bash
set -euo pipefail

ISO_PATH="${1:?Usage: $0 <path-to-iso>}"
RUN_DIR="$(mktemp -d)"
SERIAL_LOG="$RUN_DIR/serial.log"
PAYLOAD_IMG="$RUN_DIR/payload.img"
QEMU_BIN="${QEMU_BIN:-qemu-system-x86_64}"

cleanup() {
  if [ -n "${QEMU_PID:-}" ] && kill -0 "$QEMU_PID" 2>/dev/null; then
    kill "$QEMU_PID" 2>/dev/null || true
    wait "$QEMU_PID" 2>/dev/null || true
  fi
  rm -rf "$RUN_DIR"
}
trap cleanup EXIT

if ! command -v "$QEMU_BIN" >/dev/null 2>&1; then
  echo "QEMU not found: $QEMU_BIN"
  exit 1
fi

echo "Starting headless QEMU integration test for: ${ISO_PATH}"

# 1. Create a tiny virtual disk containing our sample payload file.
cp sample_payload.osl "$RUN_DIR/"

dd if=/dev/zero of="$PAYLOAD_IMG" bs=1M count=16 status=none
mkfs.vfat -n PAYLOAD "$PAYLOAD_IMG" >/dev/null
mcopy -i "$PAYLOAD_IMG" "$RUN_DIR/sample_payload.osl" ::/sample_payload.osl

# 2. Launch QEMU headlessly using the generated ISO itself as the boot source.
# QEMU on GitHub-hosted runners does not permit direct writes to /dev/ttyS0,
# so we capture the guest serial console in a file instead of interacting with
# the host serial device.
"$QEMU_BIN" \
  -m 1024 \
  -machine accel=tcg \
  -display none \
  -monitor none \
  -serial file:"$SERIAL_LOG" \
  -append "console=ttyS0 rw" \
  -drive file="$PAYLOAD_IMG",format=raw,media=disk \
  -cdrom "${ISO_PATH}" \
  -boot d \
  -no-reboot &

QEMU_PID=$!

# 3. Wait for the guest to boot far enough to emit recognizable console output.
# This validates the ISO boot path without depending on host kernel files or
# direct access to the runner's serial devices.
for _ in $(seq 1 36); do
  if grep -Eqi 'login:|root@|archiso|HYBRIDOS|Welcome' "$SERIAL_LOG" 2>/dev/null; then
    echo "QEMU boot verification succeeded."
    exit 0
  fi

  if ! kill -0 "$QEMU_PID" 2>/dev/null; then
    echo "QEMU exited before the guest finished booting."
    sed -n '1,200p' "$SERIAL_LOG" || true
    exit 1
  fi

  sleep 5
done

echo "Timed out waiting for guest boot output."
sed -n '1,200p' "$SERIAL_LOG" || true
exit 1
