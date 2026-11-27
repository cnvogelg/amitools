from amitools.vamos.lib.lexec.memfunc import MemoryMixin
from amitools.vamos.libstructs import (
    InterruptStruct,
    MemEntryStruct,
    MemHeaderStruct,
    MemListStruct,
    NodeType,
)
from lib_exec_helper import ExecHost, make_exec_lib

from types import SimpleNamespace

_ENTRY_OFF = MemListStruct.get_size()
_ENTRY_SIZE = MemEntryStruct.get_size()


class Host(ExecHost, MemoryMixin):
    pass


def _host():
    mem, alloc, el = make_exec_lib()
    return Host(mem, alloc, el)


def _make_memlist(alloc, mem, entries):
    size = _ENTRY_OFF + len(entries) * _ENTRY_SIZE
    mb = alloc.alloc_memory(size, label="input MemList")
    ml = MemListStruct(mem, mb.addr)
    ml.num_entries.val = len(entries)
    for i, (reqs, length) in enumerate(entries):
        me = MemEntryStruct(mem, mb.addr + _ENTRY_OFF + i * _ENTRY_SIZE)
        me.me_Un.val = reqs
        me.me_Length.val = length
    return ml


def exec_alloc_abs_test():
    host = _host()
    assert host.AllocAbs(host.ctx, 0x100, 0x2000) == 0


def exec_alloc_entry_free_entry_test():
    host = _host()
    mem, alloc = host.mem, host.alloc
    entry = _make_memlist(alloc, mem, [(1, 0x40), (1, 0x80)])
    res_addr = host.AllocEntry(host.ctx, entry)
    assert res_addr != 0 and not (res_addr & 0x80000000)
    res = MemListStruct(mem, res_addr)
    assert res.num_entries.val == 2
    blocks = []
    for i in range(2):
        me = MemEntryStruct(mem, res_addr + _ENTRY_OFF + i * _ENTRY_SIZE)
        blocks.append(me.me_Un.val)
        assert me.me_Un.val != 0
        assert alloc.get_memory(me.me_Un.val) is not None
    assert blocks[0] != blocks[1]
    host.FreeEntry(host.ctx, res)
    # the returned MemList and every block were freed again
    assert alloc.get_memory(res_addr) is None
    for addr in blocks:
        assert alloc.get_memory(addr) is None


def exec_alloc_entry_failure_test():
    host = _host()
    mem, alloc = host.mem, host.alloc
    entry = _make_memlist(alloc, mem, [(0x1234, 0x7FFFFFFF)])
    res = host.AllocEntry(host.ctx, entry)
    # the top bit marks a failed AllocEntry, the rest is the memory type
    assert res & 0x80000000
    assert res & 0x7FFFFFFF == 0x1234


def exec_add_mem_list_test():
    host = _host()
    mem, alloc = host.mem, host.alloc
    base = alloc.alloc_memory(0x200, label="extra RAM")
    name = SimpleNamespace(aptr=0x1234)
    host.AddMemList(host.ctx, 0x200, 1, 10, base.addr, name)
    node = host.exec_lib.mem_list.get_head()
    assert node.addr == base.addr
    mh = MemHeaderStruct(mem, base.addr)
    assert mh.mh_Node.ln_Type.val == NodeType.NT_MEMORY
    assert mh.mh_Node.ln_Pri.val == 10
    assert mh.mh_Node.ln_Name.aptr == 0x1234
    assert mh.mh_Lower.aptr == base.addr
    assert mh.mh_Upper.aptr == base.addr + 0x200
    assert mh.mh_Free.val == 0x200 - MemHeaderStruct.get_size()
    assert mh.mh_First.aptr == base.addr + MemHeaderStruct.get_size()


def exec_mem_handler_test():
    host = _host()
    handler = host.alloc.alloc_astruct(InterruptStruct, label="memhandler")
    host.AddMemHandler(host.ctx, handler)
    assert host.exec_lib.mem_handlers.get_head().addr == handler.addr
    host.RemMemHandler(host.ctx, handler)
    assert host.exec_lib.mem_handlers.is_empty()


def exec_cache_test():
    host = _host()
    el = host.exec_lib
    assert host.CacheControl(host.ctx, 0x3, 0x1) == 0
    assert el.cache_control.val == 0x1
    assert host.CacheControl(host.ctx, 0x0, 0x3) == 0x1
    assert el.cache_control.val == 0x0
    assert host.CachePreDMA(host.ctx, 0x2000, 0x100, 0) == 0x2000
    assert host.CachePostDMA(host.ctx, 0x2000, 0x100, 0) == 0x2000
    assert host.CacheClearE(host.ctx, 0x2000, 0x100, 3) is None
