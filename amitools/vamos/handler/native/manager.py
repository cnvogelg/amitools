"""``NativeHandlerManager``: owns the machine resources of native handlers.

One manager drives every ``?handler=native`` volume. It loads the handler
binary as a seglist, creates a process for it, wires up the handler's
``pr_MsgPort`` as a real Exec signal port, publishes the device node in the DOS
list and performs the startup handshake. On shutdown it sends ``ACTION_DIE``
and frees everything it allocated.

The manager is created in :meth:`SetupLibManager.open_base_libs` once exec and
dos exist (HANDLER.md step 23g) and stopped again before the base libraries are
closed.
"""

import os

from amitools.vamos.loader.fileobj import StreamFileObj
from amitools.vamos.log import log_handler
from amitools.vamos.schedule import TaskState
from amitools.vamos.task import DosProcess

from ..base import (
    ERROR_OBJECT_IN_USE,
    ERROR_OBJECT_NOT_FOUND,
    HandlerError,
)
from . import startup
from .blkdev import resolve_blkdev
from .handler import NativeHandler
from .startup import (
    SIGB_DOS,
    add_device_node,
    build_startup,
    configure_handler_port,
)

# default scheduler budget (m68k cycles) for a manager-driven run
DEFAULT_MAX_CYCLES = 100_000_000


class HandlerProgram:
    """a handler task the manager can start and free

    The default program is a :class:`~amitools.vamos.task.DosProcess` built
    from the handler seglist. Tests may supply an alternative program (e.g. a
    Python task that emulates a handler) through ``task_factory``.
    """

    def __init__(
        self,
        sched_task,
        ami_task,
        msg_port,
        seg_list_baddr=0,
        glob_vec=0,
        owner=None,
    ):
        self.sched_task = sched_task
        self.ami_task = ami_task
        self.msg_port = msg_port
        self.seg_list_baddr = seg_list_baddr
        self.glob_vec = glob_vec
        self.owner = owner

    def free(self):
        if self.owner is not None:
            self.owner.free()
            self.owner = None


class _StartedHandler:
    def __init__(self, handler, program, resources, entry, port, bstr_mem):
        self.handler = handler
        self.program = program
        self.resources = resources
        self.entry = entry
        self.port = port
        self.bstr_mem = bstr_mem


