import os
import struct
from types import SimpleNamespace

import pytest

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_BAD_NUMBER,
    ERROR_INVALID_LOCK,
    ERROR_NO_FREE_STORE,
    ERROR_NO_MORE_ENTRIES,
    ERROR_OBJECT_WRONG_TYPE,
    ERROR_READ_PROTECTED,
)
from amitools.vamos.lib.dos.Lock import Lock
from amitools.vamos.lib.dos.PatternMatch import pattern_parse
from amitools.vamos.libstructs import (
    ExAllControlStruct,
    ExAllDataStruct,
    FileInfoBlockStruct,
)
from amitools.vamos.machine import (
    Code,
    Machine,
    Runtime,
    REG_D0,
    REG_D1,
    REG_D2,
    REG_A0,
    REG_A1,
    REG_A2,
)
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc


class ExAllEnv:
    def __init__(self, path, mem=None, cpu=None, alloc=None):
        self.path = path
        for name in ("alpha", "bravo", "charlie"):
            (path / name).write_bytes(name.encode())
        self.mem = mem if mem is not None else MockMemory()
        self.cpu = cpu if cpu is not None else MockCPU()
        self.alloc = alloc if alloc is not None else MemoryAlloc(self.mem)
        self.lib = DosLibrary()
        self.lib.alloc = self.alloc
        self.lib.mem_allocs = {}
        self.lib.dos_objs = {}
        self.lib.exall_scans = {}
        self.lock = Lock(path.name, "SYS:dir", str(path))
        self.lock.key = 7
        self.lib.lock_mgr = SimpleNamespace(
            get_by_b_addr=lambda addr: self.lock if addr else None
        )
        self.ctx = SimpleNamespace(
            mem=self.mem,
            cpu=self.cpu,
            alloc=self.alloc,
            process=SimpleNamespace(
                this_task=SimpleNamespace(pr_Result2=SimpleNamespace(val=0))
            ),
        )
        self.controls = []
        self.control = self.new_control()
        self.buffer = self.alloc.alloc_memory(4104)
        self.buf = self.buffer.addr + 4

    def new_control(self):
        self.cpu.w_reg(REG_D1, 1)
        self.cpu.w_reg(REG_D2, 0)
        ptr = self.lib.AllocDosObject(self.ctx)
        control = ExAllControlStruct(self.mem, ptr)
        assert control.eac_LastKey.val == 0
        assert control.eac_MatchFunc.aptr == 0
        self.controls.append(control)
        return control

    def free_control(self, control):
        self.cpu.w_reg(REG_D1, 1)
        self.cpu.w_reg(REG_D2, control.addr)
        self.lib.FreeDosObject(self.ctx)
        self.controls.remove(control)

    def run(self, size=4096, data_type=3, control=None):
        control = self.control if control is None else control
        self.mem.clear_block(self.buffer.addr, self.buffer.size, 0xA5)
        free_before = self.alloc.get_free_bytes()
        more = self.lib.ExAll(self.ctx, 1, self.buf, size, data_type, control.addr)
        assert self.alloc.get_free_bytes() == free_before
        assert bytes(self.mem.r_block(self.buffer.addr, 4)) == b"\xa5" * 4
        assert bytes(self.mem.r_block(self.buf + size, 4)) == b"\xa5" * 4
        entries = []
        addr = self.buf
        for _ in range(control.eac_Entries.val):
            assert self.buf <= addr < self.buf + size
            entry = ExAllDataStruct(self.mem, addr)
            name = self.mem.r_cstr(entry.ed_Name.aptr)
            item = {"name": name, "addr": addr}
            if data_type >= 2:
                item["type"] = entry.ed_Type.val
            if data_type >= 3:
                item["size"] = entry.ed_Size.val
            if data_type >= 6:
                item["comment"] = entry.ed_Comment.aptr
            entries.append(item)
            addr = entry.ed_Next.aptr
        if entries:
            assert addr == 0
        return more, self.lib.io_err, entries

    def close(self):
        for control in list(self.controls):
            self.free_control(control)
        self.alloc.free_memory(self.buffer)
        assert not self.lib.exall_scans
        assert self.alloc.is_all_free()


@pytest.fixture
def env(tmp_path):
    context = ExAllEnv(tmp_path)
    yield context
    context.close()


def names(entries):
    return {entry["name"] for entry in entries}


@pytest.mark.parametrize("data_type", range(1, 8))
def dos_exall_data_types_test(env, data_type):
    more, error, entries = env.run(data_type=data_type)
    assert more == DOSFALSE and error == ERROR_NO_MORE_ENTRIES
    assert names(entries) == {"alpha", "bravo", "charlie"}
    assert not env.lib.exall_scans
    if data_type >= 3:
        assert all(item["size"] == len(item["name"]) for item in entries)
    if data_type >= 6:
        assert all(item["comment"] == 0 for item in entries)


