# Vamos process refactor: `BinProcess` / `ShellProcess` & the `shell` mode

Scope: split the DOS `Process` class
(`amitools/vamos/lib/dos/Process.py`) into a shared base plus two specialised
processes:

- **`ProcessBase`** (kept in `lib/dos`) — the shared "run a program" lifecycle.
- **`BinProcess`** — run a single binary with a minimal ("micro") CLI
  (`uCLI`). Used by the existing **`proc`** mode.
- **`ShellProcess`** — launch a shell seg (e.g. `l/Shell-Seg`). Used by a
  new **`shell`** mode.

The `-x`/`--shell` switch stays a boolean shortcut for `--mode shell`; a single
binary run and a shell run stop sharing one code path with a boolean flag. The
shell-seg binary is configured separately (default `L:shell-seg`).

## Why

`Process` currently serves two use cases behind a `shell=False` constructor
flag. That flag changes, in four unrelated places:

1. the binary entry point (`load_binary`: `prog_start += 8`, `shell_start`),
2. the argument mechanism (`init_args` + D0/A0 vs a startup `DosPacket` in D1),
3. the CLI setup (`S:Vamos-Startup`, `cli_CurrentInput`, interactive state),
4. the `SystemTagList` forwarding contract
   (`is_native_shell()` / `run_system()` / `shell_start`).

Splitting the two keeps the single-binary path free of shell-only state and
makes the shell path explicit. It also matches the two modes: `proc` runs a
binary, `shell` runs a shell.

## Current state (findings)

### The monolith

`amitools/vamos/lib/dos/Process.py` — `Process(DosProcess)`, ~426 lines. The
`shell` flag is consulted in `__init__`, `free`, `load_binary`,
`_get_start_regs`, `init_cli_struct` and `is_native_shell`.

| Member | `shell=False` | `shell=True` |
| --- | --- | --- |
| `load_binary` | entry = seglist start | entry = seglist start **+ 8**, `shell_start` recorded |
| args | `init_args` (setbuf + arg buffer) | `init_shell_packet` (message + `DosPacket` + port) |
| start regs | `D0=arglen`, `A0=argptr` | `D1=BPTR(shell_packet)` |
| CLI | prompt/name/setname + command path | **also** `S:Vamos-Startup` → `cli_CurrentInput` |
| `is_native_shell()` | `False` | `True` |
| `free` | `free_cwd` | `free_shell_packet` |
| `run_system()` / `shell_start` | unused | used by `SystemTagList` |

The `D2=stack_size` guard and the old-DOS regs (`A2/A5/A6 = odg_base`) are
common to both.

### `DosProcess` vs the `Process` base

`amitools/vamos/task/dosproc.py` — `DosProcess(ExecTask)` allocates the
`libtypes.Process` + task and already exposes `get_current_dir` /
`set_current_dir` / `get_home_dir` / `set_home_dir` / `get_local_vars` /
`get_cli_struct`, all against `self.proc`.

The DOS `Process` **duplicates** these against `self.this_task`:

```python
self.addr = self.ami_proc.addr
self.this_task = ProcessStruct(self.ctx.mem, self.addr)   # same memory as self.proc
```

`self.this_task` and `self.proc` address the same `ProcessStruct`, so
`get_input`/`set_input`/`get_output`/`set_output`/`get_current_dir`/
`set_current_dir`/`get_home_dir`/`set_home_dir`/`get_local_vars`/
`get_cli_struct` exist twice. Removing this duplication is part of the
refactor (see *Layering decision*).

`DosProcess` also has **non-program callers** that must not load a binary or
build a CLI:

- `lib/dos/Helper.py:create_child_process` (CreateNewProc children),
- `handler/native/manager.py:NativeHandlerManager._make_program` (handler
  tasks),
- tests (`test/helper/task.py`, `test/unit/lib_os_native.py`,
  `test/unit/lib_process_directories.py`, `test/unit/dos_adfs_volume.py`,
  `test/unit/task_dosproc.py`, `test/unit/task_stack_bounds.py`).

### Callers

- `amitools/vamos/mode/proc.py` (`ProcMode.create_proc`) — constructs
  `Process(..., shell=proc_cfg.command.shell, cwd=cwd)`.
- `amitools/vamos/lib/dos/Cli.py` — `from .Process import Process`; the
  non-native branch of `system_tag_list()` constructs a `Process` for a
  single command (`shell=False`).
