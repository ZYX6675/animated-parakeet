#!/usr/bin/env bash
# Fail if the ISO is larger than the limit (default 2 GiB). Usage: size-check.sh file.iso [bytes]
set -euo pipefail
iso="${1:?usage: size-check.sh file.iso [limit-bytes]}"
limit="${2:-2147483648}"
size=$(stat -c %s "$iso")
echo "ISO size: ${size} bytes (limit ${limit})"
[ "$size" -le "$limit" ] || { echo "over the footprint target" >&2; exit 1; }
