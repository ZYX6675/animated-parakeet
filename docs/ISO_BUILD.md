# Base distribution: Arch Linux (revised 2026-10-13)

This replaces the earlier NixOS decision. The NixOS files are kept, unbuilt, in
`docs/alternatives/nixos/` in case the project wants them later.

## Why the change

The earlier case for NixOS rested on rollback, reproducible images, and built-in VM tests.
A fair counter-argument showed the rollback gap is smaller than first assumed, and the costs of
NixOS land on the project's most important feature, running other platforms' software:

- **Standard Linux layout.** Arch runs unpatched third-party Linux binaries as they are. NixOS
  needs a shim (`nix-ld`) and per-case fixes.
- **Current Wine, Proton, and Mesa.** Arch ships recent versions quickly, which matters for
  Windows compatibility.
- **Lower friction for contributors and users.** Arch's documentation and package ecosystem
  are large and familiar; Nix is a separate language and mental model.
- **Rollback is available.** Btrfs snapshots with Snapper give a boot-time undo (see ROLLBACK.md).

## What the Arch route does not give you

- **"Flawless" compatibility.** No distro gives that. Wine compatibility is per application,
  and anti-cheat and DRM limits are the same on every base. Arch removes packaging friction only.
- **Reproducibility by default.** Snapshots restore state; they do not make builds reproducible.
  We approximate it by building from a dated Arch Linux Archive snapshot (`iso/ARCHIVE_DATE`),
  so the same inputs give the same package set. This is weaker than a Nix lock file.
- **A declarative, single-file system definition.** Customization is by package lists and
  config files, not one evaluated configuration.
- **Safe rolling updates.** Arch can need manual steps after updates. Snapshots limit the damage
  but do not remove it.

## Rollback tooling: what to trust

| Option | Notes |
| --- | --- |
| Btrfs + Snapper (+ snap-pac, grub-btrfs) | Mature, widely used; snapshots before and after package changes, boot into a snapshot. Design in ROLLBACK.md |
| atomic-upgrade | Real, but young: [AUR package](https://aur.archlinux.org/packages/atomic-upgrade) first submitted Feb 2026, one maintainer, 1 vote at last check, AGPL-3.0, needs UKI and Secure Boot tooling. Its [announcement thread](https://bbs.archlinux.org/viewtopic.php?id=312664) describes upgrading in a chroot on a new snapshot, one snapshot-plus-boot-image pair per generation. Evaluate in Phase 2; not a Phase 1 dependency. Review the AGPL terms before bundling |

## What is in the repo now

- `iso/build.sh` builds a live ISO from archiso's stock baseline profile plus our overlay
  (the launcher, Python, btrfs-progs), pinned to the archive date.
- `scripts/qemu-boot-test.sh` boots the ISO headless in QEMU and waits for a login prompt
  on the serial console.
- `scripts/size-check.sh` fails if the ISO exceeds the size limit (default 2 GiB).
- CI: `python` (unit tests), `iso` (build in an Arch container), `boot-test` (QEMU).

## Status

The Arch build files were written without access to Arch, archiso, or QEMU and have not been run.
Likely trouble spots on the first run: whether the pinned archive date exists and its keyring
matches the container image, the baseline profile's file layout in the installed archiso version,
the kernel and initramfs paths inside the ISO, and the serial console login detection.

## Phase 1 exit criteria

- [ ] `iso` CI job builds an ISO
- [ ] `boot-test` CI job reaches a login prompt
- [ ] ISO boots on one real machine
- [ ] Size check passes
- [ ] `iso/ARCHIVE_DATE` confirmed to exist and documented as the pin to bump