- `test/unit/lib_dos_cli.py` monkeypatches `Cli.Process` (via
  `monkeypatch.setattr(Cli, "Process", FakeProcess)`).

`is_native_shell()` is read by `system_tag_list()` (`Cli.py:1282`) to pick the
shell-forwarding branch; `test/pytask/pytask_dos_proc.py:822` and
`test/unit/lib_dos_cli.py:1114` stub it.

### Modes and config

- `amitools/vamos/mode/setup.py` — `ModeSetup.mode_map = {"proc", "test"}`;
  `select()` returns the mode named by `cmd_cfg.mode` (default `"proc"`).
- `amitools/vamos/cfg/proc.py` — `command.shell` (`-x/--shell`),
  `command.mode` (`-M/--mode`, default `"proc"`), `command.args`, `stack`,
  `vars`.
- `amitools/vamos/main.py:246` — `mode = ModeSetup.select(cmd_cfg)` when no
  mode was passed on the command line.
- Docs: `docs/vamos/user/options.rst` (`-x`, `-M`),
  `docs/vamos/user/running.rst` ("Run a Shell"),
  `docs/vamos/dev/architecture.rst` (modes list `proc`, `test`).

### Tests touching the behaviour

- `test/unit/cfg_proc.py` — config dict/args, includes `"shell": True` and
  `"mode": "proc"`.
- `test/unit/lib_dos_cli.py` — `lib_dos_cli_system_tag_list_redir_test`
  monkeypatches `Cli.Process`.
- `test/extra/shell_seg.py` — runs `wb:l/Shell-Seg` with `vargs=["-x"]`.
- `test/suite/proc_args.py` — `proc` mode argument passing.

## Layering decision: keep `ProcessBase` in `lib/dos`

The shared "run a program" lifecycle stays in a **`ProcessBase`** class in
`lib/dos/Process.py`, *not* merged into `DosProcess`. Reason: that lifecycle
is DOS-heavy (path search, seglist load, CLI construction, `DosPacket`/port
setup) and depends on the DOS lib context (`ctx.dos_lib`, `ctx.path_mgr`,
`ctx.seg_loader`, `ctx.exec_lib`). `DosProcess` lives in the lower-level
`task` package and has non-program callers (CreateNewProc children, native
handler tasks) that must stay free of CLI/packet knowledge. Keeping the
lifecycle in `lib/dos` preserves the layering:

```text
ExecTask
  └── DosProcess        (task/dosproc.py: Process struct + generic DOS accessors)
        └── ProcessBase (lib/dos/Process.py: program lifecycle)   <-- stays in lib/dos
              ├── BinProcess   (single binary + uCLI)  -> proc mode
              └── ShellProcess (shell seg + packet)    -> shell mode
```

**Dedup (`this_task` → `self.proc`).** `ProcessBase` extends `DosProcess`, so it
already has `self.proc` (the `libtypes.Process`, same memory as the old
`this_task`). The refactor drops `self.this_task` and:

- inherits `DosProcess`'s `get_current_dir`/`set_current_dir`/`get_home_dir`/
  `set_home_dir`/`get_local_vars`/`get_cli_struct` instead of reimplementing
  them;
- re-points the remaining `ProcessBase` accessors (`get_input`/`set_input`/
  `get_output`/`set_output`, `get_arg_str_ptr`/`set_arg_str_ptr`, the cwd
  lock lookups) at `self.proc.pr_*` instead of `self.this_task.pr_*`.

`get_cli_struct()` then resolves via `DosProcess` to `self.proc.pr_CLI.aptr`,
which is `self.cli.addr` once `init_task_struct` has run.

**`this_task` compat alias.** External readers (`lib/dos/FileIO.py`,
`lib/dos/Cli.py`) and the unit-test mocks still use `process.this_task`, so
Step 2 kept a read-only `ProcessBase.this_task` property that returns
`self.proc` (the same memory). This removes the duplicated `ProcessStruct`
while leaving the call sites untouched; the alias can be dropped once those
call sites are migrated to `self.proc` (Step 7).

## Target design

### `ProcessBase` (shared program lifecycle)

Owns everything identical for both subclasses, all using `self.ctx` (the DOS
lib context):

- cwd: `init_cwd`, `set_cwd`, `free_cwd`, `get_current_dir_lock`,
  `get_home_dir_lock`
- binary: `load_binary` (no shell offset), `unload_binary`
- CLI struct: `alloc_cli_struct`, `free_cli_struct` (`init_cli_struct` is
  overridden)
