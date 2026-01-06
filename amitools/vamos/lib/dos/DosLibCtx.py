from amitools.vamos.libcore import LibCtx
from amitools.vamos.task import DosProcess


class DosLibCtx(LibCtx):
    def __init__(
        self, machine, alloc, runner, seg_loader, path_mgr, scheduler, odg_base
    ):
        LibCtx.__init__(self, machine, runner, alloc)
        self.path_mgr = path_mgr
        self.seg_loader = seg_loader
        self.scheduler = scheduler
        self.odg_base = odg_base
        # compat for process
        self.process = None
        self.exec_lib = None
        self.dos_lib = None

    def __str__(self):
        return "[DosLibCtx:cpu=%s,mem=%s,process=%s]" % (
            self.cpu,
            self.mem,
            self.process,
        )

    def set_exec_lib(self, exec_lib):
        self.exec_lib = exec_lib

    def set_dos_lib(self, dos_lib):
        self.dos_lib = dos_lib

    def set_cur_process(self, process):
        if process:
            assert isinstance(process, DosProcess)
        self.process = process
