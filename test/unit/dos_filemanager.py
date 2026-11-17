import io
from types import SimpleNamespace

import pytest

from amitools.vamos.handler import (
    HandlerError,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
)
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE_S,
    ERROR_ACTION_NOT_KNOWN,
)
from amitools.vamos.lib.dos.FileManager import FileManager
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DosPacketStruct,
    InfoDataStruct,
    MessageStruct,
)
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


def _make_packet_mem(mem, msg_addr=0x100, pkt_addr=0x200, reply_port_addr=0x300):
    msg = MessageStruct(mem, msg_addr)
    msg.node.name.aptr = pkt_addr
    dos_pkt = DosPacketStruct(mem, pkt_addr)
    dos_pkt.port.aptr = reply_port_addr
    return msg, dos_pkt


def _make_port_mgr():
    registered_ports = []
    replies = []
    port_mgr = SimpleNamespace(
        has_port=lambda addr: False,
        register_port=registered_ports.append,
        put_msg=lambda port_addr, addr: replies.append((port_addr, addr)),
    )
    return port_mgr, registered_ports, replies


def dos_filemanager_disk_info_packet_test():
    from amitools.vamos.handler import HandlerInfoData

    mem = MockMemory()
    msg, dos_pkt = _make_packet_mem(mem)
    dos_pkt.type.val = DosAction.ACTION_DISK_INFO
    info_ptr = 0x400
    dos_pkt.arg1.val = info_ptr

    calls = []

    def disk_info(lock):
        calls.append(lock)
        return HandlerInfoData(num_blocks=100, num_blocks_used=10)

    handler = SimpleNamespace(disk_info=disk_info)
    port_mgr, registered_ports, replies = _make_port_mgr()
    file_mgr = FileManager.__new__(FileManager)
    file_mgr.mem = mem

    file_mgr.make_volume_put_msg(handler)(port_mgr, msg.addr)

    assert dos_pkt.res1.val == DOSTRUE_S
    assert dos_pkt.res2.val == 0
    # DISK_INFO is a lock-less volume query
    assert calls == [None]
    info = InfoDataStruct(mem, info_ptr)
    assert info.id_NumBlocks.val == 100
    assert info.id_NumBlocksUsed.val == 10
    assert registered_ports == [0x300]
    assert replies == [(0x300, msg.addr)]


def dos_filemanager_unsupported_filesys_packet_test():
    mem = MockMemory()
    msg, dos_pkt = _make_packet_mem(mem)
    # MAKE_LINK has no handler action, so the decoder reports it unknown
    dos_pkt.type.val = DosAction.ACTION_MAKE_LINK

    handler = SimpleNamespace()
    port_mgr, registered_ports, replies = _make_port_mgr()
    file_mgr = FileManager.__new__(FileManager)
    file_mgr.mem = mem

    file_mgr.make_volume_put_msg(handler)(port_mgr, msg.addr)

    assert dos_pkt.res1.val == DOSFALSE
    assert dos_pkt.res2.val == ERROR_ACTION_NOT_KNOWN
    assert registered_ports == [0x300]
    assert replies == [(0x300, msg.addr)]


def _make_file_mgr(handler_mgr):
    """A FileManager without ports/alloc, so only the routing runs."""
    file_mgr = FileManager.__new__(FileManager)
    file_mgr.handler_mgr = handler_mgr
    file_mgr.files_by_b_addr = {}
    file_mgr.std_input = None
    file_mgr.std_output = None
    file_mgr._register_file = lambda fh: fh
    return file_mgr


def _make_handler():
    return SimpleNamespace()


def _make_handler_file(data=b"data"):
    return SimpleNamespace(
        fobj=io.BytesIO(data),
        is_nil=False,
        need_close=True,
        auto_flush=False,
    )


def dos_filemanager_open_input_test():
    handler = _make_handler()
    handler_file = _make_handler_file()
    calls = []

    def find_input(path, cwd=None):
        calls.append((path, cwd))
        return handler, handler_file

    handler_mgr = SimpleNamespace(find_input=find_input)
    file_mgr = _make_file_mgr(handler_mgr)
    lock = SimpleNamespace(ami_path="work:")

    fh = file_mgr.open(lock, "work:file.txt", "rb")

    assert calls == [("work:file.txt", "work:")]
    assert fh.obj is handler_file.fobj
    assert fh.handler is handler
    assert fh.handler_file is handler_file
    assert fh.name == "file.txt"
    assert fh.ami_path == "work:file.txt"


def dos_filemanager_open_mode_test():
    handler = _make_handler()
    modes = []

    def find_output(path, mode=MODE_NEWFILE, cwd=None):
        modes.append(mode)
        return handler, _make_handler_file()

    handler_mgr = SimpleNamespace(find_output=find_output)
    file_mgr = _make_file_mgr(handler_mgr)
    lock = SimpleNamespace(ami_path="work:")

    file_mgr.open(lock, "work:f", "wb+")
    file_mgr.open(lock, "work:f", "rb+")
    file_mgr.open(lock, "work:f", "rwb+")

    assert modes == [MODE_NEWFILE, MODE_OLDFILE, MODE_READWRITE]


