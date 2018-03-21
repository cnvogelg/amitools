import datetime
from amitools.vamos.libcore import LibMem, LibInfo
from amitools.vamos.machine import MockMemory
from amitools.vamos.label import LabelManager


def libcore_mem_base_test():
  mem = MockMemory(fill=23)
  lib_mem = LibMem(mem, 0x100)
  date = datetime.date(2012, 11, 12)
  info = LibInfo('my.library', 42, 3, date, 36, 6*12)
  name_addr = 0x200
  id_str_addr = 0x300
  lib_mem.init_base()
  lib_mem.write_info(info, name_addr, id_str_addr)
  # read back info
  info2 = lib_mem.read_info()
  assert info == info2
  # flags
  assert lib_mem.read_flags() == 0
  lib_mem.write_flags(7)
  assert lib_mem.read_flags() == 7
  # open cnt
  assert lib_mem.read_open_cnt() == 0
  lib_mem.write_open_cnt(42)
  assert lib_mem.read_open_cnt() == 42
  lib_mem.inc_open_cnt()
  assert lib_mem.read_open_cnt() == 43
  lib_mem.dec_open_cnt()
  assert lib_mem.read_open_cnt() == 42
  # sum
  a = 0xdeadbeef
  b = 0xcafebabe
  mem.w32(0x100 - 4, a)
  mem.w32(0x100 - 8, b)
  assert lib_mem.read_sum() == 0
  assert not lib_mem.check_sum()
  lib_sum = lib_mem.calc_sum()
  lib_mem.update_sum()
  assert lib_mem.read_sum() == lib_sum
  assert lib_mem.check_sum()
  # label
  lm = LabelManager()
  label = lib_mem.set_label(lm)
  lib_mem.remove_label(lm)
