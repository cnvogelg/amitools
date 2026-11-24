# ARexx on vamos: feasibility review & implementation plan

Scope: run the **real AmigaOS ARexx environment** on vamos — the REXX
interpreter/host library `rexxsyslib.library`, the `RexxMast` daemon, the
`Rexxc` command set and (later) the BOOPSI `arexx.class`.

Chosen approach: **native execution** of the original AmigaOS 3.2.3 binaries,
*not* a Python reimplementation of REXX. Feasibility is confirmed: the library
loads and initialises natively under vamos today; the remaining work is a
concrete, bounded list of emulation gaps (see *Findings* / *Plan*).

Test fixtures already exist in `test/arexx/` (see `test/arexx/README.md`); the
binaries are copyrighted and are never committed (gitignored, like
`test/shell-seg/`).

## Status

The command-line path works end-to-end: `RX` launches `RexxMast`, the
`RexxMaster` daemon lives across calls, and a `REXX:` script runs to completion.

```sh
python3 -m amitools.tools.vamos --no-ts \
    -Varexx:$PWD/test/arexx -alibs:arexx:Libs \
    -a REXX:arexx:S -p arexx:System,arexx:Rexxc \
    arexx:Rexxc/RX SCRIPT=hello.rexx
# ARexx Version 1.15
# Copyright © 1987 by William S. Hawes
# All Rights Reserved
# Hello from ARexx
# 1+2= 3
```

| gap | state | fix |
|-----|-------|-----|
| G1 `AllocDosObject(DOS_CLI)` | done | `alloc_cli_struct()` allocates/fills the CLI string buffers |
| G2 child start context | done | same root cause as G1 (see below) |
| G3 daemon lifetime vs `run_sub_process` | done | `run_sub_process` runs the command as a real scheduler task |
| G4 console windows | works headless | `CON:` maps to host stdio, no extra work needed for `RX` |
| G5 `REXX:` script lookup | done | genuine ARexx `/*` requirement, see below |

Remaining known limitations are listed under *Open questions / risks*.

## Background: how ARexx is structured

ARexx is not a single program but a small client/server runtime:

- **`rexxsyslib.library`** (~35 KB) is the interpreter and the host-side API.
  It exposes the classic V33 message/argstring calls (`CreateRexxMsg`,
  `FillRexxMsg`, `CreateArgstring`, …), the V45 host calls
  (`CreateRexxHostPort`, `GetRexxVarFromMsg`, `LaunchRexxScript`, …) and the
  V47 `GetRexxBufferFromMsg` (see `FD/rexxsyslib_lib.fd`). It also *prints the
  interpreter banner* (`ARexx Version 1.15 …`) during its own init.
- **`RexxMast`** is the daemon. It is a launcher that forks a persistent
  `RexxMaster` process, which owns the public message port **`REXX`** and loops
  on `WaitPort`/`GetMsg`/`ReplyMsg`. Clients talk to it by sending REXX
  messages to that port.
- **`RX`** (and the other `Rexxc/*` commands) is a client. It opens
  `dos.library`, `icon.library` and `rexxsyslib.library` (V45), does
  `FindPort("REXX")`, and — if the server is not running — calls
  `Execute("rexxmast", NULL, fh)` and retries. Its argument template is
  `SCRIPT=NAME/K,CMD/K,ARG/F`; it opens
  `CON://640/100/Rx Output/AUTO/CLOSE/WAIT` for output.
- **`arexx.class`** is the BOOPSI/ReAction class that lets GUI applications
  register an ARexx port (`AREXX_*` attributes) and dispatch commands. It is
  not needed for the command-line `RX` path but is needed for full Workbench
  compatibility.

This client/server design is important for the plan: to run a script we do not
need the whole Workbench, only (a) the native library, (b) the `RexxMaster`
daemon task living across calls, and (c) working message ports + signals
between tasks.

## Approach

**Native execution.** Load the original 68k `rexxsyslib.library` through
vamos's native-library manager (`libnative/`, the same path used for
`Shell-Seg` and other real AmigaOS binaries) and let the interpreter run on the
emulated CPU. Clients (`RX`, …) are run as normal vamos processes.

