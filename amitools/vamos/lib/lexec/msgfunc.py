import logging

from amitools.vamos.astructs import CSTR
from amitools.vamos.libstructs import (
    NodeType,
    MsgPortFlags,
    MsgPortStruct,
    MessageStruct,
    NodeStruct,
)
from amitools.vamos.libtypes import MsgPort, Message
from amitools.vamos.libtypes.list_ import list_add_tail, list_first, list_rem_head
from amitools.vamos.log import log_exec

from .funcbase import FuncBaseMixin


def _offset(struct, name):
    return struct.sdef.find_field_def_by_name(name).offset


# messages pass for every packet and I/O request: read and write their
# fields directly instead of through struct wrappers
_LN_TYPE = _offset(MessageStruct, "mn_Node") + _offset(NodeStruct, "ln_Type")
_MP_FLAGS = _offset(MsgPortStruct, "mp_Flags")
_MP_SIGBIT = _offset(MsgPortStruct, "mp_SigBit")
_MP_SIGTASK = _offset(MsgPortStruct, "mp_SigTask")
# mp_SoftInt shares mp_SigTask's storage (a union in exec/ports.h)
_MP_SOFTINT = _MP_SIGTASK
_MP_MSGLIST = _offset(MsgPortStruct, "mp_MsgList")


