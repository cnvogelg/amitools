# vamos - virtual Amiga OS

## Introduction: The virtual AmigaOS runtime (aka Wine for Amiga :)

vamos is a tool that allows to run AmigaOS m68k CLI binaries directly on your
Mac or PC. It emulates the AmigaOS by providing implementations for some
functions of the Exec and DOS library. It will run typical console binaries
that do not rely on user interface (intuition) or graphics stuff. Its main
focus is to run old compilers and assemblers to have some sort of "cross"
compilers.

This approach will not run any applications or games using direct hardware
register access - for this use case a machine emulator like FS-UAE is the tool
you will need...

Remember, vamos is an API level emulator and never will be a full Amiga system
emulator like WinUAE or FS-UAE!!

## Overview on the Building Blocks

vamos uses the native Musashi m68k CPU Emulator written in C to emulate m68k
code. I added a simple memory interface that provides some RAM space for the
program code and added an interface for python to trap library calls and
emulate their behavior in Python.

Every call to a library is trapped during execution and realized with own
Python code or simply ignored if no trap is defined.

All public in memory structures (e.g. ExecBase) are also provided. vamos
implements a memory handler to allocate and free structures used in the heap
of a program or for library data exchange.

## Status

While at the beginning, vamos was a work in progress and mostly a proof of
concept that proved to be very instructive and even fairly fast. Its a
playground for me to learn lots about AmigaOS, its binaries, its libraries and
how they work together...

With the help of many contributors it evolved into a useable CLI program
emulator today that runs many Amiga devtools and is even able to build complex
Amiga projects including AmigaOS itself!

## Features

* Fast m68k CPU emulation with Musashi CPU Emulator
* Supports native library loading for application libs (e.g. SAS sc1.library)
* Dos Library supports: Locks, Files (Open, Read, Write, Seek, Close)
* Exec Library supports: AllocMem/Vec, LoadLibrary
* Many useful tracing and logging features

## 1. Installation

See the `amitools` Installation README for further details.

## 2. Configuration

While some simply CLI programs run out of the box when using vamos, for
typical applications some setup is required.

You can either define the environment used to run your application directly
on the command line or by writing a `.vamsosrc` configuration file.

The vamos environment consists of:

  - DOS Setup
    - **volume mappings**
    - **assigns**
    - the command **path**
  - Exec Setup
    - **library** settings
  - Hardware Settings
    - CPU selection
    - Memory config
  - Vamos Settings
    - **emulation settings**
    - **diagnos/trace** options

### 2.0 Config Files

vamos uses a configuration file as source for setup information. It is usually
named **.vamosrc** and is first searched in the **$HOME** directory and then
in the current directory. You can also use the *-c* option to specify an own
config file. The config file uses the syntax of the well-known `.ini` files.

It consists of sections that are named in brackets, e.g. `[assigns]` followed
by a list of key value pairs on a line each: `key=value`

Additionally, you can specify the parameters also on the command line. These
will overwrite the settings specified in a config file.

Use the `-S` option on the command line to avoid loading any `.vamosrc` files
even if they exist. This option is useful for testing when a clean setup is
required.

In the source archive see *config/sample_vamosrc* for an example config file.

### 2.1 DOS Setup

#### 2.1.1 Volumes

AmigaOS uses **Volumes** to name(:) and identify the different file systems
found on an Amiga system. In vamos a Volume is defined as a part of the host
(i.e. Mac or PC) file system that will be exposed to the Amiga emulation.

You specify a volume by giving a **host directory path**. All files below this
path are considered to be part of the volume.

On the command line you use the `-V` switch (used multiple times to create
more volumes) and in the `vamosrc` config file you create a section called
`[volumes]`:

    vamos -V myvol:/sys/path/to/my/voldir

    [volumes]
    myvol=/sys/path/to/my/voldir

A default volume called **root:** is created automatically and represents the
root of your host's (Posix) file system. So every host file is mappable to the
vamos world by simply prepending **root:** to its absolute path.

While it is possible to map the same host file to different names in vamos
using overlapping volume mappings it is not recommended to do so. This also
means that files accessed by a custom volume should not also be used via
**root:**.

If multiple volumes share subtrees in the file system then the Amiga volume is
always assigned from the longest path match. E.g. in our example above the
path *~/amiga/wb310/c* is covered by *system:* and *home:* volume. The mapper
then takes the longest match and thus this path is converted to *system:c*.

