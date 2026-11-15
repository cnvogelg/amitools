import time

from amitools.vamos.log import log_hw
from .error import InvalidMemoryAccessError


class HWAccessError(InvalidMemoryAccessError):
    def __str__(self):
        return "Invalid HW Access %s(%d): %06x" % (
            self.access_type,
            2**self.width,
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
        raw_mem.set_special_range_read_funcs(
            0xDF0000, 1, self.cc_r8, self.cc_r16, self.cc_r32
        )
        raw_mem.set_special_range_write_funcs(
            0xDF0000, 1, self.cc_w8, self.cc_w16, self.cc_w32
        )
        # Motherboard probe windows: custom-register aliases, RTC, SCSI,
        # Gary/Gayle and Ramsey. These devices are absent, not writable RAM.
        # A pulled-up bus avoids echoing probe writes and inventing devices.
        probe_reads = (self.probe_r8, self.probe_r16, self.probe_r32)
        raw_mem.set_special_range_read_funcs(0xDA0000, 5, *probe_reads)
        # Reuse the same bound method objects for both ranges. machine68k
        # retains callbacks in a set, which deduplicates equal bound methods
        # while its C tables retain each originally supplied object pointer.
        probe_writes = (self.probe_w8, self.probe_w16, self.probe_w32)
        raw_mem.set_special_range_write_funcs(0xDA0000, 5, *probe_writes)
        # There is no Kickstart image. A zero version/header lets callers
        # fall back to Exec instead of reporting an invented ROM version.
        raw_mem.set_special_range_read_funcs(
            0xF80000, 8, self.rom_r8, self.rom_r16, self.rom_r32
        )
        raw_mem.set_special_range_write_funcs(0xF80000, 8, *probe_writes)
        # A full 68020 has no ROM alias at this high probe address. Older
        # machine68k releases only dispatch 28 address bits and cannot
        # safely register this range; check the backend capability first.
        if getattr(raw_mem, "get_address_bits", lambda: 28)() >= 32:
            raw_mem.set_special_range_read_funcs(0x10F80000, 8, *probe_reads)
            raw_mem.set_special_range_write_funcs(0x10F80000, 8, *probe_writes)
        # set mode
        self.mode = mode
        self.raw_mem = raw_mem
        self.machine = machine

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
            self._raise("R", 0, addr)
        return 0

    def cia_w8(self, addr, val):
        log_hw.warning("CIA write byte @%06x: %02x", addr, val)
        if self.mode == self.MODE_ABORT:
            self._raise("W", 0, addr)

    def cc_r16(self, addr):
        if self.mode == self.MODE_EMU and addr == 0xDFF006:
            # Synthetic beam counter: one step every 256 ns, wrapping at 16 bits.
            r = 0xFFFF & (time.time_ns() // 256)
            log_hw.info("Custom Chip read vhposr @%06x -> %04x", addr, r)
            return r
        log_hw.warning("Custom Chip read word @%06x", addr)
        if self.mode == self.MODE_ABORT:
            self._raise("R", 1, addr)
        return 0

    def cc_w16(self, addr, val):
        log_hw.warning("Custom Chip write word @%06x: %04x", addr, val)
        if self.mode == self.MODE_ABORT:
            self._raise("W", 1, addr)

    def cc_r8(self, addr):
        if self.mode == self.MODE_ABORT:
            self._raise("R", 0, addr)
        word = self.cc_r16(addr & ~1)
        return (word >> (0 if addr & 1 else 8)) & 0xFF

    def cc_r32(self, addr):
        if self.mode == self.MODE_ABORT:
            self._raise("R", 2, addr)
        return (self.cc_r16(addr) << 16) | self.cc_r16(addr + 2)

    def cc_w8(self, addr, val):
        if self.mode == self.MODE_ABORT:
            self._raise("W", 0, addr)
        # No custom-chip write state is currently implemented.
        log_hw.warning("Custom Chip write byte @%06x: %02x", addr, val)

    def cc_w32(self, addr, val):
        if self.mode == self.MODE_ABORT:
            self._raise("W", 2, addr)
        self.cc_w16(addr, val >> 16)
        self.cc_w16(addr + 2, val & 0xFFFF)

    def _probe_read(self, addr, width):
        if self.mode == self.MODE_ABORT:
            self._raise("R", width, addr)
        value = (1 << (8 << width)) - 1 if self.mode == self.MODE_EMU else 0
        log_hw.info(
            "Absent hardware read @%06x (%d bytes): %x", addr, 1 << width, value
        )
        return value

    def _probe_write(self, addr, width, val):
        if self.mode == self.MODE_ABORT:
            self._raise("W", width, addr)
        log_hw.info("Absent hardware write @%06x (%d bytes): %x", addr, 1 << width, val)

    def probe_r8(self, addr):
        return self._probe_read(addr, 0)

    def probe_r16(self, addr):
        return self._probe_read(addr, 1)

    def probe_r32(self, addr):
        return self._probe_read(addr, 2)

    def probe_w8(self, addr, val):
        self._probe_write(addr, 0, val)

    def probe_w16(self, addr, val):
        self._probe_write(addr, 1, val)

    def probe_w32(self, addr, val):
        self._probe_write(addr, 2, val)

    def _rom_read(self, addr, width):
        if self.mode == self.MODE_ABORT:
            self._raise("R", width, addr)
        log_hw.info("Absent ROM read @%06x (%d bytes)", addr, 1 << width)
        return 0

    def rom_r8(self, addr):
        return self._rom_read(addr, 0)

    def rom_r16(self, addr):
        return self._rom_read(addr, 1)

    def rom_r32(self, addr):
        return self._rom_read(addr, 2)

    def _raise(self, mode, width, addr):
        pc = self.machine.get_pc()
        sp = self.machine.get_sp()
        raise HWAccessError(pc, sp, mode, width, addr)
