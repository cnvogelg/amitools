# AmigaDOS handler binaries

Real 68k AmigaDOS file system handlers used as fixtures by the native handler
tests (`test/unit/handler_native_e2e.py`, HANDLER.md steps 23 and 28). They are
checked in so the tests run offline; `./download.sh` (re)creates and verifies
them from their upstream sources.

Run the download script after cloning or to refresh a fixture:

```sh
test/handler/download.sh
```

It needs an LHA unpacker for the two Aminet archives: the `lha` command (on
`$PATH`, or set `$LHA` to its path) or Python's `lhafile`
(`pip install lhafile`).

## pfs3aio

* url: https://aminet.net/package/disk/misc/pfs3aio
* version: 3.1
* sha256: `185fae785d0f6e15a1936ecb44e4cb18a21b6f701094c57edbd331e5f9a16047`
* dos type: `PFS\3` (`0x50465303`)

Used by `test/tools/rdbtool.py` (as the PFS3 file system to `fsadd`) and by the
native handler end-to-end test.

## SmartFilesystem

* url: https://aminet.net/disk/misc/SFS.lha
* version: 1.279 (`Smartfilesystem/AmigaOS3.x/L/SmartFilesystem` in the archive)
* sha256: `c7dd174131035a0f5845be1076fb5c55642f6aa2125d4b5d8c029b141dcc8205`
* dos type: `SFS\0` (`0x53465300`)
* requires a 68020 or better, so its test case runs on a 68020 machine
* does **not** implement `ACTION_DIE` (it replies `ERROR_ACTION_NOT_KNOWN` and
  stays in its main loop forever), so the manager force-tears it down and its
  test case skips the orphan-set assertion — see the note in
  `test/unit/handler_native_e2e.py`

## FastFileSystem

* url: https://github.com/reinauer/FastFileSystem (release `v0.2`, asset
  `FastFileSystem.OS3`)
* version: v0.2
* sha256: `2c66aeaa747a0ba3b4e40281663d5de2b99c1345987d510d5ce4a3d1453d0b7a`
* dos type: `DOS\3` (`0x444F5303`, FFS); supports DOS\0–DOS\5
