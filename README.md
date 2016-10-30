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
 - The following Python packages are required to build/install the tools:
   - [Cython][1] >= 0.21
 - All other packages are installed automatically, if missing:
   - [pytest][2]
   - [lhafile - FS Edition][3] (Optional: required to use lha file scanner)
 - First make sure to have the Python package installer ```pip```:
  - On Mac OS X using [MacPorts][4] (Tool is called ```pip-2.7``` here):
  ```
sudo port install py27-pip
sudo pip-2.7 install cython
```
  - On Linux Ubuntu:
  ```
sudo apt-get install python-pip
sudo pip install cython
```
   - On Windows with [MSYS2][5] (use x86_64 version if possible):
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
[2]: http://pytest.org
[3]: https://github.com/FrodeSolheim/lhafile
[4]: https://www.macports.org
[5]: https://sourceforge.net/p/msys2/wiki/Home/

## Installation

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
  without any installation. You need `setup.py` only to build the native library
  of vamos:
  ```
python setup.py build
```

## Contents

### Tools

  - [vamos](doc/vamos.md) **V)irtual AM)iga OS**

    The most ambitious project in the collection emulates the Amiga OS library
    API so that native m68k Amiga OS 1.x - 3.x binaries can be loaded and
    executed (think of Wine for Amiga :). With this approach only API conform
    programs can be run (i.e. no direct hardware access is possible).

    The goal is to run CLI programs relying on Exec and Dos library starting
    with a minimal set of implemented functions. But the design of vamos is
    flexible enough to add more libraries and more functions later on.

    Remember, vamos is and never will be a full Amiga system emulator like
    WinUAE or FS-UAE!!

    It uses the Hunk library of amitools to load and relocate the binary. A
    m68k CPU emulator is used to execute the code (here: Musashi emulator
    in native C with Python binding generated via Cython.

    Every call to a library is trapped during execution and realized with own
    Python code or simply ignored if no trap is defined.

    All public in memory structures (e.g. ExecBase) are also provided. vamos
    implements a memory handler to allocate and free structures used in the
    heap of a program or for library data exchange.

    Currently, this is a work in progress and mostly a proof of concept that
    is very instructive and even fairly fast. Its a playground for me to learn
    lots about Amiga OS, its binaries, its libraries and how they work
    together...

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