def dos_filemanager_open_error_test():
    def find_input(path, cwd=None):
        raise HandlerError(205)

    handler_mgr = SimpleNamespace(find_input=find_input)
    file_mgr = _make_file_mgr(handler_mgr)
    lock = SimpleNamespace(ami_path="work:")

    assert file_mgr.open(lock, "work:missing", "rb") is None


def dos_filemanager_delete_rename_test():
    calls = []

    def delete_object(path, cwd=None):
        calls.append(("delete", path, cwd))

    def rename_object(old, new, cwd=None):
        calls.append(("rename", old, new, cwd))

    handler_mgr = SimpleNamespace(
        delete_object=delete_object, rename_object=rename_object
    )
    file_mgr = _make_file_mgr(handler_mgr)
    lock = SimpleNamespace(ami_path="work:")

    assert file_mgr.delete(lock, "work:x") == 0
    assert file_mgr.rename(lock, "work:a", "work:b") == 0
    assert calls == [
        ("delete", "work:x", "work:"),
        ("rename", "work:a", "work:b", "work:"),
    ]

    def delete_object_error(path, cwd=None):
        raise HandlerError(216)

    file_mgr.handler_mgr = SimpleNamespace(delete_object=delete_object_error)
    assert file_mgr.delete(lock, "work:full") == 216


def dos_filemanager_create_protect_test():
    calls = []

    def create_dir(path, cwd=None):
        calls.append(("dir", path, cwd))

    def set_protect(path, mask, cwd=None):
        calls.append(("prot", path, mask, cwd))

    handler_mgr = SimpleNamespace(create_dir=create_dir, set_protect=set_protect)
    file_mgr = _make_file_mgr(handler_mgr)
    lock = SimpleNamespace(ami_path="work:")

    assert file_mgr.create_dir(lock, "work:d") == 0
    assert file_mgr.set_protection(lock, "work:f", 0) == 0
    assert calls == [
        ("dir", "work:d", "work:"),
        ("prot", "work:f", 0, "work:"),
    ]

    def create_dir_error(path, cwd=None):
        raise HandlerError(203)

    file_mgr.handler_mgr = SimpleNamespace(create_dir=create_dir_error)
    assert file_mgr.create_dir(lock, "work:d") == 203


def dos_filemanager_is_file_system_test():
    devices = ("nil", "console", "notfs")

    def is_filesystem(name):
        return name.lower() not in devices

    handler_mgr = SimpleNamespace(is_filesystem=is_filesystem)
    file_mgr = _make_file_mgr(handler_mgr)

    assert file_mgr.is_file_system(None, "NIL:") is False
    assert file_mgr.is_file_system(None, "CONSOLE:") is False
    assert file_mgr.is_file_system(None, "*") is False
    assert file_mgr.is_file_system(None, "notfs:") is False
    assert file_mgr.is_file_system(None, "work:") is True


def dos_filemanager_open_nil_test():
    from amitools.vamos.handler import NilHandler

    nil = NilHandler("nil")
    handler_mgr = SimpleNamespace(
        find_input=lambda path, cwd=None: (nil, nil.find_input(path)),
    )
    file_mgr = _make_file_mgr(handler_mgr)

    fh = file_mgr.open(None, "NIL:", "r")

    assert fh.is_nil is True
    assert fh.handler is nil
    assert fh.read(10) == b""


def dos_filemanager_open_console_test():
    import sys

    from amitools.vamos.handler import ConsoleHandler

    console = ConsoleHandler("console")
    calls = []

    def find_output(path, mode=MODE_NEWFILE, cwd=None):
        calls.append((path, mode))
        return console, console.find_output(path, mode)

    handler_mgr = SimpleNamespace(find_output=find_output)
    file_mgr = _make_file_mgr(handler_mgr)

    # '*' is an alias for the console device
    fh = file_mgr.open(None, "*", "rw")

    assert calls == [("console:", MODE_READWRITE)]
    assert fh.obj.obj is sys.stdout.buffer
    assert fh.obj.direction == "out"
    assert fh.need_close is False
    assert fh.auto_flush is True
    assert fh.is_nil is False


