from amitools.vamos.libstructs import (
    DosEnvecStruct,
    DosLibraryStruct,
    FileSysStartupMsgStruct,
    ExAllControlStruct,
    ExAllDataStruct,
)
from amitools.vamos.machine.mock import MockMemory


def libstructs_dos_dosbase_test():
    mem = MockMemory()
    dosbase = DosLibraryStruct(mem, 0x100)
    assert dosbase.get_byte_size() == 70


def libstructs_dos_exall_layout_test():
    mem = MockMemory()
    control = ExAllControlStruct(mem, 0x100)
    entry = ExAllDataStruct(mem, 0x200)
    assert control.get_byte_size() == 16
    assert control.eac_LastKey.addr == 0x104
    assert control.eac_MatchString.addr == 0x108
    assert control.eac_MatchFunc.addr == 0x10C
    assert entry.get_byte_size() == 40
    assert entry.ed_Name.addr == 0x204
    assert entry.ed_Type.addr == 0x208
    assert entry.ed_Size.addr == 0x20C
    assert entry.ed_Prot.addr == 0x210
    assert entry.ed_Days.addr == 0x214
    assert entry.ed_Comment.addr == 0x220
    assert entry.ed_OwnerUID.addr == 0x224
    assert entry.ed_OwnerGID.addr == 0x226


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
