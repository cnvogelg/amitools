"""dos.library file I/O, file handles and standard input/output
(RKRM AmigaDOS 3, "File Input/Output" and "Input/Output").

Every helper maps one fd entry to a ``FileManager``/``FileHandle`` operation;
the ``DosLibrary`` methods are thin typed wrappers over these functions. The
stdout-only helpers (``PutStr``/``WriteChars``) live in :mod:`Stdio`.
"""

from amitools.vamos.astructs import CSTR, LONG
from amitools.vamos.libstructs import FileHandleStruct, DateStampStruct
from amitools.vamos.log import log_dos
from amitools.vamos.handler import HandlerError

from .Error import (
    DOSFALSE,
    DOSTRUE,
    NO_ERROR,
    ERROR_BAD_NUMBER,
    ERROR_OBJECT_NOT_FOUND,
    ERROR_SEEK_ERROR,
    ERROR_INVALID_LOCK,
    ERROR_OBJECT_WRONG_TYPE,
    ERROR_ACTION_NOT_KNOWN,
    ERROR_NOT_IMPLEMENTED,
)
from .AmiTime import AmiTime, ami_to_sys_time
from . import Helper, Printf

# ACTION_CHANGE_MODE object type (dos/dos.h)
CHANGE_LOCK = 0
CHANGE_FH = 1


# ----- open/close -----


def open_file(dos, ctx, name_ptr, mode):
    name = ctx.mem.r_cstr(name_ptr)

    # decode mode
    if mode == 1006:
        mode_name = "new"
        f_mode = "wb+"
    elif mode == 1005:
        mode_name = "old"
        f_mode = "rb+"
    elif mode == 1004:
        mode_name = "r/w"
        f_mode = "rwb+"
    else:
        mode_name = "?"
        log_dos.warning("open: invalid mode=%d!", mode)
        f_mode = "wb+"

    fh = dos.file_mgr.open(
        dos.get_current_dir(ctx), name, f_mode, home_dir=dos.get_home_dir(ctx)
    )
    log_dos.info("Open: name='%s' (%s/%d/%s) -> %s", name, mode_name, mode, f_mode, fh)

    if fh is None:
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return 0
    else:
        return fh.b_addr


def close_file(dos, ctx, fh_b_addr):
    if fh_b_addr != 0:
        fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
        dos.file_mgr.close(fh)
        log_dos.info("Close: %s", fh)
        dos.setioerr(ctx, 0)
    return DOSTRUE


# ----- read/write -----


def read_file(dos, ctx, fh_b_addr, buf_ptr, size):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, False)
    data = fh.read(size)
    if data == -1:
        log_dos.info("Read(%s, @%06x, %d) -> FAILED!", fh, buf_ptr, size)
        return -1

    got = len(data)
    if got > 0:
        ctx.mem.w_block(buf_ptr, data)
        show_data = data[: Helper.MAX_SHOW_DATA]
    else:
        show_data = "n/a"

    log_dos.info(
        "Read(%s, @%06x, %d) -> size=%d data=%s", fh, buf_ptr, size, got, show_data
    )
    return got


def write_file(dos, ctx, fh_b_addr, buf_ptr, size):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    data = ctx.mem.r_block(buf_ptr, size)
    res = fh.write(data)
    if res == -1:
        log_dos.info("Write(%s, %06x, %d) -> FAILED!", fh, buf_ptr, size)
        return -1

    got = len(data)
    if got > 0:
        show_len = min(got, Helper.MAX_SHOW_DATA)
        show_data = data[:show_len]
    else:
        show_data = "n/a"

    log_dos.info(
        "Write(%s, %06x, %d) -> size=%d data=%s", fh, buf_ptr, size, got, show_data
    )
    return size


def fwrite(dos, ctx, fh_b_addr, buf_ptr, size, number):
    # Actually, this is buffered I/O, not unbuffered IO. For the
    # time being, keep it unbuffered.
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    data = ctx.mem.r_block(buf_ptr, size * number)
    res = fh.write(data)
    if res == -1:
        log_dos.info("FWrite(%s, %06x, %d, %d) -> FAILED!", fh, buf_ptr, size, number)
        return 0

    got = len(data) // size
    show_data = data[: Helper.MAX_SHOW_DATA]
    log_dos.info(
        "FWrite(%s, %06x, %d, %d) -> %d  data=%s",
        fh,
        buf_ptr,
        size,
        number,
        got,
        show_data,
    )
    return got


