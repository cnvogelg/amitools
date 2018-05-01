import pytest
from musashi import emu


def musashi_mem_rw_test():
  mem = emu.Memory(16)
  assert mem.get_ram_size_kib() == 16

  mem.w8(0x100, 42)
  assert mem.r8(0x100) == 42

  mem.w16(0x200, 0xdead)
  assert mem.r16(0x200) == 0xdead

  mem.w32(0x300, 0xcafebabe)
  assert mem.r32(0x300) == 0xcafebabe

  mem.write(0, 0x101, 43)
  assert mem.read(0, 0x101) == 43

  mem.write(1, 0x202, 0x1234)
  assert mem.read(1, 0x202) == 0x1234

  mem.write(2, 0x304, 0x11223344)
  assert mem.read(2, 0x304) == 0x11223344

  # invalid values
  with pytest.raises(OverflowError):
    mem.w8(0x100, 0x100)
  with pytest.raises(OverflowError):
    mem.w8(0x100, -1)
  # invalid values
  with pytest.raises(OverflowError):
    mem.w16(0x100, 0x10000)
  with pytest.raises(OverflowError):
    mem.w16(0x100, -2)
  # invalid values
  with pytest.raises(OverflowError):
    mem.w32(0x100, 0x100000000)
  with pytest.raises(OverflowError):
    mem.w32(0x100, -3)
  # invalid type
  with pytest.raises(TypeError):
    mem.w8(0x100, 'hello')
  # invalid type
  with pytest.raises(TypeError):
    mem.w16(0x100, 'hello')
  # invalid type
  with pytest.raises(TypeError):
    mem.w32(0x100, 'hello')
  # invalid width
  with pytest.raises(ValueError):
    mem.write(7, 0x202, 12)
  with pytest.raises(ValueError):
    mem.read(7, 0x202)

  # out of range
  with pytest.raises(emu.MemoryError):
    mem.w8(0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.w16(0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.w32(0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.write(0, 0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.r8(0x10000)
  with pytest.raises(emu.MemoryError):
    mem.r16(0x10000)
  with pytest.raises(emu.MemoryError):
    mem.r32(0x10000)
  with pytest.raises(emu.MemoryError):
    mem.read(0, 0x10000)


def musashi_mem_rws_test():
  mem = emu.Memory(16)

  mem.w8s(0x100, 42)
  assert mem.r8s(0x100) == 42
  mem.w8s(0x100, -23)
  assert mem.r8s(0x100) == -23

  mem.w16s(0x200, 0x7ead)
  assert mem.r16s(0x200) == 0x7ead
  mem.w16s(0x200, -0x1000)
  assert mem.r16s(0x200) == -0x1000

  mem.w32s(0x300, 0x1afebabe)
  assert mem.r32s(0x300) == 0x1afebabe
  mem.w32s(0x300, -0xafebabe)
  assert mem.r32s(0x300) == -0xafebabe

  mem.writes(0, 0x101, -43)
  assert mem.reads(0, 0x101) == -43
  mem.writes(1, 0x202, -0x1234)
  assert mem.reads(1, 0x202) == -0x1234
  mem.writes(2, 0x304, -0x11223344)
  assert mem.reads(2, 0x304) == -0x11223344

  # invalid values
  with pytest.raises(OverflowError):
    mem.w8s(0x100, 0x80)
  with pytest.raises(OverflowError):
    mem.w8s(0x100, -0x81)
  # invalid values
  with pytest.raises(OverflowError):
    mem.w16s(0x100, 0x8000)
  with pytest.raises(OverflowError):
    mem.w16s(0x100, -0x8001)
  # invalid values
  with pytest.raises(OverflowError):
    mem.w32s(0x100, 0x80000000)
  with pytest.raises(OverflowError):
    mem.w32s(0x100, -0x80000001)
  # invalid type
  with pytest.raises(TypeError):
    mem.w8s(0x100, 'hello')
  # invalid type
  with pytest.raises(TypeError):
    mem.w16s(0x100, 'hello')
  # invalid type
  with pytest.raises(TypeError):
    mem.w32s(0x100, 'hello')
  # invalid width
  with pytest.raises(ValueError):
    mem.writes(7, 0x202, 12)
  with pytest.raises(ValueError):
    mem.reads(7, 0x202)

  # out of range
  with pytest.raises(emu.MemoryError):
    mem.w8s(0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.w16s(0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.w32s(0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.writes(0, 0x10000, 0)
  with pytest.raises(emu.MemoryError):
    mem.r8s(0x10000)
  with pytest.raises(emu.MemoryError):
    mem.r16s(0x10000)
  with pytest.raises(emu.MemoryError):
    mem.r32s(0x10000)
  with pytest.raises(emu.MemoryError):
    mem.reads(0, 0x10000)


def musashi_mem_block_test():
  mem = emu.Memory(16)
  data = "hello, world!"
  mem.w_block(0, data)
  assert mem.r_block(0, len(data)) == data
  bdata = bytearray(data)
  mem.w_block(0x100, bdata)
  assert mem.r_block(0x100, len(bdata)) == bdata
  mem.clear_block(0x200, 100, 42)
  assert mem.r_block(0x200, 100) == chr(42) * 100
  mem.copy_block(0x200, 0x300, 20)
  assert mem.r_block(0x300, 21) == chr(42) * 20 + chr(0)


def musashi_mem_cstr_test():
  mem = emu.Memory(16)
  data = "hello, world"
  mem.w_cstr(0, data)
  assert mem.r_cstr(0) == data
  empty = ""
  mem.w_cstr(100, empty)
  assert mem.r_cstr(100) == empty


def musashi_mem_bstr_test():
  mem = emu.Memory(16)
  data = "hello, world"
  mem.w_bstr(0, data)
  assert mem.r_bstr(0) == data
  empty = ""
  mem.w_bstr(100, empty)
  assert mem.r_bstr(100) == empty
