from .hwaccess import HWAccess
from amitools.vamos.log import log_mem_map
from amitools.vamos.label import LabelRange
from amitools.vamos.mem import MemoryAlloc


class MemoryMap(object):
    def __init__(self, machine):
        self.machine = machine
        self.label_mgr = machine.get_label_mgr()
        self.addr_24_bit = machine.get_cpu_type() == machine.CPU_TYPE_68000
        self.ram_total = machine.get_ram_total()
        # options
        self.hw_access = None
        self.dos_guard_base = 0xFF01DD05
        # init
        self._init_base_labels()
        # alloc
        self.alloc = None

    def _init_base_labels(self):
        if self.label_mgr:
            # vbr
            label = LabelRange("vbr", 0, 0x400)
            self.label_mgr.add_label(label)
            # shutdown range
            label = LabelRange("machine", 0x400, 0x800)
            self.label_mgr.add_label(label)

    def parse_config(self, cfg):
        if not cfg:
            return self.validate()
        # setup hw access
        hw_mode = cfg.hw_access
        self.setup_hw_access(hw_mode)
        # old dos guard
        odg = cfg.old_dos_guard
        if odg:
            self.setup_old_dos_guard()
        if not self.validate():
            return False
        self.setup_ram_allocator()
        return True

    def validate(self):
        # too much ram for 24 bit machine
        if self.addr_24_bit and self.ram_total >= 0x1000000:
            log_mem_map.error("Too much RAM allocated for 24 Bit addr bus of machine!")
            return False
        # too much ram if hw access is enabled
        if self.hw_access and self.ram_total >= 0xBF0000:
            log_mem_map.error("Too much RAM allocated with hw access enabled!")
            return False
        # ok!
        log_mem_map.info("dos guard base: @%08x", self.dos_guard_base)
        return True

    def cleanup(self):
        if self.alloc:
            self.alloc.dump_orphans()

    def setup_hw_access(self, mode_str):
        self.hw_access = HWAccess.from_mode_str(self.machine, mode_str)
        log_mem_map.info("setup hw access: %s", mode_str)

    def setup_old_dos_guard(self):
        # create a guard memory for tracking invalid old dos access
        raw_mem = self.machine.get_mem()
        self.dos_guard_base = raw_mem.reserve_special_range()
        if self.label_mgr:
            label = LabelRange("old_dos guard", self.dos_guard_base, 0x10000)
            self.label_mgr.add_label(label)
            log_mem_map.info(label)

    def setup_ram_allocator(self):
        mem = self.machine.get_mem()
        mem_begin = 0x1000
        mem_size = self.ram_total - mem_begin
        log_mem_map.info("setup ram allocator: @%06x +%06x", mem_begin, mem_size)
        self.alloc = MemoryAlloc(mem, mem_begin, mem_size, self.label_mgr)

    def get_old_dos_guard_base(self):
        return self.dos_guard_base

    def get_hw_access(self):
        return self.hw_access

    def get_alloc(self):
        return self.alloc
