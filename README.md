# amitools - various AmigaOS tools for other platforms

- written by Christian Vogelgsang <chris@vogelgsang.org>
- under the GNU Public License V2

## Introduction

`amitools` is a collection of Python 3 tools that I've written to work with
*Amiga OS* binaries and files on macOS and all other *nix-like platforms
supporting Python. Windows might work as
well, but is heavily untested. However, patches are welcome.

I focus with my tools on classic Amiga setups, i.e. a 680x0 based system with
Amiga OS 1.x - 3.x running on it. However, this is an open project, so you can
provide other Amiga support, too.

The tools are mostly developer-oriented, so a background in Amiga programming
will be very helpful.

## Prerequisites

- Python >= ```3.8```
- [pip3][1]

### Optional Packages

- [lhafile - FS Edition][2]: required to use ```.lha``` file scanner
- [machine68k][3]: required to run `vamos`

[1]: https://pip.pypa.io/en/stable/installation/
[2]: https://github.com/FrodeSolheim/python-lhafile
[3]: https://github.com/cnvogelg/machine68k/

## Installation

### Stable/Release Version

If you only need the tools without `vamos` then you can install the pure
Python version:

```bash
pip3 install amitools
```

If you want to run `vamos` then you need the CPU emulator from the `machine68k`
package and you can install this dependency with:

```bash
pip3 install 'amitools[vamos]'
```

Note:

- on Linux/macOS may use ``sudo`` to install for all users
- the version may be a bit outdated. If you need recent changes use the
  current version.

### Current Version from GitHub

If you wan to run `vamos` then first install the CPU emulator `machine68k`:

```bash
pip3 install -U git+https://github.com/cnvogelg/machine68k.git
```

Then install `amitools` directly from the git repository:

```bash
pip3 install -U git+https://github.com/cnvogelg/amitools.git
```

Note:

- This will install the latest version found in the github repository.
- You find the latest features but it may also be unstable from time to time.
- Repeat this command to update to the latest version.

### Developers

- Follow this route if you want to hack around with the amitools codebase
- Clone the Git repo: [amitools@git](https://github.com/cnvogelg/amitools)
- Ensure you have Cython and `machine68k` installed:

```bash
pip3 install cython machine68k
```

- Enter the directory of the cloned repo and install via pip:

```bash
pip3 install -U -e .
```

This install `amitools` in your current Python environment but takes the
source files still from this repository. So you can change the code there
and directly test the tools.

## Contents

The new Documentation of `amitools` is hosted on [readthedocs][4]

### Tools

- [vamos](docs/vamos.md) **V)irtual AM)iga OS**

  vamos allows you to run command line (CLI) Amiga programs on your host
  Mac or PC. vamos is an API level Amiga OS Emulator that replaces exec
  and dos calls with its own implementation and maps all file access to
  your local file system.

  Note: `vamos` requires the package `machine68k` installed first!

- [xdftool][5]

  Create and modify ADF or HDF disk image files.

- [xdfscan][6]

  Scan directory trees for ADF or HDF disk image files and verify the contents.

- [rdbtool][7]

  Create or modify disk images with Rigid Disk Block (RDB)

- [romtool][8]

  A tool to inspect, dissect, and build Amiga Kickstart ROM images to be
  used with emulators, run with soft kickers or burned into flash ROMs.

- hunktool

  The hunktool uses amitools' hunk library to load a hunk-based amiga
  binary. Currently, its main purpose is to display the contents of the
  files in various formats.

  You can load hunk-based binaries, libraries, and object files. Even
  overlayed binary files are supported.

- typetool

  This little tool is a companion for vamos. It allows you to dump and get
  further information on the API C structure of AmigaOS used in vamos.

- fdtool

  This tool reads the fd (function description) files Commodore supplied for
  all of their libraries and dumps their contents in different formats
  including a code structure used in vamos.

  You can query functions and find their jump table offset.

[4]: https://amitools.readthedocs.io/
[5]: https://amitools.readthedocs.io/en/latest/tools/xdftool.html
[6]: https://amitools.readthedocs.io/en/latest/tools/xdfscan.html
[7]: https://amitools.readthedocs.io/en/latest/tools/rdbtool.html
[8]: https://amitools.readthedocs.io/en/latest/tools/romtool.html

### Python Libraries

- Hunk library ```amitools.binfmt.hunk```

  This library allows to read Amiga OS loadSeg()able binaries and represent
  them in a python structure. You could query all items found there,
  retrieve the code, data, and bss segments and even relocate them to target
  addresses

- ELF library ```amitools.binfmt.elf```

  This library allows to read a subset of the ELF format mainly used in
  AROS m68k.

- .fd File Parser ```amitools.fd```

  Parse function descriptions shipped by Commodore to describe the Amiga APIs

- OFS and FFS File System Tools ```amitools.fs```

  Create or modify Amiga's OFS and FFS file system structures

- File Scanners ```amitools.scan```

  I've written some scanners that walk through file trees and retrieve the
  file data for further processing. I support file trees on the file system,
  in lha archives or in adf/hdf disk images
