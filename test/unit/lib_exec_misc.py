from amitools.vamos.lib.lexec.miscfunc import MiscMixin
from amitools.vamos.machine.mock import MockCPU
from amitools.vamos.machine.regs import REG_D0
from lib_exec_helper import ExecHost, make_exec_lib


class Host(ExecHost, MiscMixin):
    pass


def _host():
    mem, alloc, el = make_exec_lib()
    return Host(mem, alloc, el, cpu=MockCPU())


def exec_get_cc_test():
    host = _host()
    host.ctx.cpu.w_sr(0x2715)
    # GetCC returns the condition codes in D0 and leaves the SR alone
    assert host.GetCC(host.ctx) is None
    assert host.ctx.cpu.r_reg(REG_D0) == 0x15
    assert host.ctx.cpu.r_sr() == 0x2715


def exec_misc_stubs_test():
    host = _host()
    # these are documented no-op/honest stubs
    assert host.Debug(host.ctx, 0x1234) is None
    assert host.ColdReboot(host.ctx) is None
    assert host.SumKickData(host.ctx) == 0
    assert host.ObtainQuickVector(host.ctx, 0x1000) == 0
    assert host.ChildFree(host.ctx, 1) == 0
    assert host.ChildOrphan(host.ctx, 1) == 0
    assert host.ChildStatus(host.ctx, 1) == 0
    assert host.ChildWait(host.ctx, 1) == 0