Why not reimplement REXX in Python?

- The interpreter is large, subtly specified (ANSI X3.274 + ARexx extensions)
  and its observable behaviour *is* the specification users test against.
- We already load real native libraries successfully; ARexx is the same shape
  as the shell work and reuses the existing `libnative` machinery.
- It gives exact host-command / `ADDRESS` / port semantics for free.

The trade-off is that every host API the interpreter uses must be emulated
faithfully, so the plan below is about closing those gaps rather than writing
an interpreter.

## References

- NDK 3.2 autodocs: `Autodocs/rexxsyslib.doc`, `Autodocs/arexx_cl.doc`,
  `Autodocs/dos.doc` (`CreateProc`, `AllocDosObject`), `Autodocs/exec.doc`
  (ports/messages/signals).
- NDK 3.2 `FD/rexxsyslib_lib.fd` (function table / LVOs) and `dos/dostags.h`.
- ARexx reference: the RKRM "ARexx" manual / ANSI X3.274-1996 REXX, and the
  `rexxsupport.library` autodoc for the support functions.
- Existing vamos internals: `libnative/` (native library load/init),
  `libmgr/` (auto/vamos/amiga library modes), `lib/lexec/` (ports, messages,
  signals), `schedule/` (cooperative tasks), `lib/dos/Cli.py`
  (`CreateProc`/`CreateNewProc`/`Execute`/`SystemTagList`).
- `PROC.md` — the process-function correctness work this plan builds on.

## What already works (empirical)

The following was verified by running the extracted 3.2.3 binaries under
vamos:

```sh
python3 -m amitools.tools.vamos -q \
    -Varexx:$PWD/test/arexx -alibs:arexx:Libs \
    -p arexx:System,arexx:Rexxc \
    arexx:System/RexxMast
```

- `rexxsyslib.library` is found via the `LIBS:` assign and **loads and
  initialises natively** (its resident auto-init runs). The interpreter prints
  its banner:
  `ARexx Version 1.15 / Copyright © 1987 by William S. Hawse`.
- `RexxMast` opens `dos.library`, `mathieeedoubbas.library` and
  `rexxsyslib.library`, then calls
  `CreateProc("RexxMaster", pri=4, seglist=<own>, stack=0x800)`. The child
  daemon task is created and reaches its `WaitPort`/`Wait` loop.
- All libraries the runtime needs exist as vamos vlibs: `dos`, `exec`, `icon`,
  `utility`, `mathieeedoubbas`, `mathieeedoubtrans`, `timer.device`,
  `console.device`. There is **no** `rexxsyslib_lib.fd` in
  `amitools/data/fd/`, which is fine while all calls stay native→vamos; an FD
  is only needed if a vamos-side caller must call *into* ARexx (see *Risks*).

## Findings — the concrete gaps

### G1 — `AllocDosObject(DOS_CLI)` returned a CLI with NULL buffers — **fixed**

