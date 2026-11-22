# DOS process functions: correctness review & implementation plan

Scope: `CreateNewProc`, `CreateProc`, `Execute`, `RunCommand` in
`amitools/vamos/lib/dos/Cli.py` (plus the `amitools/vamos/dos/` package).

Chosen scope: **core correctness + common tags + package move + tests**.
`NP_Synchronous` and full `NP_Cli`/`NP_Path`/`NP_CommandName` construction are
explicitly deferred (see *Deferred* below) and left as documented TODOs.

## References

- RKRM AmigaDOS / autodocs:
  - `CreateNewProc` (V36) — node014C
  - `CreateProc` — node014D
  - `Execute` — node015E
  - `RunCommand` (V36) — node01AA
  - `SystemTagList` — node01C5
- AROS `rom/dos/createnewproc.c`, `createproc.c`, `execute.c`, `runcommand.c`.
- NDK `dos/dostags.h` (tag values).

## Findings

### CreateProc — `create_proc()`

- **BUG** Returns the `Process` address. Spec: returns the **`pr_MsgPort`**
  address (`struct MsgPort *`); callers recover the Process from it.
- AROS passes `NP_FreeSegList=FALSE`, `NP_CloseInput/Output=FALSE`,
  `NP_CurrentDir=0`, `NP_HomeDir=0`, `NP_Input=0`, `NP_Output=0` for AOS 3.x
  compatibility. Vamos omits these.

### CreateNewProc — `_new_proc_tags()` / `_spawn()`

- Only 9 of ~25 `NP_*` tags are read. Missing: `NP_CloseInput`,
  `NP_CloseOutput`, `NP_CloseError`, `NP_Error`, `NP_ConsoleTask`,
  `NP_WindowPtr`, `NP_CopyVars`, `NP_Cli`, `NP_Path`, `NP_CommandName`,
  `NP_Arguments`, `NP_NotifyOnDeath`, `NP_Synchronous`, `NP_ExitCode`,
  `NP_ExitData`, `NP_FreeSegList`, `NP_UserData`.
- `get_tag_data(tag, 0)` conflates *tag absent* with *explicit 0*, so
  `NP_Input=0` (request `NIL:`) cannot be distinguished from unset, and the
  `NP_Close*` defaults are unknowable.
- `NP_Arguments` is ignored, so `ReadArgs()` in the child cannot see arguments.
- `pr_Flags` (`PRF_*`) is never set → no close-on-exit, no free-seglist, no
  notify-on-death, no synchronous wait, no exit handler.
- `pr_WindowPtr` is hard-coded to `-1`; `NP_WindowPtr` is ignored.
- Defaults deviate from spec: name `"child_process"` vs `"New Process"`,
  stack `4096` vs `4000`, priority `0` vs inherit parent.
- `pr_GlobVec = 0xFFFFFFFF` rather than the DOS globvec (possibly intentional
  in vamos; leave as-is).

### Execute — `execute()`

- **BUG** Returns the command's return code. Spec/AROS: returns `DOSTRUE` if it
  could find/start the command, `DOSFALSE` otherwise — explicitly *not* the
  return code.
- IO redirection is done by poking `pr_CIS`/`pr_COS` and calling
  `_system_tag_list(ctx, cmd, None)`. It should pass `SYS_Input`/`SYS_Output`
  tags; the native-shell path already looks for `SYS_Output`, and the
  non-native path builds a fresh `Process` that won't reliably inherit the
  poked handles.
- Empty command string: spec = create a new interactive shell (AROS maps `""`
  to `"Run NewShell"`); vamos returns `DOSFALSE`.

### RunCommand — `run_command()` + `vamos/dos/run.py`

- Does not set/restore `pr_Arguments`, so `GetArgStr()` during the command is
  wrong (spec says it must be set and restored).
- Does not set/restore `pr_ReturnAddr`.
- Does not `Flush()` leftover input after the command (AROS does, to fix
  `C:Execute`).
- Raises `VamosInternalError` for an unknown seglist; spec returns `-1` only
  for stack-alloc failure. Keep the internal error (unregistered seglist is a
  host bug) but document it.
- OK: stack rounding, negative BPTR handling, `D0=arglen`/`A0=argptr`/
  `D2=stacksize`, input push/clear.

### Package layout

- `amitools/vamos/dos/` contains only `run.py` (`run_command`,
  `run_sub_process`); it is not a library. Imported only by
  `lib/dos/Cli.py` and `test/unit/dos_run.py`.

## Planned changes

### 1. Move `vamos.dos` → `vamos/lib/dos/run.py`

- Create `amitools/vamos/lib/dos/run.py` with the current contents.
- Update imports:
  - `amitools/vamos/lib/dos/Cli.py`:
    `from .run import run_command as ami_run_command, run_sub_process`
  - `test/unit/dos_run.py`: `from amitools.vamos.lib.dos.run import run_command`