- task struct: `init_task_struct`, `free_task_struct`, `_handler_port`
- regs: `_get_start_regs` (common `D2`/`A2`/`A5`/`A6`; subclasses add
  `D0`/`A0` or `D1`)
- arg pointer: `get_arg_str_ptr`, `set_arg_str_ptr`, `get_program_name`
- streams: `get_input`/`set_input`/`get_output`/`set_output`
- `is_native_shell()` → `False` (overridden by `ShellProcess`)

### `BinProcess` (was `InitProcess`)

The non-shell path:

```python
class BinProcess(ProcessBase):
    def __init__(self, ctx, bin_file, arg_str, input_fh=None,
                 output_fh=None, stack_size=4096, cwd=None, cwd_lock=None):
        self.ctx = ctx
        self.cli_paths = []
        self.bin_file = bin_file
        # default in/out handles, init cwd, load binary
        self.init_cwd(cwd, cwd_lock)
        if not self.load_binary(self.cwd_lock, bin_file): ...
        self.init_args(arg_str, input_fh)
        super().__init__(ctx, self.bin_basename, stack_size=stack_size,
                         start_pc=self.prog_start,
                         start_regs=self._get_start_regs(stack_size))
        self.alloc_cli_struct()
        self.init_task_struct(input_fh, output_fh)
        self.init_cli_struct(input_fh, output_fh, self.bin_basename)  # uCLI
        self.set_cwd()

    def _get_start_regs(self, stack_size):
        regs = super()._get_start_regs(stack_size)   # common D2/A2/A5/A6
        regs[REG_D0] = self.arg_len
        regs[REG_A0] = self.arg_base
        return regs

    def is_native_shell(self):
        return False
```

**uCLI ("micro CLI")** — a minimally initialised `CLIStruct`. `pr_CLI` is a
`BPTR(CLIStruct)`, so the struct keeps the full layout; "micro" means only the
fields a single binary actually needs are filled:

| Field | Value |
| --- | --- |
| `cli_DefaultStack` | `stack.get_size() // 4` |
| `cli_FailLevel` | `10` |
| `cli_StandardInput` / `cli_CurrentInput` | input fh BPTR |
| `cli_StandardOutput` / `cli_CurrentOutput` | output fh BPTR |
| `cli_Prompt` | default `"%N.%S> "` (60-byte buffer) |
| `cli_SetName` | `"SYS:"` (80-byte buffer) |
| `cli_CommandName` | binary basename (104-byte buffer) |
| `cli_CommandDir` | command path chain (as today) |
| `cli_Result2`, `cli_ReturnCode`, `cli_Interactive`, `cli_Background`, `cli_CommandFile`, `cli_Module` | `0` |

Deliberately **not** set (reserved for `ShellProcess`): the `S:Vamos-Startup`
redirect of `cli_CurrentInput` and the shell/background state.

The uCLI keeps `cli_CommandDir` (today's non-shell behaviour; programs that
`Execute`/`Run` commands rely on it). It is built by a small `MicroCLI` helper
in **`lib/dos/ucli.py`**, exposing `addr` and `free()`; `ShellProcess` builds
on the same allocator and adds the startup file.

### `ShellProcess`

The `shell=True` path, isolated:

- `load_binary` override adds `+8` and records `shell_start`.
- `__init__` → `init_shell_packet()`; sets `arg = None`.
- `_get_start_regs` → `D1 = BPTR(shell_packet)` plus the common regs.
- `init_cli_struct` → full CLI: uCLI fields **plus** opening
  `S:Vamos-Startup` for `cli_CurrentInput`.
- `init_shell_packet` / `free_shell_packet` / `run_system` live here.
- `is_native_shell()` → `True`.

### `Cli.system_tag_list`

`Cli.py`:

- import `BinProcess` instead of `Process`;
- the non-native branch constructs `BinProcess(...)`;
- the shell branch keeps using `ctx.process.is_native_shell()`,
  `run_system()` and `shell_start`, which now only exist on `ShellProcess`
  (the branch is only taken for one).

### Modes

- `ProcMode` (`mode/proc.py`) drops the `shell` parameter and builds
  `BinProcess`.
- New `ShellMode` (`mode/shell.py`) mirrors `ProcMode` but builds
  `ShellProcess` from the shell seg named by `command.shell_bin` (default
  `L:shell-seg`, resolved to an Amiga path via `ProcArgs`). It ignores
  positional arguments (the shell gets its command stream from
  `S:Vamos-Startup` / the console, not from `arg_str`).
