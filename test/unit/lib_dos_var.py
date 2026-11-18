"""dos.library shell variables: GetVar/SetVar/DeleteVar/FindVar.

The handlers live in ``amitools/vamos/lib/dos/Var.py``. Local variables are
kept both in the current process's ``pr_LocalVars`` list and in
``DosLibrary.local_vars``; global variables live only in
``DosLibrary.global_vars``. These tests drive the typed front-ends directly
with a ``MockMemory`` and a real ``MemoryAlloc`` so node allocations and the
list relinking can be asserted.
"""

from types import SimpleNamespace

from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_BAD_NUMBER,
    ERROR_OBJECT_NOT_FOUND,
)
from amitools.vamos.lib.dos.Var import (
    GVF_BINARY_VAR,
    GVF_GLOBAL_ONLY,
    GVF_LOCAL_ONLY,
)
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import LocalVarStruct, MinListStruct, NodeStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.mem import MemoryAlloc

NAME = 0x400
VALUE = 0x500
BUFFER = 0x600


class _Env:
    """DosLibrary with a real variable allocator and process list head."""

    def __init__(self):
        self.mem = MockMemory(size_kib=64)
        self.alloc = MemoryAlloc(self.mem)
        self.lib = DosLibrary()
        self.lib.alloc = self.alloc
        self.lib.mem_allocs = {}
        self.lib.local_vars = {}
        self.lib.global_vars = {}
        # the current process owns the local variable list; create_var_node()
        # splices new nodes into this MinList
        varlist_mem = self.alloc.alloc_memory(MinListStruct.get_size(), label="VarList")
        self.varlist = MinListStruct(self.mem, varlist_mem.addr)
        head_mem = self.alloc.alloc_memory(NodeStruct.get_size(), label="VarHead")
        self.head_addr = head_mem.addr
        self.varlist.mlh_Head.aptr = self.head_addr
        self.varlist.mlh_Tail.aptr = 0
        self.varlist.mlh_TailPred.aptr = self.head_addr
        self.process = SimpleNamespace(get_local_vars=lambda: self.varlist)
        self.ctx = SimpleNamespace(mem=self.mem, cpu=MockCPU(), process=self.process)

    # ----- helpers -----

    def name(self, text, addr=NAME):
        self.mem.w_cstr(addr, text)
        return addr

    def value(self, text, addr=VALUE):
        self.mem.w_cstr(addr, text)
        return addr

    def set(self, text, val, flags=0):
        return self.lib.SetVar(self.ctx, self.name(text), self.value(val), 0, flags)

    def get(self, text, size=64, flags=0, addr=BUFFER):
        return self.lib.GetVar(self.ctx, self.name(text), addr, size, flags)

    def delete(self, text, flags=0):
        return self.lib.DeleteVar(self.ctx, self.name(text), flags)


# ----- SetVar / GetVar round-trip -----


def lib_dos_var_set_get_string_test():
    env = _Env()
    assert env.set("foo", "bar") == DOSTRUE
    assert ("foo", env.lib.LV_VAR) in env.lib.local_vars
    # GetVar returns the string length and reports it as IoErr
    assert env.get("foo") == len("bar")
    assert env.mem.r_cstr(BUFFER) == "bar"
    assert env.lib.io_err == len("bar")


def lib_dos_var_get_errors_test():
    env = _Env()
    env.set("foo", "bar")
    # size == 0 is rejected before any lookup
    assert env.get("foo", size=0) == -1
    assert env.lib.io_err == ERROR_BAD_NUMBER
    # an unknown name is not found
    assert env.get("missing") == -1
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND


