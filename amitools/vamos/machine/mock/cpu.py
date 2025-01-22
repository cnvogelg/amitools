from amitools.vamos.machine.regs import *


class MockCPU(object):
    """fake a real CPU API by providing at least the registers"""

    def __init__(self):
        self.d_regs = [0] * 16
        self.a_regs = [0] * 16
        self.pc = 0
        self.sr = 0

    def _check_val(self, val, max_val=0xFFFFFFFF):
        if type(val) not in (int, int):
            raise TypeError("value is not an int!: %s" % val)
        if val < 0 or val > max_val:
            raise OverflowError("value is out of range: %s" % val)

    def _check_sval(self, val, min_val=-0x80000000, max_val=0x7FFFFFFF):
        if type(val) not in (int, int):
            raise TypeError("value is not an int!: %s" % val)
        if val < min_val or val > max_val:
            raise OverflowError("value is out of range: %s" % val)

    def w_reg(self, reg, val):
        self._check_val(val)
        if reg <= REG_D7:
            self.d_regs[reg] = val
        elif reg <= REG_A7:
            self.a_regs[reg - REG_A0] = val
        elif reg == REG_PC:
            self.pc = val
        else:
            raise ValueError("invalid reg: %d" % reg)

    def r_reg(self, reg):
        if reg <= REG_D7:
            return self.d_regs[reg]
        elif reg <= REG_A7:
            return self.a_regs[reg - REG_A0]
        elif reg == REG_PC:
            return self.pc
        else:
            raise ValueError("invalid reg: %d" % reg)

    def ws_reg(self, reg, val):
        self._check_sval(val)
        val &= 0xFFFFFFFF
        if reg <= REG_D7:
            self.d_regs[reg] = val
        elif reg <= REG_A7:
            self.a_regs[reg - REG_A0] = val
        elif reg == REG_PC:
            self.pc = val
        else:
            raise ValueError("invalid reg: %d" % reg)

    def rs_reg(self, reg):
        if reg <= REG_D7:
            val = self.d_regs[reg]
        elif reg <= REG_A7:
            val = self.a_regs[reg - REG_A0]
        elif reg == REG_PC:
            val = self.pc
        else:
            raise ValueError("invalid reg: %d" % reg)
        val = (val ^ 0x80000000) - 0x80000000
        return val

    # partial register access

    def w8_reg(self, reg, val):
        if val < 0 or val > 0xFF:
            raise OverflowError("Not a ubyte value!")
        old_val = self.r_reg(reg)
        val = old_val & 0xFFFFFF00 | val
        self.w_reg(reg, val)

    def w16_reg(self, reg, val):
        if val < 0 or val > 0xFFFF:
            raise OverflowError("Not a uword value!")
        old_val = self.r_reg(reg)
        val = old_val & 0xFFFF0000 | val
        self.w_reg(reg, val)

    def w32_reg(self, reg, val):
        if val < 0 or val > 0xFFFFFFFF:
            raise OverflowError("Not a ulong value!")
        self.w_reg(reg, val)

    def r8_reg(self, reg):
        return self.r_reg(reg) & 0xFF

    def r16_reg(self, reg):
        return self.r_reg(reg) & 0xFFFF

    def r32_reg(self, reg):
        return self.r_reg(reg)

    def w8s_reg(self, reg, val):
        if val < -0x80 or val >= 0x80:
            raise OverflowError("Not a byte value!")
        old_val = self.r_reg(reg)
        val = old_val & 0xFFFFFF00 | (val & 0xFF)
        self.w_reg(reg, val)

    def w16s_reg(self, reg, val):
        if val < -0x8000 or val >= 0x8000:
            raise OverflowError("Not a word value!")
        old_val = self.r_reg(reg)
        val = old_val & 0xFFFF0000 | (val & 0xFFFF)
        self.w_reg(reg, val)

    def w32s_reg(self, reg, val):
        if val < -0x80000000 or val >= 0x80000000:
            raise OverflowError("Not a long value!")
        self.w_reg(reg, val & 0xFFFFFFFF)

    def r8s_reg(self, reg):
        val = self.r_reg(reg) & 0xFF
        val = (val ^ 0x80) - 0x80
        return val

    def r16s_reg(self, reg):
        val = self.r_reg(reg) & 0xFFFF
        val = (val ^ 0x8000) - 0x8000
        return val

    def r32s_reg(self, reg):
        val = self.r_reg(reg)
        val = (val ^ 0x80000000) - 0x80000000
        return val

    # read special regs

    def w_pc(self, val):
        self._check_val(val)
        self.pc = val

    def r_pc(self):
        return self.pc

    def w_sr(self, val):
        self._check_val(val, 0xFFFF)
        self.sr = val

    def r_sr(self):
        return self.sr

    def pulse_reset(self):
        raise NotImplementedError()

    def execute(self, num_cycles):
        raise NotImplementedError()

    def end(self):
        pass

    def set_pc_changed_callback(self, py_func):
        raise NotImplementedError()

    def set_reset_instr_callback(self, py_func):
        raise NotImplementedError()

    def set_instr_hook_callback(self, py_func):
        raise NotImplementedError()

    def disassemble(self, pc):
        return 2, "nop"
