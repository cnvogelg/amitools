from amitools.vamos.astructs import CSTR
from amitools.vamos.error import VamosInternalError
from amitools.vamos.libstructs import IORequestStruct, NodeType
from amitools.vamos.libtypes import MsgPort
from amitools.vamos.log import log_exec

from .funcbase import FuncBaseMixin


class DeviceMixin(FuncBaseMixin):
    """exec.library device/IO LVOs (fd banner: devices)."""

    def CreateIORequest(self, ctx, port: MsgPort, size):
        # label alloc
        pc = self.get_callee_pc(ctx)
        name = "CreateIORequest(%06x)" % pc
        mb = self.alloc.alloc_memory(size, label=name)
        ctx.mem.w_block(mb.addr, b"\x00" * size)
        io = IORequestStruct(ctx.mem, mb.addr)
        io.message.reply_port.aptr = port.addr if port else 0
        io.message.length.val = size
        io.flags.val = 0
        io.error.val = 0
        log_exec.info(
            "CreateIORequest: (%s,%s,%s) -> 0x%06x %d bytes"
            % (mb, port.addr if port else 0, size, mb.addr, size)
        )
        return mb.addr

    def DeleteIORequest(self, ctx, iorequest):
        mb = self.alloc.get_memory(iorequest)
        if mb is not None:
            log_exec.info("DeleteIOREquest: 0x%06x -> %s" % (iorequest, mb))
            self.alloc.free_memory(mb)
        else:
            raise VamosInternalError(
                "DeleteIORequest: Unknown IORequest to delete: ptr=%06x" % iorequest
            )

    def OpenDevice(self, ctx, dev_name: CSTR, unit, io_request, flags):
        io = IORequestStruct(ctx.mem, io_request)
        io.error.val = -1
        io.unit.aptr = 0
        name = dev_name.str
        addr = self.lib_mgr.open_lib(name)
        io.device.aptr = addr
        if addr == 0:
            log_exec.info(
                "OpenDevice: '%s' unit %d flags %d -> NULL", name, unit, flags
            )
            return -1
        else:
            vlib = self.lib_mgr.get_vlib_by_addr(addr)
            impl = vlib.get_impl() if vlib is not None else None
            open_dev = getattr(impl, "open_dev", None)
            if open_dev is not None:
                try:
                    error = open_dev(ctx, io_request, unit, flags)
                except Exception:
                    io.device.aptr = 0
                    io.unit.aptr = 0
                    self.lib_mgr.close_lib(addr)
                    raise
                if error:
                    io.error.val = error
                    io.device.aptr = 0
                    io.unit.aptr = 0
                    self.lib_mgr.close_lib(addr)
                    log_exec.info(
                        "OpenDevice: '%s' unit %d flags %d -> error %d",
                        name,
                        unit,
                        flags,
                        error,
                    )
                    return io.error.val
            io.error.val = 0
            log_exec.info(
                "OpenDevice: '%s' unit %d flags %d -> %06x", name, unit, flags, addr
            )
            return 0

    def CloseDevice(self, ctx, io_request):
        if io_request != 0:
            io = IORequestStruct(ctx.mem, io_request)
            dev_addr = io.device.aptr
            if dev_addr != 0:
                log_exec.info("CloseDevice: %06x", dev_addr)
                vlib = self.lib_mgr.get_vlib_by_addr(dev_addr)
                impl = vlib.get_impl() if vlib is not None else None
                close_dev = getattr(impl, "close_dev", None)
                try:
                    if close_dev is not None:
                        close_dev(ctx, io_request)
                finally:
                    self.lib_mgr.close_lib(dev_addr)
                    io.device.aptr = 0

    def _dispatch_begin_io(self, ctx, io_request):
        mem = ctx.mem
        dev_addr = mem.r32(io_request + self._io_device_off)
        vlib = self.lib_mgr.get_vlib_by_addr(dev_addr)
        if vlib is None:
            log_exec.warning(
                "DoIO: missing device for io=0x%06x dev=0x%06x",
                io_request,
                dev_addr,
            )
            return -1
        impl = vlib.get_impl()
        if hasattr(impl, "BeginIO"):
            flags = mem.r8(io_request + self._io_flags_off) | 1
            mem.w8(io_request + self._io_flags_off, flags)
            impl.BeginIO(ctx, io_request)
            flags = mem.r8(io_request + self._io_flags_off)
            if flags & 1:
                mem.w8(io_request + self._io_node_type_off, NodeType.NT_REPLYMSG)
            return mem.r8s(io_request + self._io_error_off)
        log_exec.warning("DoIO: device impl missing BeginIO for dev=0x%06x", dev_addr)
        return -1

    def DoIO(self, ctx, io_request):
        res = self._dispatch_begin_io(ctx, io_request)
        log_exec.info("DoIO(io=0x%06x) -> %d", io_request, res)
        return res

    def AbortIO(self, ctx, io_request):
        io = IORequestStruct(ctx.mem, io_request)
        dev_addr = io.device.aptr
        vlib = self.lib_mgr.get_vlib_by_addr(dev_addr)
        impl = vlib.get_impl() if vlib is not None else None
        abort_io = getattr(impl, "AbortIO", None)
        if abort_io is None:
            log_exec.warning(
                "AbortIO: missing device for io=0x%06x dev=0x%06x",
                io_request,
                dev_addr,
            )
            return -1
        result = abort_io(ctx, io_request)
        result = 0 if result is None else result
        log_exec.info("AbortIO(io=0x%06x) -> %d", io_request, result)
        return result

    def SendIO(self, ctx, io_request):
        res = self._dispatch_begin_io(ctx, io_request)
        log_exec.info("SendIO(io=0x%06x) -> %d", io_request, res)
        mem = ctx.mem
        if not (mem.r8(io_request + self._io_flags_off) & 1):
            log_exec.info("SendIO: IO held (IOF_QUICK cleared), no reply queued")
            return res
        reply_port = mem.r32(io_request + self._io_reply_port_off)
        if reply_port != 0:
            if not self.port_mgr.has_port(reply_port):
                self.port_mgr.register_port(reply_port)
                log_exec.info("SendIO: auto-registered reply_port=0x%06x", reply_port)
            self.port_mgr.put_msg(reply_port, io_request)
            try:
                list_addr = reply_port + self._msg_port_list_off
                lh_tail_field = list_addr + 4
                old_tailpred = mem.r32(list_addr + 8)
                mem.w32(io_request + 0, lh_tail_field)
                mem.w32(io_request + 4, old_tailpred)
                mem.w32(old_tailpred + 0, io_request)
                mem.w32(list_addr + 8, io_request)
            except Exception:
                pass
            try:
                sigbit = mem.r8(reply_port + self._msg_port_sigbit_off)
                if 0 <= sigbit < 32:
                    sig_task = mem.r32(reply_port + self._msg_port_sigtask_off)
                    if sig_task != 0:
                        self.signal(sig_task, 1 << sigbit)
            except Exception:
                pass
            log_exec.info("SendIO: queued reply to port 0x%06x", reply_port)
        return res

    def CheckIO(self, ctx, io_request):
        log_exec.info("CheckIO(io=0x%06x)", io_request)
        return io_request if (ctx.mem.r8(io_request + self._io_flags_off) & 1) else 0

    def WaitIO(self, ctx, io_request):
        log_exec.info("WaitIO(io=0x%06x)", io_request)
        mem = ctx.mem
        reply_port = mem.r32(io_request + self._io_reply_port_off)
        if reply_port != 0 and self.port_mgr.has_port(reply_port):
            port = self.port_mgr.ports[reply_port]
            if port.queue is not None and io_request in port.queue:
                port.queue.remove(io_request)
            try:
                ln_succ = mem.r32(io_request + 0)
                ln_pred = mem.r32(io_request + 4)
                if ln_succ != 0 and ln_pred != 0:
                    mem.w32(ln_pred + 0, ln_succ)
                    mem.w32(ln_succ + 4, ln_pred)
            except Exception:
                pass
        return mem.r8s(io_request + self._io_error_off)
