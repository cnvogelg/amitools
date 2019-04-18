# vamos - Libraries

## Introduction

An Amiga program typically uses lot's of libraries: the OS API is provided
by them and also the application itself can place shared code inside
custom libs.

To allow vamos to emulate thoses programs it must be able to handle all kinds
of libraries. Next to Amiga's own libraries vamos also provides special
libs that replace OS libraries (including exec and dos) and implement its
functions in Python code that runs on the host directly. This allows vamos
to emulate the OS without the need for a real Kickstart ROM or Workbench disk
with the original m68k libs created by Commodore.

## Library Types

vamos distinguishes the following library types:

| Type  | Code | Description |
|-------|------|-------------|
| Amiga | m68k | original library from a real Amiga system |
| Vamos | Python | vamos library replacing original OS function |
| Fake  | - | vamos library with no actual implementation and dummy functions |

The **Vamos** and **Fake** libraries require an associated **.fd** file
for vamos otherwise the number of calls and the internal structure is not
known. Although these lib types are implemented in Python they will also
be realised in the emulated Amiga memory and appear as regular libaries to
the running program. While the **Vamos** library contains at least some
implemented functions, a **Fake** lib is totally empty, i.e. all functions
are implemented as a dummy returning 0 in `d0`.

## The Library Manager

vamos has a library manager that handles library loading, opening, closing
and expunging. The manager is called by the Vamos versions of exec's
`OpenLibray/OldOpenLibrary/CloseLibrary` calls.

### Lib Modes

To have fine control what the emulation of your progam in vamos is able to
use as a library, you can configure each requested library name to be handled
by the manager in one of the following modes:

| Mode | Description |
|:----:|-------------|
| off  | OpenLibray always returns NULL (existing libs are ignored) |
| auto (default) | Check for Vamos lib. If not found check for Amiga lib |
| vamos | Only check for Vamos lib. Ignore existing Amiga lib |
| amiga | Only check for Amiga lib. Ignore existing Vamos lib |
| fake | Create a Fake Vamos lib with dummy functions |

The lib modes define wether to actually look for a library and wether to
check for Amiga or Vamos libs.

### Expunge Modes

The library manager als handles expunging/removig of libraries. An expunge
operation can only take place if no program is using the library anymore,
i.e. our program was the last closer.

While in AmigaOS this operation is typically delayed until the system runs
out of memory, in vamos you have fine control on this behavior: you can
decide for each library individually when to expunge the lib.

vamos can handle the following expunge types:

| Expunge Mode | Description |
|:------------:|-------------|
| last_close (default) | Expunge the lib immediately after the last user closes it |
| no_mem | Like in AmigaOS expunge libs only if the system is running out of memory |
| shutdown | Expunge libs when vamos exits |

### Lib Path Mapping

The library name given in an `OpenLibrary()` call can be either a base name,
i.e. a library name without any path component or a library name prefixed
with either a relative (no `name:` at the beginning) or absolute path.

vamos currently applies the following path mapping to find the Amiga file name
of the library:

  - **base name** is searched:
    - with the `LIBS:` assign. A multi-assign is supported here and
      all locations of the multi-assign are searched for the lib
  - **relative path** is searched:
    - in the current working directory of the process emulated by vamos
  - **absolute path** is searched:
    - only at the given location

### Lib Versions

Each Amiga library has a version number that describes the function set that
is available. While real Amiga libraries already provides this version
information in the associated binary file, a Vamos library gets an abritrary
version attached. Typically you choose a version that roughly matches the
available feature set.

For internal available vamos libs a reasonable version is already preset. For
fake libraries it makes sense to provide the version in the configuration.

For all types of libraries it is possible to overwrite the provided version
in the configuration. The lib manager then uses this configured version to
match it against the version provided by the user in the `OpenLibrary` call.
I.e. you can pretend that a library is only an older version.

### Lib Profiling

To the measure the performance of the Vamos library replacements, a lib can
be created with profiling enabled. In this case the actual Python code to
perform a function is surrounded by measurement instructions. These
measurments give you detailed information on the execution time inside the
lib. However, this instrumentation is expensive and should only be enabled
for the libs you want to profile.

## Configuration

The library manager is configured in the main vamos configuration file `.vamosrc`.
You create sections for the different libs with their individual parameters.

## Lib Sections

The following library section types are supported:

| Section | Description |
|---------|-------------|
| *.library | A special section that defines the default values |
| foo.library | A library section with the base name of the lib (without any path) |
| path/to/foo.libray | A library section with a path prefix (both abs/rel) |

If a library name is passed to the lib manager from an `OpenLibrary()` call
then the configuration is searched in the following order:

  - if the library name contains a path: look for section with this path prefix
  - next search for a config with base name only
  - finally look for the default section (`*.library`)
  - if all fails use internal defaults provided by vamos

## Lib Options

Each lib section accepts the following option fields:

| Option | Values | Description |
|--------|--------|------|
| mode | `off`, `auto`, `amiga`, `vamos`, `fake` | Set the lib mode |
| expunge | `last_close`, `no_mem`, `shutdown | Set the lib expunge mode |
| version | `<number>, e.g. `39` | Pretend the library has this version |
| profile | True, False | Enable profiling of Vamos libs |

## Internal Vamos Defaults

The following config entries are provided initially by vamos. They can be
overwritten with own entries found in your configuration file.

| Section | Lib Mode | Version |
|---------|----------|---------|
| *.library | auto | 40 |
| exec.library | vamos | 40 |
| dos.library | vamos | 40 |

Note: **do not** replace the lib mode for `exec` and `dos`! vamos is not able
to run correctly if these libs are not of type Vamos.

## Example Config

    [icon.library]
    mode=fake
    version=40

    [68040.library]
    mode=off

    [dos.library]
    profile=True

    [libs/foo.library]
    mode=off

    [foo.library]
    mode=amiga
