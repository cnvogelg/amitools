from amitools.vamos.libcore import LibImpl
from amitools.vamos.machine.regs import * 
from amitools.vamos.astructs import *

from datetime import datetime

class TimerDevice(LibImpl):

  def ReadEClock(self, ctx):
    eclockval = ctx.cpu.r_reg(REG_A0)
        
    dt = datetime.now()
    
        # abuse DateStampStruct
    tv = AccessStruct(ctx.mem, DateStampStruct, struct_addr = eclockval) 
    tv.ds_Days = dt.microsecond / 1000000
    tv.ds_Minute = dt.microsecond % 1000000
    
    return 50