- Optional: factor the shared `create_proc` / `setup_vars` code into a small
  `ProcessModeBase`, with `ProcMode`/`ShellMode` providing the process class.
- `ModeSetup.mode_map` gains `"shell": ShellMode`.

### Config and `-x`

`-x`/`--shell` stays a **boolean** and is a shortcut for `-M shell` (it selects
the `shell` mode). The shell-seg binary is a separate setting.

- `vamos -x` (or `vamos -M shell`) → `shell` mode with the default seg
  `L:shell-seg`.
- `vamos -x --shell-bin wb:l/Shell-Seg` → `shell` mode with that seg.
- no `-x` and no `-M shell` → `proc` mode.

Config model (`cfg/proc.py`):

- `command.shell`: `Value(bool, False)` — the `-x` flag; truthy selects the
  `shell` mode.
- `command.shell_bin`: `Value(str, "L:shell-seg")` — Amiga path of the
  shell-seg binary.
- CLI `-x`/`--shell`: `store_true` (unchanged).
- CLI `--shell-bin NAME`: sets `command.shell_bin`.
- `ModeSetup.select()`: a truthy `cmd_cfg.shell` selects `ShellMode`;
  otherwise use `cmd_cfg.mode` (`-M`, default `"proc"`).
- `ShellMode` uses `cmd_cfg.shell_bin or SHELL_SEG_DEFAULT`
  (`SHELL_SEG_DEFAULT = "L:shell-seg"`).

## Method mapping

| Current `Process` member | `ProcessBase` | `BinProcess` | `ShellProcess` | `DosProcess` |
| --- | --- | --- | --- | --- |
| `__init__` (orchestration) | skeleton | args + uCLI | packet + shell CLI | generic ctor |
| `free` | shared | free args | free packet | frees `proc` |
| `__str__` | ✔ | | | |
| `init_cwd` / `set_cwd` / `free_cwd` | ✔ | | | |
| `load_binary` / `unload_binary` | ✔ (no offset) | | override `+8` | |
| `init_args` / `free_args` | | ✔ | | |
| `_get_start_regs` | common `D2`/`A2`/`A5`/`A6` | `D0`/`A0` | `D1` | |
| `alloc_cli_struct` / `free_cli_struct` | ✔ | | | |
| `init_cli_struct` | | uCLI | full shell CLI | |
| `init_shell_packet` / `free_shell_packet` / `run_system` | | | ✔ | |
| `init_task_struct` / `free_task_struct` / `_handler_port` | ✔ | | | |
| stream accessors (`pr_CIS`/`pr_COS`) | ✔ (via `self.proc`) | | | |
| dir/var/cli accessors | inherited | | | ✔ |
| `is_native_shell` | `False` | | `True` | |
| `get_program_name` / arg ptr | ✔ | | | |

## Transformation steps

Each step is independently landable and testable.

1. **Baseline.** Confirm `pytest test/unit test/pytask` is green before
   starting.
2. **Extract `ProcessBase`.** Pure move: rename `Process` → `ProcessBase`,
   move the shell-only pieces behind overridable hooks, reuse `DosProcess`'s
   accessors and drop `self.this_task` (use `self.proc`). No behaviour change.
3. **Add `BinProcess`.** Non-shell path as a subclass; point `mode/proc.py`
   and `Cli.system_tag_list` at it. `proc` mode must be equivalent (same
   args, same regs, same CLI fields).
4. **Add `ShellProcess`.** Shell path as a subclass; keep `-x` working by
   routing it to the new class. `test/extra/shell_seg.py` must still pass.
5. **Introduce the uCLI helper.** Extract the minimal-CLI builder used by
   `BinProcess`; `ShellProcess` reuses it and adds the startup file. Add unit
   coverage for the field set.
6. **Add the `shell` mode.** `mode/shell.py` + `ModeSetup` entry; make `-x`
   and `-M shell` both select it; drop `shell=` from `ProcMode`.
7. **Remove the old `Process` name** and fix remaining imports and the
   `Cli.Process` monkeypatch.