- Delete `amitools/vamos/dos/`.

### 2. CreateProc

- Return `ProcessStruct(ctx.mem, proc_addr).msg_port.addr` (0 when creation
  failed).
- Pass the AOS-compat tags: `NP_FreeSegList=FALSE`, `NP_CloseInput=FALSE`,
  `NP_CloseOutput=FALSE`, and explicit `NP_CurrentDir/HomeDir/Input/Output=0`
  where they match CreateProc's "inherit parent, do not close" behaviour.

### 3. CreateNewProc

- Add missing `DosTag` entries: `NP_UserData`, `NP_Affinity`.
- Read tags with an **unset sentinel** (e.g. `get_tag_data(tag, None)`) so an
  explicit `0` is preserved.
- Apply spec defaults: name `"New Process"`, stack `4000`, priority inherited
  from the parent process.
- Set `pr_Flags` and implement child exit cleanup in the scheduler event:
  - `NP_CloseInput/Output/Error` → close `pr_CIS`/`pr_COS`/`pr_CES`.
  - `NP_FreeSegList` → unload the child seglist.
  - `NP_ExitCode`/`NP_ExitData` → call the handler with `(rc, data)`.
  - `NP_NotifyOnDeath` → signal the parent task.
- Honor `NP_Error` (`pr_CES`), `NP_ConsoleTask`, `NP_WindowPtr`,
  `NP_CopyVars`, `NP_Arguments` (set `pr_Arguments` and inject into the input
  buffer so `ReadArgs()` works), `NP_UserData` (`tc_UserData`).
- Keep the existing `NP_Entry`/`NP_SegList` resolution.

### 4. Execute

- Return `DOSTRUE`/`DOSFALSE` (not the command return code).
- Pass `SYS_Input`/`SYS_Output` tags to `_system_tag_list`.
- Handle the empty-string + no-input case (new shell) per spec/AROS.

### 5. RunCommand

- Set `pr_Arguments` (GetArgStr) and `pr_ReturnAddr` while running; restore
  both in a `finally`.
- Flush leftover input after the command, preserving `IoErr`.

## Deferred (documented TODOs)

Superseded by the consolidated **Later** section at the end of this document.

- `NP_Synchronous` (block until the child exits) — interacts with the
  cooperative scheduler.
- Full `NP_Cli` / `NP_Path` / `NP_CommandName` child CLI construction.
- `NP_Affinity` (SMP-only; accept and ignore).
- `NP_CopyVars` full local-variable deep copy (do the straightforward copy and
  note any gaps).

## Tests

- `test/unit/lib_dos_cli.py`
  - CreateNewProc tag parsing incl. unset-vs-zero, defaults, flags.
  - CreateProc returns the `pr_MsgPort` address.
  - Execute returns `DOSTRUE`/`DOSFALSE` and forwards `SYS_Input`/`SYS_Output`.
- `test/unit/dos_run.py`
  - `pr_Arguments`/`pr_ReturnAddr` set and restored (GetArgStr).
- `test/pytask/pytask_dos_proc.py`
  - Close-on-exit (`NP_CloseInput/Output/Error`).
  - `NP_Error` (`pr_CES`), `NP_ConsoleTask`, `NP_WindowPtr`.
  - `NP_Arguments` + `ReadArgs`.
  - Defaults: name, stack, inherited priority.
  - `NP_ExitCode`/`NP_ExitData` invoked with `(rc, data)`.
  - `NP_NotifyOnDeath`.
  - `NP_FreeSegList`.
- Update `test/unit/dos_run.py` import after the package move.

## Implementation status

All five stages are implemented.

### 1. Package move (done)

`amitools/vamos/dos/` was removed; `run.py` now lives at
`amitools/vamos/lib/dos/run.py`. `lib/dos/Cli.py` imports it as
`from .run import run_command as ami_run_command, run_sub_process` and
`test/unit/dos_run.py` imports `amitools.vamos.lib.dos.run`.

### 2. CreateProc (done)

`create_proc()` returns `ProcessStruct(ctx.mem, proc_addr).msg_port.addr` (0 on
failure) and passes the AROS `createproc.c` compat tags: `NP_FreeSegList=0`,
`NP_CurrentDir=0`, `NP_HomeDir=0`, `NP_Input=0`, `NP_Output=0`,
`NP_CloseInput=0`, `NP_CloseOutput=0`.

### 3. CreateNewProc (done)

- `ProcessFlags(IntEnum)` (`PRF_*`) added to `libstructs/dos.py`; `NP_UserData`
  and `NP_Affinity` added to `DosTag`.
