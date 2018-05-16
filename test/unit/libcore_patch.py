from amitools.vamos.libcore import *
from amitools.vamos.machine import *
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.fd import read_lib_fd


def _create_ctx():
  machine = MockMachine()
  return LibCtx(machine)


def libcore_patch_multi_trap_test(capsys):
  name = 'vamostest.library'
  impl = VamosTestLibrary()
  fd = read_lib_fd(name)
  ctx = _create_ctx()
  # create stub
  gen = LibStubGen()
  stub = gen.gen_stub(name, impl, fd, ctx)
  # now patcher
  traps = MockTraps()
  p = LibPatcherMultiTrap(ctx.mem, traps, stub)
  base_addr = 0x100
  p.patch_jump_table(base_addr)
  # lookup trap for function
  func = fd.get_func_by_name('PrintHello')
  bias = func.get_bias()
  func_addr = base_addr - bias
  op = ctx.mem.r16(func_addr)
  # its a trap
  assert op & 0xf000 == 0xa000
  # trigger
  traps.trigger(op)
  captured = capsys.readouterr()
  assert captured.out.strip().split('\n') == [
      'VamosTest: PrintHello()'
  ]
  # remove traps
  p.cleanup()
  assert traps.get_num_traps() == 0