class MessageMixin(FuncBaseMixin):
    """exec.library message/port LVOs (fd banner: messages)."""

    def PutMsg(self, ctx, port: MsgPort, msg: Message):
        return self.put_msg(port, msg)

    def GetMsg(self, ctx, port: MsgPort) -> Message:
        return self.get_msg(port)

    def CreateMsgPort(self, ctx) -> MsgPort:
        return self.create_msg_port()

    def DeleteMsgPort(self, ctx, msg_port: MsgPort):
        return self.delete_msg_port(msg_port)

    def WaitPort(self, ctx, msg_port: MsgPort) -> Message:
        return self.wait_port(msg_port)

    def AddPort(self, ctx, msg_port: MsgPort):
        return self.add_port(msg_port)

    def RemPort(self, ctx, msg_port: MsgPort):
        return self.rem_port(msg_port)

    def FindPort(self, ctx, name: CSTR) -> MsgPort:
        return self.find_port(name)

    def ReplyMsg(self, ctx, msg: Message):
        return self.reply_msg(msg)

    # ----- internal -----

    def create_msg_port(self) -> MsgPort:
        # alloc signal first
        signal = self.alloc_signal(-1)
        if signal == -1:
            log_exec.error("CreateMsgPort: no signal!")
            return None

        # get my task
        my_task = self.find_task(None)

        # alloc port
        memory = self.ctx.alloc.alloc_memory(
            MsgPort.get_size(), label="exec_port", except_on_failure=False
        )
        if memory is None:
            self.free_signal(signal)
            return None
        msg_port = MsgPort(self.ctx.mem, memory.addr)
        msg_port.new(sig_bit=signal, sig_task=my_task)
        log_exec.info(
            "CreateMsgPort: -> signal=%d my_task=%s port=%s", signal, my_task, msg_port
        )

        # dump msg port structure
        if log_exec.isEnabledFor(logging.DEBUG):
            msg_port.dump(log_exec.debug)

        return msg_port

    def delete_msg_port(self, msg_port: MsgPort):
        # get signal
        signal = msg_port.sig_bit.val
        log_exec.info("DeleteMsgPort(%s) (signal %d)", msg_port, signal)

        # free signal if not allocated
        if signal > 15:
            self.free_signal(signal)

        # free port
        msg_port.free(self.ctx.alloc)

    def put_msg(self, port: MsgPort, msg: Message, msg_type=NodeType.NT_MESSAGE):
        # NULL port: can't queue message
        if port is None or port.addr == 0:
            log_exec.warning("PutMsg: port is NULL, msg=%s", msg)
            return

        mem = self.ctx.mem
        port_addr = port.addr
        msg_addr = msg.addr
        # check legacy port manager first
        has_port = self.port_mgr.has_port(port_addr)
        if has_port:
            log_exec.info("PutMsg(%s, %s) -> PortMgr", port, msg)
            mem.w8(msg_addr + _LN_TYPE, msg_type)
            self.port_mgr.put_msg(port_addr, msg_addr)
            if self.port_mgr.has_port(port_addr):
                self._signal_port(port)
            return

        # set type
        mem.w8(msg_addr + _LN_TYPE, msg_type)

        # add to port list
        log_exec.info("PutMsg(%s, %s)", port, msg)
        list_add_tail(mem, port_addr + _MP_MSGLIST, msg_addr)

        self.notify_port(port_addr)

    def notify_port(self, port_addr):
        """Tell a port's owner a message arrived, as PutMsg() does after
        queueing it: signal mp_SigTask (PA_SIGNAL), Cause() mp_SoftInt
        (PA_SOFTINT) or nothing (PA_IGNORE)."""
        mem = self.ctx.mem
        flags = mem.r8(port_addr + _MP_FLAGS)
        if flags == MsgPortFlags.PA_SIGNAL:
            # post signal
            task = mem.r32(port_addr + _MP_SIGTASK)
            if task == 0:
                log_exec.error("PutMsg: No task to signal?")
            else:
                sig_bit = mem.r8(port_addr + _MP_SIGBIT)
                sig_mask = 1 << sig_bit
                log_exec.debug("PutMsg: set signal %s task %08x", sig_bit, task)
                self.signal(task, sig_mask)
        elif flags == MsgPortFlags.PA_SOFTINT:
            intr = mem.r32(port_addr + _MP_SOFTINT)
            if intr == 0:
                log_exec.error("PutMsg: PA_SOFTINT port without mp_SoftInt")
            elif self.soft_int is None:
                log_exec.error("PutMsg: no software interrupts, PA_SOFTINT ignored")
            else:
                log_exec.debug("PutMsg: cause soft int %08x", intr)
                self.soft_int.cause(intr)
        elif flags == MsgPortFlags.PA_IGNORE:
            log_exec.debug("PutMsg: no notify")
        else:
            log_exec.error("PutMsg: unknown MsgPortFlags: %s", flags)

    def get_msg(self, port: MsgPort) -> Message:
        # check legacy port manager first
        has_port = self.port_mgr.has_port(port.addr)
        if has_port:
            msg_addr = self.port_mgr.get_msg(port.addr)
            if msg_addr is None:
                log_exec.info("GetMsg(%s) -> PortMgr -> None", port)
                return None
            msg = Message(self.ctx.mem, msg_addr)
            self._unlink_msg(msg_addr)
            log_exec.info("GetMsg(%s) -> PortMgr -> %s", port, msg)
            return msg

        # get message
        msg_addr = list_rem_head(self.ctx.mem, port.addr + _MP_MSGLIST)
        if msg_addr == 0:
            log_exec.info("GetMsg(%s) -> None", port)
            return None
        msg = Message(self.ctx.mem, msg_addr)
        log_exec.info("GetMsg(%s) -> %s", port, msg)
        return msg

    def wait_port(self, port: MsgPort) -> Message:
        # get sig mask
        mem = self.ctx.mem
        sig_bit = mem.r8(port.addr + _MP_SIGBIT)
        sig_mask = 1 << sig_bit
        list_addr = port.addr + _MP_MSGLIST

        log_exec.info("WaitPort: port=%s", port)
        while True:
            # a port the Python port manager owns (it was AddPort'ed): peek its
            # queue. a plain message port: check the exec message list.
            if self.port_mgr.has_port(port.addr):
                msg_addr = self.port_mgr.peek_msg(port.addr)
                if msg_addr is not None:
                    log_exec.info("WaitPort: peek message %06x", msg_addr)
                    return Message(mem, msg_addr)
            else:
                msg_addr = list_first(mem, list_addr)
                if msg_addr != 0:
                    msg = Message(mem, msg_addr)
                    log_exec.info("WaitPort: return msg %s", msg)
                    return msg
            # empty queue: block on the port's signal until a message is
            # delivered (PutMsg signals the port's task)
            log_exec.debug("WaitPort: waiting for signal %s", sig_bit)
            self.wait(sig_mask)

    def add_port(self, port: MsgPort):
        log_exec.info("AddPort(%s)", port)
        if not self.port_mgr.has_port(port.addr):
            self.port_mgr.register_port(port.addr)
        # set port type
        port.node.type.val = NodeType.NT_MSGPORT
        # enqueue
        self.exec_lib.port_list.enqueue(port.node)

    def rem_port(self, port: MsgPort):
        log_exec.info("RemPort(%s)", port)
        if self.port_mgr.has_port(port.addr):
            self.port_mgr.unregister_port(port.addr)
        # remove node
        port.node.remove()

    def find_port(self, name: CSTR) -> MsgPort:
        # find port by name in port list
        port_name = name.str
        port = self.exec_lib.port_list.find_name(port_name, promote=True)
        log_exec.info("FindPort(%s) -> %s", port_name, port)
        return port

    def reply_msg(self, msg: Message):
        port = msg.reply_port.ref
        log_exec.info("ReplyPort(%s) -> port %s", msg, port)
        if port is None:
            msg.node.type.val = NodeType.NT_FREEMSG
        else:
            self.put_msg(port, msg, msg_type=NodeType.NT_REPLYMSG)

    def _signal_port(self, port: MsgPort):
        self.notify_port(port.addr)

    def _unlink_msg(self, msg_addr):
        try:
            ln_succ = self.ctx.mem.r32(msg_addr + 0)
            ln_pred = self.ctx.mem.r32(msg_addr + 4)
            if ln_succ != 0 and ln_pred != 0:
                self.ctx.mem.w32(ln_pred + 0, ln_succ)
                self.ctx.mem.w32(ln_succ + 4, ln_pred)
        except Exception:
            pass
