"""dos.library error output (RKRM AmigaDOS 3, "Error Output" and
"ErrorReport").

File handle based error streaming: ``pr_CES`` is the standard error handle
and ``pr_COS`` the fallback, exactly like ``ErrorOutput()``. No system
requester exists in Vamos, so ``ErrorReport()`` reports the error through the
log and fails honestly.
"""

from amitools.vamos.log import log_dos

from .Error import DOSFALSE, ERROR_NOT_IMPLEMENTED


def put_str(dos, ctx, str_ptr):
    """write a C string to the process's current output (RKRM ``PutStr``)"""
    str_dat = ctx.mem.r_cbytes(str_ptr)
    # write to stdout
    fh = ctx.process.get_output()
    ok = fh.write(str_dat)

    show_data = str_dat[: dos.MAX_SHOW_DATA]
    log_dos.info("PutStr: %s", show_data)
    return 0  # ok


def write_chars(dos, ctx, buf_ptr, size):
    """write ``size`` bytes to the process's current output (``WriteChars``)"""
    fh = ctx.process.get_output()
    buf = ctx.mem.r_cbytes(buf_ptr)[:size]
    fh.write(buf)
    return len(buf)


def error_output_bptr(ctx):
    """the BPTR ErrorOutput() returns (stderr, fallback stdout)"""
    proc = ctx.process.get_ami_process()
    ces = proc.pr_CES.bptr
    if ces:
        return ces
    return proc.pr_COS.bptr


def error_output(ctx):
    return error_output_bptr(ctx)


def select_error(ctx, fh_b_addr):
    proc = ctx.process.get_ami_process()
    old = proc.pr_CES.bptr
    proc.pr_CES.bptr = fh_b_addr & 0xFFFFFFFF
    log_dos.info("SelectError(%s) -> old=%s", fh_b_addr, old)
    return old


def put_err_str(dos, ctx, str_ptr):
    if str_ptr == 0:
        return 0
    data = ctx.mem.r_cbytes(str_ptr)
    fh_b_addr = error_output_bptr(ctx)
    if fh_b_addr == 0:
        log_dos.warning("PutErrStr: no error output file handle")
        return 0
    try:
        fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    except ValueError:
        fh = None
    if fh is None:
        log_dos.warning("PutErrStr: invalid error output handle %s", fh_b_addr)
        return 0
    fh.write(data)
    log_dos.info("PutErrStr: %s", data[: dos.MAX_SHOW_DATA])
    return 0


def error_report(dos, ctx, code, report_type, arg1, device):
    # a real call would build and display a system requester
    log_dos.warning(
        "ErrorReport(code=%d, type=%d, arg1=%r, device=%06x): not implemented",
        code,
        report_type,
        arg1,
        device,
    )
    return DOSFALSE, ERROR_NOT_IMPLEMENTED
