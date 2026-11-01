from types import SimpleNamespace

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
        put_msg=lambda port_addr, addr: replies.append((port_addr, addr)),
    )
    file_mgr = FileManager.__new__(FileManager)
    file_mgr.mem = mem

    file_mgr.fs_put_msg(port_mgr, msg_addr)

    assert dos_pkt.res1.val == DOSFALSE
    assert dos_pkt.res2.val == ERROR_ACTION_NOT_KNOWN
    assert registered_ports == [reply_port_addr]
    assert replies == [(reply_port_addr, msg_addr)]