def dos_exall_continuation_test(env):
    found = []
    for _ in range(4):
        more, error, entries = env.run(size=24)
        assert len(entries) <= 1
        found.extend(item["name"] for item in entries)
        if not more:
            assert error == ERROR_NO_MORE_ENTRIES
            break
        assert error == 0
    else:
        pytest.fail("scan did not terminate")
    assert sorted(found) == ["alpha", "bravo", "charlie"]
    assert not env.lib.exall_scans


def dos_exall_partial_exnext_test(env):
    fib = env.alloc.alloc_astruct(FileInfoBlockStruct)
    try:
        assert env.lock.examine_lock(fib) == 0
        assert env.lock.examine_next(fib) == 0
        first = env.mem.r_cstr(fib.fib_FileName.addr)
        _, _, entries = env.run()
        assert names(entries) == {"alpha", "bravo", "charlie"}
        remaining = []
        while env.lock.examine_next(fib) == 0:
            remaining.append(env.mem.r_cstr(fib.fib_FileName.addr))
        assert len(remaining) == 2
        assert first not in remaining
    finally:
        fib.free()


def dos_exall_independent_controls_test(env):
    second = env.new_control()
    _, _, first_entries = env.run(size=24)
    assert len(first_entries) == 1
    assert names(env.run(control=second)[2]) == {"alpha", "bravo", "charlie"}
    _, error, rest = env.run()
    assert error == ERROR_NO_MORE_ENTRIES
    assert len(rest) == 2
    assert names(first_entries + rest) == {"alpha", "bravo", "charlie"}


def dos_exall_end_isolation_test(env):
    second = env.new_control()
    first_entries = env.run(size=24)[2]
    env.run(size=24, control=second)
    env.lib.ExAllEnd(env.ctx, 1, env.buf, 24, 3, second.addr)
    assert second.eac_LastKey.val == 0
    assert second.eac_Entries.val == 0
    assert second.addr not in env.lib.exall_scans
    rest = env.run()[2]
    assert len(rest) == 2
    assert names(first_entries + rest) == {"alpha", "bravo", "charlie"}
    assert names(env.run(control=second)[2]) == {"alpha", "bravo", "charlie"}


def dos_exall_free_control_test(env):
    env.run(size=24)
    ptr = env.control.addr
    assert ptr in env.lib.exall_scans
    env.free_control(env.control)
    assert ptr not in env.lib.exall_scans


def dos_exall_empty_directory_test(env):
    for path in env.path.iterdir():
        path.unlink()
    more, error, entries = env.run()
    assert (more, error, entries) == (DOSFALSE, ERROR_NO_MORE_ENTRIES, [])


@pytest.mark.parametrize("data_type", [0, 8, 0xFFFFFFFF])
def dos_exall_bad_type_test(env, data_type):
    assert env.run(data_type=data_type) == (DOSFALSE, ERROR_BAD_NUMBER, [])


def dos_exall_buffer_too_small_test(env):
    assert env.run(size=4) == (DOSFALSE, ERROR_NO_FREE_STORE, [])
    assert not env.lib.exall_scans
    assert names(env.run()[2]) == {"alpha", "bravo", "charlie"}


def dos_exall_not_directory_test(env):
    env.lock.sys_path = str(env.path / "alpha")
    assert env.run() == (DOSFALSE, ERROR_OBJECT_WRONG_TYPE, [])
    assert not env.lib.exall_scans


def dos_exall_directory_size_test(env, monkeypatch):
    (env.path / "zdir").mkdir()
    listdir = os.listdir
    monkeypatch.setattr(os, "listdir", lambda path: sorted(listdir(path)))
    entries = env.run()[2]
    assert next(item for item in entries if item["name"] == "zdir")["size"] == 0


def dos_exall_match_string_test(env):
    pattern = env.alloc.alloc_cstr(pattern_parse("#?A#?").pat_str)
    try:
        env.control.eac_MatchString.aptr = pattern.addr
        assert names(env.run()[2]) == {"alpha", "bravo", "charlie"}
        env.control.eac_LastKey.val = 0
        env.mem.w_cstr(pattern.addr, pattern_parse("A#?").pat_str)
        assert names(env.run()[2]) == {"alpha"}
    finally:
        env.alloc.free_cstr(pattern)


def dos_exall_match_hook_test(env):
    hook = env.alloc.alloc_memory(20)
    env.mem.w32(hook.addr + 8, 0x1234)
    env.control.eac_MatchFunc.aptr = hook.addr
    calls = []

    def runner(code, name):
        assert name == "ExAllMatch"
        assert code.pc == 0x1234
        assert code.set_regs[REG_A0] == hook.addr
        assert code.get_regs == [REG_D0]
        assert env.mem.r32(code.set_regs[REG_A2]) == 3
        entry = ExAllDataStruct(env.mem, code.set_regs[REG_A1])
        filename = env.mem.r_cstr(entry.ed_Name.aptr)
        assert entry.ed_Size.val == len(filename)
        calls.append(filename)
        return SimpleNamespace(regs={REG_D0: int(filename == "alpha")})

    env.ctx.runner = runner
    try:
        more, error, entries = env.run()
        assert more == DOSFALSE and error == ERROR_NO_MORE_ENTRIES
        assert names(entries) == {"alpha"}
        assert set(calls) == {"alpha", "bravo", "charlie"}
    finally:
        env.alloc.free_memory(hook)


