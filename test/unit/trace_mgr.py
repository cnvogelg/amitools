import logging
from amitools.vamos.trace import TraceManager
from amitools.vamos.label import *
from amitools.vamos.machine import *
from amitools.vamos.libstructs import NodeStruct, LibraryStruct
from amitools.vamos.cfgcore import ConfigDict
from amitools.fd import read_lib_fd


def setup_tm():
    machine = MockMachine()
    lm = machine.get_label_mgr()
    tm = TraceManager(machine)
    lm.add_label(LabelRange("range", 0x100, 0x100))
    lm.add_label(LabelStruct("node", 0x200, NodeStruct))
    lm.add_label(
        LabelLib("fake.library", 0x320, 0x20, LibraryStruct.get_size(), LibraryStruct)
    )
    fd = read_lib_fd("vamostest.library")
    neg_size = fd.get_neg_size()
    lm.add_label(
        LabelLib(
            "vamostest.library",
            0x400,
            neg_size,
            LibraryStruct.get_size(),
            LibraryStruct,
            fd,
        )
    )
    return tm


def check_log(chn, records):
    lvl = logging.INFO
    assert records == [
        (chn, lvl, "R(4): 000000: 00000000          [??] "),
        (chn, lvl, "W(2): 000004: 0017              [??] "),
        (chn, lvl, "R(4): 000100: 00000000          [@000100 +000000 range] "),
        (chn, lvl, "W(2): 000120: 002a              [@000100 +000020 range] "),
        (
            chn,
            lvl,
            "R(4): 000200: 00000000  Struct  [@000200 +000000 node] Node+0 = ln_Succ(Node*)+0",
        ),
        (
            chn,
            lvl,
            "W(2): 000208: 0015      Struct  [@000200 +000008 node] Node+8 = ln_Type(NodeType)+0",
        ),
        (
            chn,
            lvl,
            "R(2): 000300: 0000        JUMP  [@000300 +000000 fake.library] -32  [5]+2",
        ),
        (
            chn,
            lvl,
            "R(2): 000320: 0000      Struct  [@000300 +000020 fake.library] Library+0 = lib_Node.ln_Succ(Node*)+0",
        ),
        (
            chn,
            lvl,
            "R(2): 0003dc: 0000        JUMP  [@0003b8 +000024 vamostest.library] -36  [6]  PrintString( str/a0 )",
        ),
        (
            chn,
            lvl,
            "R(2): 000420: 0000      Struct  [@0003b8 +000068 vamostest.library] Library+32 = lib_OpenCnt(UWORD)+0",
        ),
    ]


def trace_mgr_parse_config_test():
    cfg = ConfigDict(
        {"vamos_ram": True, "memory": True, "instr": True, "reg_dump": True}
    )
    machine = Machine()
    tm = TraceManager(machine)
    assert tm.parse_config(cfg)


def trace_mgr_mem_test(caplog):
    caplog.set_level(logging.INFO)
    tm = setup_tm()
    tm.setup_cpu_mem_trace()
    # no label
    tm.trace_cpu_mem("R", 2, 0)
    tm.trace_cpu_mem("W", 1, 4, 23)
    # range label
    tm.trace_cpu_mem("R", 2, 0x100)
    tm.trace_cpu_mem("W", 1, 0x120, 42)
    # struct label
    tm.trace_cpu_mem("R", 2, 0x200)
    tm.trace_cpu_mem("W", 1, 0x208, 21)
    # lib
    tm.trace_cpu_mem("R", 1, 0x300)
    tm.trace_cpu_mem("R", 1, 0x320)
    # lib with fd
    tm.trace_cpu_mem("R", 1, 0x400 - 36)
    tm.trace_cpu_mem("R", 1, 0x420)
    check_log("mem", caplog.record_tuples)


def trace_mgr_int_mem_test(caplog):
    caplog.set_level(logging.INFO)
    tm = setup_tm()
    tm.setup_vamos_ram_trace()
    # no label
    tm.trace_int_mem("R", 2, 0)
    tm.trace_int_mem("W", 1, 4, 23)
    # range label
    tm.trace_int_mem("R", 2, 0x100)
    tm.trace_int_mem("W", 1, 0x120, 42)
    # struct label
    tm.trace_int_mem("R", 2, 0x200)
    tm.trace_int_mem("W", 1, 0x208, 21)
    # lib
    tm.trace_int_mem("R", 1, 0x300)
    tm.trace_int_mem("R", 1, 0x320)
    # lib with fd
    tm.trace_int_mem("R", 1, 0x400 - 36)
    tm.trace_int_mem("R", 1, 0x420)
    check_log("mem_int", caplog.record_tuples)


def trace_mgr_int_block_test(caplog):
    caplog.set_level(logging.INFO)
    tm = setup_tm()
    tm.setup_vamos_ram_trace()
    tm.trace_int_block("R", 0x100, 0x20)
    lvl = logging.INFO
    assert caplog.record_tuples == [
        ("mem_int", lvl, "R(B): 000100: +000020           [@000100 +000000 range] ")
    ]


def trace_mgr_code_line_test(caplog):
    caplog.set_level(logging.INFO)
    tm = setup_tm()
    tm.setup_vamos_ram_trace()
    # range
    tm.trace_code_line(0x100)
    # lib
    tm.trace_code_line(0x300)
    # lib with fd
    tm.trace_code_line(0x400 - 36)
    lvl = logging.INFO
    assert caplog.record_tuples == [
        (
            "instr",
            lvl,
            "@000100 +000000 range                     000100    nop                   ",
        ),
        (
            "instr",
            lvl,
            "@000300 +000000 fake.library(-32)         000300    nop                   ",
        ),
        (
            "instr",
            lvl,
            "@0003b8 +000024 vamostest.library(-36)    0003dc    nop                   ; PrintString",
        ),
    ]
