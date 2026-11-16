# Vamos DOS Handler Refactor

Track the work to separate `dos.library` from file-system implementations via
an AmigaDOS-style handler API.

## Goal

Remove host/sys-path dependencies from the vamos core and move host file
system handling behind an explicit host boundary. The separation between
`dos.library` and a file-system implementation is an AmigaDOS-style
**handler** API: every DOS packet used to talk to a real handler maps to a
method on the handler.

```text
dos.library
   │  Handler API (packet-shaped methods)
   ▼
HandlerManager                 volume/device name -> Handler
   ├── HostFileSysHandler       (now: host dirs behind HostFileSystem)
   ├── PacketHandler            (later: real DOS packets -> native handler)
   ├── RamHandler               (later: in-memory FS, replaces temp-dir RAM:)
   ├── NilHandler               (later: NIL:)
   └── ConsoleHandler           (later: CONSOLE:/*)
```

`dos.library`, `LockManager`, `FileManager`, `Lock`, and `FileHandle` must not
know about host paths. Only the handler talks to a file-system implementation.

## Decisions

1. **Per-volume handlers.** One `HostFileSysHandler` per host volume, bound to
   a `Volume`. Later `RAM:`, `NIL:`, `CONSOLE:` become their own handlers
   instead of `FileManager` special cases.
2. **Errors are Python exceptions.** `HandlerError(code)`; the code domain is
   DOS-compatible integer codes owned by the handler package, so DOS and the
   future `PacketHandler` map 1:1 without importing `lib/dos`.
3. **Step by step.** Implement, test, commit, then proceed.
4. **Package layout.** New top-level `amitools.vamos.handler` package:
   - `handler/base.py` — handler API, handle/result types, `HandlerError`
   - `handler/mgr.py` — `HandlerManager` (volume/device registration, Amiga
     path resolution, dispatch)
   - `handler/filesys.py` — `HostFileSysHandler`
   - later: `handler/ram.py`, `handler/nil.py`
   - `handler/hostfs/` — helper classes if `filesys` grows enough

## Handler API

Handles and results are handler-level types, not DOS structs:

- `HandlerLock` — opaque lock reference
- `HandlerFile` — opaque open-file reference
- `HandlerFileInfo` — examine result (`name`, `entry_type`, `size`, `blocks`,
  `protection`, `date`, `key`, `comment`, ...)
- `HandlerInfoData` / `HandlerDiskInfo` — volume/disk info
- `HandlerError(code)` — raised on failure, maps to DOS `IoErr`

Methods map to packet actions. Handler methods receive **volume-relative**
Amiga paths (the ``HandlerManager`` resolves assigns, cwd, and the volume
split first). Operations on an existing object take the handler lock/file.

| Action | Method |
|---|---|
| `LOCATE_OBJECT` | `locate_object(ami_path, exclusive=False) -> HandlerLock` |
| `FREE_LOCK` | `free_lock(lock)` |
| `COPY_DIR` | `copy_dir(lock) -> HandlerLock` |
| `PARENT` | `parent(lock) -> HandlerLock` |
| `SAME_LOCK` | `same_lock(a, b) -> bool` |
| `EXAMINE_OBJECT` | `examine_object(lock) -> HandlerFileInfo` |
| `EXAMINE_NEXT` | `examine_next(lock, key) -> HandlerFileInfo` |
| `FINDINPUT` | `find_input(ami_path) -> HandlerFile` |
| `FINDOUTPUT` | `find_output(ami_path, mode) -> HandlerFile` |
| `FINDUPDATE` | `find_update(ami_path) -> HandlerFile` |
| `READ` | `read(fh, size) -> bytes` |
| `WRITE` | `write(fh, data) -> int` |
| `SEEK` | `seek(fh, offset, whence) -> int` |
| `SET_FILE_SIZE` | `set_file_size(fh, size, mode) -> int` |
| `FLUSH` | `flush(fh)` |
| `END` | `end(fh)` |
| `DELETE_OBJECT` | `delete_object(ami_path)` |
| `RENAME_OBJECT` | `rename_object(old, new)` |
| `SET_PROTECT` | `set_protect(ami_path, mask)` |
| `SET_COMMENT` | `set_comment(ami_path, comment)` |
| `SET_DATE` | `set_date(ami_path, date)` |
| `CREATE_DIR` | `create_dir(ami_path)` |
| `FH_FROM_LOCK` | `fh_from_lock(lock, mode) -> HandlerFile` |
| `PARENT_FH` / `COPY_DIR_FH` | `parent_fh(fh)` / `copy_dir_fh(fh)` |
| `IS_FILESYSTEM` | handler attribute `is_filesystem` |
| `INFO` / `DISK_INFO` | `info(lock)` / `disk_info(lock)` |

Unsupported actions raise `HandlerError(ERROR_ACTION_NOT_KNOWN)`.

