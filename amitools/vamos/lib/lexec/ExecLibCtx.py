from amitools.vamos.libcore import LibCtx

class ExecLibCtx(LibCtx):

  def __init__(self, cpu, mem, machine, cpu_type, ram_size, label_mgr, alloc, traps,
               seg_loader, path_mgr):
    LibCtx.__init__(self, cpu, mem)
    self.machine = machine
    self.cpu_type = cpu_type
    self.ram_size = ram_size
    self.label_mgr = label_mgr
    self.lib_mgr = None
    self.alloc = alloc
    self.traps = traps
    self.process = None
    self.seg_loader = seg_loader
    self.path_mgr = path_mgr

  def set_lib_mgr(self, lib_mgr):
    self.lib_mgr = lib_mgr

  def set_process(self, process):
    self.process = process
