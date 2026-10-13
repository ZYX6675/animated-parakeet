# Hybrid OS (working name)

A lightweight Linux base that also runs Windows and macOS software through compatibility layers,
with open-source replacements for proprietary tools. See the roadmap doc for scope, phases, and
the Apple feasibility table.

## Status: Phase 0 and the start of Phase 3

| Piece | State |
| --- | --- |
| Clean-room policy | Draft in docs/CLEANROOM_POLICY.md, needs legal review |
| Format detection (ELF, PE, Mach-O, universal) | Working, tested on synthetic headers |
| Runtime picker (native, Wine, Darling) | Working in dry-run; prints the launch command |
| Recipe format and validator | Working; one illustrative example, no real compatibility claims. Recipes can only set a narrow allow-list (no LD_PRELOAD, PATH, and so on) |
| Recipe application | Working in dry run: first launch provisions the Wine prefix (wineboot, winetricks verbs), then runs with DLL overrides and env from the recipe |
| binfmt_misc registrations (`python -m osl.binfmt`) | Generated for PE and 64-bit Mach-O; universal Mach-O deliberately excluded (its magic collides with Java class files) |
| Base distribution | Arch Linux with Btrfs rollback, decided 2026-10-13 (docs/ISO_BUILD.md); earlier NixOS draft kept in docs/alternatives/nixos |
| archiso build, QEMU boot test, size check | Written but never run; first CI run is the real test |
| App-parity harness (`parity/`) | Working: round-trip, second-save, and fuzz checks for DOCX, XLSX, PPTX, PSD headers; tested with synthetic files and fake adapters only. Optional visual checks (render-and-diff pages) tested with fake renderers only (docs/PARITY.md) |
| Rollback design | Design only (docs/ROLLBACK.md) |
| License | Not chosen |

## Try it

```
python3 -m unittest discover -s tests -t . -v
python3 -m osl.cli /path/to/some/file          # dry run: shows runtime and command
python3 -m osl.cli --exec /path/to/file        # actually launches (needs wine or darling installed)
python3 -m osl.recipes recipes/*.json          # validate recipes
python3 -m osl.binfmt                          # print binfmt_misc lines for /etc/binfmt.d/
python3 -m parity run --adapter 'cp {input} {output}' --corpus DIR --out results/   # parity report
```

Windows apps each get their own Wine prefix (`~/.local/share/osl/prefixes/<name>-<hash>`).
Unsupported cases explain themselves, for example an Apple Silicon-only Mach-O binary on an x86-64
host. Nothing here is a compatibility claim: a recipe's status becomes `works` or `partial` only
with recorded evidence.

## Build (Arch Linux container or disposable VM only; the script refuses to run on a normal host)

```
iso/build.sh                       # pinned archiso build, output in out/
scripts/size-check.sh out/*.iso    # ISO size vs the 2 GiB limit
scripts/qemu-boot-test.sh out/*.iso  # headless QEMU boot, waits for a login prompt
```

## Layout

- `osl/` detection, runtime choice, recipes, CLI (standard library only)
- `parity/` app-parity harness (standard library only)
- `tests/` unit tests using synthetic samples and fake adapters
- `recipes/` per-app compatibility data
- `iso/` archiso overlay and build script
- `scripts/` size check and QEMU boot test
- `docs/` policy and build notes