def fread(dos, ctx, fh_b_addr, buf_ptr, size, number):
    # Again, this is actually buffered I/O and I should really
    # go through all the buffer logic. However, for the time
    # being, keep it unbuffered.
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)

    data = fh.read(size * number)
    if data == -1:
        log_dos.info("FRead(%s, %06x, %d, %d) -> FAILED!", fh, buf_ptr, size, number)
        return 0

    got = len(data) // size
    ctx.mem.w_block(buf_ptr, data)
    show_data = data[: Helper.MAX_SHOW_DATA]
    log_dos.info(
        "FRead(%s, %06x, %d, %d) -> %d  data=%s",
        fh,
        buf_ptr,
        size,
        number,
        got,
        show_data,
    )
    return got


def seek(dos, ctx, fh_b_addr, pos, mode):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    if mode == 0xFFFFFFFF:
        mode_str = "BEGINNING"
        whence = 0
    elif mode == 0:
        mode_str = "CURRENT"
        whence = 1
        if pos >= 0x80000000:
            pos = pos - 0x100000000
    elif mode == 1:
        mode_str = "END"
        if pos > 0:
            pos = pos - 0x100000000
        whence = 2
    else:
        from amitools.vamos.error import UnsupportedFeatureError

        raise UnsupportedFeatureError("Seek: mode=%d" % mode)

    old_pos = fh.tell()
    new_pos = fh.seek(pos, whence)
    log_dos.info(
        "Seek(%s, %d, %s) -> old_pos=%d new_pos=%d",
        fh,
        pos,
        mode_str,
        old_pos,
        new_pos,
    )
    if new_pos < 0:
        dos.setioerr(ctx, ERROR_SEEK_ERROR)
        return -1
    else:
        dos.setioerr(ctx, 0)
        return old_pos


def set_file_size(dos, ctx, fh_b_addr, pos, mode):
    # normalize the register values to signed 32-bit
    if pos >= 0x80000000:
        pos -= 0x100000000
    if mode >= 0x80000000:
        mode -= 0x100000000
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    if fh is None:
        dos.setioerr(ctx, ERROR_INVALID_LOCK)
        return -1
    new_size = fh.set_file_size(pos, mode)
    log_dos.info("SetFileSize(%s, %d, %d) -> %d", fh, pos, mode, new_size)
    if new_size < 0:
        dos.setioerr(ctx, ERROR_OBJECT_WRONG_TYPE)
        return -1
    dos.setioerr(ctx, NO_ERROR)
    return new_size


# ----- char/line I/O -----


def fgetc(dos, ctx, fh_b_addr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, False)
    ch = fh.getc()
    if ch == -2:
        log_dos.info("FGetC(%s) -> EOF (%d)", fh, ch)
        # EOF is also -1
        ch = -1
    elif ch == -1:
        log_dos.info("FGetC(%s) -> Error (%d)", fh, ch)
    else:
        dos.setioerr(ctx, 0)
        log_dos.info("FGetC(%s) -> '%c' (%d)", fh, ch, ch)
    return ch


def fputc(dos, ctx, fh_b_addr, val):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    log_dos.info("FPutC(%s, '%c' (%d))", fh, val, val)
    fh.write(bytes((val,)))
    return val


def fputs(dos, ctx, fh_b_addr, str_ptr):
    str_dat = ctx.mem.r_cbytes(str_ptr)
    # write to stdout
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    ok = fh.write(str_dat)

    show_data = str_dat[: Helper.MAX_SHOW_DATA]
    log_dos.info("FPuts(%s,#%d:%s)", fh, len(str_dat), show_data)
    return 0 if ok else -1


def ungetc(dos, ctx, fh_b_addr, val):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, False)
    ch = fh.ungetc(val)
    log_dos.info("UnGetC(%s, %d) -> ch=%d (%d)", fh, val, ch, ch)
    return ch


