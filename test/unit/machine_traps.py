from amitools.vamos.machine.mock import MockMachine
from amitools.vamos.machine import Traps, TrapCall


def machine_trap_test():
    class Setter:
        def __init__(self):
            self.call = None

        def __call__(self, call):
            self.call = call

    setter = Setter()
    machine = MockMachine()
    traps = Traps(machine, setter)

    class TrapFunc:
        def __init__(self):
            self.op = None
            self.pc = None

        def func(self, op, pc):
            self.op = op
            self.pc = pc

    # setup trap
    trap_func = TrapFunc()
    tid = traps.setup(trap_func.func)
    assert tid != -1

    # trigger trap
    machine.traps.trigger(tid, 0x1234)

    # now expect call to be set
    assert type(setter.call) is TrapCall

    # trap func not yet called
    assert trap_func.op is None
    assert trap_func.pc is None

    # now call trap delayed
    setter.call.call()

    # trap func now was called
    assert trap_func.op == tid | 0xA000
    assert trap_func.pc == 0x1234

    traps.free(tid)
