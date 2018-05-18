from amitools.vamos.machine.regs import *
from amitools.vamos.Trampoline import Trampoline
from amitools.vamos.lib.dos.Printf import *

def raw_do_fmt(ctx, fmtString, dataStream, putProc, putData):
  fmt        = ctx.mem.r_cstr(fmtString)
  ps         = printf_parse_string(fmt)
  dataStream = printf_read_data(ps, ctx.mem, dataStream)
  resultstr  = printf_generate_output(ps)
  fmtstr     = resultstr+"\0"
  # Try to use a shortcut to avoid an unnecessary slow-down
  known      = False
  putcode    = ctx.mem.r32(putProc)
  if putcode == 0x16c04e75:
    known    = True
  elif putcode == 0x4e55fffc: #link #-4,a5
    putcode2 = ctx.mem.r32(putProc+4)
    putcode3 = ctx.mem.r32(putProc+8)
    putcode4 = ctx.mem.r16(putProc+12)
    if putcode2 == 0x2b40fffc and putcode3 == 0x16c04e5d and putcode4 == 0x4e75:
      known = True
  if known:
    ctx.mem.w_cstr(putData,fmtstr)
  else:
    # This is a recursive trampoline that writes the formatted data through
    # the put-proc. Unfortunately, this is pretty convoluted.
    def _make_trampoline(fmtstr,olda3,newa3,ctx):
      if len(fmtstr) > 0:
        tr = Trampoline(ctx,"RawDoFmt")
        tr.set_dx_l(0,ord(fmtstr[0:1]))
        tr.set_ax_l(2,putProc)
        tr.set_ax_l(3,newa3)
        tr.jsr(putProc)
        def _done_func():
          a3 = ctx.cpu.r_reg(REG_A3)
          _make_trampoline(fmtstr[1:],olda3,a3,ctx)
        tr.final_rts(_done_func)
        tr.done()
      else:
        ctx.cpu.w_reg(REG_A3,olda3)
    _make_trampoline(fmtstr,putData,putData,ctx)
  return dataStream, fmt, resultstr, known