Volume names are accessed like all other file paths in a case insenstive
manner inside vamos (just the way AmigaOS handles it). However, the host
directory path in the volume definition is case sensitive.

It makes sense to define a **sys:** volume as some AmigaOS calls default to
this volume.

A typical example:

    [volumes]
    system=~/amiga/wb310
    home=~
    work=~/amiga/work
    shared=$HOME/amiga/shared

As you see, tilde is allowed as a synonym for your home directory for system
paths. Also host environment variables can be expanded with a dollar sign.

#### 2.1.2 Assigns

AmigaOS uses **Assigns** to give paths inside AmigaOS a new name alias (E.g.
`c:` is a short hand for `sys:c` directory). An assign always maps a name to
an absolute Amiga path starting with a volume or starting with another assign
name.

In vamos assigns work similar: You specify an assign name and map it to an
absolute Amiga path. Please note: no host path (on Mac/PC) is used here!

On the command line you define an assign with the `-a` switch (repeated for
more assign definitions) and in the config file you create an `[assigns]`
section:

    -a myassign:sys:path/to/dir
    -a myalias:myassign:more/path

    [assigns]
    myassign=sys:path/to/dir
    myalias=myassign:more/path

Many applications use this mechanism to find their install directory (sc:) or
things like includes (include:) or libs (lib:).

A typical example looks like:

    [assigns]
    sc=shared:sc
    include=sc:include
    lib=sc:lib
    c=system:c,sc:c

Like AmigaOS vamos also supports **Multi Assigns**. This special type of
assign maps a single name to multiple paths. If a file is specified with a
multi assign path then vamos searches the file in all locations attached to
the multi assign.

On the command line you start defining a multi assign by first creating a
regular assign that maps a new name to a single absolute path. Then you add
more paths to the same name with consecutive mapping calls. Use the

    -a mymulti:sys:foo/bar
    -a mymulti:+sys:bar/baz

In the config file you specify the whole list on a line separated by commas.

    [assigns]
    mymulti=sys:foo/bar,sys:bar/baz

#### 2.1.3 Auto Assign

If an amiga path cannot be mapped to a Mac/PC system path (because it uses
undefined volume or assign names) then vamos will abort. You will then have to
restart vamos and specify the required assign or volume mappings.

vamos also provides a feature called *Auto Assign*. If enabled then you assign a
single amiga path prefix. If vamos then finds an unknown assign it will not
abort vamos but implicitly map the assign to a directory in the given path
prefix.

In the config file write this:

    [path]
    auto_assign=sys:

On the command line give the -A option:

    ./vamos -A sys:

With this auto assign in place the unknown assign *t:* will be mapped
automatically to the amiga path *sys:t*

#### 2.1.4 Command Path

Like the AmigaOS shell vamos searches commands on a list of AmigaOS paths
called **path**.

The path is defined either on the command line with:

    ./vamos -p sys:c,sc:c

Note a single list with absolute AmigaOS path seperated by comma is given.

In the config file you state:

    [path]
    path=sys:c,sc:c

#### 2.1.5 Current Working Directory

Each AmigaOS process has a current working directory assigned to it. In vamos
the cwd is automatically derived from the current host directory vamos was
launched from. This directory is mapped to AmigaOS and used as the cwd there.

If you want to specify another directory then use the command line to set
another Amiga path:

    vamos -d sys:ami/path

Or in config file:

    [vamos]
    cwd=sys:ami/path

#### 2.1.6 Permit Host Paths for Commands

When a command path is given to vamos it finally also searches if a host
path matches. If yes then the path is converted back to an Amiga path and
this one is used internally to locate the executable.

If you don't want this behaviour and if you want to enforce pure Amige paths
given on the vamos command line then set the option `pure_ami_paths`.

On the command line give the `-P`:

    vamos -P

or in the config file:

    [vamos]
    pure_ami_paths=True

### 2.2 Exec Setup

#### 2.2.1 Stack Size

The command run by vamos needs a stack of a certain size to run without any
issues.

By default the stack size is set to 4 KiB.

Use the command line switch `-s <KiB>` to set a new stack size.

    vamos -s 16

Or in the config write:

    [vamos]
    stack=16

#### 2.2.2 Library Settings

