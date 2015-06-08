# AmigaOS Program Section in amitools

## Compiler Setup

amitools currently supports the following cross-compilers to create the
AmigaOS binaries:

  - gcc 2.95 with AmigaOS support
  - [vbcc](http://sun.hasenbraten.de/vbcc/) and [vasm]()
  - gcc 4.x with AROS m68k support
  - SAS C v6.52 Amiga version running in vamos (commercial)

### m68k-amigaos-toolchain

Krystian Baclawski's great script suite called
[m68k-amigaos-toolchain](https://github.com/cahirwpz/m68k-amigaos-toolchain)
allows to greatly simplify the installation of gcc 2.95 and vbcc cross on
*nix based plattforms.

#### Prerequisites

  - Mac OS X
    - Install [MacPorts](http://macports.org)
    - Install the following Ports:

```
> sudo port install wget lha unzip
```

#### Build

  - create a user accessible installation directory

```
> sudo mkdir -p /opt/m68k-amigaos
> sudo chown $USER /opt/m68k-amigaos
```

  - run build and install

```
> git clone https://github.com/cahirwpz/m68k-amigaos-toolchain
> cd m68k-amiga-toolchain
> (cd archives && ./fetch.sh)
> ./bootstrap.sh --prefix=/opt/m68k-amigaos build
```

  - add the bin directory to your PATH (also add to your shell startup)

      > export PATH=/opt/m68k-amigaos/bin:$PATH

### AROS

AROS now supports m68k directly and also provides a gcc 4.x based toolchain
to build m68k binaries

#### Prerequisites

  - Mac OS X
    - Install [MacPorts](http://macports.org)
    - Install the following Ports:

```
> sudo port install gawk gsed netpbm
```

#### Build

  - create a user accessible installation directory

```
> sudo mkdir -p /opt/m68k-aros
> sudo chown $USER /opt/m68k-aros
```

  - run build and install

```
> git clone http://repo.or.cz/AROS.git
> mkdir AROS-build
> cd AROS-build
> ../AROS/configure --target=m68k-amiga --with-aros-toolchain-install=/opt/m68k-aros
> make tools-crosstools
```

  - add the bin directory to your PATH (also add to your shell startup)

      > export PATH=/opt/m68k-aros:$PATH

