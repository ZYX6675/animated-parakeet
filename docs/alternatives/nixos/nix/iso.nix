# Phase 1 live ISO: the minimal installer image plus the shared base.
{ lib, modulesPath, ... }:

{
  imports = [ "${modulesPath}/installer/cd-dvd/installation-cd-minimal.nix" ];

  isoImage.isoName = lib.mkForce "hybrid-os-dev-x86_64.iso";
  isoImage.makeEfiBootable = true;
  isoImage.makeUsbBootable = true;
}
