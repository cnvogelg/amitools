import sys

from amitools.vamos.error import VamosInternalError
from amitools.vamos.handler import (
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
    HandlerError,
    PacketDecoder,
)
from amitools.vamos.log import log_file
from amitools.vamos.path.amipath import AmiPath

from .Error import (
    ERROR_INVALID_LOCK,
    ERROR_OBJECT_NOT_FOUND,
    NO_ERROR,
)
from .FileHandle import FileHandle
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
        # the lock manager is created after the file manager, so dos.library
        # assigns it later; the packet resolvers read it lazily
        self.lock_mgr = None

        self.files_by_b_addr = {}

        # every handler gets its own packet port (a dispatcher bundling the
        # port with the decoder that serves that handler)
        self._bind_dispatchers()

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
        # free the handlers' packet ports
        self._detach_dispatchers()

    def _create_console_fh(self, read):
        """wrap the console device's input/output as the default DOS handle

        The console handler owns the tty and encoding conversions, so the
        default stdin/stdout handles go through it too.
        """
        name = "<STDIN>" if read else "<STDOUT>"
        if self.handler_mgr is not None:
            try:
                if read:
                    handler, handler_file = self.handler_mgr.find_input("console:")
                else:
                    handler, handler_file = self.handler_mgr.find_output("console:")
            except (HandlerError, AttributeError):
                pass
            else:
                return FileHandle(
                    handler_file.fobj,
                    name,
                    name,
                    handler=handler,
                    handler_file=handler_file,
                    need_close=handler_file.need_close,
                    auto_flush=handler_file.auto_flush,
                    is_nil=handler_file.is_nil,
                )
        # fall back to the raw host streams (e.g. bare test managers)
        obj = sys.stdin.buffer if read else sys.stdout.buffer
        return FileHandle(obj, name, name, need_close=False, auto_flush=not read)

    def _create_stdin_fh(self):
        return self._create_console_fh(read=True)

    def _create_stdout_fh(self):
        return self._create_console_fh(read=False)

    def _register_file(self, fh):
        baddr = fh.alloc_fh(self.alloc)
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

    def wrap_handler_file(self, handler, handler_file, ami_path, name=None):
        """wrap a handler file into a registered DOS :class:`FileHandle`

        Shared by the path-based open and ``OpenFromLock`` (which already has
        a handler file).
        """
        if name is None:
            name = self._ami_name(ami_path)
        fh = FileHandle(
            handler_file.fobj,
            ami_path,
            name,
            handler=handler,
            handler_file=handler_file,
            need_close=handler_file.need_close,
            auto_flush=handler_file.auto_flush,
            is_nil=handler_file.is_nil,
        )
        self._register_file(fh)
        return fh

    def open_from_lock(self, lock, mode=MODE_OLDFILE):
        """open a file from a lock (ACTION_FH_FROM_LOCK)

        The returned handle owns the file; the caller releases the DOS lock.
        Raises :class:`HandlerError` if the object can not be opened.
        """
        if lock.handler is None or lock.handler_lock is None:
            raise HandlerError(ERROR_OBJECT_NOT_FOUND)
        handler_file = lock.handler.fh_from_lock(lock.handler_lock, mode)
        return self.wrap_handler_file(
            lock.handler, handler_file, lock.ami_path, name=lock.name
        )

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
        return self.wrap_handler_file(handler, handler_file, ami_path)

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
            # AmigaDOS has no problem reading from an output console handle
            # or writing to the input handle for the console. The console
            # streams know their direction, so redirect between the two.
            direction = getattr(fh.obj, "direction", None)
            if for_writing == True and direction == "in":
                return self.std_output
            elif for_writing == False and direction == "out":
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

    # ----- Packet decoding -----

    def _make_decoder(self, handler):
        """build the :class:`PacketDecoder` that serves ``handler``

        The decoder is scoped to the handler: ``volume_handler`` names it (for
        ZERO-lock path packets) and the decoder rejects fh/lock packets whose
        handle belongs to a different handler.
        """
        return PacketDecoder(
            self.mem,
            resolve_fh=self._resolve_fh,
            resolve_lock=self._resolve_lock,
            volume_handler=lambda: handler,
            register_lock=self._register_handler_lock,
            register_file=self._register_handler_file,
            release_lock=self._release_lock,
            release_file=self._release_file,
        )

    def _bind_dispatchers(self):
        """give every handler its own packet port (see HandlerManager)"""
        attach = getattr(self.handler_mgr, "attach_dispatchers", None)
        if attach is not None:
            attach(self.port_mgr, self.mem, self._make_decoder)

    def _detach_dispatchers(self):
        detach = getattr(self.handler_mgr, "detach_dispatchers", None)
        if detach is not None:
            detach()

    # ----- packet resolvers (injected into the decoder) -----

    def _resolve_fh(self, fh_id):
        try:
            fh = self.get_by_b_addr(fh_id)
        except (ValueError, VamosInternalError):
            raise HandlerError(ERROR_INVALID_LOCK)
        if fh is None or fh.handler is None or fh.handler_file is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        return fh.handler, fh.handler_file, fh.ami_path

    def _resolve_lock(self, lock_id):
        if self.lock_mgr is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        try:
            lock = self.lock_mgr.get_by_b_addr(lock_id)
        except (ValueError, KeyError, IndexError, VamosInternalError):
            raise HandlerError(ERROR_INVALID_LOCK)
        if lock is None or lock.handler is None or lock.handler_lock is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        return lock.handler, lock.handler_lock, lock.ami_path

    def _register_handler_lock(self, handler, handler_lock, ami_path):
        if self.lock_mgr is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        lock = self.lock_mgr.register_handler_lock(handler, handler_lock, ami_path)
        if lock is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        return lock.b_addr

    def _register_handler_file(self, handler, handler_file, ami_path):
        fh = self.wrap_handler_file(handler, handler_file, ami_path)
        return fh.b_addr

    def _release_lock(self, lock_id):
        if self.lock_mgr is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        try:
            lock = self.lock_mgr.get_by_b_addr(lock_id)
        except (ValueError, KeyError, IndexError, VamosInternalError):
            raise HandlerError(ERROR_INVALID_LOCK)
        if lock is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        self.lock_mgr.release_lock(lock)

    def _release_file(self, fh_id):
        try:
            fh = self.get_by_b_addr(fh_id)
        except (ValueError, VamosInternalError):
            raise HandlerError(ERROR_INVALID_LOCK)
        if fh is None:
            raise HandlerError(ERROR_INVALID_LOCK)
        self.close(fh)
