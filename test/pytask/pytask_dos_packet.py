import pytest

from amitools.vamos.error import UnsupportedFeatureError
from amitools.vamos.lib.dos.Error import (
    DOSFALSE,
    DOSTRUE,
    ERROR_NO_MORE_ENTRIES,
)
from amitools.vamos.lib.dos.action import DosAction
from amitools.vamos.libstructs import (
    DevProcStruct,
    DosPacketStruct,
    FileHandleStruct,
    InfoDataStruct,
    MessageStruct,
    ProcessStruct,
)
from amitools.vamos.libtypes import DosPacket, Message, MsgPort

MODE_OLDFILE = 1005
MODE_NEWFILE = 1006
# the handler API's ``seek`` uses Python whence (0 = start, 1 = current,
# 2 = end); the packet carries that value unchanged
SEEK_BEGINNING = 0


def _volume_handler_port(ctx, name):
    """the MsgPort of the handler serving a mounted volume"""
    entry = ctx.dos_lib.dos_list.get_entry_by_name(name)
    assert entry is not None, "volume not mounted: %s" % name
    port = entry.struct.dol_Task.aptr
    assert port != 0, "volume has no handler port: %s" % name
    return port


def pytask_dos_dopkt_file_test(vamos_task):
    """drive FINDINPUT/WRITE/SEEK/READ/END through the real handler port"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        port = _volume_handler_port(ctx, "ram")

        path = ctx.alloc.alloc_bstr("dos_pkt_test.txt")
        fh_mem = ctx.alloc.alloc_astruct(FileHandleStruct, label="FH")
        fh = FileHandleStruct(ctx.mem, fh_mem.addr)
        buf = ctx.alloc.alloc_memory(16, label="buf")

        # FINDOUTPUT creates the file and stores the DOS handle in fh_Args
        res = dos_proxy.DoPkt(
            port,
            DosAction.ACTION_FINDOUTPUT,
            fh_mem.addr >> 2,
            0,
            path.addr >> 2,
            MODE_NEWFILE,
            0,
        )
        assert res == DOSTRUE
        fh_b = fh.fh_Args.val
        assert fh_b != 0

        # WRITE
        ctx.mem.w_block(buf.addr, b"hello")
        assert (
            dos_proxy.DoPkt(port, DosAction.ACTION_WRITE, fh_b, buf.addr, 5, 0, 0) == 5
        )

        # SEEK back to the start, then READ the bytes back
        assert (
            dos_proxy.DoPkt(port, DosAction.ACTION_SEEK, fh_b, 0, SEEK_BEGINNING, 0, 0)
            == 0
        )
        ctx.mem.clear_block(buf.addr, 16, 0)
        assert (
            dos_proxy.DoPkt(port, DosAction.ACTION_READ, fh_b, buf.addr, 5, 0, 0) == 5
        )
        assert ctx.mem.r_block(buf.addr, 5) == b"hello"

        # END releases the handle
        assert dos_proxy.DoPkt(port, DosAction.ACTION_END, fh_b, 0, 0, 0, 0) == 0

        # FINDINPUT opens the file we just wrote
        assert (
            dos_proxy.DoPkt(
                port,
                DosAction.ACTION_FINDINPUT,
                fh_mem.addr >> 2,
                0,
                path.addr >> 2,
                MODE_OLDFILE,
                0,
            )
            == DOSTRUE
        )
        fh_b = fh.fh_Args.val
        ctx.mem.clear_block(buf.addr, 16, 0)
        assert (
            dos_proxy.DoPkt(port, DosAction.ACTION_READ, fh_b, buf.addr, 5, 0, 0) == 5
        )
        assert ctx.mem.r_block(buf.addr, 5) == b"hello"
        assert dos_proxy.DoPkt(port, DosAction.ACTION_END, fh_b, 0, 0, 0, 0) == 0

        ctx.alloc.free_memory(buf)
        ctx.alloc.free_struct(fh_mem)
        ctx.alloc.free_bstr(path)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_dopkt_disk_info_test(vamos_task):
    """a lock-less DISK_INFO packet is answered by the volume's handler"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        port = _volume_handler_port(ctx, "ram")
        info_mem = ctx.alloc.alloc_astruct(InfoDataStruct, label="InfoData")

        assert (
            dos_proxy.DoPkt(
                port, DosAction.ACTION_DISK_INFO, info_mem.addr >> 2, 0, 0, 0, 0
            )
            == DOSTRUE
        )
        info = InfoDataStruct(ctx.mem, info_mem.addr)
        assert info.id_NumBlocks.val > 0

        ctx.alloc.free_struct(info_mem)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_getdevproc_test(vamos_task):
    """GetDeviceProc reports the volume's own handler port (like AmigaDOS)"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        ram_port = _volume_handler_port(ctx, "ram")

        # the DevProc's packet port is the ram handler's port
        # (GetDeviceProc takes a C string, not a BSTR)
        name = ctx.alloc.alloc_cstr("ram:")
        devproc = dos_proxy.GetDeviceProc(name.addr, 0)
        assert devproc != 0
        assert DevProcStruct(ctx.mem, devproc).dvp_Port.aptr == ram_port
        dos_proxy.FreeDeviceProc(devproc)

        # a file opened on ram: carries the same handler port in fh_Type
        path = ctx.alloc.alloc_bstr("ram:devproc.txt")
        fh_mem = ctx.alloc.alloc_astruct(FileHandleStruct, label="FH")
        fh = FileHandleStruct(ctx.mem, fh_mem.addr)
        assert (
            dos_proxy.DoPkt(
                ram_port,
                DosAction.ACTION_FINDOUTPUT,
                fh_mem.addr >> 2,
                0,
                path.addr >> 2,
                MODE_NEWFILE,
                0,
            )
            == DOSTRUE
        )
        fh_b = fh.fh_Args.val
        dos_fh = ctx.dos_lib.file_mgr.get_by_b_addr(fh_b)
        assert dos_fh.struct.fh_Type.aptr == ram_port
        assert dos_proxy.DoPkt(ram_port, DosAction.ACTION_END, fh_b, 0, 0, 0, 0) == 0

        ctx.alloc.free_struct(fh_mem)
        ctx.alloc.free_bstr(path)
        ctx.alloc.free_cstr(name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_getdevproc_enum_test(vamos_task):
    """GetDeviceProc("*") walks the DOS device list and fills each DevProc"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        dos_list = ctx.dos_lib.dos_list
        star = ctx.alloc.alloc_cstr("*")

        names = []
        devproc = 0
        while True:
            devproc = dos_proxy.GetDeviceProc(star.addr, devproc)
            if devproc == 0:
                break
            dp = DevProcStruct(ctx.mem, devproc)
            # every device is reachable and owns a root lock
            assert dp.dvp_Port.aptr != 0
            assert dp.dvp_Lock.aptr != 0
            assert dp.dvp_Flags.val & ctx.dos_lib.DVPF_UNLOCK
            entry = dos_list.get_entry_by_b_addr(dp.dvp_DevNode.aptr >> 2)
            assert entry is not None
            names.append(entry.name)

        # the walk ends with ERROR_NO_MORE_ENTRIES
        assert dos_proxy.IoErr() == ERROR_NO_MORE_ENTRIES
        assert "nil" in names
        assert "console" in names
        assert "ram" in names

        ctx.alloc.free_cstr(star)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_getdevproc_lock_test(vamos_task):
    """GetDeviceProc fills dvp_Lock/dvp_Flags for devices and volumes"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        unlock = ctx.dos_lib.DVPF_UNLOCK

        # NIL:/CONSOLE: are devices without a DOS list lock, so the DevProc
        # owns a temporary root lock it has to unlock again; a volume hands
        # out its persistent DOS list root lock (no DVPF_UNLOCK)
        for name, owned in (("NIL:", True), ("CONSOLE:", True), ("ram:", False)):
            cname = ctx.alloc.alloc_cstr(name)
            devproc = dos_proxy.GetDeviceProc(cname.addr, 0)
            assert devproc != 0
            dp = DevProcStruct(ctx.mem, devproc)
            assert dp.dvp_Port.aptr != 0
            assert dp.dvp_Lock.aptr != 0
            assert dp.dvp_DevNode.aptr != 0
            assert bool(dp.dvp_Flags.val & unlock) is owned
            dos_proxy.FreeDeviceProc(devproc)
            ctx.alloc.free_cstr(cname)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_getdevproc_multi_assign_test(vamos_task):
    """a multi-directory assign sets DVPF_ASSIGN and iterates its dirs"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        dos_list = ctx.dos_lib.dos_list
        lock_mgr = ctx.dos_lib.lock_mgr

        # make ``multi:`` a two-directory assign (AssignLock is single-dir)
        assign_name = ctx.alloc.alloc_cstr("multi")
        first_lock = lock_mgr.create_lock(None, "ram:", False)
        assert dos_proxy.AssignLock(assign_name.addr, first_lock.b_addr) == DOSTRUE
        entry = dos_list.get_entry_by_name("multi")
        second_lock = lock_mgr.create_lock(None, "root:", False)
        entry.locks.append(second_lock)
        entry.assigns.append("root:")

        name = ctx.alloc.alloc_cstr("multi:")
        ports = []
        devproc = dos_proxy.GetDeviceProc(name.addr, 0)
        assert devproc != 0
        # first directory: DVPF_ASSIGN asks the caller to loop
        dp = DevProcStruct(ctx.mem, devproc)
        assert dp.dvp_Flags.val & ctx.dos_lib.DVPF_ASSIGN
        ports.append(dp.dvp_Port.aptr)
        # second directory (same DevProc, advanced in place)
        assert dos_proxy.GetDeviceProc(name.addr, devproc) == devproc
        dp = DevProcStruct(ctx.mem, devproc)
        assert dp.dvp_Flags.val & ctx.dos_lib.DVPF_ASSIGN
        ports.append(dp.dvp_Port.aptr)
        assert len(set(ports)) == 2
        # exhausted: NULL + ERROR_NO_MORE_ENTRIES (the DevProc is freed)
        assert dos_proxy.GetDeviceProc(name.addr, devproc) == 0
        assert dos_proxy.IoErr() == ERROR_NO_MORE_ENTRIES

        assert dos_proxy.AssignLock(assign_name.addr, 0) == DOSTRUE
        ctx.alloc.free_cstr(name)
        ctx.alloc.free_cstr(assign_name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_sendpkt_abortpkt_test(vamos_task):
    """SendPkt posts a packet and WaitPkt collects the handler's reply"""

    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()
        port = _volume_handler_port(ctx, "ram")

        # the reply is collected from the process's own port by WaitPkt
        proc_addr = ctx.process.proc.addr
        proc_port_addr = ProcessStruct(ctx.mem, proc_addr).msg_port.addr
        if not ctx.exec_lib.port_mgr.has_port(proc_port_addr):
            ctx.exec_lib.port_mgr.register_port(proc_port_addr)

        info_mem = ctx.alloc.alloc_astruct(InfoDataStruct, label="InfoData")
        msg = Message.alloc(ctx.alloc)
        pkt_mem = ctx.alloc.alloc_struct(DosPacketStruct, label="DosPacket")
        pkt = DosPacket(ctx.mem, pkt_mem.addr)
        pkt.link.ref = msg
        pkt.port.aptr = proc_port_addr
        msg_access = MessageStruct(ctx.mem, msg.addr)
        msg_access.node.name.aptr = pkt.addr
        pkt.type.val = DosAction.ACTION_DISK_INFO
        pkt.arg1.val = info_mem.addr >> 2

        dos_proxy.SendPkt(pkt, port, proc_port_addr)
        assert dos_proxy.WaitPkt() == pkt.addr
        assert pkt.res1.val == -1  # DOSTRUE as a signed LONG
        assert pkt.res2.val == 0

        # AbortPkt is a no-op that reports failure
        assert dos_proxy.AbortPkt(port, pkt.addr) == DOSFALSE

        ctx.alloc.free_struct(pkt_mem)
        msg.free()
        ctx.alloc.free_struct(info_mem)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]


