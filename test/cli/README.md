# CLI test files

This folder is a collection of original AmigaOS **CLI commands** used for
testing `vamos` against the real command-line programs. The files are taken
from the final **AmigaOS 3.2.3** state of the operating system.

The commands are the same binaries AmigaOS keeps in `C:`. Running them under
`vamos` exercises `dos.library`, `ReadArgs`, the `dos` handlers, the console,
`utility.library`, `math`, `expansion`, `resources`, ... with real m68k
programs instead of the hand-written `test/suite` programs.

## Copyright — do not commit

These files are **copyrighted AmigaOS binaries**. They are **never committed**
to this repository (`.gitignore` ignores `C`). Populate this folder locally
with the extraction script described below.

For CI they are bundled (encrypted) into `../blob.tar.zstd.enc` and restored
with `../blob_decode.sh`; see section 4 of `../README.md`. The same files are
listed in `../blob_files.txt`.

## Populating the folder

Run `extract-cli.py` with one or more sources. A source may be a folder
(scanned recursively) or an Amiga disk image (`.adf`, `.adz`, `.adf.gz`,
`.hdf`, `.hdz`, `.hdf.gz`, `.rdb`, `.rdisk`):

```sh
python3 test/cli/extract-cli.py \
    ~/Documents/FS-UAE/Floppies/AmigaOS3.2/Workbench3.2.adf \
    ~/Documents/FS-UAE/Floppies/AmigaOS-3.2.3/Update3.2.3/ADFs/Update3.2.3.adf
```

Pointing the script at a folder that contains all the disk images (for example
the whole `~/Documents/FS-UAE/Floppies` tree) also works. The script extracts
every known command it can find, verifies each one's SHA-1 against the expected
value below, and warns about any that are missing. Files stored `.Z` compressed
on the update disk are decompressed on the fly. By default the files are
written to `C/` next to the script; use `-o DIR` to change that.

The script exits with status `1` if any expected command is missing.

The extracted commands are marked **executable**, exactly like the real `C:`
drawer. AmigaDOS only runs a hostfs file whose host mode has the execute bit
set (the shell checks `fib_Protection` before `LoadSeg`), so without it the
`Shell-Seg` session and `Which` cannot use the fixture.

## Sources — AmigaOS 3.2 base + 3.2.3 update

Like the ARexx fixture, the final 3.2.3 state is the base **AmigaOS 3.2**
release overlaid by the **3.2.3 update**:

* base: `AmigaOS3.2/Workbench3.2.adf`, commands in `C/`;
* update: `AmigaOS-3.2.3/Update3.2.3/ADFs/Update3.2.3.adf`, commands in `C/`
  (several stored `.Z` compressed and decompressed on the fly).

The update replaces `AssignWedge`, `ConClip`, `DefIcons` and `IPrefs` and adds
`AmigaModel`, `CopyTooltypes`, `Group`, `GuessBootDev`, `MD5Sum`, `Owner`,
`ROMReserveLow` and `WBInfo`. Everything else still comes from the base 3.2
release. There is no separate `C/` drawer on the Extras disks.

## Expected files

`<version>` is the `$VER:` string of the binary; the SHA-1 describes the final
(decompressed) 3.2.3 file.

