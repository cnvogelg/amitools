# ARexx test files

This folder is a collection of original AmigaOS **ARexx** binaries and support
files used for testing ARexx support in `vamos`. The files are taken from the
final **AmigaOS 3.2.3** state of the operating system.

## Copyright — do not commit

These files are **copyrighted AmigaOS binaries**. They are **never committed**
to this repository (`.gitignore` ignores them). Populate this folder locally
with the extraction script described below.

For CI they are bundled (encrypted) into `../blob.tar.zstd.enc` and restored
with `../blob_decode.sh`; see section 4 of `../README.md`. The same files are
listed in `../blob_files.txt`.

## Contents

The folder mirrors the AmigaOS layout so the files can be dropped into a vamos
system directory or the matching assigns can be set up directly:

| path                       | what it is                                          | version             |
|----------------------------|-----------------------------------------------------|---------------------|
| `Libs/rexxsyslib.library`  | core ARexx library (message ports, parsing, host)   | `rexxsyslib 47.2`   |
| `Libs/rexxsupport.library` | ARexx support functions (`SHOWDIR`, `STATEF`, ...)  | `rexxsupport 47.2`  |
| `System/RexxMast`          | ARexx master/daemon that runs REXX scripts          | `RexxMast 47.2`     |
| `Classes/arexx.class`      | BOOPSI/ReAction ARexx class (`AREXX_*`)             | `arexx.class 47.3`  |
| `Rexxc/HI`                 | REXX host command                                   | `hi 45.1`           |
| `Rexxc/RX`                 | run a REXX script                                   | `rx 45.9`           |
| `Rexxc/RXC`                | compile a REXX script                               | `rxc 45.1`          |
| `Rexxc/RXLIB`              | list/create function libraries                      | `rxlib 45.1`        |
| `Rexxc/RXSET`              | set REXX environment variables                      | `rxset 45.1`        |
| `Rexxc/TCC`                | tokenise/compile helper                             | `tcc 45.1`          |
| `Rexxc/TCO`                | tokenise helper                                     | `tco 45.1`          |
| `Rexxc/TE`                 | tokenise/expand helper                              | `te 45.1`           |
| `Rexxc/TS`                 | tokenise helper                                     | `ts 45.1`           |
| `Rexxc/WaitForPort`        | wait for a REXX port to appear                      | `waitforport 45.1`  |

The `Rexxc` commands are what AmigaOS keeps in `SYS:Rexxc` and adds to the
command `Path`; the `REXX:` assign points at `S:` where REXX scripts live. On
the Workbench disk the commands sit in a top-level `Rexxc` drawer.

## Populating the folder

Run `extract-arexx.py` with one or more sources. A source may be a folder
(scanned recursively) or an Amiga disk image (`.adf`, `.adz`, `.adf.gz`,
`.hdf`, `.hdz`, `.hdf.gz`, `.rdb`, `.rdisk`):

```sh
python3 test/arexx/extract-arexx.py \
    ~/Documents/FS-UAE/Floppies/AmigaOS3.2 \
    ~/Documents/FS-UAE/Floppies/AmigaOS-3.2.3/Update3.2.3/ADFs
```

Pointing the script at a single folder that contains all the disk images (for
example the whole `~/Documents/FS-UAE/Floppies` tree) also works.

The script extracts every known file it can find, verifies each one's SHA-1
against the expected value, and warns about any that are missing. Files stored
`.Z` compressed on the update disks are decompressed on the fly. By default the
files are written next to the script; use `-o DIR` to change that.

The script exits with status `1` if any expected file is missing.

## Sources — AmigaOS 3.2 base + 3.2.3 update

ARexx was left almost untouched for the whole AmigaOS 3.2 line. Only two files
were replaced by the 3.2.3 update, both shipped `.Z` compressed:

* `Libs/rexxsupport.library` — `47.1` (3.2) → **`47.2`** (3.2.3), on
  `Update3.2.3.adf`
* `Classes/arexx.class` — `47.1` (3.2) → **`47.3`** (3.2.3), on
  `Classes3.2.3.adf`

Everything else still comes from the base **AmigaOS 3.2** release, in
particular:

* `Libs/rexxsyslib.library`, `System/RexxMast` and the `Rexxc/*` commands come
  from `Workbench3.2.adf`.
* `Classes/arexx.class` is on `Classes3.2.adf` in the base release and is
  overridden by the 3.2.3 update.

## Expected files

SHA-1 is used because that is what the amitools tests already use for original
AmigaOS binaries. All hashes describe the final **3.2.3** state.

| file                       | version  | AmigaOS | source                                       | SHA-1                                      |
|----------------------------|----------|---------|----------------------------------------------|--------------------------------------------|
| `Libs/rexxsyslib.library`  | 47.2     | 3.2     | disk (`Workbench3.2.adf`, `Libs/`)           | `54982a5e9919097050c3fe56cb319e20763e6326` |
| `Libs/rexxsupport.library` | 47.2     | 3.2.3   | disk (`Update3.2.3.adf`, `LIBS/rexxsupport.library.Z`) | `d0d25ee6584eba401f62f18de7758e6fb886ed31` |
| `System/RexxMast`          | 47.2     | 3.2     | disk (`Workbench3.2.adf`, `System/`)         | `c5ff779e18ea2d15275f62ccab5746b2d66d2d5d` |
| `Classes/arexx.class`      | 47.3     | 3.2.3   | disk (`Classes3.2.3.adf`, `Classes/arexx.class.Z`) | `a4dd6d7051bf73dfd62c87c3a4e70447ac4f2617` |
| `Rexxc/HI`                 | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `8c0be07a0a339f1386d55431cbfa1562349b8772` |
| `Rexxc/RX`                 | 45.9     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `cb62bb549d954f889b46faf00e8655975eea3a89` |
| `Rexxc/RXC`                | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `f143b053179a100758f9e1943ae5fec1410513e5` |
| `Rexxc/RXLIB`              | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `ad6ed8b0adb785cd81f334a302ba3195a4b35370` |
| `Rexxc/RXSET`              | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `361ee72cf92846c40d1b1b1726e05d7e53cba5eb` |
| `Rexxc/TCC`                | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `765c34d8a57367dba79925f97014a50040a962ec` |
| `Rexxc/TCO`                | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `8864f978ddfd47d88ccc6c591e899e682f86b081` |
| `Rexxc/TE`                 | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `b0daae98210379c522eec5ceae38d68ae2fc3757` |
| `Rexxc/TS`                 | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `13b27bd330fd0cd47b4006ecd8bbb14c843a727b` |
| `Rexxc/WaitForPort`        | 45.1     | 3.2     | disk (`Workbench3.2.adf`, `Rexxc/`)          | `cf2a4fdbe02c712d7db36a86acda2936ffc46a48` |

### Notes

* The libraries report their version in the resident/library structure rather
  than in a `$VER:` string; the versions above are taken from the binary.
  `rexxsyslib.library` also carries the `ARexx Version 1.15` marker.
* `rexxmathlib.library` is **not** shipped with AmigaOS 3.2/3.2.3, so it is
  intentionally not included.
* The 3.2.3 update archives (`AmigaOS-3.2.3.lha`) only ship release notes for
  ARexx; the binaries themselves live on the update ADFs inside that archive
  (`ADFs/Update3.2.3.adf`, `ADFs/Classes3.2.3.adf`).
