#!/usr/bin/env bash
# Build the Phase 1 live ISO. Run as root inside an Arch Linux container or host.
# UNVERIFIED: written without access to Arch or archiso; expect small fixes on the first run.
set -euo pipefail

# This script rewrites /etc/pacman.d/mirrorlist and runs a full pacman -Syyuu (including downgrades).
# Run it only in a throwaway container or VM. Refuse otherwise unless explicitly overridden.
if [ ! -f /.dockerenv ] && [ ! -f /run/.containerenv ] && [ "${HYBRIDOS_ALLOW_HOST_BUILD:-}" != "1" ]; then
  echo "refusing to run outside a container: it would rewrite your pacman mirrorlist and re-sync packages." >&2
  echo "use a container (see .github/workflows/ci.yml) or a disposable VM, or set HYBRIDOS_ALLOW_HOST_BUILD=1." >&2
  exit 1
fi

repo="$(cd "$(dirname "$0")/.." && pwd)"
date_pin="$(tr -d '[:space:]' < "$repo/iso/ARCHIVE_DATE")"   # YYYY/MM/DD of an Arch Linux Archive snapshot
work="${WORK:-/tmp/hybridos-build}"
out="${OUT:-$repo/out}"

# 1. Pin the whole package set to a dated snapshot so the same inputs give the same ISO contents.
cat > /etc/pacman.d/mirrorlist <<MIRRORS
Server = https://archive.archlinux.org/repos/${date_pin}/\$repo/os/\$arch
MIRRORS
pacman -Syyuu --noconfirm --needed archiso python

# 2. Start from the stock baseline profile so boot files always match the installed archiso version.
rm -rf "$work"
mkdir -p "$work" "$out"
profile="$work/profile"
cp -r /usr/share/archiso/configs/baseline "$profile"

# 3. Overlay: extra packages, launcher files.
cat "$repo/iso/packages.extra" >> "$profile/packages.x86_64"
cp -r "$repo/iso/airootfs/." "$profile/airootfs/"
dest="$profile/airootfs/usr/local/lib/hybrid-os"
mkdir -p "$dest"
cp -r "$repo/osl" "$repo/recipes" "$dest/"
find "$dest" -name __pycache__ -prune -exec rm -rf {} +
cat >> "$profile/profiledef.sh" <<'PROFILE'
file_permissions+=(["/usr/local/bin/osl-run"]="0:0:755" ["/usr/local/bin/osl-open"]="0:0:755")
PROFILE

# 4. Fixed label and name (the boot test finds the ISO by this label).
sed -i 's/^iso_label=.*/iso_label="HYBRIDOS"/; s/^iso_name=.*/iso_name="hybrid-os"/' "$profile/profiledef.sh"

# 5. Build.
mkarchiso -v -w "$work/work" -o "$out" "$profile"
ls -l "$out"
