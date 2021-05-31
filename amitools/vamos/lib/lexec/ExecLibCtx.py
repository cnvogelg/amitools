from amitools.vamos.libcore import LibCtx


class ExecLibCtx(LibCtx):
    def __init__(self, machine, alloc, seg_loader, path_mgr, lib_mgr):
        LibCtx.__init__(self, machine)
        self.machine = machine
        self.traps = machine.get_traps()
        self.cpu_type = machine.get_cpu_type()
        self.cpu_name = machine.get_cpu_name()
        self.ram_size = self.mem.get_ram_size_bytes()
        self.label_mgr = machine.get_label_mgr()
        self.alloc = alloc
        self.seg_loader = seg_loader
        self.path_mgr = path_mgr
        self.lib_mgr = lib_mgr
        self.process = None

    def set_process(self, process):
        self.process = process
