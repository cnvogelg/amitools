from amitools.vamos.AmigaLibrary import *

class ExecLibrary(AmigaLibrary):
  
  def __init__(self, version, context, lib_mgr):
    AmigaLibrary.__init__(self,"exec.library", version, 30, 100, 10, context)
    self.lib_mgr = lib_mgr
    # vector
    self.add_key(-552,self.OpenLibrary,name="OpenLibrary",param=(REG_D0,REG_A1),ret=REG_D0)
    self.add_key(-408,self.OldOpenLibrary,name="OldOpenLibrary",param=(REG_A1),ret=REG_D0)
    self.add_key(-414,self.CloseLibrary,name="CloseLibrary",param=(REG_A1))
    
  def OpenLibrary(self):
    ver = self.cpu.r_reg(REG_D0)
    name_ptr = self.cpu.r_reg(REG_A1)
    name = self.mem.read_cstring(name_ptr)
    addr = self.lib_mgr.open_lib(name, ver)
    print "  '%s' V%d -> %06x" % (name, ver, addr)
    self.cpu.w_reg(REG_D0, addr)
  
  def OldOpenLibrary(self):
    name_ptr = self.cpu.r_reg(REG_A1)
    name = self.mem.read_cstring(name_ptr)
    addr = self.lib_mgr.open_lib(name, 0)
    print "  '%s' -> %06x" % (name, addr)
    self.cpu.w_reg(REG_D0, addr)
  
  def CloseLibrary(self):
    lib_addr = self.cpu.r_reg(REG_A1)
    lib = self.lib_mgr.close_lib(lib_addr)
    if lib != None:
      print "  '%s' V%d -> %06x" % (lib.name, lib.version, lib_addr)
    else:
      print "  INVALID"
