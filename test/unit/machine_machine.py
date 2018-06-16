from __future__ import print_function
from amitools.vamos.machine import Machine, CPUState
from amitools.vamos.machine.opcodes import *
from amitools.vamos.error import *
from amitools.vamos.log import log_machine
import logging


log_machine.setLevel(logging.DEBUG)


def create_machine():
  m = Machine(Machine.CPU_TYPE_68000, raise_on_main_run=False)
  cpu = m.get_cpu()
  mem = m.get_mem()
  traps = m.get_traps()
  code = m.get_ram_begin()
  stack = code + 0x1000
  return m, cpu, mem, traps, code, stack


def machine_machine_run_rts_test():
  m, cpu, mem, traps, code, stack = create_machine()
  # single RTS to immediately return from run
  mem.w16(code, op_rts)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error is None
  m.cleanup()


def machine_machine_shutdown_test():
  m, cpu, mem, traps, code, stack = create_machine()
  a = []
  # set shutdown handler

  def my_shutdown():
    a.append(1)
  m.set_shutdown_hook(my_shutdown)
  # single RTS to immediately return from run
  mem.w16(code, op_rts)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error is None
  assert a == [1]
  m.cleanup()


def machine_machine_instr_hook_test():
  m, cpu, mem, traps, code, stack = create_machine()
  a = []
  # set instr hook

  def my_hook():
    pc = cpu.r_pc()
    a.append(pc)
  m.set_instr_hook(my_hook)
  # single RTS to immediately return from run
  mem.w16(code, op_rts)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error is None
  assert a == [0x800, 0x400]
  m.cleanup()


def machine_machine_cpu_mem_trace_test():
  m, cpu, mem, traps, code, stack = create_machine()
  a = []
  # set instr hook

  def my_trace(*args):
    a.append(args)
  m.set_cpu_mem_trace_hook(my_trace)
  # single RTS to immediately return from run
  mem.w16(code, op_rts)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error is None
  assert a[0] == ('R', 2, 0, 0x1800)
  m.cleanup()


def machine_machine_cpu_mem_invalid_test(caplog):
  m, cpu, mem, traps, code, stack = create_machine()
  a = []
  rs = m.run(0xf80000, stack)
  assert rs.done
  assert type(rs.error) == InvalidMemoryAccessError
  m.cleanup()
  log = caplog.record_tuples
  assert ('machine', logging.ERROR, '----- ERROR in CPU Run #1 -----') in log
  assert ('machine', logging.ERROR,
          'InvalidMemoryAccessError: Invalid Memory Access R(2): f80000') in log


def machine_machine_run_nested_ok_test():
  m, cpu, mem, traps, code, stack = create_machine()
  a = []
  res = []

  def nested2(op, pc):
    a.append(3)

  tid2 = traps.setup(nested2, auto_rts=True)
  opc2 = 0xa000 | tid2
  ncode = code + 0x100
  mem.w16(ncode, opc2)

  def nested(op, pc):
    a.append(1)
    rs = m.run(ncode)
    res.append(rs)
    a.append(2)

  tid = traps.setup(nested, auto_rts=True)
  opc = 0xa000 | tid
  mem.w16(code, opc)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error is None
  assert a == [1, 3, 2]
  rs2 = res[0]
  assert rs2.done
  assert rs2.error is None
  traps.free(tid)
  traps.free(tid2)
  m.cleanup()


def machine_machine_run_raise_test():
  m, cpu, mem, traps, code, stack = create_machine()
  error = ValueError("bla")

  def nested(op, pc):
    raise error

  tid = traps.setup(nested, auto_rts=True)
  opc = 0xa000 | tid
  mem.w16(code, opc)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error == error
  traps.free(tid)
  m.cleanup()


def machine_machine_run_raise2_test():
  m, cpu, mem, traps, code, stack = create_machine()
  error = ValueError("bla")

  def nested(op, pc):
    raise error

  tid = traps.setup(nested)
  opc = 0xa000 | tid
  mem.w16(code, opc)
  mem.w16(code+2, op_nop)
  mem.w16(code+4, op_rts)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error == error
  traps.free(tid)
  m.cleanup()


def machine_machine_run_nested_raise_test():
  m, cpu, mem, traps, code, stack = create_machine()
  a = []
  res = []
  error = ValueError("bla")

  def nested2(op, pc):
    raise error

  tid2 = traps.setup(nested2)
  opc2 = 0xa000 | tid2
  ncode = code + 0x100
  mem.w16(ncode, opc2)
  mem.w16(ncode+2, op_nop)
  mem.w16(ncode+2, op_rts)

  def nested(op, pc):
    a.append(1)
    rs = m.run(ncode)
    res.append(rs)
    a.append(2)

  tid = traps.setup(nested)
  opc = 0xa000 | tid
  mem.w16(code, opc)
  mem.w16(code+2, op_nop)
  mem.w16(code+4, op_rts)

  rs = m.run(code, stack)
  assert rs.done
  assert type(rs.error) == NestedCPURunError
  assert rs.error.error == error
  assert a == [1]

  traps.free(tid)
  traps.free(tid2)
  m.cleanup()


def machine_machine_run_trap_unbound_test(capfd):
  m, cpu, mem, traps, code, stack = create_machine()
  # place an unbound trap
  mem.w16(code, 0xa100)
  # single RTS to immediately return from run
  mem.w16(code+2, op_rts)
  rs = m.run(code, stack)
  assert rs.done
  assert rs.error is None
  m.cleanup()
  captured = capfd.readouterr()
  assert captured.out.strip().split('\n') == [
      'UNBOUND TRAP: code=a100, pc=000800'
  ]
