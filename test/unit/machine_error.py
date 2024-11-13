import pytest
import logging

from machine68k import CPUType
from amitools.vamos.machine import (
    Machine,
    Runtime,
    Code,
    ResetOpcodeError,
    ErrorReporter,
)
from amitools.vamos.machine.opcodes import op_reset


def create_runtime(cpu_type=CPUType.M68000, supervisor=False):
    m = Machine(cpu_type, supervisor=supervisor)
    cpu = m.get_cpu()
    mem = m.get_mem()
    code = m.get_ram_begin()
    stack = m.get_scratch_top()
    r = Runtime(m)
    return r, m, cpu, mem, code, stack


def machine_error_reporter_test(caplog):
    caplog.set_level(logging.ERROR)

    r, m, cpu, mem, code, stack = create_runtime(supervisor=True)
    er = ErrorReporter(r)

    # reset opcode
    mem.w16(code, op_reset)
    try:
        r.start(Code(code, stack), name="foo")
    except ResetOpcodeError as e:
        er.report_error(e)
    m.cleanup()

    # check error report
    assert len(caplog.record_tuples) > 0
