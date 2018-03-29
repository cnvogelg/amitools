import logging
from amitools.vamos.trace import *
from amitools.vamos.label import *
from amitools.vamos.machine import *
from amitools.vamos.astructs import NodeStruct, LibraryStruct


class FakeLib:
  def __init__(self):
    self.name = "fake.library"
    self.addr_begin = 0x300
    self.addr_base = 0x320
    self.struct = LibraryStruct
    self.mem_pos_size = self.struct.get_size()
    self.mem_neg_size = 0x20
    self.fd = None


def setup_tmem():
  mem = MockMemory()
  cpu = MockCPU()
  lm = LabelManager()
  tm = TraceManager(cpu, lm)
  lm.add_label(LabelRange("range", 0x100, 0x100))
  lm.add_label(LabelStruct("node", 0x200, NodeStruct))
  lib = FakeLib()
  lm.add_label(LabelLib(lib))
  return TraceMemory(mem, tm)


def trace_mem_rw_test(caplog):
  caplog.set_level(logging.INFO)
  tmem = setup_tmem()
  tmem.w8(0, 42)
  assert tmem.r8(0) == 42
  tmem.w16(2, 4711)
  assert tmem.r16(2) == 4711
  tmem.w32(4, 0xdeadbeef)
  assert tmem.r32(4) == 0xdeadbeef
  tmem.write(2, 8, 0xcafebabe)
  assert tmem.read(2, 8) == 0xcafebabe
  lvl = logging.INFO
  assert caplog.record_tuples == [
      ('mem_int', lvl, 'W(1): 000000: 2a                [??] '),
      ('mem_int', lvl, 'R(1): 000000: 2a                [??] '),
      ('mem_int', lvl, 'W(2): 000002: 1267              [??] '),
      ('mem_int', lvl, 'R(2): 000002: 1267              [??] '),
      ('mem_int', lvl, 'W(4): 000004: deadbeef          [??] '),
      ('mem_int', lvl, 'R(4): 000004: deadbeef          [??] '),
      ('mem_int', lvl, 'W(4): 000008: cafebabe          [??] '),
      ('mem_int', lvl, 'R(4): 000008: cafebabe          [??] ')
  ]


def trace_mem_rws_test(caplog):
  caplog.set_level(logging.INFO)
  tmem = setup_tmem()
  tmem.w8s(0, -42)
  assert tmem.r8s(0) == -42
  tmem.w16s(2, -4711)
  assert tmem.r16s(2) == -4711
  tmem.w32s(4, -0x1eadbeef)
  assert tmem.r32s(4) == -0x1eadbeef
  tmem.writes(2, 8, -0x2afebabe)
  assert tmem.reads(2, 8) == -0x2afebabe
  lvl = logging.INFO
  assert caplog.record_tuples == [
      ('mem_int', lvl, 'W(1): 000000: -2a                [??] '),
      ('mem_int', lvl, 'R(1): 000000: -2a                [??] '),
      ('mem_int', lvl, 'W(2): 000002: -1267              [??] '),
      ('mem_int', lvl, 'R(2): 000002: -1267              [??] '),
      ('mem_int', lvl, 'W(4): 000004: -1eadbeef          [??] '),
      ('mem_int', lvl, 'R(4): 000004: -1eadbeef          [??] '),
      ('mem_int', lvl, 'W(4): 000008: -2afebabe          [??] '),
      ('mem_int', lvl, 'R(4): 000008: -2afebabe          [??] ')
  ]