def lib_dos_var_get_truncate_test():
    env = _Env()
    env.set("foo", "hello")
    # a 4 byte buffer leaves room for 3 chars + NUL
    assert env.get("foo", size=4) == 3
    assert env.mem.r_cstr(BUFFER) == "hel"
    # IoErr still reports the full stored length
    assert env.lib.io_err == len("hello")
    # the same truncation applies to a global string
    env.lib.SetVar(env.ctx, env.name("g"), env.value("world"), 0, GVF_GLOBAL_ONLY)
    assert env.get("g", size=4, flags=GVF_GLOBAL_ONLY) == 3
    assert env.mem.r_cstr(BUFFER) == "wor"
    assert env.lib.io_err == len("world")


def lib_dos_var_set_overwrite_test():
    env = _Env()
    env.set("foo", "one")
    node = env.lib.local_vars[("foo", env.lib.LV_VAR)]
    first_buf = node.lv_Value.aptr
    # re-setting replaces the value and frees the old buffer. The allocator
    # may hand the same address back out, so record the free calls directly.
    freed = []
    orig_free = env.lib._free_mem
    env.lib._free_mem = lambda addr: (freed.append(addr), orig_free(addr))
    assert env.set("foo", "longer value") == DOSTRUE
    assert first_buf in freed
    node = env.lib.local_vars[("foo", env.lib.LV_VAR)]
    assert node.lv_Len.val == len("longer value") + 1
    assert env.get("foo") == len("longer value")
    assert env.mem.r_cstr(BUFFER) == "longer value"


# ----- DeleteVar and the freeing path -----


def lib_dos_var_delete_test():
    env = _Env()
    env.set("foo", "bar")
    env.set("baz", "qux")
    foo = env.lib.local_vars[("foo", env.lib.LV_VAR)]
    foo_addr = foo.addr
    foo_buf = foo.lv_Value.aptr
    # deleting unlinks the node and frees both node and value buffer
    assert env.delete("foo") == DOSTRUE
    assert ("foo", env.lib.LV_VAR) not in env.lib.local_vars
    assert foo_addr not in env.lib.mem_allocs
    assert foo_buf not in env.lib.mem_allocs
    # the surviving variable is now the list head
    assert env.varlist.mlh_Head.aptr == env.lib.local_vars[("baz", env.lib.LV_VAR)].addr
    assert env.get("foo") == -1
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND
    # deleting the last variable restores the empty list head
    baz = env.lib.local_vars[("baz", env.lib.LV_VAR)]
    assert env.delete("baz") == DOSTRUE
    assert baz.addr not in env.lib.mem_allocs
    assert env.varlist.mlh_Head.aptr == env.head_addr
    # deleting a missing local variable still succeeds ...
    assert env.delete("foo") == DOSTRUE
    # ... but a missing global delete reports the miss
    assert env.delete("foo", GVF_GLOBAL_ONLY) == DOSFALSE


def lib_dos_var_set_null_delete_test():
    env = _Env()
    env.set("foo", "bar")
    env.lib.SetVar(env.ctx, env.name("foo"), env.value("gfoo"), 0, GVF_GLOBAL_ONLY)
    node = env.lib.local_vars[("foo", env.lib.LV_VAR)]
    node_addr = node.addr
    # a NULL buffer removes the local variable and frees its node
    assert env.lib.SetVar(env.ctx, env.name("foo"), 0, 0, 0) == DOSTRUE
    assert ("foo", env.lib.LV_VAR) not in env.lib.local_vars
    assert node_addr not in env.lib.mem_allocs
    assert env.varlist.mlh_Head.aptr == env.head_addr
    # the global entry of the same name is untouched
    assert env.get("foo", flags=GVF_GLOBAL_ONLY) == len("gfoo")
    assert env.mem.r_cstr(BUFFER) == "gfoo"
    # a NULL buffer with GVF_GLOBAL_ONLY removes the global entry
    assert env.lib.SetVar(env.ctx, env.name("foo"), 0, 0, GVF_GLOBAL_ONLY) == DOSTRUE
    assert ("foo", env.lib.LV_VAR) not in env.lib.global_vars
    assert env.get("foo", flags=GVF_GLOBAL_ONLY) == -1


# ----- FindVar type filter -----


