import pytest
from amitools.vamos.libstructs import DosLibraryStruct
from amitools.vamos.machine import MockMemory


def libstructs_dos_dosbase_test():
    mem = MockMemory()
    dosbase = DosLibraryStruct(mem, 0x100)
    assert dosbase.get_byte_size() == 70
