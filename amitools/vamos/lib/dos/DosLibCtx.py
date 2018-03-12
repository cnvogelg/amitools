from amitools.vamos.libcore import LibCtx

class DosLibCtx(LibCtx):

  def __init__(self, cpu, mem, alloc, path_mgr, seg_loader,
               run_command, start_sub_process):
    LibCtx.__init__(self, cpu, mem)
    self.alloc = alloc
    self.path_mgr = path_mgr
    self.exec_lib = None
    self.seg_loader = seg_loader
    self.run_command = run_command
    self.start_sub_process = start_sub_process
    self.process = None
    # compat for process
    self.dos_lib = None

  def set_exec_lib(self, exec_lib):
    self.exec_lib = exec_lib

  def set_dos_lib(self, dos_lib):
    self.dos_lib = dos_lib

  def set_process(self, process):
    self.process = process
