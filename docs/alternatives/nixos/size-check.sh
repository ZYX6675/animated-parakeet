#!/usr/bin/env bash
# Fail if the installed system closure exceeds the footprint target (default 2 GiB).
set -euo pipefail
limit="${1:-2147483648}"
bytes=$(nix path-info -S ".#nixosConfigurations.iso.config.system.build.toplevel" | awk '{print $2}')
echo "system closure: ${bytes} bytes (limit ${limit})"
if [ "${bytes}" -gt "${limit}" ]; then
  echo "over the footprint target" >&2
  exit 1
fi