def lib_dos_var_find_test():
    env = _Env()
    env.set("foo", "bar")
    addr = env.lib.FindVar(env.ctx, env.name("foo"), env.lib.LV_VAR)
    assert addr == env.lib.local_vars[("foo", env.lib.LV_VAR)].addr
    node = LocalVarStruct(env.mem, addr)
    assert env.mem.r_cstr(node.lv_Node.ln_Name.aptr) == "foo"
    assert node.lv_Len.val == len("bar") + 1
    # a different vtype does not match
    assert env.lib.FindVar(env.ctx, env.name("foo"), env.lib.LV_ALIAS) == 0
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND
    # an alias is stored under its own type
    env.lib.SetVar(env.ctx, env.name("alias"), env.value("ls"), 0, env.lib.LV_ALIAS)
    assert env.lib.FindVar(env.ctx, env.name("alias"), env.lib.LV_ALIAS) == (
        env.lib.local_vars[("alias", env.lib.LV_ALIAS)].addr
    )
    assert env.lib.FindVar(env.ctx, env.name("alias"), env.lib.LV_VAR) == 0


def lib_dos_var_ignore_flag_test():
    env = _Env()
    env.set("foo", "bar")
    # LVF_IGNORE is part of the lookup key, so it does not match a plain var
    assert env.lib.FindVar(env.ctx, env.name("foo"), env.lib.LVF_IGNORE) == 0
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND


# ----- global vs local flags -----


def lib_dos_var_global_test():
    env = _Env()
    # the same name exists as a local and a global variable
    env.set("foo", "local")
    env.lib.SetVar(env.ctx, env.name("foo"), env.value("global"), 0, GVF_GLOBAL_ONLY)
    # a plain lookup prefers the local value
    assert env.get("foo") == len("local")
    assert env.mem.r_cstr(BUFFER) == "local"
    # GVF_GLOBAL_ONLY reads the global table
    assert env.get("foo", flags=GVF_GLOBAL_ONLY) == len("global")
    assert env.mem.r_cstr(BUFFER) == "global"
    # GVF_LOCAL_ONLY stays local
    assert env.get("foo", flags=GVF_LOCAL_ONLY) == len("local")
    # a global-only variable is still found by a plain lookup ...
    env.lib.SetVar(env.ctx, env.name("bar"), env.value("gbar"), 0, GVF_GLOBAL_ONLY)
    assert env.get("bar") == len("gbar")
    assert env.mem.r_cstr(BUFFER) == "gbar"
    # ... but not when only local variables are wanted
    assert env.get("bar", flags=GVF_LOCAL_ONLY) == -1
    assert env.lib.io_err == ERROR_OBJECT_NOT_FOUND
    # FindVar only ever searches local variables
    assert env.lib.FindVar(env.ctx, env.name("bar"), env.lib.LV_VAR) == 0


# ----- binary variables -----


def lib_dos_var_binary_test():
    env = _Env()
    payload = b"\x00\x01\x02\xff"
    env.mem.w_block(VALUE, payload)
    flags = GVF_BINARY_VAR
    assert (
        env.lib.SetVar(env.ctx, env.name("bin"), VALUE, len(payload), flags) == DOSTRUE
    )
    node = env.lib.local_vars[("bin", env.lib.LV_VAR)]
    assert node.lv_Len.val == len(payload)
    assert env.mem.r_block(node.lv_Value.aptr, len(payload)) == payload
    # GetVar copies the raw bytes and reports the stored length
    assert env.lib.GetVar(env.ctx, env.name("bin"), BUFFER, 64, flags) == len(payload)
    assert env.mem.r_block(BUFFER, len(payload)) == payload
    assert env.lib.io_err == len(payload)
    # a small buffer copies only what fits but still returns that byte count
    assert env.lib.GetVar(env.ctx, env.name("bin"), BUFFER, 2, flags) == 2
    assert env.mem.r_block(BUFFER, 2) == payload[:2]
    assert env.lib.io_err == len(payload)
