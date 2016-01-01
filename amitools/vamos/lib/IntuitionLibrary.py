from amitools.vamos.AmigaLibrary import *
from amitools.vamos.lib.lexec.ExecStruct import LibraryDef
from amitools.vamos.Log import *

class IntuitionLibrary(AmigaLibrary):
  name = "intuition.library"
  
  def __init__(self, config):
    AmigaLibrary.__init__(self, self.name, LibraryDef, config)

  def setup_lib(self, ctx):
    AmigaLibrary.setup_lib(self, ctx)

  def DisplayAlert(self, ctx):
    alert_num = ctx.cpu.r_reg(REG_D0)
    msg_ptr = ctx.cpu.r_reg(REG_A0)
    msg = ctx.mem.access.r_cstr(msg_ptr)
    log_main.error("-----> DisplayAlert: #%08x - '%s'@%08x <-----", alert_num, msg, msg_ptr)
