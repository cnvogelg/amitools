import logging
from amitools.vamos.trace import *
from amitools.vamos.label import *
from amitools.vamos.machine import *
from amitools.vamos.libstructs import NodeStruct, LibraryStruct
from amitools.vamos.log import log_mem_int


def setup_tmem():
    machine = MockMachine()
    mem = machine.get_mem()
    lm = machine.get_label_mgr()
    tm = TraceManager(machine)
    lm.add_label(LabelRange("range", 0x100, 0x100))
    lm.add_label(LabelStruct("node", 0x200, NodeStruct))
    lm.add_label(
        LabelLib("fake.library", 0x320, 0x20, LibraryStruct.get_size(), LibraryStruct)
    )
    return TraceMemory(mem, tm)


def trace_mem_rw_test(caplog):
    caplog.set_level(logging.INFO)
    log_mem_int.setLevel(logging.INFO)
    tmem = setup_tmem()
    tmem.w8(0, 42)
    assert tmem.r8(0) == 42
    tmem.w16(2, 4711)
    assert tmem.r16(2) == 4711
    tmem.w32(4, 0xDEADBEEF)
    assert tmem.r32(4) == 0xDEADBEEF
    tmem.write(2, 8, 0xCAFEBABE)
    assert tmem.read(2, 8) == 0xCAFEBABE
    lvl = logging.INFO
    assert caplog.record_tuples == [
        ("mem_int", lvl, "W(1): 000000: 2a                [??] "),
        ("mem_int", lvl, "R(1): 000000: 2a                [??] "),
        ("mem_int", lvl, "W(2): 000002: 1267              [??] "),
        ("mem_int", lvl, "R(2): 000002: 1267              [??] "),
        ("mem_int", lvl, "W(4): 000004: deadbeef          [??] "),
        ("mem_int", lvl, "R(4): 000004: deadbeef          [??] "),
        ("mem_int", lvl, "W(4): 000008: cafebabe          [??] "),
        ("mem_int", lvl, "R(4): 000008: cafebabe          [??] "),
    ]


def trace_mem_rws_test(caplog):
    caplog.set_level(logging.INFO)
    log_mem_int.setLevel(logging.INFO)
    tmem = setup_tmem()
    tmem.w8s(0, -42)
    assert tmem.r8s(0) == -42
    tmem.w16s(2, -4711)
    assert tmem.r16s(2) == -4711
    tmem.w32s(4, -0x1EADBEEF)
    assert tmem.r32s(4) == -0x1EADBEEF
    tmem.writes(2, 8, -0x2AFEBABE)
    assert tmem.reads(2, 8) == -0x2AFEBABE
    lvl = logging.INFO
    assert caplog.record_tuples == [
        ("mem_int", lvl, "W(1): 000000: -2a                [??] "),
        ("mem_int", lvl, "R(1): 000000: -2a                [??] "),
        ("mem_int", lvl, "W(2): 000002: -1267              [??] "),
        ("mem_int", lvl, "R(2): 000002: -1267              [??] "),
        ("mem_int", lvl, "W(4): 000004: -1eadbeef          [??] "),
        ("mem_int", lvl, "R(4): 000004: -1eadbeef          [??] "),
        ("mem_int", lvl, "W(4): 000008: -2afebabe          [??] "),
        ("mem_int", lvl, "R(4): 000008: -2afebabe          [??] "),
    ]
