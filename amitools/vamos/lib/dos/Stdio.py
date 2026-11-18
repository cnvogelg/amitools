"""dos.library error output (RKRM AmigaDOS 3, "Error Output" and
"ErrorReport").

File handle based error streaming: ``pr_CES`` is the standard error handle
and ``pr_COS`` the fallback, exactly like ``ErrorOutput()``. No system
requester exists in Vamos, so ``ErrorReport()`` reports the error through the
log and fails honestly.
"""

from amitools.vamos.log import log_dos

from .Error import DOSFALSE, DOSTRUE, ERROR_NOT_IMPLEMENTED, dos_error_strings


def io_err(dos, ctx):
    if dos.io_err in dos_error_strings:
        errstring = dos_error_strings[dos.io_err]
    else:
        errstring = "%d" % dos.io_err
    log_dos.info("IoErr: %d (%s)", dos.io_err, errstring)
    return dos.io_err


def set_io_err(dos, ctx, err):
    old_io_err = dos.io_err
    dos.setioerr(ctx, err)
    log_dos.info("SetIoErr: IoErr=%d old IoErr=%d", dos.io_err, old_io_err)
    return old_io_err


def fault(dos, ctx, errcode, hdr_ptr, buf_ptr, buf_len):
    if errcode >= 0x80000000:
        idx = errcode - 0x100000000
    else:
        idx = errcode
    if hdr_ptr != 0:
        hdr = ctx.mem.r_cstr(hdr_ptr)
    else:
        hdr = ""
    if idx in dos_error_strings:
        err_str = dos_error_strings[idx]
    else:
        err_str = "%d ERROR" % dos.io_err
    log_dos.info("Fault: code=%d header='%s' err_str='%s'", dos.io_err, hdr, err_str)
    # write to stdout
    if hdr_ptr != 0:
        txt = "%s: %s" % (hdr, err_str)
    else:
        txt = "%s" % err_str
    ctx.mem.w_cstr(buf_ptr, txt[: buf_len - 1])
    return DOSTRUE


def print_fault(dos, ctx, errcode, hdr_ptr):
    dos.io_err = errcode
    if dos.io_err >= 0x80000000:
        idx = dos.io_err - 0x100000000
    else:
        idx = dos.io_err
    # get header string
    if hdr_ptr != 0:
        hdr = ctx.mem.r_cstr(hdr_ptr)
    else:
        hdr = ""
    # get error string
    if idx in dos_error_strings:
        err_str = dos_error_strings[idx]
    else:
        err_str = "%d ERROR" % dos.io_err
    log_dos.info(
        "PrintFault: code=%d header='%s' err_str='%s'", dos.io_err, hdr, err_str
    )
    # write to stdout
    if hdr_ptr != 0:
        txt = "%s: %s\n" % (hdr, err_str)
    else:
        txt = "%s\n" % err_str
    fh = ctx.process.get_output()
    fh.write(txt.encode("latin-1"))
    return DOSTRUE


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
