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


def mem_alloc_struct_binding_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    cli = alloc.alloc_struct(CLIStruct, label="CLI")

    assert isinstance(cli.struct, CLIStruct)
    assert not hasattr(cli, "access")

    cli.struct.cli_DefaultStack.val = 42
    cli.struct.cli_CurrentInput.aptr = 0x120

    assert cli.struct.cli_DefaultStack.val == 42
    assert cli.struct.cli_CurrentInput.aptr == 0x120
    assert mem.r32(cli.struct.cli_CurrentInput.addr) == 0x120 >> 2


def mem_alloc_astruct_binding_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    cli = alloc.alloc_astruct(CLIStruct, label="CLI")
    mem_obj = alloc.get_memory(cli.addr)

    assert isinstance(cli, CLIStruct)
    assert mem_obj is cli._mem_obj
    assert not hasattr(mem_obj, "struct")

    cli.cli_DefaultStack.val = 42
    cli.cli_CurrentInput.aptr = 0x120

    assert cli.cli_DefaultStack.val == 42
    assert cli.cli_CurrentInput.aptr == 0x120
    assert mem.r32(cli.cli_CurrentInput.addr) == 0x120 >> 2


def mem_alloc_struct_alloc_fast_path_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    cli = CLIStruct.alloc(alloc, tag="CLI")
    mem_obj = alloc.get_memory(cli.addr)

    assert isinstance(cli, CLIStruct)
    assert mem_obj is cli._mem_obj
    assert not hasattr(mem_obj, "struct")


def mem_alloc_lib_struct_addr_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = alloc.alloc_lib(LibraryStruct, neg_size=32, label="Library")

    assert isinstance(lib.struct, LibraryStruct)
    assert not hasattr(lib, "access")
    assert lib.struct.addr == lib.addr + 32

    lib.struct.lib_Node.ln_Type.val = NodeType.NT_LIBRARY
    assert lib.struct.lib_Node.ln_Type.val == NodeType.NT_LIBRARY


def mem_alloc_alib_fast_path_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    lib = LibraryStruct.alloc(alloc, neg_size=32)

    assert isinstance(lib, LibraryStruct)
    assert lib._mem_obj is alloc.get_memory(lib.addr - 32)
    assert not hasattr(lib._mem_obj, "struct")