8. **Docs.** `options.rst` (`-x` as a shortcut for `-M shell`, `--shell-bin
   NAME` with default `L:shell-seg`, `-M` list), `running.rst` ("Run a
   Shell"), `architecture.rst` (modes list). Update this file's status section.

## Tests

- `test/unit/lib_dos_cli.py`: monkeypatch `Cli.BinProcess`; the redirection
  test must be unchanged otherwise.
- `test/unit/cfg_proc.py`: config expectations for `shell`/`mode` after the
  `-x` → `shell` mapping.
- New `test/unit/dos_process.py` (or extend an existing unit file):
  - `BinProcess`: start regs `D0/A0/D2` + old-DOS guards; uCLI fields
    (streams, prompt, set name, command name, command path, `DefaultStack`,
    `FailLevel`); no `S:Vamos-Startup`; `is_native_shell() is False`.
  - `ShellProcess`: entry `+8` / `shell_start`; `D1 = BPTR(packet)`; packet
    message/port wiring; `is_native_shell() is True`; `run_system()`.
  - `free()` releases args vs packet and the CLI in both cases.
  - `ProcessBase` accessors address the same struct as `self.proc` (no
    separate `this_task`).
- New `test/unit/mode_shell.py`: `ShellMode` builds a `ShellProcess`; `-x`
  and `-M shell` both select it.
- `test/extra/shell_seg.py`: update `vargs=["-x"]` to
  `vargs=["-x", "--shell-bin", "wb:l/Shell-Seg"]` (the positional stays for
  `make_prog`); `-x` is still a boolean.
- `test/suite/proc_args.py`: `proc` mode argument passing unchanged.
- Existing `DosProcess` users (`test/unit/task_dosproc.py`,
  `test/unit/lib_process_directories.py`, handler tests, CreateNewProc
  pytask tests) must stay green.

## Risks / compatibility

- **Generic `DosProcess` callers.** `DosProcess` is unchanged in behaviour;
  the program lifecycle stays in `ProcessBase` (`lib/dos`), so
  `create_child_process`, `NativeHandlerManager._make_program` and the tests
  that construct `DosProcess(machine, alloc, name, ...)` are unaffected.
- **`this_task` removal.** The duplicated `ProcessStruct` view is gone: the
  accessors use `self.proc` and `this_task` is a read-only property aliasing it,
  so field addresses are unchanged. `test/unit/dos_process.py` pins the dedup
  (accessors use `self.proc`, dir/var/cli accessors inherited from
  `DosProcess`).
- **Case-insensitive filesystem.** Do not create `lib/dos/process/` next to
  `lib/dos/Process.py` on macOS. Default: keep a single module with
  `ProcessBase`/`BinProcess`/`ShellProcess`.
- **uCLI field set.** Dropping any field the old non-shell path set changes
  single-binary behaviour; the plan keeps the old field set for `BinProcess`
  and only moves shell-only fields to `ShellProcess`.
- **`-x` semantics.** `-x` stays a boolean shortcut for `-M shell`. The shell
  seg moves to `command.shell_bin` / `--shell-bin` (default `L:shell-seg`), so
  the old `vamos -x Shell-Seg` becomes
  `vamos -x --shell-bin Shell-Seg` (a positional is ignored in shell mode).
- **`is_native_shell` / `run_system` / `shell_start`.** These must stay
  reachable on the object stored in `dos_ctx.process`; only `ShellProcess`
  provides them, and `SystemTagList`'s shell branch is only reached when
  `is_native_shell()` is true.

## Resolved decisions

1. **uCLI command path.** The uCLI keeps `cli_CommandDir`.
2. **`-x` semantics.** `-x`/`--shell` is a boolean shortcut for `--mode shell`.
   The shell-seg binary is `command.shell_bin` / `--shell-bin`, default
   `L:shell-seg`.
3. **`MicroCLI` home.** `lib/dos/ucli.py`.
4. **Layering.** `ProcessBase` stays in `lib/dos` (see *Layering decision*).

## Verification checklist

- [ ] `pytest test/unit test/pytask`
- [ ] `pytest test/extra/shell_seg.py` (with the Shell-Seg fixture)
- [ ] `pytest test/suite/proc_args.py`
- [ ] `grep -rn "import Process\b\|Cli.Process" amitools test` returns only the
      intended references
- [ ] `ruff` clean
- [ ] docs build / references updated

## Status

- [x] Step 1 — baseline
- [x] Step 2 — extract `ProcessBase` (reuse `DosProcess` accessors)
- [ ] Step 3 — `BinProcess`
- [ ] Step 4 — `ShellProcess`
- [ ] Step 5 — uCLI helper
- [ ] Step 6 — `shell` mode
- [ ] Step 7 — remove old `Process`
- [ ] Step 8 — docs