def pytask_dos_waitpkt_replypkt_test(vamos_task):
    def proc(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        proc_addr = ctx.process.proc.addr
        proc_access = ProcessStruct(ctx.mem, proc_addr)
        proc_port_addr = proc_access.msg_port.addr
        proc_port = MsgPort(ctx.mem, proc_port_addr)
        if not ctx.exec_lib.port_mgr.has_port(proc_port_addr):
            ctx.exec_lib.port_mgr.register_port(proc_port_addr)

        with pytest.raises(UnsupportedFeatureError):
            dos_proxy.WaitPkt()

        reply_port = exec_proxy.CreateMsgPort()
        if not ctx.exec_lib.port_mgr.has_port(reply_port.addr):
            ctx.exec_lib.port_mgr.register_port(reply_port.addr)

        msg = Message.alloc(ctx.alloc)
        pkt_mem = ctx.alloc.alloc_struct(DosPacketStruct, label="DosPacket")
        pkt = DosPacket(ctx.mem, pkt_mem.addr)

        pkt.link.ref = msg
        pkt.port.ref = reply_port
        msg_access = MessageStruct(ctx.mem, msg.addr)
        msg_access.node.name.aptr = pkt.addr

        exec_proxy.PutMsg(proc_port, msg)
        assert dos_proxy.WaitPkt() == pkt.addr
        assert exec_proxy.GetMsg(proc_port) is None

        dos_proxy.ReplyPkt(pkt, 0xFFFFFFFF, 0x80000002)

        assert pkt.res1.val == -1
        assert pkt.res2.val == -2147483646
        assert pkt.port.aptr == proc_port_addr

        reply_msg = exec_proxy.GetMsg(reply_port)
        assert reply_msg == msg
        assert exec_proxy.GetMsg(reply_port) is None

        exec_proxy.DeleteMsgPort(reply_port)
        msg.free()
        ctx.alloc.free_struct(pkt_mem)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
