from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc
from amitools.vamos.libstructs.dos import CLIStruct
from amitools.vamos.libstructs.exec_ import LibraryStruct, NodeType


def mem_alloc_base_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    assert alloc.is_all_free()
    addr = alloc.alloc_mem(1024)
    alloc.free_mem(addr, 1024)
    assert alloc.is_all_free()


def mem_alloc_nonbase4_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    assert alloc.is_all_free()
    addr = alloc.alloc_mem(1021)
    alloc.free_mem(addr, 1021)
    assert alloc.is_all_free()


def mem_alloc_struct_access_compat_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    cli = alloc.alloc_struct(CLIStruct, label="CLI")

    assert isinstance(cli.struct, CLIStruct)
    assert cli.access.struct is cli.struct

    cli.access.w_s("cli_DefaultStack", 42)
    cli.access.w_s("cli_CurrentInput", 0x120)

    assert cli.access.r_s("cli_DefaultStack") == 42
    assert cli.access.r_s("cli_CurrentInput") == 0x120
    assert cli.struct.cli_DefaultStack.val == 42
    assert cli.struct.cli_CurrentInput.aptr == 0x120
    assert mem.r32(cli.access.s_get_addr("cli_CurrentInput")) == 0x120 >> 2


def mem_alloc_lib_struct_addr_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = alloc.alloc_lib(LibraryStruct, neg_size=32, label="Library")

    assert isinstance(lib.struct, LibraryStruct)
    assert lib.struct.addr == lib.addr + 32

    lib.access.w_s("lib_Node.ln_Type", NodeType.NT_LIBRARY)
    assert lib.struct.lib_Node.ln_Type.val == NodeType.NT_LIBRARY
