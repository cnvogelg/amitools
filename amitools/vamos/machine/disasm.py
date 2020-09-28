from .machine import Machine


class DisAsm(object):
    def __init__(self, machine):
        self.machine = machine
        self.cpu = machine.get_cpu()
        self.traps = machine.get_traps()

    @classmethod
    def create(cls, cpu_name="68000"):
        cpu_type, cpu_name = Machine.parse_cpu_type(cpu_name)
        assert cpu_type
        machine = Machine(cpu_type=cpu_type)
        return cls(machine)

    def disassemble(self, pc):
        num_bytes, txt = self.cpu.disassemble(pc)
        # trap?
        if txt.startswith("dc.w    $a"):
            tid = int(txt[10:13], 16)
            txt = self._parse_trap(tid)
        return num_bytes, txt

    def disassemble_raw(self, pc, data):
        num_bytes, txt = self.cpu.disassemble_raw(pc, data)
        if num_bytes > len(data):
            return 0, ""
        return num_bytes, txt

    def disassemble_line(self, pc, data):
        """disassemble a line and return (pc, words, code)"""
        num_bytes, txt = self.disassemble_raw(pc, data)
        if num_bytes == 0:
            return (pc, [], "")
        words = []
        pos = 0
        num_words = num_bytes // 2
        for i in range(num_words):
            w = data[pos] << 8 | data[pos + 1]
            words.append(w)
            pos += 2
        return (pc, words, txt)

    def disassemble_block(self, data, start_pc=0):
        """disassemble a block and return a list of (pc, words, code)"""
        num = len(data)
        off = 0
        pc = start_pc
        code = []
        while off < num:
            pc, words, txt = self.disassemble_line(pc, data[off:])
            if len(words) == 0:
                break
            code.append((pc, words, txt))
            num_bytes = len(words) * 2
            off += num_bytes
            pc += num_bytes
        return code

    def dump_block(self, code, func=print):
        """dump a code block"""
        for pc, words, txt in code:
            words_str = " ".join(["%04x" % x for x in words])
            func("%08x:  %-20s  %s" % (pc, words_str, txt))

    def _parse_trap(self, tid):
        func = self.traps.get_func(tid)
        if func:
            if hasattr(func, "__name__"):
                name = func.__name__
            else:
                name = str(func)
            return "PyTrap  #$%03x ; %s" % (tid, name)
        else:
            return "PyTrap  #$%03x" % tid
