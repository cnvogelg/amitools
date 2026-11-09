# amitools - AmigaOS tools for other platforms

[![PyPI](https://img.shields.io/pypi/v/amitools)](https://pypi.org/project/amitools/)
[![Python](https://img.shields.io/pypi/pyversions/amitools)](https://pypi.org/project/amitools/)
[![Docs](https://readthedocs.org/projects/amitools/badge/?version=latest)](https://amitools.readthedocs.io/)
[![Tests](https://github.com/cnvogelg/amitools/actions/workflows/test.yml/badge.svg)](https://github.com/cnvogelg/amitools/actions)

`amitools` is a set of command line tools and Python libraries for working
with classic Amiga disk images, file systems, Kickstart ROMs, icons and
executables on macOS, Linux and Windows. Its centrepiece, `vamos`, runs
AmigaOS command line programs directly on the host by emulating the 68k CPU
and the AmigaOS API.

The tools target the classic 680x0 Amiga with AmigaOS 1.x to 3.x and are
written for developers, so a background in Amiga programming helps.

- Documentation: <https://amitools.readthedocs.io/>
- Source and issues: <https://github.com/cnvogelg/amitools>
- Releases: <https://pypi.org/project/amitools/>, [change log](CHANGELOG.md)

## Installation

`amitools` supports Python 3.11 through 3.15 and can be installed with `pip`
or [uv](https://docs.astral.sh/uv/).

### Tools only

```bash
pip install amitools
```

This installs the pure Python package: all tools except `vamos` work out of
the box.

### With vamos

`vamos` needs the 68k CPU emulator from the
[machine68k](https://github.com/cnvogelg/machine68k) package, which the
`vamos` extra pulls in:

```bash
pip install 'amitools[vamos]'
```

`machine68k` is a C extension published as a source package, so a C compiler
has to be available (Xcode command line tools on macOS, `gcc` on Linux,
Visual Studio Build Tools on Windows).

With uv, install the command-line tools in an isolated environment:

```bash
uv tool install amitools
```

To include `vamos` and its emulator dependency:

```bash
uv tool install 'amitools[vamos]'
```

### Latest development version

```bash
pip install -U git+https://github.com/cnvogelg/machine68k.git
pip install -U git+https://github.com/cnvogelg/amitools.git
```

Repeat the commands to update. The development version has the newest
features but may be unstable from time to time.

### Optional packages

- [lhafile](https://github.com/FrodeSolheim/python-lhafile) lets the file
  scanners look inside `.lha` archives.
- [pypng](https://pypi.org/project/pypng/) is needed by `icontool` to import
  and export PNG images.

## Tools

| Tool | Purpose | Docs |
| --- | --- | --- |
| `xdftool` | Create, inspect and modify ADF and HDF disk images: format, list, read, write, delete, pack and unpack whole images, boot blocks, bitmaps | [xdftool](https://amitools.readthedocs.io/en/latest/tools/xdftool.html) |
| `xdfscan` | Scan single images or whole directory trees of ADF/HDF files and verify their file systems | [xdfscan](https://amitools.readthedocs.io/en/latest/tools/xdfscan.html) |
| `rdbtool` | Create and edit hard disk images and devices with a Rigid Disk Block: partitions, file system drivers, geometry | [rdbtool](https://amitools.readthedocs.io/en/latest/tools/rdbtool.html) |
| `romtool` | Scan, split, patch and build Kickstart ROM images for emulators, soft kickers and flash ROMs | [romtool](https://amitools.readthedocs.io/en/latest/tools/romtool.html) |
| `icontool` | List and batch edit Workbench `.info` icon files: tool types, positions, structure fields, PNG import and export | [icontool](https://amitools.readthedocs.io/en/latest/tools/icontool.html) |
| `vamos` | Run AmigaOS command line programs on the host: the **V**irtual **Am**iga **OS** | [vamos](https://amitools.readthedocs.io/en/latest/vamos.html), [reference](https://amitools.readthedocs.io/en/latest/vamos-ref.html), [libraries](https://amitools.readthedocs.io/en/latest/vamos-lib.html) |
| `vamospath` | Convert between AmigaOS and host paths using a vamos configuration | |
| `vamostool` | Helpers around vamos: path conversion, type inspection, library profile dumps and state file info | |
| `hunktool` | Load and dump Amiga Hunk executables, libraries, object files and overlays | |
| `typetool` | Inspect the AmigaOS C structure definitions vamos uses | |
| `fdtool` | Read Commodore's `.fd` function description files and dump them in several formats, including vamos' code structures | |
| `geotool` | Detect and compute disk geometries (cylinders, heads, sectors) for image files and sizes | |

Every tool prints its usage with `-h` or `help`.

### Quick examples

```bash
# list a floppy image, then read a file from it to the current directory
xdftool wb310.adf list
xdftool wb310.adf read c/dir

# create a new disk, format it and copy a file in, all in one command line
xdftool test.adf format "My Image" + makedir c + write myfile c

# create a 10 MiB RDB hard disk image with one partition
rdbtool work.hdf create size=10Mi + init + fill

# check a whole directory tree of disk images
xdfscan my_disks

# show what is inside a Kickstart ROM
romtool scan kick31.rom -i

# run an Amiga program; -V maps a host directory to an Amiga volume
vamos -V work:/path/to/dir myprog
```

## Python libraries

The tools are built on packages you can use in your own code:

| Package | Contents |
| --- | --- |
| `amitools.fs` | OFS and FFS file systems, block devices and image files, Rigid Disk Blocks and partitions |
| `amitools.binfmt` | Readers for Amiga Hunk binaries (`binfmt.hunk`) and the ELF subset used by AROS m68k (`binfmt.elf`), with relocation |
| `amitools.rom` | Kickstart ROM parsing, splitting and building |
| `amitools.icon` | Workbench `.info` icon files |
| `amitools.fd` | Parser for `.fd` function description files |
| `amitools.scan` | Scanners that walk file trees, `.lha` archives and disk images |
| `amitools.vamos` | The vamos runtime: machine, memory, scheduler, library and device implementations |

The vamos library API is described in the
[library documentation](https://amitools.readthedocs.io/en/latest/vamos-lib.html).

## Development

Clone the repository and set up an editable install with the development and
test requirements:

```bash
git clone https://github.com/cnvogelg/amitools.git
cd amitools
make init
```

`make init` installs `machine68k` from its git repository, the test and
documentation tools, and `amitools` itself in editable mode, so edits in the
tree take effect immediately.

To set up the same environment with uv, create and activate a virtual
environment, then install the existing development and test requirements:

```bash
uv venv
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
uv pip install -r requirements-dev.txt -r requirements-test.txt -e .
```

### Tests

The unit tests run in a few seconds:

```bash
pytest test/unit
```

`pytest test` also runs the vamos test suite, which executes the prebuilt
Amiga test programs under vamos and compares their output with recordings
from real Amigas; add `--full-suite` for the slow tests as well. `make test`
runs everything through `tox` for all supported Python versions. Rebuilding
the test programs needs the cross compilers described in
[test/README.md](test/README.md).

### Publishing releases

The `Build and publish Python distributions` workflow builds a source
archive and a pure Python wheel, checks their metadata, runs the test suite,
and smoke-tests the installed command line tools. Pull requests and manual
runs retain the packages as workflow artifacts without publishing them.

To enable publishing, create the `pypi` and `testpypi` environments in the
GitHub repository. Configure a trusted publisher for the `amitools` project
on each index using owner `cnvogelg`, repository `amitools`, workflow
`publish-to-pypi.yml`, and the matching environment name. PyPI and TestPyPI
require separate publisher registrations; no API tokens are needed. See
the [PyPA setup guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
for registration details.

After setup, pushes to upstream `main` publish development builds to
TestPyPI. Pushing a `v*` release tag publishes the source archive and wheel
to both PyPI and TestPyPI after the build and tests pass. The two uploads
are independent, so a TestPyPI outage does not block a PyPI release.
Publishing is disabled in forks.

Versions come from Git tags via `setuptools-scm`. Development builds omit
the local Git hash suffix so package indexes accept them. TestPyPI skips
files that are already present, allowing a workflow to be rerun. PyPI
releases require a new version if that version has already been uploaded.

### Code style and docs

The code is formatted with [Ruff](https://docs.astral.sh/ruff/formatter/):
`make format`. The documentation is Sphinx; `make docs` builds it into
`build/docs/html`.

### Contributing

Bug reports and pull requests are welcome on
[GitHub](https://github.com/cnvogelg/amitools). Please add a unit test for a
fix where possible and run `ruff format .` before submitting.

## License and authors

`amitools` is written by Christian Vogelgsang <chris@vogelgsang.org>, with
contributions from many others, and is licensed under the GNU General Public
License version 2 or later.
