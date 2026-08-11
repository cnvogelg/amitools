from amitools.vamos.libstructs import (
    DosEnvecStruct,
    DosLibraryStruct,
    FileSysStartupMsgStruct,
)
from amitools.vamos.machine.mock import MockMemory


def libstructs_dos_dosbase_test():
    mem = MockMemory()
    dosbase = DosLibraryStruct(mem, 0x100)
    assert dosbase.get_byte_size() == 70


def libstructs_dos_disk_startup_test():
    mem = MockMemory()
    fssm = FileSysStartupMsgStruct(mem, 0x100)

    assert DosEnvecStruct.get_byte_size() == 80
    assert FileSysStartupMsgStruct.get_byte_size() == 16

    fssm.fssm_Unit.val = 7
    fssm.fssm_Device.aptr = 0x200
    fssm.fssm_Environ.aptr = 0x300
    fssm.fssm_Flags.val = 3

    assert mem.r32(0x100) == 7
    assert mem.r32(0x104) == 0x200 >> 2
    assert mem.r32(0x108) == 0x300 >> 2
    assert mem.r32(0x10C) == 3
