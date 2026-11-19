# AmigaDOS handler binaries

Real 68k AmigaDOS file system handlers used as fixtures by the native handler
tests (HANDLER.md step 23).

## pfs3aio

* url: https://aminet.net/package/disk/misc/pfs3aio
* version: 3.1
* sha256: `185fae785d0f6e15a1936ecb44e4cb18a21b6f701094c57edbd331e5f9a16047`

Used by `test/tools/rdbtool.py` (as the PFS3 file system to `fsadd`) and by the
native handler end-to-end test.