vamos allows you to control library loading in many ways. Please see
[vamos Libraries](vamos-lib.md) for details.

### 2.3 Hardware Settings

#### 2.3.1 CPU Selection

vamos can either emulate a 68000 (default) or a 68020 CPU. While the 68k
can only address memory with 24 Bits, the 020 has a full 32 Bit address
bus. Furthermore, the 020 has an extended instruction set.

| CPU        | Alias       | Remarks  |
| -----------|-------------|----------|
| 68000      | 00,000      | 24 Bit   |
| 68020      | 20,020      | 32 Bit   |
| 68030      | 30,030      | Fakes only AttnFlags in Exec, still a 020 |

On the command line use the `-C` switch:

    vamos -C 20

In the config file use:

    [vamos]
    cpu=68020

#### 2.3.2 Memory Size

vamos does not distinguish any memory types like a real Amiga does. It only
manages a single large blob of memory used for your command, its data and
the associated libraries.

Specify the max size with the `-m <KiB>` on the command line:

    vamos -m 8192

Or in the config file:

    [vamos]
    ram_size=8192

#### 2.3.3 Hardware Access Emulation

As an OS level emulator vamos does not need to emulate lower aspects of the
real Amiga like its custom chips or the CIAs. This is true to run OS-compliant
programs and libraries. Unfortunately, some popular programs while working
on API level most of the time perform some tasks by direct HW access.

To be able to run such tools vamos supports to emulate some simple access
patterns to the custom chips. Just enough to make some programs happy...

When talking about HW Access here I mean the range of the custom chips and
also the CIA addresses.

| Mode | Description |
|-----------|-------------|
| emu       | Emulate Access |
| ignore    | Ignore any access to the HW address ranges |
| abort     | Abort vamos on the first access of a HW range |
| disable   | No HW access detection at all |

Note: If you want to allocate more memory than ranging from adress 0 to the
beginning of the CIA range then you have to disable HW access completely.

Specify the hardware access mode of vamos on the command line:

    vamos -H emu

Or in the config file:

    [vamos]
    hw_access=disable

### 2.4 Vamos Settings

#### 2.4.1 Emulation Settings

TBD

#### 2.4.2 Diagnosis and Tracing

TBD

## 3. Run a Program with vamos

### 3.1 Program and Arguments

A typical vamos call to run a program looks like this:

    vamos ami_bin arg1 arg2 ...

with `ami_bin` being the Amiga binary and `arg1 arg2 ...` being command line
arguments for the binary.

If you want to pass vamos options then provide them before the Amiga binary:

    vamos -V myvol:~ ami_bin

If you want to use dashes (`-`) in your Amiga command line then terminate
the vamos option list with a double dash (`--`) first:

    vamos -V myvol:~ -- ami_bin -my-amiga-option

### 3.2 Program Search Path

