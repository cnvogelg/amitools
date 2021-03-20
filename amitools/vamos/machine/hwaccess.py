from amitools.vamos.log import log_hw
from amitools.vamos.error import InvalidMemoryAccessError


class HWAccessError(InvalidMemoryAccessError):
    def __str__(self):
        return "Invalid HW Access %s(%d): %06x" % (
            self.access_type,
            2 ** self.width,
            self.addr,
        )


class HWAccess:
    """As an OS-level emulator vamos usually does not need to emulate
    any custom chips. Unfortunately, some libs (e.g. xvs.library)
    need custom chip access to work correctly. We emulate a minimal
    sub set to make those broken (i.e. non OS-compliant) libs work.
    """

    MODE_IGNORE = 0
    MODE_EMU = 1
    MODE_ABORT = 2
    MODE_DISABLE = 3

    def __init__(self, machine, mode):
        raw_mem = machine.get_mem()
        # setup $BFxxxx CIA range
        raw_mem.set_special_range_read_funcs(0xBF0000, 1, self.cia_r8, None, None)
        raw_mem.set_special_range_write_funcs(0xBF0000, 1, self.cia_w8, None, None)
        # setup $DFxxxx Custom Chip range
        raw_mem.set_special_range_read_funcs(0xDF0000, 1, None, self.cc_r16, None)
        raw_mem.set_special_range_write_funcs(0xDF0000, 1, None, self.cc_w16, None)
        # set mode
        self.mode = mode
        self.raw_mem = raw_mem

    @classmethod
    def from_mode_str(cls, machine, mode_str):
        if mode_str == "emu":
            return HWAccess(machine, cls.MODE_EMU)
        elif mode_str == "ignore":
            return HWAccess(machine, cls.MODE_IGNORE)
        elif mode_str == "abort":
            return HWAccess(machine, cls.MODE_ABORT)
        elif mode_str == "disable":
            return None
        else:
            raise ValueError("invalid hwaccess mode: %s" % mode_str)

    def cia_r8(self, addr):
        log_hw.warning("CIA read byte @%06x", addr)
        if self.mode == self.MODE_ABORT:
            raise HWAccessError("R", 0, addr)
        return 0

    def cia_w8(self, addr, val):
        log_hw.warning("CIA write byte @%06x: %02x", addr, val)
        if self.mode == self.MODE_ABORT:
            raise HWAccessError("W", 0, addr)

    def cc_r16(self, addr):
        log_hw.warning("Custom Chip read word @%06x", addr)
        if self.mode == self.MODE_ABORT:
            raise HWAccessError("R", 1, addr)
        return 0

    def cc_w16(self, addr, val):
        log_hw.warning("Custom Chip write word @%06x: %04x", addr, val)
        if self.mode == self.MODE_ABORT:
            raise HWAccessError("W", 1, addr)
