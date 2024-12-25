class ModeContext:
    """context shared with all modes"""

    def __init__(self, proc_cfg, exec_ctx, dos_ctx, scheduler, def_runtime):
        self.proc_cfg = proc_cfg
        self.exec_ctx = exec_ctx
        self.dos_ctx = dos_ctx
        self.scheduler = scheduler
        self.def_runtime = def_runtime
