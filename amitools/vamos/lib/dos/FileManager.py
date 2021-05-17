import sys
import os.path
import os
import logging
import errno
import stat

from amitools.vamos.log import log_file
from amitools.vamos.error import UnsupportedFeatureError
from amitools.vamos.astructs import AccessStruct
from amitools.vamos.libstructs import MessageStruct, DosPacketStruct
from .Error import *
from .DosProtection import DosProtection
from .FileHandle import FileHandle


class FileManager:
    def __init__(self, path_mgr, port_mgr, alloc, mem):
        self.path_mgr = path_mgr
        self.port_mgr = port_mgr
        self.alloc = alloc
        self.mem = mem

        self.files_by_b_addr = {}

        # get current umask
        self.umask = os.umask(0)
        os.umask(self.umask)

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
        # free ports
        self.port_mgr.free_port(self.fs_handler_port)
        self.port_mgr.free_port(self.console_handler_port)

    def _create_stdin_fh(self):
        return FileHandle(sys.stdin.buffer, "<STDIN>", "/dev/stdin", need_close=False)

    def _create_stdout_fh(self):
        fobj = sys.stdout.buffer
        # try to get a fd from fobj
        try:
            fileno = fobj.fileno()
            # create unbuffered raw stream if its a tty
            if os.isatty(fileno):
                fobj = open(fileno, "wb", buffering=0)
                log_file.debug(
                    "open no buffering: fileno=%s -> %s, fileno=%s",
                    fileno,
                    fobj,
                    fobj.fileno(),
                )
        except Exception:
            pass
        return FileHandle(fobj, "<STDOUT>", "/dev/stdout", need_close=False)

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

    def open(self, lock, ami_path, f_mode):
        try:
            # special names
            uname = ami_path.upper()
            # thor: NIL: and CONSOLE: also work as device names
            # and the file names behind are ignored.
            if uname.startswith("NIL:"):
                sys_name = "/dev/null"
                if f_mode == "rwb+":
                    f_mode = "rb+"
                fobj = open(sys_name, f_mode)
                fh = FileHandle(fobj, ami_path, sys_name, is_nil=True)
            elif uname == "*" or uname.startswith("CONSOLE:"):
                sys_name = ""
                fh = self._create_stdout_fh()
            else:
                # map to system path
                sys_path = self.path_mgr.ami_to_sys_path(
                    lock, ami_path, searchMulti=True
                )
                if sys_path == None:
                    log_file.info("file not found: '%s' -> '%s'" % (ami_path, sys_path))
                    return None

                # make some checks on existing file
                if os.path.exists(sys_path):
                    # if not writeable -> no append mode
                    if f_mode == "rwb+":
                        f_mode = "rb+"
                    if not os.access(sys_path, os.W_OK):
                        if f_mode[-1] == "+":
                            f_mode = f_mode[:-1]
                else:
                    # if the file does not exist, but the mode is MODE_READWRITE, create it.
                    if f_mode == "rwb+":
                        f_mode = "wb+"

                log_file.debug(
                    "opening file: '%s' -> '%s' f_mode=%s"
                    % (ami_path, sys_path, f_mode)
                )
                fobj = open(sys_path, f_mode)
                fh = FileHandle(fobj, ami_path, sys_path)

            self._register_file(fh)
            return fh
        except IOError as e:
            log_file.info(
                "error opening: '%s' -> '%s' f_mode=%s -> %s"
                % (ami_path, sys_path, f_mode, e)
            )
            return None

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
        sys_path = self.path_mgr.ami_to_sys_path(lock, ami_path)
        if sys_path == None or not os.path.exists(sys_path):
            log_file.info("file to delete not found: '%s'" % (ami_path))
            return ERROR_OBJECT_NOT_FOUND
        try:
            if os.path.isdir(sys_path):
                os.rmdir(sys_path)
            else:
                os.remove(sys_path)
            return 0
        except OSError as e:
            if e.errno == errno.ENOTEMPTY:  # Directory not empty
                log_file.info("can't delete directory: '%s' -> not empty!" % (ami_path))
                return ERROR_DIRECTORY_NOT_EMPTY
            else:
                log_file.info("can't delete file: '%s' -> %s" % (ami_path, e))
                return ERROR_OBJECT_IN_USE

    def rename(self, lock, old_ami_path, new_ami_path):
        old_sys_path = self.path_mgr.ami_to_sys_path(lock, old_ami_path)
        new_sys_path = self.path_mgr.ami_to_sys_path(lock, new_ami_path)
        if old_sys_path == None or not os.path.exists(old_sys_path):
            log_file.info("old file to rename not found: '%s'" % old_ami_path)
            return ERROR_OBJECT_NOT_FOUND
        if new_sys_path == None:
            log_file.info("new file to rename not found: '%s'" % new_ami_path)
            return ERROR_OBJECT_NOT_FOUND
        try:
            os.rename(old_sys_path, new_sys_path)
            return 0
        except OSError as e:
            log_file.info(
                "can't rename file: '%s','%s' -> %s" % (old_ami_path, new_ami_path, e)
            )
            return ERROR_OBJECT_IN_USE

    def is_file_system(self, lock, name):
        uname = name.upper()
        if uname.startswith("NIL:"):
            return False
        elif uname == "*" or uname.startswith("CONSOLE:"):
            return False
        # Everything else is a file system here, we don't support any
        # other devices.
        return True

    def set_protection(self, lock, ami_path, mask):
        sys_path = self.path_mgr.ami_to_sys_path(lock, ami_path)
        if sys_path == None or not os.path.exists(sys_path):
            log_file.info("file to set proteciton not found: '%s'", ami_path)
            return ERROR_OBJECT_NOT_FOUND
        prot = DosProtection(mask)
        posix_mask = 0
        if prot.is_e():
            posix_mask |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        if prot.is_w():
            posix_mask |= stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
        if prot.is_r():
            posix_mask |= stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
        posix_mask &= ~self.umask
        log_file.info(
            "set protection: '%s': %s -> '%s': posix_mask=%03o umask=%03o",
            ami_path,
            prot,
            sys_path,
            posix_mask,
            self.umask,
        )
        try:
            os.chmod(sys_path, posix_mask)
            return NO_ERROR
        except OSError:
            return ERROR_OBJECT_WRONG_TYPE

    def create_dir(self, lock, ami_path):
        sys_path = self.path_mgr.ami_to_sys_path(lock, ami_path)
        try:
            os.mkdir(sys_path)
            return NO_ERROR
        except OSError:
            return ERROR_OBJECT_EXISTS

    # ----- Direct Handler Access -----

    # callback from port manager for fs handler port
    # -> Async I/O
    def fs_put_msg(self, port_mgr, msg_addr):
        msg = AccessStruct(self.mem, MessageStruct, struct_addr=msg_addr)
        dos_pkt_addr = msg.r_s("mn_Node.ln_Name")
        dos_pkt = AccessStruct(self.mem, DosPacketStruct, struct_addr=dos_pkt_addr)
        reply_port_addr = dos_pkt.r_s("dp_Port")
        pkt_type = dos_pkt.r_s("dp_Type")
        log_file.info(
            "FS DosPacket: msg=%06x -> pkt=%06x: reply_port=%06x type=%06x",
            msg_addr,
            dos_pkt_addr,
            reply_port_addr,
            pkt_type,
        )
        # handle packet
        if pkt_type == ord("R"):  # read
            fh_b_addr = dos_pkt.r_s("dp_Arg1")
            buf_ptr = dos_pkt.r_s("dp_Arg2")
            size = dos_pkt.r_s("dp_Arg3")
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
            dos_pkt.w_s("dp_Res1", got)
        elif pkt_type == ord("W"):  # write
            fh_b_addr = dos_pkt.r_s("dp_Arg1")
            buf_ptr = dos_pkt.r_s("dp_Arg2")
            size = dos_pkt.r_s("dp_Arg3")
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
            dos_pkt.w_s("dp_Res1", put)
        else:
            raise UnsupportedFeatureError("Unsupported DosPacket: type=%d" % pkt_type)
        # do reply
        if not port_mgr.has_port(reply_port_addr):
            port_mgr.register_port(reply_port_addr)
        port_mgr.put_msg(reply_port_addr, msg_addr)

    # handle console packet
    def console_put_msg(self, port_mgr, msg_addr):
        msg = AccessStruct(self.mem, MessageStruct, struct_addr=msg_addr)
        dos_pkt_addr = msg.r_s("mn_Node.ln_Name")
        dos_pkt = AccessStruct(self.mem, DosPacketStruct, struct_addr=dos_pkt_addr)
        reply_port_addr = dos_pkt.r_s("dp_Port")
        pkt_type = dos_pkt.r_s("dp_Type")
        log_file.info(
            "Console DosPacket: msg=%06x -> pkt=%06x: reply_port=%06x type=%06x",
            msg_addr,
            dos_pkt_addr,
            reply_port_addr,
            pkt_type,
        )
        # fake result
        dos_pkt.w_s("dp_Res1", 0)
        # do reply
        if not port_mgr.has_port(reply_port_addr):
            port_mgr.register_port(reply_port_addr)
        port_mgr.put_msg(reply_port_addr, msg_addr)
