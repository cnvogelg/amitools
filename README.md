# amitools - various AmigaOS tools for other platforms

 - written by Christian Vogelgsang <chris@vogelgsang.org>
 - under the GNU Public License V2

## Introduction

amitools is a collection of (currently python 2.x only) tools that I've
written to work with Amiga OS binaries and files on Mac OS X. But they
should work on all other platforms supporting Pythons, too.

I focus with my tools on classic Amiga setups, i.e. a 680x0 based system with
Amiga OS 1.x - 3.x running on it. However, this is an open project, so you can
provide other Amiga support, too.

The tools are mostly developer-oriented, so a background in Amiga programming
will be very helpful.

## Prerequisites

 - Python 2.7.x is currently supported
 - pip

### Optional Packages

 - If you want to rebuild the C extension or work on the Git repo then you need:
   - [Cython][1] >= 0.21
 - Optional Package:
   - [lhafile - FS Edition][2] (Optional: required to use lha file scanner)

### Install pip

 - First make sure to have the Python package installer ```pip```:

#### macOS

 - On macOS using [MacPorts][3] (Tool is called ```pip-2.7``` here):
```
sudo port install py27-pip
sudo pip-2.7 install cython
```

#### Linux/Ubuntu

 - On Linux Ubuntu use the provided packages ```python-pip```
  ```
sudo apt-get install python-pip
sudo pip install cython
```

#### Windows

 - On Windows with [MSYS2][4] (use x86_64 version if possible):
   - Install with exe installer
   - Initial update is done with: (Open shell first)
```
pacman -Sy
pacman --needed -S bash pacman msys2-runtime
```
   - Now close shell and re-open a new dev shell (```MinGW-w64 Win64 Shell```)
```
pacman -Su
pacman -S mingw-w64-x86_64-python2-pip mingw-w64-x86_64-gcc git make
```

[1]: http://cython.org
[2]: https://github.com/FrodeSolheim/lhafile
[3]: https://www.macports.org
[4]: https://github.com/msys2/msys2/wiki

## Installation

### The Easy Way

```
pip install amitools
```

Note: requires a host C compiler to compile the extension.

### Developers

 - Clone the Git repo: [amitools@git](https://github.com/cnvogelg/amitools)

 - You have multiple variants to install the tools with Python's `setuptools`:
 - **Global Install** is available for all users of your system and needs root privileges
```
sudo python setup.py install
```
 - **User Install** is available for your user only but does not require special privileges
```
python setup.py install --user
```
 - **Developer Setup** only links this code into your installation and allows
   you to change/develop the code and test it immediately. (I prefer user install here)
```
python setup.py develop --user
```
 - **Run In Place** allows you to run the binaries directly from the `bin` directory
   without any installation. You need `make` only to build the native library
   of vamos:
```
python setup.py build_ext -i
```
or simply
```
make
```

## Contents

### Tools

  - [vamos](doc/vamos.md) **V)irtual AM)iga OS**

    vamos allows you to run command line (CLI) Amiga programs on your host
    Mac or PC. vamos is an API level Amiga OS Emulator that replaces exec
    and dos calls with its own implementation and maps all file access to
    your local file system.

  - [xdftool](doc/xdftool.txt)

    Create and modify ADF or HDF disk image files.

  - [xdfscan](doc/xdfscan.txt)

    Scan directory trees for ADF or HDF disk image files and verify the contents.

  - [rdbtool](doc/rdbtool.txt)

    Create or modify disk images with Rigid Disk Block (RDB)

  - [romtool](doc/romtool.md)

    A tool to inspect, dissect, and build Amiga Kickstart ROM images to be
    used with emulators, run with soft kickers or burned into flash ROMs.

  - hunktool

    The hunktool uses amitools' hunk library to load a hunk-based amiga
    binary. Currently, its main purpose is to display the contents of the
    files in various formats.

    You can load hunk-based binaries, libraries, and object files. Even
    overlayed binary files are supporte.

  - typetool

    This little tool is a companion for vamos. It allows you to dump and get
    further information on the API C structure of AmigaOS used in vamos.

  - fdtool

    This tool reads the fd (function description) files Commodore supplied for
    all of their libraries and dumps their contents in different formats
    including a code structure used in vamos.

    You can query functions and find their jump table offset.


### Libraries

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


