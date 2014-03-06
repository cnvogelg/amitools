# vamos - virtual Amiga OS

## The virtual AmigaOS runtime (aka Wine for Amiga :)

vamos is a tool that allows to run AmigaOS m68k binaries directly on your Mac
or PC. It emulates the AmigaOS by providing implementations for some functions
of the Exec and DOS library. It will run typical console binaries that do not
rely on user interface (intuition) or graphics stuff. Its main focus is to run
old compilers and assemblers to have some sort of "cross" compilers. This
approach will not run any applications or games using direct hardware register
access - for this a machine emulator like FS-UAE is the tool you will need...

vamos uses the native Musashi m68k CPU Emulator written in C to run m68k code.
I added a simple memory interface that provides some RAM space for the program
code and added an interface for python to trap library calls and emulate their
behavior in Mac OS.

# Features

* Fast m68k CPU emulation with Musashi CPU Emulator
* Supports native library loading for application libs (e.g. SAS sc1.library)
* Dos Library supports: Locks, Files (Open, Read, Write, Seek, Close)
* Exec Library supports: AllocMem/Vec, LoadLibrary
* Many useful tracing and logging features


## 1. Installation

vamos contains a native library for the CPU/memory emulation. This library
needs to be compiled first. All other code is python and runs directly out of
the box.

Build the library with:

    cd musashi
    make

This will create **libmusashi.so|.dylib** in this directory. Now you are ready
to run vamos from the top-level directory!


## 2. Setup

vamos uses a configuration file as source for setup information. It is usually
named **.vamosrc** and is first searched in the **$HOME** directory and then
in the current directory. You can also use the *-c* option to specify an own
config file. The config file uses the syntax of the well-known .ini files.

Additionally, you can specify the parameters also on the command line. These
will overwrite the settings specified in a config file.

In the source archive see *config/sample_vamosrc* for an example config file.

### 2.1 Volumes

vamos works internally with AmigaOS compatible file and path names. An AmigaOS
absolute path is usually rooted in a volume ("volname:abs/path/file"). vamos
automatically translates these paths to host (Mac/PC) system paths for file
access. This is done by specifying a volume to system path mapping.

In the config file the section volumes contains this mapping:

    [volumes]
    system=~/amiga/wb310
    home=~
    work=~/amiga/work
    shared=$HOME/amiga/shared

This example defines the volume names system:. home:, work:, and shared: and
assigns them native paths on the host computer.

Note that the native path may contain ~ for your home directory. Even $ENV
environment variable access is possible.

You can also specify volumes on the command line with:

    ./vamos -V system:~/amiga/wb310 -V work:. ..

By default vamos defines the root: volume name to be root of your file system
(/). So every host system path can be mapped to an Amiga path.

If multiple volumes share subtrees in the file system then the Amiga volume is
always assigned from the longest path match. E.g. in our example above the
path *~/amiga/wb310/c* is covered by *system:* and *home:* volume. The mapper
then takes the longest match and thus this path is converted to *system:c*.

### 2.2 Assigns

AmigaOS also allows to use assigns to introduce some kind of virtual volume
names that map to other amiga paths. Many applications use this mechanism to
find their install directory (sc:) or things like includes (include:) or libs
(lib:).

vamos adapts this mechanism and allows to define assigns yourself in the
config file or on the command line. The config file needs a section assigns:

    [assigns]
    sc=shared:sc
    include=sc:include
    lib=sc:lib
    c=system:c,sc:c

*Note*: an assign might reference other assigns and also allows to specify
multiple expansions seperated with commas.

*Note2*: assigns always map to amiga paths and never directly to system paths.
Mac system paths are only allowed when defining volumes.

On the command line assigns are given by *-a* options:

    ./vamos -a c:system:c -a lib:sc:lib ...

If an assign is specified in the config file and later on the command line
then the original assign in the config file is overwritten. You can extend an
assign by writing a plus sign right at the beginning of the mapping:

    ./vamos -a c:+cool:c

This example will extend the c: assign that might be already defined in the
config file and does not replace it.

### 2.2 Auto Assign

If an amiga path cannot be mapped to a Mac system path (because it uses
undefined volume or assign names) then vamos will abort. You will then have to
restart vamos and specify the required assign or volume mappings.

vamos also provides a feature called *Auto Assign*. If enabled then you assign a
single amiga path prefix. If vamos then finds an unknown assign it will not
abort vamos but implicitly map the assign to a directory in the given path
prefix.

In the config file write this:

    [path]
    auto_assign=system:

On the command line give the -A option:

    ./vamos -A system:

With this auto assign in place the unknown assign *t:* will be mapped to the
amiga path *system:t*


## 3. Usage Examples

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
