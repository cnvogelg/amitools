# Change Log

## [0.8.0][8] (2024-03-03)

### global

* moved native part with CPU emulation to own project: machine68k
* moved to cython 3.x

### xdftool

* compute checksum correctly for large bootblocks (#199)
* 'add' option for read and write commands
* fixed bitmap dump
* fixed reading ffs+dircache images
* fixed 'time' command

### rdbtool

* only increase DosEnv size in PartitionBlock if needed

### romtool

* issue an error/warning if ROM was not written
* fixed build with kickety split

### hunktool

* show hunk allocation size memory attributes (#182)

### vamos

* handle holes in fd tables of libraries and set a dummy func
* added 68040 to doc
* fixed output after running sub shells


## [0.7.0][7] (2023-01-17)

### global

* Python 3.7 up to 3.11 supported and tested
* simplified install docs in README (#173)
* moved project to modern pyproject.toml setup
* use git version for project and docs
* typo fixes, cosmetics (#175) (#167) (#156) @reinauer

### xdftool

* improved bitmap allocation in writes significantly

### rdbtool

* added json output
* added `list` command
* in new rdbs: fixed the dos env size to honor the boot_blocks field

### romtool

* added padding when imported partition file is smaller than partition
* ext rom images can be 512/1536/3584KiB (#163) @reinauer
* Add support for 4MB ROMs (#160) @reinauer
* Fix 1mb_rom patch on 3.1.4 A500 (#154) @reinauer
* Update splitdata to ROMSplit 1.30 (23.12.2021) (#168) @reinauer
* Update splitdata from ROMsplit 1.28 (#162) @reinauer
* Update splitdata from Remus Datafiles Update 1.78u2 (#157) @reinauer

### vamos

* added RELRELOC32 support in hunk loader
* fixed AllocPooled when allocating larger chunks (Frank Wille)

### vamos internal

* alloc: cleaned up labels in API
* improved lock key handling
* improved ExNext keys
* updated musashi from upstream fc7a6fc6
* added proxy mgr to libctx
* do not expose lib_mgr to all lib ctx
* allow to use atypes in libcalls
* reworked vamos type system


## [0.6.0][6] (2021-04-13)

### global

* Requires Python 3.6 minimum
* Added Python 3.9 support
* Update README to py3 (#153)

### rdbtool

* added 'addimg', 'remap', and 'adjust' command

### xdftool

* py3 fix for delete with wipe

### vamos

* allow fd arguments in func impls
* added ctx func support for testing
* Allocate()/Deallocate() fixes (#152)
* dos.library fixes (@bebbo #151)
* import fixes (@bebbo #151)
* added ReadEClock in timer.device (@bebbo #151)
* added locale.library (@bebbo #151)
* fixed ExNext()
* fixed WriteChars()
* fixed closing console
* added support for 'endcli'
* dos ReadArgs() allow empty key (fixes 'echo')
* trace BADDR fixes
* updated Musashi to 4.10
* dos pattern match: fixed not-any patterns e.g. ~(#?.o)


## [0.5.0][5] (2020-06-13)

### global

* Requires Python 3.5 minimum
* Python 3.8 compatible (#132)
* Lots of Python 3 fixes
* vamos-test: renamed -V switch to -A
* xdf/rdbtool: allow to call main() with custom args and defaults
* use black for source code formatting
* introduced full test suite to limit tests in normal runs
* fixed reading HUNK_INDEX with empty unit names
* switched disasm to machine DisAsm

### xdftool

* added support for HD disk images
* in DOS5 (DirCache) fixed creating empty directories
* allow multiple open part commands in a single command list

### vamos

* fixed internal mem trace with -T
* use unbuffered I/O on ttys
* dos:ReadArgs: fixed prompt with '?'
* dos:Seek now sets IoErr correctly


## [0.4.0][4] (2019-11-2)

### global

* Moved to Python 3 (>= 3.4) (#86, #95)

### xdftool

* Fixed `read`/`write` with directories (#121)
* Fixed file name hashing when block size > 512 (#116)

### vamos

* Musashi m68k CPU emulator updated to v3.32 (@bebbo)
* Fixed `.ini` format detection if it starts with a comment ()


## [0.3.0][3] (2019-11-01)

### xdftool

* Filesystem bitmaps are cached now to speed up packing
* Pack/Unpack/Repack support for block size > 512 and DOS 6/7
* Use a new notation for timestamp ticks `.00`
* Auto open first partition when using a RDB image
* Added `ln`/`longname` as alias for DOS 6/7 when formatting
* Allow to unpack/pack with meta info stored in FS-UAE .uaem files
* Fixed packing of files with decomposed unicode names (#106)

### rdbtool

* Fixed geometry setup of large (>4GiB) images

### romtool

* Added new option to fix kick sum when copying (@daleking)


## [0.2.0][2] (2019-06-27)

### vamos

* Re-implemented dos ReadArgs() to be more compatible (#80)
* Re-implemented dos ReadItem() to be more compatible
* Fix exception when running in Vim (#77) (@zedr)
* added more tests to vamos-test suite
* Allow to SelectInput()/SelectOutput() with BNULL
* truncate inodes to 32 bit for fl_Key in Lock (workround for 64bit fs) (#72, #35)
* added dummy OpenResource() (@selco)
* added Uitlity's Amiga2Date(), Date2Amiga(), CheckDate() (@selco)
* added full math library support (double, single and ffp precision) (@selco)
* Added ExamineFH() (@bebbo)
* fix SDivMod32 (@bebbo)
* added Docker based toolchains for building test programs with vc, gcc6 and AROS gcc
* added profiling support
* machine: run code in user mode
* machine: do not pulse reset on every run
* allow to create temp volumes
* allow to auto create assign dirs
* machine: removed obsolete Trampoline (replaced by machine sub runs)
* complete rewrite of config infrastructure. added .json configs
* rewrote lib handling and support creation via MakeLibrary()
* replaced VamosRun with a machine layer
* honor cwd and progdir in OpenLibrary() calls
* added GetProgramDir()
* do not split command line args when parsing. fixed args with comma, parentheses.

### hunktool

* fixed loading of short relocations

### romtool

* fixed romtool to allow splitting ext ROMs
* updated split files to ROMsplit 1.25
* fixed scanning residents without name

### xdftool

* allow to format/work with partitions of arbitrary block size (>512 bytes) (>4GB FFS)
* fixed relabel command (@Zalewa)

### rdbtool

* added import/export partition image
* fixed init of empty disk

### misc

* started moving the docs to RST and ReadTheDocs
* added vamostool and refactored typetool and vamospath


## [0.1.0][1] (2017-08-03)

* First public release


[1]: https://github.com/cnvogelg/amitools/tree/v0.1.0
[2]: https://github.com/cnvogelg/amitools/tree/v0.2.0
[3]: https://github.com/cnvogelg/amitools/tree/v0.3.0
[4]: https://github.com/cnvogelg/amitools/tree/v0.4.0
[5]: https://github.com/cnvogelg/amitools/tree/v0.5.0
[6]: https://github.com/cnvogelg/amitools/tree/v0.6.0
[7]: https://github.com/cnvogelg/amitools/tree/v0.7.0
[8]: https://github.com/cnvogelg/amitools/tree/v0.8.0