| file | version | source | SHA-1 |
|------|---------|--------|-------|
| `AddBuffers` | addbuffers 47.1 (28.11.2019) | Workbench 3.2, C/ | `b8bae93dc109c0bc18f87b372361cf44eb8046c2` |
| `AddDataTypes` | adddatatypes 47.2 (20.2.2020) | Workbench 3.2, C/ | `2f2c1c7f5bd6c9da41f383f94a4c0841ce63edb9` |
| `AmigaModel` | amigamodel 47.1 (17.8.2020) | 3.2.3 update, C/ | `d9a0aea9361f69e5a9bcb689314457a5a79fd6e9` |
| `Assign` | Assign 47.5 (30.1.2021) | Workbench 3.2, C/ | `7160378f7ab1a8d01dd023dc20318a0b1d11ae71` |
| `AssignWedge` | assignwedge 47.15 (26.10.2021) | 3.2.3 update, C/AssignWedge.Z | `1a9614b8bbe292245e9f132aaaf9915591678c61` |
| `Avail` | avail 47.1 (28.7.2019) | Workbench 3.2, C/ | `e2947b8456070341dde817298ed917d79dc22552` |
| `BindDrivers` | binddrivers 45.1 (12.4.2019) | Workbench 3.2, C/ | `738cd1481da486fe9863a21d39e52276e5f03c97` |
| `Break` | break 47.1 (28.11.2019) | Workbench 3.2, C/ | `04c35975cbf7a0790a90bd7d7927c2cdbdb8d233` |
| `ChangeTaskPri` | changetaskpri 47.1 (28.11.2019) | Workbench 3.2, C/ | `cfde61b5d9a94d6b77238c8ea9498a8a2826239b` |
| `ConClip` | conclip 47.6 (16.10.2021) | 3.2.3 update, C/ConClip.Z | `ff9950eb8f7a7897faaa9f808152522ad979f077` |
| `Copy` | Copy 47.7 (30.1.2021) | Workbench 3.2, C/ | `8d17b03b0cb92608e31c3da203d1afdf5d6c0a61` |
| `CopyTooltypes` | copytooltypes 47.1 (20.10.2019) | 3.2.3 update, C/ | `09dbf313267f2d4983c0abf381069e289508d4c6` |
| `CPU` | cpu 47.1 (19.10.2020) | Workbench 3.2, C/ | `339d3c13eff9d98ee373668c863c56fb660476fb` |
| `Date` | date 47.2 (14.12.2019) | Workbench 3.2, C/ | `28ae411c9fcada25598839710b3b566a6a726f0f` |
| `DefIcons` | deficons 47.9 (28.10.2021) | 3.2.3 update, C/DefIcons.Z | `1c3f8c72bf7335cd6094bdbfdcf067ac2a2b3dd7` |
| `Delete` | delete 47.2 (7.1.2020) | Workbench 3.2, C/ | `030191ef5fdfb185fca182bd286de30b39ae89bd` |
| `Dir` | dir 47.2 (19.12.2019) | Workbench 3.2, C/ | `9c4044d3e06697fdd68cd1add615c6e3ce8ff8fd` |
| `DiskChange` | diskchange 45.1 (13.4.2019) | Workbench 3.2, C/ | `650836abbddba51990ccb58cf847473c3ff85c99` |
| `Ed` | ed 47.2 (24.5.2020) | Workbench 3.2, C/ | `d19392f9e669eaee3aa41edbebc5d2cd46ac10f9` |
| `Eval` | Eval 47.2 (30.1.2021) | Workbench 3.2, C/ | `648fe7e4262b05716af6ff32ab4cb5aef38c93b7` |
| `Filenote` | filenote 47.1 (28.11.2019) | Workbench 3.2, C/ | `43c8a7f8840539b44050a933280d2b56845a7812` |
| `Group` | group 47.2 (10.12.2022) | 3.2.3 update, C/Group.Z | `6451090722636d3d9e69a975b8c8d1455cc7b0b0` |
| `GuessBootDev` | guessbootdev 45.2 (4.8.2019) | 3.2.3 update, C/ | `39d5acd6af505423330ed25b20e1862277e33849` |
| `IconX` | iconx 45.1 (18.11.2017) | Workbench 3.2, C/ | `4f49b2fa5531ae1a1851c21ee570b324c0c48437` |
| `Info` | Info 45.7 (27.5.2018) | Workbench 3.2, C/ | `2c9c98a4b7a576eb50c4b2b8f32ea6eeaa9fcabb` |
| `Install` | install 47.4 (19.7.2020) | Workbench 3.2, C/ | `5af5975ef92ec650bf6648cce9697a9a51d5fe42` |
| `IPrefs` | IPrefs 47.32 (7.11.2024) | 3.2.3 update, C/IPrefs.Z | `0c7c6cae81ef5c3d79cb72efe41add712970f0f4` |
| `Join` | join 47.2 (7.1.2021) | Workbench 3.2, C/ | `3b6b1fb2ec0dace4754d09a0079309248634323b` |
| `List` | list 47.19 (28.7.2020) | Workbench 3.2, C/ | `bae8df6ae7ea1ed00965f10ba01289b061179452` |
| `LoadResource` | loadresource 47.2 (24.5.2020) | Workbench 3.2, C/ | `5ed2503fe7e33b3c5b46ba4e7e2a952794248223` |
| `LoadWB` | loadwb 47.1 (1.2.2020) | Workbench 3.2, C/ | `3d02dd9e10a3bded701ba58f31e1a7423b1b78a0` |
| `Lock` | lock 47.1 (28.11.2019) | Workbench 3.2, C/ | `4194a3b434eded744a9a441c88379e7d284d0685` |
| `MakeDir` | makedir 47.1 (28.11.2019) | Workbench 3.2, C/ | `95ac383e94c1d20ea9a1df1cf0f2ded219d8d12d` |
| `MakeLink` | makelink 47.1 (28.11.2019) | Workbench 3.2, C/ | `f1d8d6e57c3942cc61a6603038084abc1d3652e1` |
| `MD5Sum` | MD5Sum 47.21 (16.3.2024) | 3.2.3 update, C/MD5Sum.Z | `7a34420776012dbbc7bd655cd032def6bdab9b82` |
| `Mount` | mount 47.2 (24.5.2020) | Workbench 3.2, C/ | `2d0a52eea75b0014ec88303947ebebf658e50a2d` |
| `Owner` | owner 47.2 (10.12.2022) | 3.2.3 update, C/Owner.Z | `54bafce8ee40e8bafa6dd3f11215cd1063745ecf` |
| `Protect` | protect 47.5 (11.4.2020) | Workbench 3.2, C/ | `9b26a63513e5b8c9ec1c2408e8d079c9b7b1040f` |
| `Relabel` | relabel 47.2 (7.1.2020) | Workbench 3.2, C/ | `b1ddad5f18df7c6abb81e77d17ee6159cccf4bf6` |
| `RemRAD` | remrad 47.1 (28.11.2019) | Workbench 3.2, C/ | `0485fdf28e02a901d45aabc5e1d3ac55623fd011` |
| `Rename` | Rename 47.3 (30.1.2021) | Workbench 3.2, C/ | `294c26dfaea572a873f0f830b46b121f9d94142f` |
| `RequestChoice` | requestchoice 45.3 (6.10.2018) | Workbench 3.2, C/ | `bf4c7f185f4c28bf84ee7872ac32b7de7423e3a5` |
| `RequestFile` | requestfile 45.3 (7.9.2018) | Workbench 3.2, C/ | `7fe5264a195246badc1f92ea7150ad86744c6ba9` |
| `ROMReserveLow` | RomReserveLow 47.1 (29.10.2024) | 3.2.3 update, C/ROMReserveLow.Z | `3066d15ae861c8eb60b523a6c043330dc59650e6` |
| `Search` | search 47.1 (28.11.2019) | Workbench 3.2, C/ | `72a6bbd06f4acca369ad01da2daadc5b940d744f` |
| `SetClock` | setclock 47.1 (28.11.2019) | Workbench 3.2, C/ | `abaff8bfc1a1d798aa3fc70499beb2ae075dd48a` |
| `SetDate` | setdate 47.1 (19.9.2019) | Workbench 3.2, C/ | `776441fae311743f9692e19c0c17b9a1126adcce` |
| `SetFont` | setfont 45.1 (20.4.2019) | Workbench 3.2, C/ | `895c3945eeee1d259c55775d4527c8df299be70d` |
| `SetKeyboard` | setkeyboard 47.1 (28.11.2019) | Workbench 3.2, C/ | `31884318765220bb3c3b79f84f946ade58b0ee70` |
| `SetPatch` | setpatch 47.4 (4.8.2020) | Workbench 3.2, C/ | `93dfc11808dcec0aaa0a8fc164c7cbb6f3cd7466` |
| `Sort` | sort 46.4 (22.4.2018) | Workbench 3.2, C/ | `a7692005073b8b59290dbad6b2905c9a379d68e3` |
| `Status` | status 47.1 (28.11.2019) | Workbench 3.2, C/ | `065742381ef0308f2d574835d74aa217dbe30735` |
| `Type` | type 47.3 (7.1.2021) | Workbench 3.2, C/ | `39ccf36f48f13772f0744bc98c42ee01e7a13984` |
| `Version` | version 47.3 (31.1.2021) | Workbench 3.2, C/ | `359f76f5843dee097c15f4bffce678a7c70e8d45` |
| `Wait` | wait 47.1 (28.11.2019) | Workbench 3.2, C/ | `0c16d8160a37575288310a4bbb86b9611666a5cf` |
| `WBInfo` | WBInfo 47.1 (21.9.2021) | 3.2.3 update, C/WBInfo.Z | `5b21931ef82f92abad4bb154b84a979700c3cc1b` |
| `WBLoad` | wbload 47.1 (28.11.2019) | Workbench 3.2, C/ | `12aceb32c2125442f6a5f6322c17fdbf6c8798fb` |
| `Which` | which 45.2 (30.12.2019) | Workbench 3.2, C/ | `408453c504fdcad87cf9b827ab672effe50d21b6` |