## Staging

### 5a. Handler API + `HostFileSysHandler` + `HandlerManager` (standalone)

- [x] Create `amitools/vamos/handler/` package (`__init__.py`, `base.py`,
      `mgr.py`, `filesys.py`, `protection.py`).
- [x] Define `Handler` API, handle/result types, and `HandlerError` in
      `handler/base.py`.
- [x] Extend `HostFileSystem` (`path/syspath.py`) with `open`, `stat`,
      `access`, `remove`, `rmdir`, `rename`, `chmod`, `mkdir`, `utime`,
      `disk_usage`, `get_umask`; factor `follow_path_no_case`.
- [x] Move `DosProtection` into `handler/protection.py` (re-exported from
      `lib/dos/DosProtection.py`).
- [x] Implement per-volume `HostFileSysHandler` using `HostFileSystem` and
      case-insensitive path lookup.
- [x] Implement `HandlerManager` (volume/device registration, Amiga path
      resolution, dispatch).
- [x] Add standalone unit tests (tmpdir) for the handler
      (`test/unit/handler_filesys.py`, `test/unit/handler_mgr.py`).
- [x] Run `black`, `test/unit`, `test/suite`; commit 5a.

No DOS wiring in 5a.

### 5b. Wire DOS to handlers

- [x] Register volume handlers at `DosLibrary.setup_lib` (one
      `HostFileSysHandler` per host volume, shared `HostFileSystem`).
- [x] `LockManager`/`FileManager`/`DosLibrary` delegate to `HandlerManager`
      (`open`, `delete`, `rename`, `set_protection`, `create_dir`,
      `is_file_system`, `SetFileDate`, `Info`).
- [x] Keep existing DOS BPTR/struct behavior.
- [x] `Lock`/`FileHandle` still keep their fields (`sys_path` etc.) for now;
      `Lock` gained optional `handler`/`handler_lock`.
- [x] `HostFileSystem.disk_usage` reports `read_only`; the handler maps it to
      the DOS disk state. `find_output` matches the old DOS mode handling
      (truncate on `MODE_NEWFILE`, read-only fallback for unwritable files).
- [x] Test and commit 5b.

### 5c. Remove `sys_path` from `Lock`/`FileHandle`

- [x] `Lock` stores handler + handler lock + Amiga path (no `sys_path`);
      `examine_lock`/`examine_next` go through the handler and fill the FIB
      from `HandlerFileInfo`; `find_volume_node` stays.
- [x] `FileHandle` stores handler + handler file + Amiga path (no `sys_path`).
- [x] `LockManager` keys locks by `(handler identity, handler lock key)`
      (Amiga path fallback for handler-less locks).
- [x] `DosLibrary.ExAll` uses `lock.clone_for_scan()` (a fresh handler lock
      with its own ExNext cache; maps non-directory to
      `ERROR_OBJECT_WRONG_TYPE`).
- [x] `DosLibrary.Info` uses the lock's handler for disk usage.
- [x] Retire DOS use of `ami_to_sys_path` (the direct calls are gone;
      `PathMatch`/`MatchFirstNext` still list dirs via the legacy
      `ami_list_dir`/`ami_path_exists` path-manager helpers, see Later).
- [x] Fix the three latent `LockManager` bugs (`no_locks()` inversion,
      `self.locks` -> `self.keys`, and the never-populated key map), with a
      lock release test (`test/unit/dos_lockmanager.py`).
- [x] Update `test/unit/dos_exall.py` (build a `HostFileSysHandler`) and
      add the multi-assign pin.
- [x] Multi-assign writes: keep the previous DOS `searchMulti` behavior in
      `HandlerManager.find_output` (prefer an existing candidate, else
      create in the first), pinned by a test.
- [x] Test and commit 5c.

### Later

- [ ] `PacketHandler` bridge (real `DosPacketStruct` to a native handler port).
- [ ] `RamHandler` replacing the temp-dir `RAM:`.
- [ ] `NilHandler` / `ConsoleHandler` replacing `FileManager` special cases.
- [ ] Route `PathMatch`/`MatchFirstNext` directory listing through handlers.
- [ ] Call `handler.free_lock` on lock release once a handler needs it.

## Verification

- `test/unit` (notably `dos_filehandle*`, `dos_filemanager`, `dos_exall`,
  `dos_lockmanager`, `handler_mgr`, `lib_dos_info`)
- `test/suite`
- Manual host-path and Amiga-path binary runs, plus `dos_examine` and
  `dos_match`

## Progress log

| Step | Commit | State |
|---|---|---|
| 5a | `c2a9df45` handler API + host FS handler | done |
| 5b | `0650744a` route DOS file/lock ops through handlers | done |
| 5c | `2f8ec12c` handler-based locks, no sys_path | done |
