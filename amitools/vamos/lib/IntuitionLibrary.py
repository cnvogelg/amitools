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

#selco, 30.Oct.2017
  def AutoRequest(self,ctx):
    IntuiText = ctx.cpu.r_reg(REG_A1)
    IText = ctx.mem.access.r32(IntuiText+12) # IntuiText.ITexT
    msg = ctx.mem.access.r_cstr(IText)
    log_main.error("-----> AutoRequest '%s'",msg)

#selco, 17. Nov.2017
  def EasyRequestArgs(self,ctx):
    EasyStruct = ctx.cpu.r_reg(REG_A1)
    es_TextFormat = ctx.mem.access.r32(EasyStruct+12) # EasyStruct.es_TextFormat
    msg = ctx.mem.access.r_cstr(es_TextFormat)
    log_main.error("-----> AutoRequest '%s'",msg)

