import logging
from amitools.vamos.trace import TraceManager
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


def setup_tm():
  mem = MockMemory()
  cpu = MockCPU()
  lm = LabelManager()
  tm = TraceManager(cpu, lm)
  lm.add_label(LabelRange("range", 0x100, 0x100))
  lm.add_label(LabelStruct("node", 0x200, NodeStruct))
  lib = FakeLib()
  lm.add_label(LabelLib(lib))
  return tm


def check_log(chn, records):
  lvl = logging.INFO
  assert records == [
      (chn, lvl, 'R(4): 000000: 00000000          [??] '),
      (chn, lvl, 'W(2): 000004: 0017              [??] '),
      (chn, lvl, 'R(4): 000100: 00000000          [@000100 +000000 range] '),
      (chn, lvl, 'W(2): 000120: 002a              [@000100 +000020 range] '),
      (chn, lvl,
          'R(4): 000200: 00000000  Struct  [@000200 +000000 node] Node+0 = ln_Succ(Node*)+0'),
      (chn, lvl,
          'W(2): 000208: 0015      Struct  [@000200 +000008 node] Node+8 = ln_Type(UBYTE)+0'),
      (chn, lvl,
          'R(2): 000300: a000        TRAP  [@000300 +000000 fake.library] -32 [5]  '),
      (chn, lvl,
          'R(2): 000320: 0000      Struct  [@000300 +000020 fake.library] Library+0 = lib_Node.ln_Succ(Node*)+0')
  ]


def trace_mgr_mem_test(caplog):
  caplog.set_level(logging.INFO)
  tm = setup_tm()
  # no label
  tm.trace_mem(ord('R'), 2, 0)
  tm.trace_mem(ord('W'), 1, 4, 23)
  # range label
  tm.trace_mem(ord('R'), 2, 0x100)
  tm.trace_mem(ord('W'), 1, 0x120, 42)
  # struct label
  tm.trace_mem(ord('R'), 2, 0x200)
  tm.trace_mem(ord('W'), 1, 0x208, 21)
  # lib
  tm.trace_mem(ord('R'), 1, 0x300, 0xa000)
  tm.trace_mem(ord('R'), 1, 0x320)
  check_log("mem", caplog.record_tuples)


def trace_mgr_int_mem_test(caplog):
  caplog.set_level(logging.INFO)
  tm = setup_tm()
  # no label
  tm.trace_int_mem('R', 2, 0)
  tm.trace_int_mem('W', 1, 4, 23)
  # range label
  tm.trace_int_mem('R', 2, 0x100)
  tm.trace_int_mem('W', 1, 0x120, 42)
  # struct label
  tm.trace_int_mem('R', 2, 0x200)
  tm.trace_int_mem('W', 1, 0x208, 21)
  # lib
  tm.trace_int_mem('R', 1, 0x300, 0xa000)
  tm.trace_int_mem('R', 1, 0x320)
  check_log("mem_int", caplog.record_tuples)


def trace_mgr_int_block_test(caplog):
  caplog.set_level(logging.INFO)
  tm = setup_tm()
  tm.trace_int_block('R', 0x100, 0x20)
  lvl = logging.INFO
  assert caplog.record_tuples == [
      ('mem_int', lvl,
       'R(B): 000100: +000020           [@000100 +000000 range] ')
  ]


def trace_mgr_code_line_test(caplog):
  caplog.set_level(logging.INFO)
  tm = setup_tm()
  tm.trace_code_line(0x100)
  lvl = logging.INFO
  assert caplog.record_tuples == [
      ('instr', lvl, '@000100 +000000 range                     000100    nop                 ')
  ]
