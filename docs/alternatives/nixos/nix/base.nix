# Phase 1 base: boots, has networking, and nothing else.
# Every package added here is a deliberate decision (the "bloat-free" rule).
{ config, lib, pkgs, ... }:

{
  system.stateVersion = lib.mkDefault "25.11";

  networking.hostName = "hybridos";
  networking.networkmanager.enable = lib.mkDefault true;

  # Keep the image small: no docs, no man pages, no suggestions.
  documentation.enable = false;
  documentation.nixos.enable = false;
  programs.command-not-found.enable = false;
  environment.defaultPackages = lib.mkForce [ ];

  # Flakes on, so the system is reproducible and rollback is one command.
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Run unpatched third-party Linux binaries (an ELF file downloaded from the web).
  # NixOS lacks a standard /lib by default, so this compatibility shim is needed.
  programs.nix-ld.enable = true;

  # Phase 2 adds the desktop. Phase 3 adds Wine/Proton and binfmt_misc registration.
}
