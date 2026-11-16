import io
from types import SimpleNamespace

from amitools.vamos.handler import (
    HandlerError,
    MODE_NEWFILE,
    MODE_OLDFILE,
    MODE_READWRITE,
)
from amitools.vamos.lib.dos.Error import DOSFALSE, ERROR_ACTION_NOT_KNOWN
from amitools.vamos.lib.dos.FileManager import FileManager
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import DosPacketStruct, MessageStruct
from amitools.vamos.machine.mock import MockMemory


def dos_filemanager_unsupported_filesys_packet_test():
    mem = MockMemory()
    msg_addr = 0x100
    dos_pkt_addr = 0x200
    reply_port_addr = 0x300
    msg = MessageStruct(mem, msg_addr)
    msg.node.name.aptr = dos_pkt_addr
    dos_pkt = DosPacketStruct(mem, dos_pkt_addr)
    dos_pkt.port.aptr = reply_port_addr
    dos_pkt.type.val = DosAction.ACTION_DISK_INFO

    registered_ports = []
    replies = []
    port_mgr = SimpleNamespace(
        has_port=lambda addr: False,
        register_port=registered_ports.append,
        put_msg=lambda port_addr, addr: replies.append((port_addr, msg_addr)),
    )
    file_mgr = FileManager.__new__(FileManager)
    file_mgr.mem = mem

    file_mgr.fs_put_msg(port_mgr, msg_addr)

    assert dos_pkt.res1.val == DOSFALSE
    assert dos_pkt.res2.val == ERROR_ACTION_NOT_KNOWN
    assert registered_ports == [reply_port_addr]
    assert replies == [(reply_port_addr, msg_addr)]


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
    return SimpleNamespace(fobj=io.BytesIO(data))


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
    handler_mgr = SimpleNamespace(
        is_filesystem=lambda name: name != "notfs",
    )
    file_mgr = _make_file_mgr(handler_mgr)

    assert file_mgr.is_file_system(None, "NIL:") is False
    assert file_mgr.is_file_system(None, "CONSOLE:") is False
    assert file_mgr.is_file_system(None, "*") is False
    assert file_mgr.is_file_system(None, "notfs:") is False
    assert file_mgr.is_file_system(None, "work:") is True
