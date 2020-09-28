class CPUState:
    def __init__(self):
        self.pc = None
        self.sr = None
        self.dx = None
        self.ax = None
        self.usp = None
        self.isp = None
        self.msp = None

    sr_chars = "CVZNX"

    def _sr_str(self, val):
        mask = 1
        res = []
        for c in self.sr_chars:
            if (val & mask) == mask:
                res.append(c)
            else:
                res.append("-")
            mask *= 2
        return "".join(res)

    def get(self, cpu):
        self.pc = cpu.r_pc()
        self.sr = cpu.r_sr()
        self.usp = cpu.r_usp()
        self.isp = cpu.r_isp()
        self.msp = cpu.r_msp()
        # data register
        dx = []
        self.dx = dx
        for i in range(8):
            dx.append(cpu.r_reg(i))
        # addr register
        ax = []
        self.ax = ax
        for i in range(8):
            ax.append(cpu.r_reg(8 + i))

    def set(self, cpu):
        cpu.w_pc(self.pc)
        cpu.w_sr(self.sr)
        cpu.w_usp(self.usp)
        cpu.w_isp(self.isp)
        cpu.w_msp(self.msp)
        num = 0
        for v in self.dx:
            cpu.w_reg(num, v)
            num += 1
        for v in self.ax:
            cpu.w_reg(num, v)
            num += 1

    def dump(self):
        res = []
        res.append(
            "PC=%08x  SR=%s    USP=%08x ISP=%08x MSP=%08x"
            % (self.pc, self._sr_str(self.sr), self.usp, self.isp, self.msp)
        )
        # data register
        dx = []
        pos = 0
        for d in self.dx:
            dx.append("D%d=%08x" % (pos, d))
            pos += 1
        res.append("  ".join(dx))
        # addr register
        ax = []
        pos = 0
        for a in self.ax:
            ax.append("A%d=%08x" % (pos, a))
            pos += 1
        res.append("  ".join(ax))
        return res