def dos_exall_match_reject_all_test(env):
    hook = env.alloc.alloc_memory(20)
    env.mem.w32(hook.addr + 8, 0x1234)
    env.control.eac_MatchFunc.aptr = hook.addr
    env.ctx.runner = lambda *args, **kwargs: SimpleNamespace(regs={REG_D0: 0})
    try:
        assert env.run(size=24) == (DOSFALSE, ERROR_NO_MORE_ENTRIES, [])
    finally:
        env.alloc.free_memory(hook)


def dos_exall_hook_exception_cleanup_test(env):
    hook = env.alloc.alloc_memory(20)
    env.mem.w32(hook.addr + 8, 0x1234)
    env.control.eac_MatchFunc.aptr = hook.addr

    def fail(*args, **kwargs):
        raise RuntimeError("hook failed")

    env.ctx.runner = fail
    free_before = env.alloc.get_free_bytes()
    try:
        with pytest.raises(RuntimeError, match="hook failed"):
            env.run()
        assert env.alloc.get_free_bytes() == free_before
        assert not env.lib.exall_scans
    finally:
        env.alloc.free_memory(hook)


def dos_exall_no_scratch_memory_test(env, monkeypatch):
    monkeypatch.setattr(env.alloc, "alloc_memory", lambda *args, **kwargs: None)
    assert env.run() == (DOSFALSE, ERROR_NO_FREE_STORE, [])
    assert not env.lib.exall_scans


def dos_exall_host_error_cleanup_test(env, monkeypatch):
    def denied(path):
        raise PermissionError("cannot read directory")

    monkeypatch.setattr(os, "listdir", denied)
    assert env.run() == (DOSFALSE, ERROR_READ_PROTECTED, [])
    assert not env.lib.exall_scans


def dos_exall_wrong_resume_lock_test(env):
    env.run(size=24)
    env.lock = Lock("other", "SYS:other", str(env.path))
    assert env.run() == (DOSFALSE, ERROR_INVALID_LOCK, [])
    assert not env.lib.exall_scans


def dos_exall_native_hook_test(tmp_path):
    machine = Machine()
    mem = machine.get_mem()
    cpu = machine.get_cpu()
    alloc = MemoryAlloc.for_machine(machine)
    env = ExAllEnv(tmp_path, mem, cpu, alloc)
    runtime = Runtime(machine)
    env.ctx.runner = runtime.run
    hook = alloc.alloc_memory(20)
    code = alloc.alloc_memory(64)
    record = alloc.alloc_memory(16)
    outer = alloc.alloc_memory(8)
    # Record the actual A0/A1/A2 arguments and the pointed-to LONG type.
    program = bytearray()
    for opcode, offset in ((0x23C8, 0), (0x23C9, 4), (0x23CA, 8)):
        program.extend(struct.pack(">HI", opcode, record.addr + offset))
    program.extend(struct.pack(">HHI", 0x2012, 0x23C0, record.addr + 12))
    # move.l 4(a1),a0; moveq #0,d0; cmpi.b #'a',(a0); seq d0; rts
    program.extend(bytes.fromhex("2069000470000c10006157c04e75"))
    mem.w_block(code.addr, bytes(program))
    mem.w32(hook.addr + 8, code.addr)
    env.control.eac_MatchFunc.aptr = hook.addr
    results = []

    def enumerate_directory(op, pc):
        results.append(env.run())

    trap = machine.setup_quick_trap(enumerate_directory)
    mem.w_block(outer.addr, struct.pack(">HIH", 0x4EB9, trap, 0x4E75))
    saved = {REG_A0: 0x1111, REG_A1: 0x2222, REG_A2: 0x3333}
    try:
        state = runtime.start(
            Code(
                outer.addr,
                machine.get_scratch_top(),
                set_regs=saved,
                get_regs=list(saved),
            )
        )
        assert state.mach_error is None
        assert state.regs == saved
        assert len(results) == 1
        more, error, entries = results[0]
        assert (more, error) == (DOSFALSE, ERROR_NO_MORE_ENTRIES)
        assert names(entries) == {"alpha"}
        assert mem.r32(record.addr) == hook.addr
        assert env.buf <= mem.r32(record.addr + 4) < env.buf + 4096
        assert mem.r32(record.addr + 8) != 0
        assert mem.r32(record.addr + 12) == 3
    finally:
        for allocation in (hook, code, record, outer):
            alloc.free_memory(allocation)
        env.close()
        machine.cleanup()
