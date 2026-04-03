import logging
from .funcbase import FuncBase
from amitools.vamos.log import log_exec
from amitools.vamos.libtypes import MsgPort, Message
from amitools.vamos.libstructs import NodeType, MsgPortFlags
from amitools.vamos.astructs import CSTR
from amitools.vamos.error import UnsupportedFeatureError
from amitools.vamos.machine.regs import REG_A7


class MessageFunc(FuncBase):
    def __init__(self, ctx, exec_lib, signal_func, task_func, port_mgr):
        super().__init__(ctx, exec_lib)
        self.signal_func = signal_func
        self.task_func = task_func
        # legacy port mgr
        self.port_mgr = port_mgr

    def create_msg_port(self) -> MsgPort:
        # get my task
        my_task = self.task_func.find_task(None)

        # In amifuse's single-task fallback mode there is no scheduler-backed
        # signal allocation. Handlers like CDFileSystem expect CreateMsgPort()
        # to yield a port using signal bit 0, matching the historical
        # port-handler-support behavior.
        if self.signal_func.get_my_sched_task() is None:
            msg_port = MsgPort.alloc(self.ctx.alloc, tag="exec_port")
            msg_port.new(sig_bit=0, sig_task=my_task)
            log_exec.info(
                "CreateMsgPort: fallback signal=0 my_task=%s port=%s",
                my_task,
                msg_port,
            )
            return msg_port

        # alloc signal first
        signal = self.signal_func.alloc_signal(-1)
        if signal == -1:
            log_exec.error("CreateMsgPort: no signal!")
            return None

        # alloc port
        msg_port = MsgPort.alloc(self.ctx.alloc, tag="exec_port")
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

        # free signal
        if not (
            self.signal_func.get_my_sched_task() is None and 0 <= signal < 16
        ):
            self.signal_func.free_signal(signal)

        # free port
        msg_port.free(self.ctx.alloc)

    def put_msg(self, port: MsgPort, msg: Message, msg_type=NodeType.NT_MESSAGE):
        # check legacy port manager first
        has_port = self.port_mgr.has_port(port.addr)
        if has_port:
            log_exec.info("PutMsg(%s, %s) -> PortMgr", port, msg)
            msg.node.type.val = msg_type
            self.port_mgr.put_msg(port.addr, msg.addr)
            self._signal_port(port)
            return

        # set type
        msg.node.type.val = msg_type

        # add to port list
        log_exec.info("PutMsg(%s, %s)", port, msg)
        port.msg_list.add_tail(msg.node)

        # signal?
        flags = port.flags.val
        if flags == MsgPortFlags.PA_SIGNAL:
            # post signal
            task = port.sig_task.aptr
            if task is None:
                log_exec.error("PutMsg: No task to signal?")
            else:
                sig_bit = port.sig_bit.val
                sig_mask = 1 << sig_bit
                log_exec.debug("PutMsg: set signal %s task %08x", sig_bit, task)
                self.signal_func.signal(task, sig_mask)
        elif flags == MsgPortFlags.PA_SOFTINT:
            log_exec.error("PutMsg: PA_SOFTINT is ignored!")
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

        # get message list
        msg_list = port.msg_list

        # no messages
        if msg_list.is_empty():
            log_exec.info("GetMsg(%s) -> None", port)
            return None

        # get message
        msg = port.msg_list.rem_head(promote=True)
        log_exec.info("GetMsg(%s) -> %s", port, msg)
        return msg

    def wait_port(self, port: MsgPort) -> Message:
        # check port mgr first
        has_port = self.port_mgr.has_port(port.addr)
        if has_port:
            has_msg = self.port_mgr.has_msg(port.addr)
            if not has_msg:
                from amitools.vamos.lib.ExecLibrary import ExecLibrary

                sp = self.ctx.cpu.r_reg(REG_A7)
                ExecLibrary._waitport_blocked_sp = sp
                ExecLibrary._waitport_blocked_port = port.addr
                ExecLibrary._waitport_blocked_ret = self.ctx.mem.r32(sp)
                raise UnsupportedFeatureError(
                    "WaitPort on empty message queue called: Port (%06x)" % port.addr
                )
            msg_addr = self.port_mgr.peek_msg(port.addr)
            log_exec.info("WaitPort: peek message %06x", msg_addr)
            return Message(self.ctx.mem, msg_addr)

        # get sig mask
        sig_bit = port.sig_bit.val
        sig_mask = 1 << sig_bit
        msg_list = port.msg_list

        log_exec.info("WaitPort: port=%s", port)
        while msg_list.is_empty():
            log_exec.debug("WaitPort: waiting for signal %s", sig_bit)
            self.signal_func.wait(sig_mask)

        msg = msg_list.get_head().cast(Message)
        log_exec.info("WaitPort: return msg %s", msg)
        return msg

    def add_port(self, port: MsgPort):
        log_exec.info("AddPort(%s)", port)
        # set port type
        port.node.type.val = NodeType.NT_MSGPORT
        # enqueue
        self.exec_lib.port_list.enqueue(port.node)

    def rem_port(self, port: MsgPort):
        log_exec.info("RemPort(%s)", port)
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
        try:
            flags = port.flags.val
            if flags == MsgPortFlags.PA_SIGNAL:
                task = port.sig_task.aptr
                if task is not None:
                    sig_bit = port.sig_bit.val
                    self.signal_func.signal(task, 1 << sig_bit)
        except Exception:
            pass

    def _unlink_msg(self, msg_addr):
        try:
            ln_succ = self.ctx.mem.r32(msg_addr + 0)
            ln_pred = self.ctx.mem.r32(msg_addr + 4)
            if ln_succ != 0 and ln_pred != 0:
                self.ctx.mem.w32(ln_pred + 0, ln_succ)
                self.ctx.mem.w32(ln_succ + 4, ln_pred)
        except Exception:
            pass
