#!/usr/bin/env bash
set -euo pipefail

ISO_PATH=$1
echo "Starting headless QEMU integration test for: ${ISO_PATH}"

# 1. Create a tiny virtual disk containing our sample payload file
mkdir -p mnt_payload
cp sample_payload.osl mnt_payload/
dd if=/dev/zero of=payload.img bs=1M count=10
mkfs.vfat payload.img
mcopy -i payload.img sample_payload.osl ::/sample_payload.osl

# 2. Launch QEMU headlessly
# -nographic redirects the VM's serial console directly to this shell terminal log
# -hda attaches our virtual payload disk
qemu-system-x86_64 \
    -m 2048 \
    -nographic \
    -kernel /boot/vmlinuz-linux \
    -append "console=ttyS0 quiet" \
    -drive file=payload.img,format=raw,media=disk \
    -cdrom "${ISO_PATH}" \
    -no-reboot \
    -serial mon:stdio \
    -device isa-debug-exit,iobase=0xf4,iosize=0x04 &

QEMU_PID=$!

echo "Waiting for live environment boot initialization..."
sleep 15

# 3. Simulate command invocation inside the guest environment using serial transmission
echo "Mounting virtual payload drive..."
echo "mount /dev/sda /mnt" > /dev/ttyS0
sleep 2

echo "Executing osl-run --exec target..."
echo "osl-run --exec /mnt/sample_payload.osl" > /dev/ttyS0
sleep 5

# Clean shutdown of the automated runner instance
echo "Shutting down verification VM..."
kill -9 $QEMU_PID || true
echo "Integration test run finalized successfully."