Total: **58** commands.

## Tests

The tests live in `../extra/cli_<prog>.py` (one module per command) and drive
the commands through `vamos` in `proc` mode:

```text
bin/vamos --no-ts -c test.vamosrc -Vcli:cli -p cli:C -- cli:C/<name> [args...]
```

They run **in-process** (`VamosRunner.run_prog`) and skip cleanly when the
fixture is absent. The shared helper is `../extra/cli_util.py`; a scratch
hostfs volume (`tmp_path`) is passed as `work:` for tests that need input or
output files.

`../extra/cli_shell.py` additionally runs the real AmigaOS shell
(`Shell-Seg-47.48` from `../shell-seg/`) through vamos' `shell` mode and feeds
it a script on stdin, so several commands run inside one session (command
search path, `RunCommand`, the prompt and the shell's error handling). It
skips when either the shell seg or the commands are missing.

## Status under vamos

The table below is kept in sync with `../extra/cli_*.py`. "works" means the
command ran to completion with the expected effect. Behavioral bugs are pinned
as `xfail` so the test flips to `xpass` once vamos is fixed; they are tracked
in the [vamos issue tracker](https://github.com/cnvogelg/amitools/issues).

| command | status |
|---------|--------|
| `Type`, `List`, `Dir`, `Copy`, `Delete`, `Rename`, `MakeDir`, `Join`, `Sort` | works |
| `Version`, `Avail`, `Eval`, `Date`, `Info`, `Wait`, `Lock`, `AddBuffers`, `SetDate`, `ChangeTaskPri`, `CPU`, `DiskChange`, `MD5Sum`, `Assign` | works |
| `Which` | works (the target must have the execute bit) |
| `AmigaModel`, `GuessBootDev`, `SetPatch`, `SetClock`, `RemRAD`, `ROMReserveLow`, `SetFont`, `RequestChoice` | works (the result reflects the vamos environment, e.g. no clock, no RAM disk) |
| `CopyTooltypes`, `Install` | works (error path only; there is no icon or installable disk) |
| `Ed`, `WBLoad` | works (argument check only; the real commands need a window) |
| `WBInfo` | works (the Workbench info window is stubbed; `FILE=`/`DRAWER=` complete) |
| `Relabel` | works (rc `0`); a hostfs volume's name is not persisted |
| `Break` | works (error path); breaking a real task needs a shell session |
| `Protect` (set) | works |
| `Protect` (no flags) | works (clears the owner bits; `Protect` has no display mode) |
| `Search` | works (matches case-insensitively) |
| `Filenote` | **xfail** — the note is not readable back on hostfs |
| `MakeLink` | **xfail** — cannot create a link |
| `Status` | **xfail** — no CLI process table to list |
| `Group`, `Owner` | **xfail** — hostfs returns `ERROR_NOT_IMPLEMENTED` |
| `LoadResource` | **xfail** — the task never terminates |
| `Mount` | **xfail** — needs `DEVS:MountList` |

## Not covered

The remaining commands cannot run to a meaningful result under `vamos`, so they
are deliberately left out (each reason is what a probe of the real 3.2.3 binary
showed):

* `AssignWedge`, `DefIcons` — the task never terminates (`did not terminate
  (state=TS_WAIT)`, rc `255`); they wait for an Intuition message port that
  `vamos` never delivers.
* `SetKeyboard` — the only path needs `keymap.resource`
  (`ERROR_INVALID_RESIDENT_LIBRARY`, rc `20`); the missing-argument path is
  still checked by the `cli_readargs` smoke test.
* `AddDataTypes`, `BindDrivers`, `ConClip`, `IconX`, `IPrefs`, `LoadWB`,
  `RequestFile` — they run but are no-ops: no output and nothing observable to
  assert (they return a bare rc `0`/`5`/`20`). `ConClip`, `IPrefs` and `LoadWB`
  wait for a Workbench that `vamos` does not provide.

Commands that *do* produce a deterministic result are covered above even when
they only reach their error path, because the error path is what `vamos` can
actually exercise today.
