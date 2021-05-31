import pytest
from amitools.vamos.machine import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libstructs import NodeType
from amitools.vamos.libtypes import Process, CLI


def libtypes_process_base_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # alloc proc
    name = "my_proc"
    proc = Process.alloc(alloc, name=name)
    assert proc.name.str == name
    # proc setup
    proc.new_proc()
    node = proc.task.node
    assert node.type.val == NodeType.NT_PROCESS
    # done
    proc.free()
    assert alloc.is_all_free()


def libtypes_process_bptr_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    # alloc proc
    proc = Process.alloc(alloc)
    # set list (as baddr)
    proc.seg_list.bptr = 0x40
    assert proc.seg_list.bptr == 0x40
    # check in mem seg list baddr
    off = proc.sdef.pr_SegList.offset
    addr = proc.addr + off
    assert mem.r32(addr) == 0x40
    # setup CLI
    cli = CLI.alloc(alloc)
    proc.cli.ref = cli
    assert type(proc.cli.ref) is CLI
    assert proc.cli.aptr == cli.addr
    # check in mem CLI baddr
    off = proc.sdef.pr_CLI.offset
    addr = proc.addr + off
    assert mem.r32(addr) == cli.addr >> 2
    cli.free()
    # done
    proc.free()
    assert alloc.is_all_free()
