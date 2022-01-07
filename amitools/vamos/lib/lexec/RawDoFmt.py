import struct
from amitools.vamos.machine.regs import *
from amitools.vamos.lib.dos.Printf import *

# setup loop code fragment:
# +0000: 243c <len-1.l>       move.l #<len-1>,d2
# +0006: 49f9 <fmtstr_addr>   lea    fmtstr_addr,a4
# loop:
# +000c: 101c                 move.b (a4)+,d0
# +000e: 4eb9 <putproc>       jsr    putproc
# +0014: 51ca fff6            dbra   d2,loop
# +0018: 4e75                 rts
# =001a

code_hex = (0x243C, 0, 0, 0x49F9, 0, 0, 0x101C, 0x4EB9, 0, 0, 0x51CA, 0xFFF6, 0x4E75)
code_bin = b"".join([struct.pack(">H", x) for x in code_hex])


def _setup_fragment(ctx, fmt_str, put_proc):
    fmt_len = len(fmt_str)
    code_len = len(code_bin)
    assert code_len == 0x1A
    size = fmt_len + code_len
    mem_obj = ctx.alloc.alloc_memory(size, "RawDoFmtFrag")
    addr = mem_obj.addr
    fmt_addr = addr + 0x1A
    ctx.mem.w_block(addr, code_bin)
    ctx.mem.w32(addr + 2, fmt_len - 1)
    ctx.mem.w32(addr + 8, fmt_addr)
    ctx.mem.w32(addr + 16, put_proc)
    ctx.mem.w_cstr(addr + 0x1A, fmt_str)
    return mem_obj


def raw_do_fmt(ctx, fmtString, dataStream, putProc, putData):
    fmt = ctx.mem.r_cstr(fmtString)
    ps = printf_parse_string(fmt)
    dataStream = printf_read_data(ps, ctx.mem, dataStream)
    resultstr = printf_generate_output(ps)
    fmtstr = resultstr + "\0"
    # Try to use a shortcut to avoid an unnecessary slow-down
    known = False
    putcode = ctx.mem.r32(putProc)
    if putcode == 0x16C04E75:
        known = True
    elif putcode == 0x4E55FFFC:  # link #-4,a5
        putcode2 = ctx.mem.r32(putProc + 4)
        putcode3 = ctx.mem.r32(putProc + 8)
        putcode4 = ctx.mem.r16(putProc + 12)
        if putcode2 == 0x2B40FFFC and putcode3 == 0x16C04E5D and putcode4 == 0x4E75:
            known = True
    if known:
        ctx.mem.w_cstr(putData, fmtstr)
    else:
        mem_obj = _setup_fragment(ctx, fmtstr, putProc)
        set_regs = {REG_A2: putProc, REG_A3: putData}
        addr = mem_obj.addr
        ctx.machine.run(addr, set_regs=set_regs, name="RawDoFmt")
        ctx.alloc.free_memory(mem_obj)
    return dataStream, fmt, resultstr, known