`RexxMast` allocates a `DOS_CLI` right after `CreateProc`. The old
`alloc_dos_object()` (`amitools/vamos/lib/dos/DosList.py`) built a bare
`CLIStruct` (via `alloc_astruct`) and left `cli_Prompt`, `cli_CommandName`,
`cli_CommandFile` and `cli_SetName` as NULL pointers. A caller that writes a
default through one of them (`SetPrompt`, `SetCurrentDirName`,
`SetProgramName`, the library's own init) then scribbles over low memory —
including `ExecBase`, which is what made the forked `RexxMaster` child fault
with a corrupt `A6` (that was G2; it is the same bug).

The fix adds `alloc_cli_struct(dos, ctx, label, stack_size)` in `lib/dos/Cli.py`,
which allocates the struct *and* its four string buffers and fills the
documented defaults (`cli_FailLevel = 10`, `cli_DefaultStack` from the stack
size, prompt `%N.%S> `, set name `SYS:`). `_alloc_child_cli()` now shares the
helper, and `alloc_dos_object()` builds `DOS_CLI` through it. `free_dos_object()`
releases the struct and its buffers; `dos.dos_objs` entries now carry the extra
resources. Pinned by `test/unit/lib_dos_dosobject.py`.

### G2 — the forked `RexxMaster` child crashed on entry — **fixed**

With the old G1 stub, the child task started at the seglist entry and
immediately faulted with a corrupt `A6`:

```
machine: ERROR: ----- CPU HW Exception: Invalid Memory Access
              (pc=002ba6, sp=00f0ac) R(4) @533f34 -----
   A6=25533e20   A7=0000f0ac
```

`A6` was already garbage before the first `movea.l ($114,A6)`. The cause was the
NULL-buffer writes from G1 corrupting low memory (notably `ExecBase`), not the
seglist-entry convention (`create_new_proc` already used `(seglist_bptr<<2)+4`,
matching `Process.load_binary`). With `alloc_cli_struct()` in place the child
starts cleanly and reaches its `WaitPort` loop. No spawn-path change was needed.

### G3 — daemon lifetime vs. `run_sub_process` — **fixed**

`SystemTagList`/`Execute` must run a child **synchronously** (block until the
command is done) yet the command is its own AmigaDOS process: it may `Wait()`,
`Signal()` and start further processes (the `RexxMaster` daemon) that outlive
it. The old `run_sub_process` ran the command's code inline in the caller's task
and faked the scheduler events, reporting an `ACTIVE_TASK` for an *unconfigured*
child task.

`run_sub_process` (`lib/dos/Cli.py`) now adds the command as a real scheduler
task and blocks the caller on `SIGF_SINGLE` until that task has been removed
(via the new `_SubProcessWatcher`); the wake-up is deferred to an
after-schedule callback so the command's process is fully freed first. When
there is no running caller task (a pure Python caller) the code is still run
inline as before. This is what lets `RX` call `Execute("rexxmast")` while the
`RexxMaster` daemon keeps running.

### G4 — console windows — **works headless**

`RexxMast` opens `CON:160/60/320/80/Starting REXX …/AUTO/CLOSE/WAIT/INACTIVE`
and the daemon uses `CON:160/0/320/80/ARexx/a/inactive`; `RX` opens
`CON://640/100/Rx Output/AUTO/CLOSE/WAIT`. In vamos the console maps to host
stdio, so the window geometry and the `AUTO/CLOSE/WAIT/INACTIVE` flags are
accepted and the extra consoles do not block the headless run. No `RX`-path work
was needed; a GUI `arexx.class` host would need more.

### G5 — host-command / script lookup — **fixed (and a genuine ARexx rule)**

REXX scripts live under the `REXX:` assign (normally `S:`), and `RX SCRIPT=…`
resolves a script name through the command/path mechanism. The fixture volume
`test/arexx/S/` provides the scripts and the assign is set with
`-a REXX:arexx:S`.

A script **must begin with a `/*` comment** — this is documented ARexx
behaviour, not an emulation artifact: the AmigaOS manual states *"ARexx programs
must always begin with a comment line"*, and the grimore.org ARexx manual says
*"Each ARexx program must begin with a comment"*. `rexxsyslib`'s loader
(`rexxsyslib.library` at `0xcea6` → helper `0xcfe4`/`0xcfe8`) `Lock`s the file,
`OpenProgram`s it, then reads characters skipping the control/space class (bit 0
of the class table at `lib+0x78`), and requires the first two graphic characters
to be `/` then `*`; otherwise it closes the file and returns 0 (rc 5, "Program
not found"). The `/*` is the magic marker that distinguishes a REXX script from
a shell script or a binary. Test scripts therefore start with `/*`.

## Plan

Ordered by dependency. Steps 1–3 and 5 are done (see *Status*); step 4 needs no
work for the headless `RX` path; step 6 is the end-to-end test; step 7 remains a
stretch goal.

1. **`AllocDosObject(DOS_CLI)` / `FreeDosObject` (G1).** Done: `alloc_cli_struct()`
   fills the `CLIStruct` with sane defaults, mirroring the `NP_Cli` child-CLI
   construction in `_alloc_child_cli()` (which now shares the helper), and
   `free_dos_object()` releases the struct and its buffers. This unblocked
   `RexxMast`.
2. **Fix the child-process start context (G2).** Done: the fault was low-memory
   corruption from the NULL G1 buffers, not the spawn path. No spawn-path change
   was needed.
3. **Daemon lifecycle (G3).** Done: `run_sub_process` runs the command as a real
   scheduler task and blocks the caller on `SIGF_SINGLE`; the `RexxMaster` daemon
   survives its launcher's exit and `RX`'s `Execute("rexxmast")`.
4. **Console handling (G4).** No work needed for the headless path: `CON:` maps
   to host stdio and the window flags are accepted.
5. **REXX script fixtures + `REXX:` assign (G5).** Done: `test/arexx/S/hello.rexx`
   plus the `REXX:arexx:S` assign; scripts start with `/*`.
6. **End-to-end: run a script.** Done in `test/extra/arexx.py` (`RX` + a trivial
   script, and the missing-script error path). A `rexxsupport.library` script
   (`SHOWDIR`, `STATEF`, …) is not yet covered.
7. **`arexx.class` / BOOPSI host ports (stretch).** Still open; only needed for
   Workbench/GUI compatibility, and a `rexxsyslib_lib.fd` is required if a
   vamos-side caller must invoke ARexx.

## Testing

Reuse the existing binary-dependent test harness (`test/helper/runner.py`,
`test/conftest.py`, modeled on `test/extra/shell_seg.py`):

- `test/extra/arexx.py` adds `test/arexx` as a volume, assigns `libs=arexx:Libs`
  and `REXX:arexx:S`, and puts `arexx:System,arexx:Rexxc` on the command path.
- `vrun.skip_if_prog_not_available("arexx/...", sha1)` skips gracefully when the
  copyrighted fixtures are absent (CI has no binaries).
- Tests:
  - `arexx_rx_script_test` — `RX` + `hello.rexx` runs to completion (banner,
    `say` output, exit 0).
  - `arexx_rx_missing_script_test` — a missing script reports
    `Command returned 5/1: Program not found` (rc 5).
- `test/unit/lib_dos_dosobject.py` pins `AllocDosObject(DOS_CLI)` (buffers,
  defaults, free) independently of ARexx.

## Open questions / risks

- **Daemon shutdown residue (cosmetic).** The `RexxMaster` daemon stays alive
  after the client exits, so at session shutdown its open libraries cannot be
  expunged (`dos.library` count 2, `mathieeedoubbas` 1, `utility` 1,
  `timer.device` 2) and a handful of allocations are reported as orphans.
  Stopping the leftover tasks before teardown was tried and did not clear these
  — the residue is owned by the daemon's still-open libs — so the warnings are
  left as-is and are hidden under the tests' `quiet=True` (level ERROR). A
  proper fix would need the daemon to be told to quit (a `REXX`/host command)
  or a stronger library teardown.
- **Scheduler concurrency.** ARexx assumes preemptive multitasking (a daemon
  waiting on a port while a client runs). The port/signal wake-up path across
  tasks works for the `RX`/`RexxMaster` pattern; deeper multi-daemon scenarios
  are untested.
- **`mathieeedoubbas` / numeric behaviour** — used by the interpreter; the
  simple `1+2` arithmetic works, but the vlib's accuracy for heavier REXX
  numeric use is unverified.
- **`rexxsupport.library`** is small and native; verify which of its functions
  trap into other libraries and whether those are all emulated.
- **Proxy/FD.** If a vamos-side caller must call ARexx (e.g. a Python test
  invoking `LaunchRexxScript`), we need a `rexxsyslib_lib.fd` in
  `amitools/data/fd/`. Not required for the native client/server path.
- **Copyright** — the extracted binaries stay gitignored; tests must skip when
  they are missing.
