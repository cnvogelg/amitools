"""``NativeHandler``: a handler whose file system is an original 68k handler.

Unlike every other handler in vamos this one is not implemented in Python. It
is a *client* of a real AmigaDOS handler binary that runs as its own task in
the emulator. The handler API is unchanged: the base
:class:`~amitools.vamos.handler.dospkt.DosPktHandler` builds the ``DosPacket``
for every action and :meth:`NativeHandler._dopkt` transports it over the exec
message/signal layer to the running handler task.

The transport does not poke the exec structures by hand: it uses the real
exec.library functions (``CreateMsgPort``/``PutMsg``/``WaitPort``/``GetMsg``/
``DeleteMsgPort``) through the exec lib proxy. Those calls need a *current*
task (``AllocSignal`` allocates the reply port's signal, ``WaitPort`` blocks on
it), so the transport runs inside a scheduler task:

* a ``dos.library`` call made from an m68k program already runs inside a task,
  so the transport runs in that task's context;
* a Python-driven call (the startup handshake, ``ACTION_DIE``) runs in the main
  greenlet, so a small helper :class:`~amitools.vamos.task.ExecTask` carries it
  out and is added to the scheduler for the duration of the call.

A volume selects it with ``?handler=native&binary=<handler>``. Because a volume
is bound before ``exec.library`` exists, the handler is created *detached*: it
records the config and is attached to the live machine (and its started task)
by :class:`~amitools.vamos.handler.native.manager.NativeHandlerManager` once
the base libraries are open.
"""

from amitools.vamos.libstructs import MessageStruct
from amitools.vamos.schedule import TaskState
from amitools.vamos.task import ExecTask

from ..base import ERROR_NOT_IMPLEMENTED, HandlerError
from ..dospkt import DosPktHandler
from . import startup
from .config import NativeConfig


class _ReplyHolder:
    """carries the outcome of a transport run out of a helper task"""

    def __init__(self):
        self.done = False
        self.error = None


