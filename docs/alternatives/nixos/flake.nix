{
  description = "Hybrid OS: lightweight NixOS base with Windows and macOS compatibility layers";

  # Pin with `nix flake lock` and commit flake.lock. Switch to a stable release branch
  # (github:NixOS/nixpkgs/nixos-<YY.MM>) once you want slower, steadier updates.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      osl = pkgs.callPackage ./nix/osl.nix { };

      # The one module every image and test shares.
      baseModule = { ... }: {
        imports = [ ./nix/base.nix ];
        environment.systemPackages = [ osl ];
      };
    in
    {
      nixosModules.base = baseModule;

      nixosConfigurations.iso = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [ ./nix/iso.nix baseModule ];
      };

      packages.${system} = {
        inherit osl;
        iso = self.nixosConfigurations.iso.config.system.build.isoImage;
        default = self.packages.${system}.iso;
      };

      checks.${system} = {
        # Python unit tests for the launcher core.
        unit = pkgs.runCommand "osl-unit-tests" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          cp -r ${./.} src
          chmod -R u+w src
          cd src
          python3 -m unittest discover -s tests -t . -v
          python3 -m osl.recipes recipes/*.json
          touch $out
        '';

        # Boots the base in a QEMU VM and checks it reaches multi-user and runs the launcher.
        boot = pkgs.testers.runNixOSTest {
          name = "hybrid-os-boot";
          nodes.machine = { ... }: { imports = [ baseModule ]; };
          testScript = ''
            machine.wait_for_unit("multi-user.target")
            machine.succeed("osl-run --help")
            # Launcher should classify a tiny ELF file (a copy of /bin/sh) as native.
            machine.succeed("osl-run $(readlink -f /run/current-system/sw/bin/sh) | grep -q 'runtime: native'")
          '';
        };
      };
    };
}
