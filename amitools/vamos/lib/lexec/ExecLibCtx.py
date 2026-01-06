from amitools.vamos.libcore import LibCtx
from amitools.vamos.task import ExecTask, DosProcess


class ExecLibCtx(LibCtx):
    def __init__(self, machine, alloc, runner, seg_loader, path_mgr, lib_mgr):
        LibCtx.__init__(self, machine, runner, alloc)
        self.machine = machine
        self.traps = machine.get_traps()
        self.cpu_type = machine.get_cpu_type()
        self.cpu_name = machine.get_cpu_name()
        self.ram_size = self.mem.get_ram_size_bytes()
        self.label_mgr = machine.get_label_mgr()
        self.seg_loader = seg_loader
        self.path_mgr = path_mgr
        self.lib_mgr = lib_mgr
        self.task = None
        self.process = None

    def set_cur_task_process(self, task, process):
        if task:
            assert isinstance(task, ExecTask)
        self.task = task
        # process is optional if its really a DosProcess
        if process:
            assert isinstance(process, DosProcess)
        self.process = process

    def __str__(self):
        return "[DosLibCtx:cpu=%s,mem=%s,task=%s,process=%s]" % (
            self.cpu,
            self.mem,
            self.task,
            self.process,
        )
