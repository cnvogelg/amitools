class LibManager:
  def __init__(self, lib_begin_addr, offset, layout):
    self.layout = layout
    self.lib_addr = lib_begin_addr
    self.offset = offset
    self.libs = []
    
  def add_lib(self, lib):
    addr = self.lib_addr
    self.lib_addr += self.offset
    self.libs.append([addr,lib,0])
    lib.set_addr(addr)
    return addr
  
  def open_lib(self, name, ver):
    for lib in self.libs:
      if lib[1].name == name and lib[1].version >= ver:
        lib[2] += 1
        if lib[2] == 1:
          print "  [OpenLibrary: %s]" % lib[1]
          self.layout.add_range(lib[1])
        return lib[0]
    return 0

  def close_lib(self, addr):
    for lib in self.libs:
      if lib[0] == addr:
        lib[2] -= 1
        if lib[2] == 0:
          print "  [CloseLibrary: %s]" % lib[1]
        return lib[1]
    return None