class NativeHandlerManager:
    """start/stop the 68k handler tasks of the native handler volumes"""

    def __init__(
        self,
        machine,
        alloc,
        scheduler,
        seg_loader,
        exec_impl,
        dos_impl,
        handler_mgr=None,
        disk_session=None,
        max_cycles=None,
        task_factory=None,
    ):
        self.machine = machine
        self.alloc = alloc
        self.scheduler = scheduler
        self.seg_loader = seg_loader
        self.exec_impl = exec_impl
        self.dos_impl = dos_impl
        self.handler_mgr = handler_mgr
        self.disk_session = disk_session
        self.max_cycles = DEFAULT_MAX_CYCLES if max_cycles is None else max_cycles
        self.task_factory = task_factory
        self.started = []

    # ----- lifecycle -----

    def start_all(self):
        """start every detached native handler registered with the manager"""
        if self.handler_mgr is None:
            return
        for handler in self.handler_mgr.get_all_handlers():
            if isinstance(handler, NativeHandler):
                self.start(handler)

    def start(self, handler):
        """load, start and publish one native handler"""
        if self._find(handler) is not None:
            return handler
        spec = resolve_blkdev(self.disk_session, handler.cfg)
        program = self._make_program(handler)
        # the handler's pr_MsgPort becomes a real Exec signal port. The port is
        # signalled with SIGB_DOS, like a process port (dos/Cli.py)
        port = program.msg_port
        configure_handler_port(port, SIGB_DOS, program.ami_task.addr)
        self.exec_impl.exec_lib.port_list.enqueue(port.node)

        resources = build_startup(self.alloc, spec.unit, spec.device, spec.geometry)
        bstr_mem = self._alloc_bstr(handler.binary or handler.name)
        entry = add_device_node(
            self.dos_impl.dos_list,
            handler.name,
            resources.startup.addr >> 2,
            task=port.addr,
            seg_list=program.seg_list_baddr,
            glob_vec=program.glob_vec,
            # dol_Handler is a BSTR (a byte address), not a BPTR
            handler=bstr_mem.addr if bstr_mem is not None else 0,
        )
        self.dos_impl.update_dos_list_head()

        handler.attach_native(
            self,
            self.machine,
            self.alloc,
            self.alloc.get_mem(),
            self.exec_impl.port_mgr,
            self.exec_impl,
            self.scheduler,
            port.addr,
            max_cycles=self.max_cycles,
        )
        started = _StartedHandler(handler, program, resources, entry, port, bstr_mem)
        self.started.append(started)
        self.scheduler.add_task(program.sched_task)
        try:
            bptr = (bstr_mem.addr >> 2) if bstr_mem is not None else 0
            alt_port = handler.send_startup(
                bptr, resources.startup.addr >> 2, entry.baddr
            )
            if alt_port:
                handler.handler_port = alt_port
        except Exception:
            self._teardown(started)
            raise
        log_handler.info("started native handler '%s'", handler.name)
        return handler

    def stop(self, handler):
        """stop one handler (idempotent)

        Sends ``ACTION_DIE``. A handler that still holds locks or files refuses
        to die with ``ERROR_OBJECT_IN_USE``; the error is raised and the handler
        is left running so the caller can close its objects and retry (or call
        :meth:`shutdown` to force the teardown).
        """
        started = self._find(handler)
        if started is None:
            return
        self._request_die(started)
        self._teardown(started)

    def shutdown(self):
        """stop every started handler, preserving the first error

        A handler that refuses to die is torn down anyway, so no resource is
        leaked; the first refusal is re-raised once every handler is freed.
        """
        first_error = None
        for started in list(self.started):
            try:
                self._request_die(started)
            except Exception as e:  # noqa: BLE001 - preserve the first error
                if first_error is None:
                    first_error = e
            finally:
                self._teardown(started)
        if first_error is not None:
            raise first_error

    def _request_die(self, started):
        """send ``ACTION_DIE`` and raise if the handler refuses to die"""
        handler = started.handler
        try:
            ok, err = handler.send_die()
        except HandlerError as e:
            # the handler already died or never answered: the teardown still
            # runs, but a dead handler is not an error to report
            log_handler.warning("native handler '%s' stop: %s", handler.name, e)
            return
        if ok:
            return
        if err == ERROR_OBJECT_IN_USE:
            raise HandlerError(err, "native handler still has open objects")
        raise HandlerError(err, "native handler '%s' refused to die" % handler.name)

    def _teardown(self, started):
        if started not in self.started:
            return
        self.started.remove(started)
        handler = started.handler
        # unlink the port from the exec port list
        node = started.port.node
        try:
            if node.get_succ_addr() is not None:
                node.remove()
        except Exception:
            pass
        # remove + free the device node
        try:
            self.dos_impl.dos_list.remove_entry(started.entry)
            self.dos_impl.dos_list.free_entry(started.entry)
            self.dos_impl.update_dos_list_head()
        except Exception as e:  # noqa: BLE001
            log_handler.warning("native handler '%s' device node: %s", handler.name, e)
        started.resources.free()
        if started.bstr_mem is not None:
            self.alloc.free_bstr(started.bstr_mem)
            started.bstr_mem = None
        # make sure the task is gone before its memory is freed
        sched_task = started.program.sched_task
        if sched_task.get_state() != TaskState.TS_REMOVED:
            try:
                self.scheduler.rem_task(sched_task)
            except Exception:
                pass
        started.program.free()
        # unbind and free the reply port the manager created at attach time
        handler.detach_native()
        log_handler.info("stopped native handler '%s'", handler.name)

    def _find(self, handler):
        for started in self.started:
            if started.handler is handler:
                return started
        return None

    # ----- program creation -----

    def _make_program(self, handler):
        if self.task_factory is not None:
            return self.task_factory(self, handler)
        return self._load_program(handler)

    def _load_program(self, handler):
        binary = handler.binary
        if not binary:
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND,
                "native handler '%s' has no binary configured" % handler.name,
            )
        baddr = self._load_seglist(binary)
        if baddr == 0:
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND, "can't load native handler '%s'" % binary
            )
        info = self.seg_loader.get_info(baddr)
        seglist = info.seglist
        proc = DosProcess(
            self.machine,
            self.alloc,
            "%s_handler" % handler.name,
            start_pc=seglist.get_start_pc(),
        )
        return HandlerProgram(
            proc.get_sched_task(),
            proc.get_ami_task(),
            proc.proc.msg_port,
            seg_list_baddr=baddr,
            glob_vec=startup.GLOBVEC_C,
            owner=_ProcessOwner(self, proc, baddr),
        )

    def _load_seglist(self, binary):
        text = str(binary)
        if ":" in text and not os.path.exists(text):
            return self.seg_loader.load_ami_seglist(text)
        if not os.path.exists(text):
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND, "native handler not found: %s" % text
            )
        fobj = open(text, "rb")
        try:
            baddr = self.seg_loader.load_seglist(StreamFileObj(fobj), name=text)
        except Exception:
            fobj.close()
            raise
        return baddr

    def _alloc_bstr(self, text):
        if not text:
            return None
        return self.alloc.alloc_bstr(str(text), label="NativeHandlerName")


class _ProcessOwner:
    """frees a :class:`DosProcess` and its seglist"""

    def __init__(self, manager, proc, seglist_baddr):
        self.manager = manager
        self.proc = proc
        self.seglist_baddr = seglist_baddr

    def free(self):
        proc = self.proc
        self.proc = None
        if proc is not None:
            proc.free()
        if self.seglist_baddr:
            self.manager.seg_loader.unload_seglist(self.seglist_baddr)
            self.seglist_baddr = 0


def build_native_manager(slm, disk_session=None, task_factory=None):
    """create a :class:`NativeHandlerManager` for an initialized ``SetupLibManager``

    ``slm`` must have its base libraries open (``exec_impl``/``dos_impl``).
    """
    return NativeHandlerManager(
        slm.machine,
        slm.alloc,
        slm.scheduler,
        slm.seg_loader,
        slm.exec_impl,
        slm.dos_impl,
        handler_mgr=slm.handler_mgr,
        disk_session=disk_session,
        task_factory=task_factory,
    )