def fgets(dos, ctx, fh_b_addr, buf_addr, buflen):
    # Hack for 'endcli': check FH if fh_End was set to 0 (faked EOF)
    fh_acc = FileHandleStruct(ctx.mem, fh_b_addr << 2)
    fh_end = fh_acc.fh_End.val
    if fh_end == 0:
        return 0

    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, False)
    line, error = fh.gets(buflen)
    log_dos.info("FGetS(%s,%d) -> '%s' error=%s", fh, buflen, line, error)
    ctx.mem.w_cstr(buf_addr, line)
    if line == "":
        return 0
    return buf_addr


# ----- flush/buffer -----


def flush_file(dos, ctx, fh_b_addr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    fh.flush()
    return -1


def set_vbuf(dos, ctx, fh_b_addr, buf_ptr, buf_type, size):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    if fh is None:
        log_dos.warning("SetVBuf: invalid fh=%x", fh_b_addr)
        return 0
    fh.setvbuf(buf_ptr, buf_type, size)
    log_dos.info(
        "SetVBuf(%s, buff=%06x, type=%d, size=%d) -> ok",
        fh,
        buf_ptr,
        buf_type,
        size,
    )
    return 0


# ----- formatted output -----


def printf_to_handle(dos, ctx, fh, fmt, argv_ptr):
    """the printf body shared by VPrintf/VFPrintf"""
    log_dos.info("Printf: format='%s' argv=%06x", fmt, argv_ptr)
    ps = Printf.printf_parse_string(fmt)
    Printf.printf_read_data(ps, ctx.mem, argv_ptr)
    log_dos.debug("Printf: parsed format: %s", ps)
    result = Printf.printf_generate_output(ps)
    # write result
    fh.write(result.encode("latin-1"))
    return len(result)


def vfprintf(dos, ctx, fh_b_addr, fmt, argv_ptr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    log_dos.info("VFPrintf: format='%s' argv=%06x", fmt, argv_ptr)
    return printf_to_handle(dos, ctx, fh, fmt, argv_ptr)


def vfwritef(dos, ctx, fh_b_addr, fmt, args_ptr):
    import ctypes

    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, True)
    log_dos.info("VFWritef: fh=%s format='%s' args_ptr=%06x", fh, fmt, args_ptr)
    out = ""
    pos = 0
    state = ""
    val = 0
    while pos < len(fmt):
        ch = fmt[pos].upper()
        pos = pos + 1
        if state[0:1] == "x":
            n = ord(ch)
            if n >= ord("0") and n <= ord("9"):
                n = n - ord("0")
            elif n >= ord("A") and n <= ord("Z"):
                n = (n - ord("A")) + 10
            else:
                n = 0
            ch = state[1:2]
            if ch == "T":
                out = out + ("%*s" % (-n, ctx.mem.r_cstr(val)))
            elif ch == "O":
                out = out + ("%*O" % (-n, val))
            elif ch == "X":
                out = out + ("%*X" % (-n, val))
            elif ch == "I":
                out = out + ("%*ld" % (-n, ctypes.c_long(val).value))
            elif ch == "U":
                out = out + ("%*lu" % (-n, ctypes.c_ulong(val).value))
            else:
                out = out + "%" + state[1] + state[0]
            state = ""
        elif state == "%":
            if ch == "S":
                out = out + ctx.mem.r_cstr(val)
                state = ""
            elif ch == "C":
                out = out + chr(val & 0xFF)
                state = ""
            elif ch == "N":
                out = out + ("%ld" % ctypes.c_long(val).value)
                state = ""
            elif ch == "$":
                state = ""
            elif ch == "T" or ch == "O" or ch == "X" or ch == "I" or ch == "U":
                state = "x" + ch
            else:
                out = out + "%" + ch
                state = ""
        else:
            if ch == "%":
                state = "%"
                val = ctx.mem.r32(args_ptr)
                args_ptr = args_ptr + 4
            else:
                out = out + ch
    data = out.encode("latin-1")
    fh.write(data)
    return len(data)


# ----- standard handles -----


def select_input(dos, ctx, fh_b_addr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    log_dos.info("SelectInput(fh=%s)", fh)
    cur_in = dos.Input(ctx)
    ctx.process.set_input(fh)
    return cur_in


def select_output(dos, ctx, fh_b_addr):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    log_dos.info("SelectOutput(fh=%s)", fh)
    cur_out = dos.Output(ctx)
    ctx.process.set_output(fh)
    return cur_out


def input(dos, ctx):
    inp_bptr = ctx.process.proc.pr_CIS.aptr >> 2
    log_dos.info("Input() -> b%06x", inp_bptr)
    return inp_bptr


def output(dos, ctx):
    out_bptr = ctx.process.proc.pr_COS.aptr >> 2
    log_dos.info("Output() -> b%06x", out_bptr)
    return out_bptr


def cli(dos, ctx):
    cli_addr = ctx.process.get_cli_struct()
    log_dos.info("Cli() -> %06x", cli_addr)
    return cli_addr


def extended_cli(dos, ctx):
    # is ignored for now
    log_dos.info("ExtendedCli() -> 0")
    return 0


def is_interactive(dos, ctx, fh_b_addr):
    log_dos.info("IsInteractive: @%06x", fh_b_addr)
    if fh_b_addr == 0:
        return DOSFALSE
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr, False)
    res = fh.is_interactive()
    log_dos.info("IsInteractive(%s): %s", fh, res)
    if res:
        return DOSTRUE
    else:
        return DOSFALSE


def wait_for_char(dos, ctx, fh_b_addr, timeout):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    log_dos.info("WaitForChar(fh=%s,timeout=%d ms)", fh, timeout)

    if fh.is_interactive():
        # timeout is given in us resolution so convert it
        timeout = timeout / 1_000_000
        ok = fh.wait_for_char(timeout)
        if ok:
            # char is available
            log_dos.info("WaitForChar: has char")
            dos.setioerr(ctx, 1)  # number of input lines
            return DOSTRUE
        elif ok is False:
            # no char is available
            log_dos.info("WaitForChar: no char available")
            dos.setioerr(ctx, 0)
            return DOSFALSE
        else:
            # wait_for_char not supported
            log_dos.warning("WaitForChar() not supported on this platform!")
            dos.setioerr(ctx, ERROR_NOT_IMPLEMENTED)
            return DOSFALSE
    else:
        log_dos.warning("WaitForChar() not available on non-interactive FH!")
        dos.setioerr(ctx, ERROR_ACTION_NOT_KNOWN)
        return DOSFALSE


def set_mode(dos, ctx, fh_b_addr, mode):
    fh = dos.file_mgr.get_by_b_addr(fh_b_addr)
    log_dos.info("SetMode(fh=%s,mode=%d)", fh, mode)
    # check mode
    if mode == 0:
        cooked = True
    elif mode == 1 or mode == -1:
        cooked = False
    elif mode == 2:
        # ignore medium for now
        log_dos.info("SetMode() ignore medium mode.")
        return DOSFALSE
    else:
        log_dos.warning("SetMode() mode=%d not supported!", mode)
        dos.setioerr(ctx, ERROR_ACTION_NOT_KNOWN)
        return DOSFALSE

    if fh.is_interactive():
        # try to use setmode in interactive
        ok = fh.set_mode(cooked)
        if ok:
            log_dos.info("SetMode: cooked=%s", cooked)
            dos.setioerr(ctx, 0)  # no console window
            return DOSTRUE
        else:
            log_dos.warning("SetMode() not supported on this platform!")
            dos.setioerr(ctx, ERROR_NOT_IMPLEMENTED)
            return DOSFALSE
    else:
        log_dos.info("SetMode() not available on non-interactive FH!")
        dos.setioerr(ctx, ERROR_ACTION_NOT_KNOWN)
        return DOSFALSE


# ----- name operations -----


def delete_file(dos, ctx, name):
    dos.setioerr(ctx, dos.file_mgr.delete(dos.get_current_dir(ctx), name))
    log_dos.info("DeleteFile: '%s': err=%s", name, dos.io_err)
    if dos.io_err == NO_ERROR:
        return DOSTRUE
    else:
        return DOSFALSE


def rename(dos, ctx, old_name, new_name):
    lock = dos.get_current_dir(ctx)
    dos.setioerr(ctx, dos.file_mgr.rename(lock, old_name, new_name))
    log_dos.info("Rename: '%s' -> '%s': err=%s", old_name, new_name, dos.io_err)
    if dos.io_err == NO_ERROR:
        return DOSTRUE
    else:
        return DOSFALSE


def set_protection(dos, ctx, name, mask):
    lock = dos.get_current_dir(ctx)
    dos.setioerr(ctx, dos.file_mgr.set_protection(lock, name, mask))
    log_dos.info("SetProtection: '%s' mask=%04x: err=%s", name, mask, dos.io_err)
    if dos.io_err == NO_ERROR:
        return DOSTRUE
    else:
        return DOSFALSE


def set_comment(dos, ctx, name, comment):
    # the typical unixoid file system does not implement this
    log_dos.warning("SetComment: not implemented")
    return DOSTRUE


def create_dir(dos, ctx, name):
    lock = dos.get_current_dir(ctx)
    err = dos.file_mgr.create_dir(lock, name)
    if err != NO_ERROR:
        dos.setioerr(ctx, err)
        return 0
    else:
        lock = dos.lock_mgr.create_lock(lock, name, True)
        log_dos.info("CreateDir: '%s' -> %s", name, lock)
    if lock is None:
        dos.setioerr(ctx, ERROR_OBJECT_NOT_FOUND)
        return 0
    else:
        return lock.b_addr


def set_file_date(dos, ctx, name, date_ptr):
    ds = DateStampStruct(ctx.mem, date_ptr)
    seconds = ami_to_sys_time(AmiTime(ds.ds_Days.val, ds.ds_Minute.val, ds.ds_Tick.val))
    log_dos.info("SetFileDate: file=%s date=%d", name, seconds)
    try:
        dos.handler_mgr.set_date(name, seconds, cwd=dos.get_cwd_path(ctx))
        return DOSTRUE
    except HandlerError as e:
        log_dos.info("SetFileDate: '%s' failed: %s", name, e)
        dos.setioerr(ctx, e.code)
        return DOSFALSE


# ----- object mode/owner (ACTION_CHANGE_MODE / ACTION_SET_OWNER) -----


def change_mode(dos, ctx, change_type, fh, newmode):
    """ChangeMode(): set the mode of a lock (CHANGE_LOCK) or file (CHANGE_FH)"""
    if change_type == CHANGE_LOCK:
        try:
            obj = dos.lock_mgr.get_by_b_addr(fh) if fh else None
        except Exception:
            obj = None
        if obj is None or obj.handler is None or obj.handler_lock is None:
            dos.setioerr(ctx, ERROR_INVALID_LOCK)
            return DOSFALSE
        handler, handler_obj = obj.handler, obj.handler_lock
    elif change_type == CHANGE_FH:
        try:
            file_handle = dos.file_mgr.get_by_b_addr(fh, False) if fh else None
        except Exception:
            file_handle = None
        if (
            file_handle is None
            or file_handle.handler is None
            or file_handle.handler_file is None
        ):
            dos.setioerr(ctx, ERROR_INVALID_LOCK)
            return DOSFALSE
        handler, handler_obj = file_handle.handler, file_handle.handler_file
    else:
        dos.setioerr(ctx, ERROR_BAD_NUMBER)
        return DOSFALSE
    try:
        handler.change_mode(handler_obj, newmode)
    except HandlerError as e:
        dos.setioerr(ctx, e.code)
        return DOSFALSE
    log_dos.info("ChangeMode(type=%d, mode=%d): ok", change_type, newmode)
    return Helper.bool_result(dos, ctx, True, 0)


def set_owner(dos, ctx, name, owner_info):
    """SetOwner(): pass the new owner info to the handler of ``name``"""
    if dos.handler_mgr is None:
        dos.setioerr(ctx, ERROR_NOT_IMPLEMENTED)
        return DOSFALSE
    try:
        dos.handler_mgr.set_owner(name, owner_info, cwd=dos.get_cwd_path(ctx))
    except HandlerError as e:
        dos.setioerr(ctx, e.code)
        return DOSFALSE
    return Helper.bool_result(dos, ctx, True, 0)


class FileIOMixin:
    """dos.library fd methods (HANDLER.md step 22m)."""

    def SetFileDate(self, ctx, name: CSTR, date):
        return set_file_date(self, ctx, name.get_str(), date)

    def SetComment(self, ctx, name: CSTR, comment: CSTR):
        return set_comment(self, ctx, name.get_str(), comment.get_str())

    def Cli(self, ctx):
        return cli(self, ctx)

    def ExtendedCli(self, ctx):
        return extended_cli(self, ctx)

    def Input(self, ctx):
        return input(self, ctx)

    def Output(self, ctx):
        return output(self, ctx)

    def SelectInput(self, ctx, fh_b_addr):
        return select_input(self, ctx, fh_b_addr)

    def SelectOutput(self, ctx, fh_b_addr):
        return select_output(self, ctx, fh_b_addr)

    def SetMode(self, ctx, fh_b_addr, mode: LONG):
        return set_mode(self, ctx, fh_b_addr, mode.val)

    def WaitForChar(self, ctx, fh_b_addr, timeout: LONG):
        return wait_for_char(self, ctx, fh_b_addr, timeout.val)

    def Open(self, ctx, name_ptr, mode):
        return open_file(self, ctx, name_ptr, mode)

    def Close(self, ctx, fh_b_addr):
        return close_file(self, ctx, fh_b_addr)

    def Read(self, ctx, fh_b_addr, buf_ptr, size):
        return read_file(self, ctx, fh_b_addr, buf_ptr, size)

    def Write(self, ctx, fh_b_addr, buf_ptr, size):
        return write_file(self, ctx, fh_b_addr, buf_ptr, size)

    def FWrite(self, ctx, fh_b_addr, buf_ptr, size, number):
        return fwrite(self, ctx, fh_b_addr, buf_ptr, size, number)

    def FRead(self, ctx, fh_b_addr, buf_ptr, size, number):
        return fread(self, ctx, fh_b_addr, buf_ptr, size, number)

    def Seek(self, ctx, fh_b_addr, pos, mode):
        return seek(self, ctx, fh_b_addr, pos, mode)

    def SetFileSize(self, ctx, fh_b_addr, pos, mode):
        return set_file_size(self, ctx, fh_b_addr, pos, mode)

    def FGetC(self, ctx, fh_b_addr):
        return fgetc(self, ctx, fh_b_addr)

    def FPutC(self, ctx, fh_b_addr, val):
        return fputc(self, ctx, fh_b_addr, val)

    def FPuts(self, ctx, fh_b_addr, str_ptr):
        return fputs(self, ctx, fh_b_addr, str_ptr)

    def UnGetC(self, ctx, fh_b_addr, val):
        return ungetc(self, ctx, fh_b_addr, val)

    def Flush(self, ctx, fh_b_addr):
        return flush_file(self, ctx, fh_b_addr)

    def SetVBuf(self, ctx, fh_b_addr, buf_ptr, buf_type, size):
        return set_vbuf(self, ctx, fh_b_addr, buf_ptr, buf_type, size)

    def VPrintf(self, ctx, format: CSTR, argv_ptr):
        return printf_to_handle(
            self, ctx, ctx.process.get_output(), format.get_str(), argv_ptr
        )

    def VFPrintf(self, ctx, fh_b_addr, format: CSTR, argv_ptr):
        return vfprintf(self, ctx, fh_b_addr, format.get_str(), argv_ptr)

    def VFWritef(self, ctx, fh_b_addr, format: CSTR, args_ptr):
        return vfwritef(self, ctx, fh_b_addr, format.get_str(), args_ptr)

    def FGets(self, ctx, fh_b_addr, buf_addr, buflen):
        return fgets(self, ctx, fh_b_addr, buf_addr, buflen)

    def DeleteFile(self, ctx, name: CSTR):
        return delete_file(self, ctx, name.get_str())

    def Rename(self, ctx, oldName: CSTR, newName: CSTR):
        return rename(self, ctx, oldName.get_str(), newName.get_str())

    def SetProtection(self, ctx, name: CSTR, protect):
        return set_protection(self, ctx, name.get_str(), protect)

    def IsInteractive(self, ctx, fh_b_addr):
        return is_interactive(self, ctx, fh_b_addr)

    def CreateDir(self, ctx, name: CSTR):
        return create_dir(self, ctx, name.get_str())

    def ChangeMode(self, ctx, type: LONG, fh: LONG, newmode: LONG):
        return change_mode(self, ctx, type.val, fh.val, newmode.val)

    def SetOwner(self, ctx, name: CSTR, owner_info: LONG):
        return set_owner(self, ctx, name.get_str(), owner_info.val)
