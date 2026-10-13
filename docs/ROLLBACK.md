# Rollback design (not yet implemented)

Goal: a bad update or a bad compatibility change can be undone from the boot menu.

## Layout

- Btrfs root with subvolumes: `@` (system), `@home`, `@snapshots`, `@log`, `@cache`.
  Keeping home, logs, and caches out of the root snapshot means a rollback does not erase user
  data or fill the disk with old logs.
- The kernel and initramfs must live **inside** the root subvolume, with the EFI system
  partition mounted at `/efi`. If the kernel sits on the FAT partition outside the snapshot,
  rolling the root back leaves a kernel that no longer matches the restored modules, and the
  system may fail to boot. (A per-generation unified kernel image is the other way to avoid this,
  and is what atomic-upgrade does.)

## Tooling for the first implementation

- Snapper for snapshot management, snap-pac for automatic snapshots around every pacman
  transaction, and grub-btrfs to list snapshots in the boot menu.
- A documented one-command rollback, tested in a QEMU CI job: install a package, snapshot,
  break something, boot the old snapshot, check the system is back.

## Open questions

- Bootloader: GRUB (reads Btrfs, works with grub-btrfs) versus systemd-boot with unified kernel images.
- Whether to adopt atomic-upgrade for chroot-isolated upgrades (young project, AGPL).
- How compatibility-layer state (Wine prefixes under home) is snapshotted separately from the system.
