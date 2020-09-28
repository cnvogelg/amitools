import pytest
from amitools.vamos.libcore import LibJumpTable, NoJumpTableEntryError
from amitools.vamos.machine import MockMachine
from amitools.fd import read_lib_fd


def get_jump_table(with_fd=False, **kwargs):
    machine = MockMachine()
    mem = machine.get_mem()
    name = "vamostest.library"
    fd = read_lib_fd(name)
    neg_size = fd.get_neg_size()
    lib_base = neg_size + 0x100
    if not with_fd:
        fd = None
    jt = LibJumpTable(mem, lib_base, neg_size, fd=fd, **kwargs)
    return jt


def libcore_jumptab_create_test():
    jt = get_jump_table(create=True)
    # set entry by index
    jt[1] = 0xCAFEBABE
    assert jt[1] == 0xCAFEBABE
    # invalid key: string
    with pytest.raises(KeyError):
        jt["hello"]
    # invalid index: out of range
    with pytest.raises(IndexError):
        jt[99]
    # set entry by lvo
    jt[-42] = 0x12345678
    assert jt[-42] == 0x12345678
    # invalid index: not modulo 6
    with pytest.raises(IndexError):
        jt[-41]
    # invalid index: out of range
    with pytest.raises(IndexError):
        jt[-99]


def libcore_jumptab_with_fd_test():
    jt = get_jump_table(with_fd=True, create=True)
    # set entry by name
    jt.PrintHello = 0xDEADBEEF
    assert jt.PrintHello == 0xDEADBEEF
    with pytest.raises(AttributeError):
        jt.Blubber
    # set entry by index
    jt[1] = 0xCAFEBABE
    assert jt[1] == 0xCAFEBABE
    assert jt[4] == 0xDEADBEEF
    # invalid key: string
    with pytest.raises(KeyError):
        jt["hello"]
    # invalid index: out of range
    with pytest.raises(IndexError):
        jt[99]
    # set entry by lvo
    jt[-42] = 0x12345678
    assert jt[-42] == 0x12345678
    assert jt[-30] == 0xDEADBEEF
    assert jt[-12] == 0xCAFEBABE
    # invalid index: not modulo 6
    with pytest.raises(IndexError):
        jt[-41]
    # invalid index: out of range
    with pytest.raises(IndexError):
        jt[-99]


def libcore_jumptab_no_create_test():
    jt = get_jump_table(with_fd=True)
    # set entry by name
    with pytest.raises(NoJumpTableEntryError):
        jt.PrintHello = 0xDEADBEEF
    # set entry by index
    with pytest.raises(NoJumpTableEntryError):
        jt[1] = 0xCAFEBABE
    # set entry by lvo
    with pytest.raises(NoJumpTableEntryError):
        jt[-42] = 0x12345678


def libcore_jumptab_iter_test():
    jt = get_jump_table(with_fd=True, create=True)
    for entry in jt:
        entry.set(0)
        print(entry)