class NativeHandler(DosPktHandler):
    """handler-API client bound to a started 68k handler task"""

    # mark the handler so the packet dispatcher wiring leaves it alone: its
    # packets are served by the 68k task, not by a Python decoder
    is_native = True

    def __init__(self, name, cfg=None):
        super().__init__(name, is_filesystem=True)
        self.cfg = dict(cfg or {})
        # validate the volume options once (HANDLER.md 24a)
        self.config = NativeConfig(cfg)
        self.binary = self.config.binary
        # the started handler's port and the manager that owns it
        self.manager = None
        self.machine = None
        self.exec_lib = None
        self.scheduler = None
        self.max_cycles = None
        # a dispatcher shim that reports the handler's real packet port, so
        # GetDeviceProc/DeviceProc see the running task (see 23e); its presence
        # also makes HandlerManager.attach_dispatchers skip this handler
        self.dispatcher = _NativeDispatcher(self)

    # ----- attaching the live machine -----

    def attach_native(
        self,
        manager,
        machine,
        alloc,
        mem,
        port_mgr,
        exec_lib,
        scheduler,
        handler_port,
        max_cycles=None,
    ):
        """bind the handler to its started task and the live exec/dos"""
        self.manager = manager
        self.machine = machine
        self.alloc = alloc
        self.mem = mem
        self.port_mgr = port_mgr
        self.exec_lib = exec_lib
        self.scheduler = scheduler
        self.handler_port = handler_port
        self.max_cycles = max_cycles

    def shutdown(self):
        """ask the manager to stop the handler task"""
        if self.manager is not None:
            self.manager.stop(self)
        else:
            self.detach_native()

    def detach_native(self):
        """unbind from the manager (idempotent)"""
        self.manager = None
        self.exec_lib = None
        self.scheduler = None
        super().shutdown()

    # ----- transport hook -----

    def _call(self, action):
        if self.exec_lib is None:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "native transport not attached")
        return super()._call(action)

    def _dopkt(self, pkt):
        if self.exec_lib is None or self.handler_port == 0:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "native transport not attached")
        # only wait on the caller when we really run inside its task: the
        # scheduler keeps a task as "current" after it went idle, so use the
        # greenlet-based check (Python-driven calls run in the main greenlet)
        if self.scheduler.get_running_task() is not None:
            self._transport_pkt(pkt)
        else:
            self._transport_in_task(pkt)

    def _exec_proxy(self):
        """the exec.library proxy of the running exec instance"""
        return self.exec_lib.msg_func.ctx.proxies.get_exec_lib_proxy()

    def _transport_pkt(self, pkt):
        """send one packet with exec functions and copy the reply into ``pkt``

        Runs with a current task: ``CreateMsgPort`` allocates a signal on it
        and ``WaitPort`` blocks it until the handler replies. The reply is read
        back *before* the message is freed - a busy handler reuses the freed
        message memory, so copying afterwards would read garbage. The reply
        port is freed again (its signal included) before returning.
        """
        exec_lib = self._exec_proxy()
        reply_port = exec_lib.CreateMsgPort()
        if reply_port is None or reply_port.addr == 0:
            raise HandlerError(ERROR_NOT_IMPLEMENTED, "can't create a reply port")
        msg = self.alloc.alloc_astruct(MessageStruct, label="DosPkt")
        try:
            msg.node.name.aptr = pkt.addr
            pkt.link.aptr = msg.addr
            pkt.port.aptr = reply_port.addr
            # a real handler replies with ReplyMsg(), which uses the message's
            # own reply port, not the packet's dp_Port
            msg.reply_port.setup(reply_port.addr)
            exec_lib.PutMsg(self.handler_port, msg.addr)
            exec_lib.WaitPort(reply_port.addr)
            reply = exec_lib.GetMsg(reply_port.addr)
            if reply is None or reply.addr == 0:
                raise HandlerError(
                    ERROR_NOT_IMPLEMENTED,
                    "no reply from native handler '%s'" % self.name,
                )
            self._copy_result(pkt, reply.addr)
        finally:
            msg.free()
            exec_lib.DeleteMsgPort(reply_port)

    def _transport_in_task(self, pkt):
        """run the transport inside a helper task

        A Python-driven call has no current task, so a helper ``ExecTask`` is
        added to the scheduler and performs the transport via the exec proxy.
        The scheduler is driven until the helper is done.
        """
        holder = _ReplyHolder()
        helper = ExecTask(
            self.machine,
            self.alloc,
            "native_transport",
            func=lambda task: self._run_transport(pkt, holder),
        )
        sched_task = helper.get_sched_task()
        try:
            self.scheduler.add_task(sched_task)
            self.scheduler.run_until_idle(self.max_cycles)
            if holder.error is not None:
                raise holder.error
            if not holder.done:
                raise HandlerError(
                    ERROR_NOT_IMPLEMENTED,
                    "no reply from native handler '%s'" % self.name,
                )
        finally:
            if sched_task.get_state() != TaskState.TS_REMOVED:
                try:
                    self.scheduler.rem_task(sched_task)
                except Exception:
                    pass
            helper.free()

    def _run_transport(self, pkt, holder):
        try:
            self._transport_pkt(pkt)
        except Exception as e:  # noqa: BLE001 - reported to the caller
            holder.error = e
        finally:
            holder.done = True
        return 0

    # ----- startup/shutdown packets (driven by the manager) -----

    def send_startup(self, bstr_bptr, startup_bptr, doslist_bptr):
        """send the ``ACTION_STARTUP`` packet and return the handler port

        ``dp_Arg4`` may carry an alternative action port supplied by the
        handler; otherwise the handler's own ``pr_MsgPort`` is used.
        """
        pkt = self._make_packet(startup.ACTION_STARTUP)
        try:
            pkt.arg1.val = bstr_bptr
            pkt.arg2.val = startup_bptr
            pkt.arg3.val = doslist_bptr
            pkt.arg4.val = 0
            self._dopkt(pkt)
            if pkt.res1.val == 0:
                from ..base import ERROR_ACTION_NOT_KNOWN

                raise HandlerError(
                    ERROR_ACTION_NOT_KNOWN,
                    "native handler '%s' refused startup" % self.name,
                )
            return pkt.arg4.val
        finally:
            pkt.free()

    def send_die(self):
        """send the ``ACTION_DIE`` packet and return ``(ok, error)``

        ``ok`` is False with ``dp_Res2 == ERROR_OBJECT_IN_USE`` when the
        handler still has open locks or files.
        """
        pkt = self._make_packet(startup.ACTION_DIE)
        try:
            self._dopkt(pkt)
            return bool(pkt.res1.val), pkt.res2.val
        finally:
            pkt.free()

    def _make_packet(self, action):
        from amitools.vamos.libtypes import DosPacket

        pkt = self.alloc.alloc_astruct(DosPacket, label="NativePkt")
        pkt.type.val = int(action)
        return pkt


class _NativeDispatcher:
    """a :class:`HandlerDispatcher`-shaped shim for a native handler

    ``GetDeviceProc``/``DeviceProc``/``ReadLink`` only need ``.port`` (and
    ``free()``); a native handler's port is its running task's ``pr_MsgPort``.
    """

    def __init__(self, handler):
        self.handler = handler

    @property
    def port(self):
        return self.handler.handler_port

    def free(self):
        pass


def native_factory(name, path, cfg, file_system):
    """registry factory for the ``native`` handler type

    The handler is created detached; the manager attaches it once the base
    libraries are open.
    """
    return NativeHandler(name, cfg)
