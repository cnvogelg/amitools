from .mem import LibMem


class LibAllocMem(object):
  """a small wrapper class around LibMem that allocates the library
     memory. This is typically done for vamos internal libs.
  """

  def __init__(self, info, alloc, struct=None, label_mgr=None):
    self.info = info
    self.alloc = alloc
    self.struct = struct
    self.label_mgr = label_mgr
    self.lib_mem = None
    self.lib_obj = None
    self.id_str_obj = None
    self.name_obj = None

  def alloc_lib(self):
    # alloc memory
    name = self.info.get_name()
    # setup memory
    # name
    name_size = self.info.get_name_cstr_size()
    name_tag = "LibName(%s)" % name
    self.name_obj = self.alloc.alloc_memory(name_tag, name_size)
    name_addr = self.name_obj.addr
    # id string
    id_str_size = self.info.get_id_string_cstr_size()
    id_str_tag = "LibIdString(%s)" % name
    self.id_str_obj = self.alloc.alloc_memory(id_str_tag, id_str_size)
    id_str_addr = self.id_str_obj.addr
    # lib
    lib_size = self.info.get_total_size()
    lib_tag = "LibBase(%s)" % name
    self.lib_obj = self.alloc.alloc_memory(lib_tag, lib_size, add_label=False)
    lib_addr = self.lib_obj.addr + self.info.get_neg_size()
    # lib_mem creation
    lib_mem = LibMem(self.alloc.mem, lib_addr, self.struct)
    lib_mem.init_base()
    lib_mem.write_info(self.info, name_addr, id_str_addr)
    # (optional) create memory label
    if self.label_mgr is not None:
      lib_mem.set_label(self.label_mgr)
    # return lib_mem
    self.lib_mem = lib_mem
    return lib_mem

  def get_lib_mem(self):
    return self.lib_mem

  def get_addr(self):
    return self.lib_mem.get_addr()

  def free_lib(self):
    lib_mem = self.lib_mem
    if lib_mem is None:
      return
    # remove label
    if self.label_mgr is not None:
      lib_mem.remove_label(self.label_mgr)
    # free memory
    self.alloc.free_memory(self.lib_obj)
    self.alloc.free_memory(self.id_str_obj)
    self.alloc.free_memory(self.name_obj)
    # clear values
    self.lib_mem = None
    self.lib_obj = None
    self.id_str_obj = None
    self.name_obj = None
