from amitools.vamos.machine import Machine, REG_D1, REG_D0
from amitools.vamos.schedule import Code


def schedule_code_simple_test():
    code = Code(100, start_regs={REG_D1: 23}, return_regs=[REG_D0, REG_D1], start_sp=42)
    assert code.get_start_regs() == {REG_D1: 23}
    assert code.get_return_regs() == [REG_D0, REG_D1]
    assert code.get_start_pc() == 100
    assert code.get_start_sp() == 42
