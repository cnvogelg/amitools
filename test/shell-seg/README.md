# Shell-Seg test files

This folder is a collection of original AmigaOS **Shell-Seg** binaries used for
testing `vamos` (see `vamos -x Shell-Seg`) against different shell versions.

## Copyright — do not commit

These files are **copyrighted AmigaOS binaries**. They are **never committed**
to this repository (`.gitignore` ignores `Shell-Seg-*`). Populate this folder
locally with the extraction script described below.

## Populating the folder

Run `extract-shell-seg.py` with a folder of Amiga disk images and a folder of
Kickstart ROMs:

```sh
python3 test/shell-seg/extract-shell-seg.py \
    ~/Documents/FS-UAE/Floppies \
    ~/Documents/FS-UAE/Kickstarts
```

The script extracts every known shell it can find, verifies each one's SHA-1
against the expected value below, and warns about any that are missing. By
default the files are written next to the script; use `-o DIR` to change that.

* **Disk images** (`.adf`, `.adz`, `.adf.gz`, `.hdf`, `.hdz`, `.hdf.gz`,
  `.rdb`, `.rdisk`) are scanned recursively for files named `Shell-Seg`.
* **Kickstart ROMs** (`.rom`) are scanned recursively; the shell resident is
  pulled out of the ROM with amitools' module splitter. ROMs that are not in
  the split database are skipped.

The script exits with status `1` if any expected shell is missing.

## Expected files

`<version>` is the shell version from the binary's `$VER:` line. SHA-1 is used
because that is what the amitools tests already use for `Shell-Seg`.

| file              | shell   | AmigaOS       | source                                          | SHA-1                                      |
|-------------------|---------|---------------|-------------------------------------------------|--------------------------------------------|
| `Shell-Seg-1.3`   | 1.3     | 1.3           | disk (Workbench 1.3, no `$VER`)                 | `4bbe3ccb55fab49c83ff7ab52b2af277e6d92429` |
| `Shell-Seg-37.69` | 37.69   | 2.x           | ROM (Kickstart 37.175)                          | `40a54732afd46a4649e53088e722da0e0f4e6900` |
| `Shell-Seg-39.13` | 39.13   | 3.0           | ROM (Kickstart 39.106)                          | `0534b29813f87247d9bdd8f02c25e6ebe58fe699` |
| `Shell-Seg-40.2`  | 40.2    | 3.1           | ROM (Kickstart 40.68)                           | `02ba4b4368ed89177acfc17b45cbde4ae2062d2a` |
| `Shell-Seg-45.7`  | 45.7    | 3.9           | ROM (Kickstart 45.66, Cloanto "AmigaOS 3.X")    | `f091f33d28abe5c55de0e881d16861dfc703df01` |
| `Shell-Seg-46.10` | 46.10   | 3.1.4         | disk (`wb314_Modules_A*.adf`)                   | `8609de3b11da6b5d40d375a8d383fa2513316b28` |
| `Shell-Seg-47.47` | 47.47   | 3.2           | disk (`ModulesA*_3.2.adf`)                      | `0fe2a77ee989b343149f234ec7935aee2e0339f8` |
| `Shell-Seg-47.48` | 47.48   | 3.2.1–3.2.3   | disk (`ModulesA*_3.2.1.adf`)                    | `2be0093a67cacf6efec1258d5bd91db4ee7f1f6f` |

### Where each version lives

* **1.3** — `L/Shell-Seg` on the Workbench 1.3 disks (and identical copies on
  several boot disks). The binary carries no `$VER:` string.
* **2.x, 3.0, 3.1, 3.9** — the shell is a resident inside the Kickstart ROM;
  the Workbench disks / the 3.9 CD ship no `Shell-Seg` file on disk. The 3.9
  shell (45.7) comes from the Cloanto "AmigaOS 3.X" Kickstart 45.66 ROM.
* **3.1.4, 3.2, 3.2.1** — `L/Shell-Seg` on the Modules disks. 3.2.2 and 3.2.3
  ship the same 47.48 shell as 3.2.1.

### Notes

* The ROM-extracted files are reconstructed hunk images (single code hunk plus
  relocations), not the original on-disk layout — no on-disk copy exists for
  those versions. They still run under `vamos -x`.
* A different 3.1-era build `40.2 (ESCOM)` (SHA-1
  `f2614b0f06e5a37742ee77bbc2a0f3d4673b7193`) exists in the Walker 43.1 ROM and
  is intentionally not part of this set.

## Status under `vamos -x`

`test/extra/shell_seg.py` runs every collected seg through the `shell` mode
(`vamos -x --shell-bin seg:<name>`) and pins its exit code:

| shell   | runs | exit code |
|---------|------|-----------|
| 1.3     | no   | —         |
| 37.69   | yes  | 46        |
| 39.13   | yes  | 46        |
| 40.2    | yes  | 44        |
| 45.7    | yes  | 188       |
| 46.10   | yes  | 212       |
| 47.47   | yes  | 136       |
| 47.48   | yes  | 132       |

The 2.x–3.2.1 shells are C programs with a BCPL-compatible entry stub at
seglist `+8`. The stub ends with `jmp (a6)`, where `a6` is the address of the
BCPL return code (see RKRM-dos, "Runtime binding of BCPL programs").
`ShellProcess` points `a6` at the machine's exit trap, so the shell leaves the
process cleanly.

The 1.3 shell is a genuine BCPL program: its first long-word is a BCPL Global
Vector init offset, so it needs the `dos.library` BCPL Global Vector and the
BCPL call/return trampolines (`dl_A2`/`dl_A5`/`dl_A6`). None of that is
implemented in vamos yet, so its test is marked `xfail`.
