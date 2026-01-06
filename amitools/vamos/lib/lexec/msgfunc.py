import logging
from .funcbase import FuncBase
from amitools.vamos.log import log_exec
from amitools.vamos.libtypes import MsgPort, Message
from amitools.vamos.libstructs import NodeType, MsgPortFlags
from amitools.vamos.astructs import CSTR
from amitools.vamos.libstructs.exec_ import MsgPortStruct
from amitools.vamos.lib.intuition import IntuiMessageStruct


class MessageFunc(FuncBase):
    def __init__(self, ctx, exec_lib, signal_func, task_func, port_mgr):
        super().__init__(ctx, exec_lib)
        self.signal_func = signal_func
        self.task_func = task_func
        # legacy port mgr
        self.port_mgr = port_mgr

    def create_msg_port(self) -> MsgPort:
        # alloc signal first
        signal = self.signal_func.alloc_signal(-1)
        if signal == -1:
            log_exec.error("CreateMsgPort: no signal!")
            return None

        # get my task
        my_task = self.task_func.find_task(None)

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
        self.signal_func.free_signal(signal)

        # free port
        msg_port.free(self.ctx.alloc)

    def put_msg(self, port: MsgPort, msg: Message, msg_type=NodeType.NT_MESSAGE):
        # check legacy port manager first
        has_port = self.port_mgr.has_port(port.addr)
        if has_port:
            log_exec.info("PutMsg(%s, %s) -> PortMgr", port, msg)
            self.port_mgr.put_msg(port.addr, msg.addr)
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
            msg = Message(self.ctx.mem, msg_addr)
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
            if has_msg:
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
            if port.addr == 0xFFEDCB:
                # Intuition-only message, free it and stop.
                self.ctx.alloc.free_mem(msg.addr, IntuiMessageStruct.get_size())
                return 0

            self.put_msg(port, msg, msg_type=NodeType.NT_REPLYMSG)