- `_new_proc_tags()` reads all common `NP_*` tags with an **unset sentinel**
  (`_tag_data`), so an explicit `0` is preserved. Defaults follow the **RKRM
  AmigaDOS book** (real AmigaDOS): name `"New Process"`, stack `4000`,
  priority `0`; `NP_CurrentDir`/`HomeDir`/`ConsoleTask`/`WindowPtr` inherited
  from the parent.
- `NP_Input`/`NP_Output` default to a fresh `NIL:` open; `NP_Error` defaults to
  `ZERO` (RKRM/NDK); an explicit `0` (BNULL) is kept as `0` for all three.
  `NP_CloseInput`/`NP_CloseOutput` default to `TRUE`, `NP_CloseError` to
  `FALSE` (RKRM/NDK), and `NP_FreeSegList` to `FALSE` (RKRM: real AmigaDOS does
  not release the caller's seglist unless asked).
- `_spawn()` fills `pr_Flags`, `pr_ExitCode`/`pr_ExitData`, `tc_UserData`,
  `pr_CIS/COS/CES`, the process port and copies `NP_Arguments` into DOS memory
  (`PRF_FREEARGS`) and injects it into the input stream for `ReadArgs()`.
- `child_proc_event()` (now in `CliMixin`, registered by `DosLibrary`) runs the
  DOS shutdown when the child task ends: `NP_ExitCode(rc, data)`,
  close-on-exit handles, `NP_FreeSegList`, free `NP_Arguments`,
  `NP_NotifyOnDeath` (`Signal(parent, SIGF_CHILD)`). The return code is read
  from the run state's `D0` because `NativeTask` stores `exit_code` only after
  it has already reported `REMOVE_TASK`.
- `NP_Synchronous`, `NP_Cli`, `NP_Path`, `NP_CommandName` are accepted and
  ignored with a warning; `NP_CopyVars` is a no-op (local vars are shared
  process-wide in vamos).

### 4. Execute (done)

`execute()` builds `SYS_Input`/`SYS_Output` tags and returns `DOSTRUE` when the
command could be started (SystemTagList result `0`) and `DOSFALSE` otherwise.
An empty command string with no handles is mapped to `"Run NewShell"`. The
native-shell path of `system_tag_list()` honours `SYS_Input` when given.
`DosTag` now has the correct `SYS_UserShell`/`SYS_CustomShell`
(`SYS_Dummy + 4/5`, they were `36`/`37`) plus `SYS_ScriptInput`,
`SYS_Background`, `SYS_CliNumPtr`, `SYS_CliType`.

### 5. RunCommand (done)

`run_command()` sets `pr_Arguments` and `pr_ReturnAddr` (to the machine's exit
trap) while the command runs and restores both in a `finally`, then flushes the
leftover input while preserving `IoErr` (AROS `runcommand.c`).

## Verification checklist

- [x] `pytest test/unit/lib_dos_cli.py test/unit/dos_run.py`
- [x] `pytest test/pytask/pytask_dos_proc.py`
- [x] `grep -rn "vamos.dos\|vamos import dos"` returns nothing
- [x] `ruff` clean
- [x] `pytest test/unit test/pytask`

## RKRM DOS book cross-check

Verified against the RKRM AmigaDOS book source
(`github.com/thorfdbg/rkrm-dos`, `dos.tex`): chapter "Processes"
(`sec:process`, `sec:createnewproc`, `sec:createproc`), `sec:runcommand`,
`sec:exit`, `sec:getargstr`. The book describes the **real AmigaDOS** behaviour
(AmigaDOS 47) and in a few places explicitly contradicts the older official
autodoc; where that happens vamos now follows the book (chosen policy:
"Follow RKRM book / real AmigaDOS").

### CreateNewProc

Confirmed correct against the book:

- Returns a `struct Process *`; the process port carries `SIGB_DOS` and is not
  a public `FindPort()` port.
- `NP_SegList` starts at the first byte of the first segment; `NP_Entry` is an
  absolute entry point; either one is required.
- `NP_Name` is copied (default `"New Process"`); `NP_StackSize` default `4000`.
- `NP_Arguments` is copied into DOS memory (`PRF_FREEARGS`), installed in
  `pr_Arguments`, pushed into the `pr_CIS` buffer so `ReadArgs()` works, and —
  **fixed in this pass** — loaded into `A0`/`D0` (string/length) before the
  entry point runs (book: "the string and its lengths will be loaded into
  registers A0 and D0 before execution of the process begins").
- `NP_ExitCode(rc, data)` is called on shutdown with the return code in `D0`
  and `NP_ExitData` in `D1`.
- `NP_FreeSegList` unloads only a DOS-managed seglist.
- `NP_NotifyOnDeath` signals the parent with `SIGF_CHILD` (vamos implements
  this; the book notes real AmigaDOS ignores the tag — a benign superset).

Changed to match the book:

| Tag | Book / real AmigaDOS | AROS (previous vamos) | Now |
| --- | --- | --- | --- |
| `NP_Error` default | `ZERO` | `NIL:` | `ZERO` |
| `NP_CloseError` default | `FALSE` | `TRUE` | `FALSE` |
| `NP_FreeSegList` default | `FALSE` | `TRUE` | `FALSE` |
| `NP_Priority` default | `0` | inherit parent | `0` |

The book also disagrees with the autodoc on `NP_FreeSegList` ("Unlike what the
official documentation claims, the default value of this tag is DOSFALSE") and
with the autodoc's "priority is copied" claim; vamos follows the book.

Remaining known simplifications (documented, not changed):

- `NP_CurrentDir`/`NP_HomeDir`: the book says the default is a `DupLock()` of
  the caller's lock and that the lock is released on process termination. Vamos
  shares the caller's lock `bptr` and does not release it on child exit
  (vamos' process-wide lock manager makes the shared lock safe; no
  `PRF_FREECURRDIR` handling is implemented).
- `NP_WindowPtr`: the book's rule is "copy the caller's value only if it is
  `NULL` or `-1`, else `NULL`". Vamos inherits the parent value unconditionally
  (vamos has no intuition screen, so this only affects the `-1` "suppress
  requesters" sentinel).
- `NP_Synchronous`, `NP_Cli`, `NP_Path`, `NP_CommandName` remain deferred.

### CreateProc

Matches the book exactly: returns the `pr_MsgPort` address; name/priority/stack
from the arguments; `pr_ConsoleTask`/`pr_WindowPtr`/`pr_FileSystemTask`
inherited (or `NULL`/`0` from a task); input/output/error `ZERO`; no CLI
structure; current/home dir `ZERO`; no arguments; the seglist is **not**
released.

### RunCommand

Matches the book exactly: the command runs in the caller's process with its own
stack (the caller's `tc_SPLower`/`tc_SPUpper` are updated and restored), the
arguments are placed in `A0`/`D0`, `pr_Arguments` is temporarily replaced (so
`GetArgStr()` sees them) and restored, a copy of the argument line is put into
the `pr_CIS` buffer for `ReadArgs()`, and all of this is reverted when the
command returns. The return value is the command's result code and `IoErr()`
survives the cleanup.

### Execute

The book does not document the `Execute()` *function* (only the `Execute`
shell command, `sec:executecmd`), so it remains verified against the autodoc
and AROS (`execute.c`): returns `DOSTRUE`/`DOSFALSE` (not the command's return
code), forwards `SYS_Input`/`SYS_Output`, and maps an empty command with no
handles to `"Run NewShell"`.

## Later

Open points that are deliberately *not* implemented yet. None of them block the
current scope (core correctness + common tags + package move + tests); they are
recorded here so they are not lost.

### Deferred by the chosen scope

- [ ] **`NP_Synchronous`** — wait until the created process has finished before
  returning (sets `PRF_SYNCHRONOUS`/`PRF_WAITINGFORCHILD` and waits on
  `SIGF_SINGLE`). Interacts with the cooperative scheduler; currently accepted
  and ignored with a warning.
- [ ] **`NP_Cli` / `NP_Path` / `NP_CommandName`** — build a real child
  `CommandLineInterface` (prompt/path/command-name copied from the caller).
  Largest remaining item; currently accepted and ignored with a warning.
- [ ] **`NP_Affinity`** — SMP CPU mask. SMP-only; accepted and ignored.
- [ ] **`NP_CopyVars`** — deep copy of the caller's local shell variables and
  aliases into the child. Currently a no-op because vamos keeps local variables
  process-wide.

### RKRM simplifications (documented, not yet implemented)

- [ ] **`NP_CurrentDir` / `NP_HomeDir` defaults** — the RKRM book says the
  default is a `DupLock()` of the caller's lock, that the current dir sets
  `PRF_FREECURRDIR`, and that both locks are released when the child terminates
  (and on creation failure). Vamos currently shares the caller's lock `bptr` and
  does not release it on child exit. Needs `PRF_FREECURRDIR` handling in
  `_child_exit_cleanup()` and a `DupLock()`/`UnLock()` path in `_spawn()`.
- [ ] **`NP_WindowPtr` default** — the book copies the caller's value only when
  it is `NULL` or `-1`, otherwise `NULL`; vamos inherits the parent value
  unconditionally. Only observable via the `-1` "suppress error requesters"
  sentinel.

### Adjacent

- [ ] **`Execute()` redirection** — the non-native `system_tag_list()` path still
  has a `# TODO: redirs` for command-line redirection parsing.
- [ ] **`NP_NotifyOnDeath`** — vamos implements it (`Signal(parent, SIGF_CHILD)`),
  which is a benign superset; the RKRM book states real AmigaDOS ignores the tag.
  Keep as-is unless strict AOS 47 behaviour is required.