def dos_filemanager_console_redirect_test():
    from amitools.vamos.handler import ConsoleHandler

    console = ConsoleHandler("console")

    def find_input(path, cwd=None):
        return console, console.find_input(path)

    def find_output(path, mode=MODE_NEWFILE, cwd=None):
        return console, console.find_output(path, mode)

    handler_mgr = SimpleNamespace(find_input=find_input, find_output=find_output)
    file_mgr = _make_file_mgr(handler_mgr)
    # build the default console handles and register them manually
    file_mgr.std_input = file_mgr._create_stdin_fh()
    file_mgr.std_output = file_mgr._create_stdout_fh()
    file_mgr.std_input.b_addr = 1
    file_mgr.std_output.b_addr = 2
    file_mgr.files_by_b_addr = {1: file_mgr.std_input, 2: file_mgr.std_output}

    # writing to the console input handle is redirected to the output handle
    assert file_mgr.get_by_b_addr(1, True) is file_mgr.std_output
    # reading from the console output handle is redirected to the input handle
    assert file_mgr.get_by_b_addr(2, False) is file_mgr.std_input
    # matching directions are not redirected
    assert file_mgr.get_by_b_addr(2, True) is file_mgr.std_output
    assert file_mgr.get_by_b_addr(1, False) is file_mgr.std_input


# ----- handler-file wrapping / OpenFromLock (step 12d) -----


def _make_real_file_mgr(handler_mgr=None):
    """A FileManager with a real allocator, so files register for real."""
    mem = MockMemory(size_kib=64)
    alloc = MemoryAlloc(mem)
    file_mgr = FileManager.__new__(FileManager)
    file_mgr.handler_mgr = handler_mgr
    file_mgr.alloc = alloc
    file_mgr.mem = mem
    file_mgr.fs_handler_port = 0
    file_mgr.files_by_b_addr = {}
    file_mgr.std_input = None
    file_mgr.std_output = None
    return file_mgr


def _make_lock(handler, handler_lock, ami_path="work:file.txt", name="file.txt"):
    return SimpleNamespace(
        handler=handler,
        handler_lock=handler_lock,
        ami_path=ami_path,
        name=name,
    )


def dos_filemanager_wrap_handler_file_test():
    handler = _make_handler()
    handler_file = _make_handler_file()
    file_mgr = _make_real_file_mgr()

    fh = file_mgr.wrap_handler_file(handler, handler_file, "work:file.txt")

    # the handle is registered under its own b_addr and reachable again
    assert fh.b_addr != 0
    assert file_mgr.get_by_b_addr(fh.b_addr) is fh
    assert fh.name == "file.txt"
    assert fh.ami_path == "work:file.txt"
    assert fh.handler is handler
    assert fh.handler_file is handler_file
    assert fh.obj is handler_file.fobj
    assert fh.need_close is handler_file.need_close


def dos_filemanager_wrap_handler_file_explicit_name_test():
    file_mgr = _make_real_file_mgr()

    fh = file_mgr.wrap_handler_file(
        _make_handler(), _make_handler_file(), "work:d/x", name="x"
    )

    assert fh.name == "x"
    assert fh.ami_path == "work:d/x"


def dos_filemanager_open_from_lock_test():
    handler_file = _make_handler_file()
    calls = []

    def fh_from_lock(handler_lock, mode=MODE_OLDFILE):
        calls.append((handler_lock, mode))
        return handler_file

    handler = SimpleNamespace(fh_from_lock=fh_from_lock)
    file_mgr = _make_real_file_mgr()
    handler_lock = object()
    lock = _make_lock(handler, handler_lock, "work:file.txt", "file.txt")

    fh = file_mgr.open_from_lock(lock)

    assert calls == [(handler_lock, MODE_OLDFILE)]
    assert fh.handler is handler
    assert fh.handler_file is handler_file
    assert fh.name == "file.txt"
    assert fh.ami_path == "work:file.txt"
    assert file_mgr.get_by_b_addr(fh.b_addr) is fh


def dos_filemanager_open_from_lock_mode_test():
    modes = []
    handler = SimpleNamespace(
        fh_from_lock=lambda handler_lock, mode: (
            modes.append(mode) or _make_handler_file()
        )
    )
    file_mgr = _make_real_file_mgr()

    file_mgr.open_from_lock(_make_lock(handler, object()), MODE_READWRITE)

    assert modes == [MODE_READWRITE]


def dos_filemanager_open_from_lock_error_test():
    def fh_from_lock(handler_lock, mode=MODE_OLDFILE):
        raise HandlerError(212)

    handler = SimpleNamespace(fh_from_lock=fh_from_lock)
    file_mgr = _make_real_file_mgr()
    lock = _make_lock(handler, object())

    with pytest.raises(HandlerError) as exc:
        file_mgr.open_from_lock(lock)
    assert exc.value.code == 212


def dos_filemanager_open_from_lock_no_handler_test():
    file_mgr = _make_real_file_mgr()
    lock = SimpleNamespace(handler=None, handler_lock=None, ami_path="work:f", name="f")

    with pytest.raises(HandlerError) as exc:
        file_mgr.open_from_lock(lock)
    assert exc.value.code == 205
