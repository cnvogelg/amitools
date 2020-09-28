from .mockcpu import MockCPU
from .mockmem import MockMemory
from .mocktraps import MockTraps
from amitools.vamos.label import LabelManager


class MockMachine(object):
    def __init__(self, size_kib=16, fill=0, use_labels=True):
        self.cpu = MockCPU()
        self.mem = MockMemory(size_kib, fill)
        self.traps = MockTraps()
        if use_labels:
            self.label_mgr = LabelManager()
        else:
            self.label_mgr = None

    def get_cpu(self):
        return self.cpu

    def get_mem(self):
        return self.mem

    def get_traps(self):
        return self.traps

    def get_label_mgr(self):
        return self.label_mgr

    def get_ram_begin(self):
        return 0x800

    def set_cpu_mem_trace_hook(self, func):
        pass

    def set_mem(self, mem):
        self.mem = mem
