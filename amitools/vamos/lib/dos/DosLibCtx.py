from amitools.vamos.libcore import LibCtx


class DosLibCtx(LibCtx):
    def __init__(self, machine, alloc, seg_loader, path_mgr, scheduler, odg_base):
        LibCtx.__init__(self, machine)
        self.alloc = alloc
        self.path_mgr = path_mgr
        self.seg_loader = seg_loader
        self.scheduler = scheduler
        self.odg_base = odg_base
        # compat for process
        self.process = None
        self.exec_lib = None
        self.dos_lib = None

    def set_exec_lib(self, exec_lib):
        self.exec_lib = exec_lib

    def set_dos_lib(self, dos_lib):
        self.dos_lib = dos_lib

    def set_process(self, process):
        self.process = process