The given `ami_bin` Amiga executable is searched for at a number of places:

  - if no local/abs path is given then the `path` is searched (see above)
  - or the current working directory
  - if a path is given then vamos tries to match an Amiga path first
  - finally a system path is matched that is later converted to an Amiga path
    automatically. (Disable this option with `pure_ami_paths=True)

### 3.3 Run a Shell

In addition to running regular Amiga executables, vamos is also capable to run
a real Amiga Shell.

As a binary you need an original `Shell-Seg` from a modern AmigaOS (e.g. 3.9).

Now run vamos with the `-x` switch and pass in the `Shell-Seg` as your Amiga
binary:

    vamos -x Shell-Seg
    0.SYS:>

If available the shell reads the file `S:Vamos-Startup` as its startup
configuration file.

## 4. Usage Examples

Pick an amiga binary (e.g. here I use the A68k assembler from aminet) and run it:

```
> ./vamos a68k
Source file name is missing.

68000 Assembler - version 2.71 (April 16, 1991)
Copyright 1985 by Brian R. Anderson
AmigaDOS conversion copyright 1991 by Charlie Gibbs.

Usage: a68k <source file>
 [-d[[!]<prefix>]]       [-o<object file>]
 [-e[<equate file>]]     [-p<page depth>]
 [-f]                    [-q[<quiet interval>]]
 [-g]                    [-s]
 [-h<header file>]       [-t]
 [-i<include dirlist>]   [-w[<hash size>][,<heap size>]]
 [-k]                    [-x]
 [-l[<listing file>]]    [-y]
 [-m<small data offset>] [-z[<debug start>][,<debug end>]]
 [-n]

Heap size default:  -w2047,1024
```

Yehaw! What has happened? Vamos loaded the amiga binary and ran it in the m68k
Emulation... The output you see was generated as output by a68k.

Let's enable some verboseness during operation:

```
> ./vamos -v a68k
19:14:26.661       main:   INFO:  setting up main memory with 1024 KiB RAM: top=100000
19:14:26.661       main:   INFO:  loading binary: test_bin/a68k
19:14:26.663       main:   INFO:  args:
 (2)
19:14:26.692       main:   INFO:  setting up m68k
19:14:26.694       main:   INFO:  start cpu: 002004
...
19:14:26.705       main:   INFO:  done (284836 cycles in 0.0025s -> 114.19 MHz, trap time 0.0083s)
```

Wow! The m68k in the emulation is running really fast: 114 MHz. The trap time
mentioned there is the time spent in the library emulation of vamos written in
Python...

You can have more info during runtime by enabling logging channels with *-l*
switch:

```
> ./vamos -l dos:info,exec:info a68k
19:18:10.840       exec:   INFO:  open exec.library V39
19:18:10.840        dos:   INFO:  dos fs handler port: fd0000
19:18:10.843       exec:   INFO:  SetSignals: new_signals=00000000 signal_mask=00003000 old_signals=00000000
19:18:10.845        dos:   INFO:  open dos.library V39
19:18:10.845       exec:   INFO:  OpenLibrary: 'dos.library' V0 -> [Lib:'dos.library',V0]
19:18:10.845        dos:   INFO:  Input: [FH:''(ami='<STDIN>',sys='',nc=False)@fe0000=B@3f8000]
19:18:10.845        dos:   INFO:  Output: [FH:''(ami='<STDOUT>',sys='',nc=False)@fe002c=B@3f800b]
19:18:10.845        dos:   INFO:  Open: name='*' (old/1005/rb) -> [FH:''(ami='*',sys='',nc=False)@fe0058=B@3f8016]
19:18:10.846       exec:   INFO:  SetSignals: new_signals=00000000 signal_mask=00003000 old_signals=00000000
Source file name is missing.
19:18:10.846        dos:   INFO:  Write([FH:''(ami='*',sys='',nc=False)@fe0058=B@3f8016], 00ffa0, 29) -> 29
19:18:10.846       exec:   INFO:  SetSignals: new_signals=00000000 signal_mask=00003000 old_signals=00000000
...
```

Now you see what library calls occurred and how they were handled by vamos.

Use *-L <file>* to redirect the logging into a file instead of stdout.

You can even look deeper inside the workings of vamos by enabling memory
tracing with *-t* (and *-T* for vamos' own memory accesses during traps) (You
have to specify *-t/-T* to enable memory tracing at all and then you will need
to enable the according logging channels to see the traces). Memory tracing
will catch each memory access of the CPU emulation and redirects it to vamos.
This is very slow! So enable it only for debugging:

```
> ./vamos -t -T -l mem:info a68k
19:23:36.033        mem:   INFO:  R(2): 00f7c6: 4e70        TRAP  [@00f5bc +00020a exec.library] -306 [51]
19:23:36.033        mem:   INFO:  R(2): 00f7c8: 4e75        TRAP  [@00f5bc +00020c exec.library] -304 [50]
19:23:36.033        mem:   INFO:  R(2): 00f6d0: 4e70        TRAP  [@00f5bc +000114 exec.library] -552 [92]
19:23:36.035        mem:   INFO:  R(2): 00f6d2: 4e75        TRAP  [@00f5bc +000116 exec.library] -550 [91]
19:23:36.035        mem:   INFO:  R(4): 00fa0c: 0000f4d8  Struct  [@00f5bc +000450 exec.library] ExecLibrary+276 = ThisTask(Task*)+0
19:23:36.035        mem:   INFO:  R(4): 00f570: 00000000  Struct  [@00f4d8 +000098 ThisTask] Process+152 = pr_CurrentDir(BPTR)+0
19:23:36.036        mem:   INFO:  R(4): 00f584: 00003d22  Struct  [@00f4d8 +0000ac ThisTask] Process+172 = pr_CLI(BPTR)+0
19:23:36.036        mem:   INFO:  R(4): 00f584: 00003d22  Struct  [@00f4d8 +0000ac ThisTask] Process+172 = pr_CLI(BPTR)+0
19:23:36.036        mem:   INFO:  R(4): 00f498: 00003d32  Struct  [@00f488 +000010 CLI] CLI+16 = cli_CommandName(BSTR)+0
19:23:36.037        mem:   INFO:  R(2): 00f832: 4e70        TRAP  [@00f5bc +000276 exec.library] -198 [33]
19:23:36.037        mem:   INFO:  R(2): 00f834: 4e75        TRAP  [@00f5bc +000278 exec.library] -196 [32]
19:23:36.043        mem:   INFO:  R(2): 00ff28: 4e70        TRAP  [@00fb74 +0003b4 dos.library] -54 [9]
...
```

Now you can see every trapped library call and even access to in memory
structures... That's very convenient for debugging! It even labels every
memory location with a source description (library, code segment) and shows
symbolic names of structure entries...

The lowest level is memory debugging on level debug. Then _every_ access to
memory is logged:

```
> ./vamos -t -T -l mem:debug a68k
19:26:47.022        mem:  DEBUG:  R(4): 000000: 00001ff8          [@000000 +000000 zero_page]
19:26:47.022        mem:  DEBUG:  R(4): 000004: 00002004          [@000000 +000004 zero_page]
19:26:47.022        mem:  DEBUG:  R(2): 002004: 48e7              [@002004 +000000 a68k:0:code]
19:26:47.023        mem:  DEBUG:  R(2): 002006: 7efe              [@002004 +000002 a68k:0:code]
19:26:47.023        mem:  DEBUG:  W(4): 001ff4: 00fc0000          [@001000 +000ff4 stack]
19:26:47.023        mem:  DEBUG:  W(4): 001ff0: 00fc0000          [@001000 +000ff0 stack]
19:26:47.023        mem:  DEBUG:  W(4): 001fec: 00000000          [@001000 +000fec stack]
19:26:47.023        mem:  DEBUG:  W(4): 001fe8: 00000000          [@001000 +000fe8 stack]
19:26:47.023        mem:  DEBUG:  W(4): 001fe4: 00fc0000          [@001000 +000fe4 stack]
19:26:47.023        mem:  DEBUG:  W(4): 001fe0: 00000000          [@001000 +000fe0 stack]
19:26:47.023        mem:  DEBUG:  W(4): 001fdc: 0000f484          [@001000 +000fdc stack]
19:26:47.023        mem:  DEBUG:  W(4): 001fd8: 00000000          [@001000 +000fd8 stack]
19:26:47.023        mem:  DEBUG:  W(4): 001fd4: 00000000          [@001000 +000fd4 stack]
19:26:47.024        mem:  DEBUG:  W(4): 001fd0: 00000000          [@001000 +000fd0 stack]
19:26:47.024        mem:  DEBUG:  W(4): 001fcc: 00000000          [@001000 +000fcc stack]
19:26:47.024        mem:  DEBUG:  W(4): 001fc8: 00000000          [@001000 +000fc8 stack]
19:26:47.024        mem:  DEBUG:  W(4): 001fc4: 00000000          [@001000 +000fc4 stack]
19:26:47.024        mem:  DEBUG:  R(2): 002008: 2448              [@002004 +000004 a68k:0:code]
19:26:47.024        mem:  DEBUG:  R(2): 00200a: 2400              [@002004 +000006 a68k:0:code]
19:26:47.024        mem:  DEBUG:  R(2): 00200c: 49f9              [@002004 +000008 a68k:0:code]
19:26:47.024        mem:  DEBUG:  R(4): 00200e: 0000d9c4          [@002004 +00000a a68k:0:code]
19:26:47.024        mem:  DEBUG:  R(2): 002012: 2c78              [@002004 +00000e a68k:0:code]
19:26:47.025        mem:  DEBUG:  R(2): 002014: 0004              [@002004 +000010 a68k:0:code]
19:26:47.025        mem:  DEBUG:  R(4): 000004: 0000f8f8          [@000000 +000004 zero_page]
...
```

This output is very useful to see all code fetches and have a look what code
is running now. Use a hunktool disassembly side-by-side to check out whats
going on or going wrong ;)

You can use the *-c* option to limit the program execution to a given number
of cycles to keep the output short...

That's it for now! Have fun playing with vamos!

EOF
