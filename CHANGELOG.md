# Change Log

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
