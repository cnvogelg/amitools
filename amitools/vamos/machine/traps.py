class TrapCall:
    """store the execution of a trap"""

    def __init__(self, cpu, op, pc, func):
        self.cpu = cpu
        self.op = op
        self.pc = pc
        self.func = func

    def call(self):
        # save pc
        old_pc = self.cpu.r_pc()
        self.cpu.w_pc(self.pc)
        # trigger trap
        self.func(self.op, self.pc)
        # restore pc
        self.cpu.w_pc(old_pc)

    def __repr__(self):
        name = getattr(self.func, "__name__", str(self.func))
        return f"TrapCall(op={self.op:04x}, pc={self.pc:x}, func={name})"


class Traps:
    """while machine68k directly executes a trap when the trap instruction
    is encountered, these traps postpone the trap execution after cpu code
    execution. the advantage is that cpu runs inside a trap do not recurse
    the cpu execution but keep the sub runs on Python top level.
    This makes centalized exception handling a lot easier.
    """

    def __init__(self, machine, set_trap_call):
        self.traps = machine.traps
        self.cpu = machine.cpu
        self.set_trap_call = set_trap_call

    def setup(self, py_func):
        def my_trap(op, pc):
            # wrap trap
            trap_call = TrapCall(self.cpu, op, pc, py_func)
            # store trap
            self.set_trap_call(trap_call)
            # end cycle of cpu execution
            self.cpu.end()

        # rename wrap func for get_func() and disassembly
        my_trap.__name__ = py_func.__name__

        tid = self.traps.setup(my_trap)
        return tid

    def free(self, tid):
        self.traps.free(tid)

    def get_func(self, tid):
        return self.traps.get_func(tid)

    def cleanup(self):
        self.traps.cleanup()
