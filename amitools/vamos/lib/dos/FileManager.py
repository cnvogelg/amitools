import sys

from amitools.vamos.log import log_file
from amitools.vamos.handler import (
    HandlerError,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
)
from amitools.vamos.libstructs import MessageStruct, DosPacketStruct
from amitools.vamos.path.amipath import AmiPath
from .Error import *
from .FileHandle import FileHandle
from .action import DosAction
from .PathPart import expand_progdir_path

# map the Python-ish modes used by the DOS layer to AmigaDOS open modes
_DOS_MODES = {
    "w": MODE_NEWFILE,
    "wb": MODE_NEWFILE,
    "wb+": MODE_NEWFILE,
    "rw": MODE_READWRITE,
    "rwb+": MODE_READWRITE,
    "r": MODE_OLDFILE,
    "rb": MODE_OLDFILE,
    "rb+": MODE_OLDFILE,
}

# modes that only need read access
_READ_MODES = ("r", "rb")


class FileManager:
    def __init__(self, handler_mgr, port_mgr, alloc, mem):
        self.handler_mgr = handler_mgr
        self.port_mgr = port_mgr
        self.alloc = alloc
        self.mem = mem

        self.files_by_b_addr = {}

        # setup ports
        # currently we use a single fake port for all devices
        self.fs_handler_port = port_mgr.create_port("FakeFSPort", self.fs_put_msg)
        log_file.info("dos fs handler port: %06x" % self.fs_handler_port)
        # create console handler
        self.console_handler_port = port_mgr.create_port(
            "ConsolePort", self.console_put_msg
        )
        log_file.info("dos console port: %06x" % self.console_handler_port)

        # setup std input/output
        self.std_input = self._create_stdin_fh()
        self.std_output = self._create_stdout_fh()
        self._register_file(self.std_input)
        self._register_file(self.std_output)

    def finish(self):
        self._unregister_file(self.std_input)
        self._unregister_file(self.std_output)
        # close stdin/out (cleanup TTY if needed)
        self.std_input.close()
        self.std_output.close()
        # free ports
        self.port_mgr.free_port(self.fs_handler_port)
        self.port_mgr.free_port(self.console_handler_port)

    def _create_stdin_fh(self):
        return FileHandle(sys.stdin.buffer, "<STDIN>", "<STDIN>", need_close=False)

    def _create_stdout_fh(self):
        return FileHandle(
            sys.stdout.buffer,
            "<STDOUT>",
            "<STDOUT>",
            need_close=False,
            auto_flush=True,
        )

    def get_fs_handler_port(self):
        return self.fs_handler_port

    def get_console_handler_port(self):
        return self.console_handler_port

    def _register_file(self, fh):
        baddr = fh.alloc_fh(self.alloc, self.fs_handler_port)
        self.files_by_b_addr[baddr] = fh
        log_file.info("registered: %s" % fh)

    def _unregister_file(self, fh):
        if fh.b_addr in self.files_by_b_addr:
            check = self.files_by_b_addr[fh.b_addr]
            if check != fh:
                raise ValueError("Invalid File to unregister: %s" % fh)
        else:
            raise ValueError("Invalid File to unregister: %s" % fh)
        del self.files_by_b_addr[fh.b_addr]
        log_file.info("unregistered: %s" % fh)
        fh.free_fh(self.alloc)

    def get_input(self):
        return self.std_input

    def get_output(self):
        return self.std_output

    def _ami_name(self, ami_path):
        name = AmiPath(str(ami_path)).filename()
        return name if name else str(ami_path)

    def _open_via_handler(self, ami_path, f_mode, cwd):
        try:
            if f_mode in _READ_MODES:
                handler, handler_file = self.handler_mgr.find_input(ami_path, cwd=cwd)
            else:
                mode = _DOS_MODES.get(f_mode, MODE_OLDFILE)
                handler, handler_file = self.handler_mgr.find_output(
                    ami_path, mode, cwd=cwd
                )
        except HandlerError as e:
            log_file.info("error opening: '%s' f_mode=%s -> %s", ami_path, f_mode, e)
            return None
        return FileHandle(
            handler_file.fobj,
            ami_path,
            self._ami_name(ami_path),
            handler=handler,
            handler_file=handler_file,
            need_close=handler_file.need_close,
            auto_flush=handler_file.auto_flush,
            is_nil=handler_file.is_nil,
        )

    def open(self, lock, ami_path, f_mode, home_dir=None):
        cwd = lock.ami_path if lock is not None else None
        # '*' is the AmigaDOS console device
        if str(ami_path) == "*":
            ami_path = "console:"
        else:
            # Handle '*' prefix (PROGDIR: - program's home directory)
            expanded = expand_progdir_path(ami_path, home_dir)
            if expanded != ami_path:
                log_file.debug("expanded '*' path to: %s", expanded)
                ami_path = expanded
        fh = self._open_via_handler(ami_path, f_mode, cwd)
        if fh is None:
            return None
        self._register_file(fh)
        return fh

    def close(self, fh):
        fh.close()
        # do not unregister stdin/stdout. it will be done in finish()
        if fh not in (self.std_input, self.std_output):
            self._unregister_file(fh)

    def get_by_b_addr(self, b_addr, for_writing=None):
        if b_addr == 0:
            return None
        if b_addr in self.files_by_b_addr:
            fh = self.files_by_b_addr[b_addr]
            # AmigaDos has no problem reading from an output console handle
            # or writing to the input handle for the console.
            if for_writing == True and fh.obj == sys.stdin:
                return self.std_output
            elif for_writing == False and fh.obj == sys.stdout:
                return self.std_input
            return fh
        else:
            addr = b_addr << 2
            raise ValueError("Invalid File Handle at b@%06x = %06x" % (b_addr, addr))

    def delete(self, lock, ami_path):
        cwd = lock.ami_path if lock is not None else None
        try:
            self.handler_mgr.delete_object(ami_path, cwd=cwd)
            return NO_ERROR
        except HandlerError as e:
            log_file.info("can't delete '%s': %s", ami_path, e)
            return e.code

    def rename(self, lock, old_ami_path, new_ami_path):
        cwd = lock.ami_path if lock is not None else None
        try:
            self.handler_mgr.rename_object(old_ami_path, new_ami_path, cwd=cwd)
            return NO_ERROR
        except HandlerError as e:
            log_file.info(
                "can't rename '%s' -> '%s': %s", old_ami_path, new_ami_path, e
            )
            return e.code

    def is_file_system(self, lock, name):
        # '*' is an alias for the console device
        if str(name) == "*":
            name = "console:"
        # look up a registered handler by device/volume name
        vol_name = name.split(":")[0] if ":" in name else name
        return self.handler_mgr.is_filesystem(vol_name)

    def set_protection(self, lock, ami_path, mask):
        cwd = lock.ami_path if lock is not None else None
        try:
            self.handler_mgr.set_protect(ami_path, mask, cwd=cwd)
            return NO_ERROR
        except HandlerError as e:
            log_file.info("can't set protection '%s': %s", ami_path, e)
            return e.code

    def create_dir(self, lock, ami_path):
        cwd = lock.ami_path if lock is not None else None
        try:
            self.handler_mgr.create_dir(ami_path, cwd=cwd)
            return NO_ERROR
        except HandlerError as e:
            log_file.info("can't create dir '%s': %s", ami_path, e)
            return e.code

    # ----- Direct Handler Access -----

    # callback from port manager for fs handler port
    # -> Async I/O
    def fs_put_msg(self, port_mgr, msg_addr):
        msg = MessageStruct(self.mem, msg_addr)
        dos_pkt_addr = msg.node.name.aptr
        dos_pkt = DosPacketStruct(self.mem, dos_pkt_addr)
        reply_port_addr = dos_pkt.port.aptr
        pkt_type = dos_pkt.type.val
        log_file.info(
            "FS DosPacket: msg=%06x -> pkt=%06x: reply_port=%06x type=%06x (%s)",
            msg_addr,
            dos_pkt_addr,
            reply_port_addr,
            pkt_type,
            DosAction(pkt_type).name,
        )
        # handle packet
        if pkt_type == DosAction.ACTION_READ:  # read
            fh_b_addr = dos_pkt.arg1.val
            buf_ptr = dos_pkt.arg2.val
            size = dos_pkt.arg3.val
            # get fh and read
            fh = self.get_by_b_addr(fh_b_addr)
            data = fh.read(size)
            self.mem.w_block(buf_ptr, data)
            got = len(data)
            log_file.info(
                "DosPacket: Read fh_b_addr=%06x buf=%06x len=%06x -> got=%06x fh=%s",
                fh_b_addr,
                buf_ptr,
                size,
                got,
                fh,
            )
            dos_pkt.res1.val = got
        elif pkt_type == DosAction.ACTION_WRITE:  # write
            fh_b_addr = dos_pkt.arg1.val
            buf_ptr = dos_pkt.arg2.val
            size = dos_pkt.arg3.val
            fh = self.get_by_b_addr(fh_b_addr)
            data = self.mem.r_block(buf_ptr, size)
            fh.write(data)
            put = len(data)
            log_file.info(
                "DosPacket: Write fh=%06x buf=%06x len=%06x -> put=%06x fh=%s",
                fh_b_addr,
                buf_ptr,
                size,
                put,
                fh,
            )
            dos_pkt.res1.val = put
        else:
            log_file.warning(
                "Unsupported Filesys Packet: %d (%s)",
                pkt_type,
                DosAction(pkt_type).name,
            )
            # return error
            dos_pkt.res1.val = DOSFALSE
            dos_pkt.res2.val = ERROR_ACTION_NOT_KNOWN

        # do reply
        if not port_mgr.has_port(reply_port_addr):
            port_mgr.register_port(reply_port_addr)
        port_mgr.put_msg(reply_port_addr, msg_addr)

    # handle console packet
    def console_put_msg(self, port_mgr, msg_addr):
        msg = MessageStruct(self.mem, msg_addr)
        dos_pkt_addr = msg.node.name.aptr
        dos_pkt = DosPacketStruct(self.mem, dos_pkt_addr)
        reply_port_addr = dos_pkt.port.aptr
        pkt_type = dos_pkt.type.val
        log_file.info(
            "Console DosPacket: msg=%06x -> pkt=%06x: reply_port=%06x type=%d (%s)",
            msg_addr,
            dos_pkt_addr,
            reply_port_addr,
            pkt_type,
            DosAction(pkt_type).name,
        )

        if pkt_type == DosAction.ACTION_SCREEN_MODE:
            mode = dos_pkt.arg1.val
            if mode == 0:
                cooked = True
            elif mode == 1 or mode == -1:
                cooked = False
            else:
                log_file.warning("Unsupported Console Mode: %d", mode)
                # return error
                pkt_result = (DOSFALSE, ERROR_BAD_NUMBER)
                cooked = None

            res = False
            if cooked is not None:
                res = self.std_input.set_mode(cooked)
                if res:
                    log_file.info("Set Console Mode %d -> cooked=%s", mode, cooked)
                    pkt_result = (DOSTRUE_S, 0)  # 0=no window
                else:
                    log_file.warning(
                        "Can't set Console Mode %d -> cooked=%s", mode, cooked
                    )
                    # return error
                    pkt_result = (DOSFALSE, ERROR_ACTION_NOT_IMPLEMENTED)
        else:
            log_file.warning(
                "Unsupported Console Packet: %d (%s)",
                pkt_type,
                DosAction(pkt_type).name,
            )
            pkt_result = (DOSFALSE, ERROR_ACTION_NOT_KNOWN)

        # return set result
        dos_pkt.res1.val = pkt_result[0]
        dos_pkt.res2.val = pkt_result[1]

        # do reply
        if not port_mgr.has_port(reply_port_addr):
            port_mgr.register_port(reply_port_addr)
        port_mgr.put_msg(reply_port_addr, msg_addr)
