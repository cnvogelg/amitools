from amitools.vamos.machine import MockMemory

def machine_mem_rwx_test():
  mem = MockMemory()
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

def machine_mem_block_test():
  mem = MockMemory()
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

def machine_mem_cstr_test():
  mem = MockMemory()
  data = "hello, world"
  mem.w_cstr(0, data)
  assert mem.r_cstr(0) == data
  empty = ""
  mem.w_cstr(100, empty)
  assert mem.r_cstr(100) == empty

def machine_mem_bstr_test():
  mem = MockMemory()
  data = "hello, world"
  mem.w_bstr(0, data)
  assert mem.r_bstr(0) == data
  empty = ""
  mem.w_bstr(100, empty)
  assert mem.r_bstr(100) == empty
