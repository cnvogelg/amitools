from amitools.vamos.libstructs import (
    InterruptStruct,
    MemEntryStruct,
    MemListStruct,
    NodeType,
)
from amitools.vamos.libtypes import ExecLibrary as ExecLibraryType

# a MemList holds its MemEntry[] right after the header
_ENTRY_OFF = MemListStruct.get_size()
_ENTRY_SIZE = MemEntryStruct.get_size()


def pytask_exec_alloc_entry_test(vamos_task):
    def task(ctx, task):
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # build an input MemList with two requested blocks
        size = _ENTRY_OFF + 2 * _ENTRY_SIZE
        in_mem = ctx.alloc.alloc_memory(size, label="in MemList")
        ml = MemListStruct(ctx.mem, in_mem.addr)
        ml.num_entries.val = 2
        for i, (reqs, length) in enumerate([(1, 0x40), (1, 0x80)]):
            me = MemEntryStruct(ctx.mem, in_mem.addr + _ENTRY_OFF + i * _ENTRY_SIZE)
            me.me_Un.val = reqs
            me.me_Length.val = length

        res_addr = exec_lib.AllocEntry(ml)
        assert res_addr != 0 and not (res_addr & 0x80000000)

        res = MemListStruct(ctx.mem, res_addr)
        assert res.num_entries.val == 2
        blocks = []
        for i in range(2):
            me = MemEntryStruct(ctx.mem, res_addr + _ENTRY_OFF + i * _ENTRY_SIZE)
            assert me.me_Un.val != 0
            assert ctx.alloc.get_memory(me.me_Un.val) is not None
            blocks.append(me.me_Un.val)
        assert blocks[0] != blocks[1]

        exec_lib.FreeEntry(res)
        # the returned MemList and every block were freed again
        assert ctx.alloc.get_memory(res_addr) is None
        for addr in blocks:
            assert ctx.alloc.get_memory(addr) is None

        ctx.alloc.free_memory(in_mem)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_alloc_entry_failure_test(vamos_task):
    def task(ctx, task):
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        # a request that cannot be satisfied reports the failed memory type
        size = _ENTRY_OFF + _ENTRY_SIZE
        in_mem = ctx.alloc.alloc_memory(size, label="in MemList")
        ml = MemListStruct(ctx.mem, in_mem.addr)
        ml.num_entries.val = 1
        me = MemEntryStruct(ctx.mem, in_mem.addr + _ENTRY_OFF)
        me.me_Un.val = 0x1234
        me.me_Length.val = 0x7FFFFFFF

        res = exec_lib.AllocEntry(ml)
        # the top bit marks a failed AllocEntry, the rest is the memory type
        assert res & 0x80000000
        assert res & 0x7FFFFFFF == 0x1234

        ctx.alloc.free_memory(in_mem)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_add_mem_list_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        exec_base = ExecLibraryType(ctx.mem, exec_proxy.base_addr)

        # register an extra block of RAM as a MemHeader
        block = ctx.alloc.alloc_memory(0x200, label="extra RAM")
        # keep the name string alive: exec stores the pointer, it does not copy
        name_mem = ctx.alloc.alloc_cstr("extra RAM", label="memname")
        exec_proxy.AddMemList(0x200, 1, 10, block.addr, name_mem.addr)

        node = exec_base.mem_list.find_name("extra RAM")
        assert node is not None
        assert node.type.val == NodeType.NT_MEMORY
        assert node.name.str == "extra RAM"

        # unlink and release the extra block again
        node.remove()
        ctx.alloc.free_cstr(name_mem)
        ctx.alloc.free_memory(block)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_mem_handler_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        exec_base = ExecLibraryType(ctx.mem, exec_proxy.base_addr)

        handler_mem = ctx.alloc.alloc_struct(InterruptStruct)
        handler = InterruptStruct(ctx.mem, handler_mem.addr)

        exec_proxy.AddMemHandler(handler)
        assert exec_base.mem_handlers.get_head().addr == handler.addr

        exec_proxy.RemMemHandler(handler)
        assert exec_base.mem_handlers.is_empty()

        ctx.alloc.free_struct(handler_mem)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]


def pytask_exec_cache_control_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        exec_base = ExecLibraryType(ctx.mem, exec_proxy.base_addr)

        before = exec_base.cache_control.val
        old = exec_proxy.CacheControl(0x3, 0x1)
        assert old == before
        assert exec_base.cache_control.val == (before & ~0x1) | (0x3 & 0x1)
        # restore the original value
        exec_proxy.CacheControl(before, 0xFFFFFFFF)
        assert exec_base.cache_control.val == before
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
