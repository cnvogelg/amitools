"""``NativeHandlerManager``: owns the machine resources of native handlers.

One manager drives every ``?handler=native`` volume. It loads the handler
binary as a seglist, creates a process for it, wires up the handler's
``pr_MsgPort`` as a real Exec signal port, publishes the device node in the DOS
list (adopting the ``--disk`` partition node when the mount name matches) and
performs the startup handshake. On shutdown it sends ``ACTION_DIE`` and frees
everything it allocated.

The manager is created in :meth:`SetupLibManager.open_base_libs` once exec and
dos exist (HANDLER.md step 23g) and stopped again before the base libraries are
closed.
"""

import io
import os

from amitools.vamos.loader.fileobj import StreamFileObj
from amitools.vamos.log import log_handler
from amitools.vamos.schedule import TaskState
from amitools.vamos.task import DosProcess

from ..base import (
    ERROR_ACTION_NOT_KNOWN,
    ERROR_OBJECT_IN_USE,
    ERROR_OBJECT_NOT_FOUND,
    HandlerError,
)
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
    def __init__(
        self,
        handler,
        program,
        resources,
        entry,
        port,
        bstr_mem,
        adopted=False,
    ):
        self.handler = handler
        self.program = program
        # ``resources`` is None when the manager adopted an existing node (the
        # startup message belongs to the DiskSession then)
        self.resources = resources
        self.entry = entry
        self.port = port
        self.bstr_mem = bstr_mem
        # an adopted node is owned by the DiskSession, not by the manager
        self.adopted = adopted


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
        spec = resolve_blkdev(self.disk_session, handler.config, handler.name)
        program = self._make_program(handler, spec)
        # the handler's pr_MsgPort becomes a real Exec signal port. The port is
        # signalled with SIGB_DOS, like a process port (dos/Cli.py)
        port = program.msg_port
        configure_handler_port(port, SIGB_DOS, program.ami_task.addr)
        self.exec_impl.exec_lib.port_list.enqueue(port.node)

        bstr_mem = self._alloc_bstr(handler.binary or handler.name)
        # dol_Handler is a BSTR (a byte address), not a BPTR
        handler_addr = bstr_mem.addr if bstr_mem is not None else 0
        dos_list = self.dos_impl.dos_list
        entry = dos_list.get_device_by_name(handler.name)
        if entry is not None:
            # adopt the ``--disk`` partition node the DiskSession published
            # (step 24c): fill in the handler fields and leave ``dol_Startup``
            # (and the node's lifetime) with the DiskSession
            dos_list.fill_device(
                entry,
                task=port.addr,
                seg_list=program.seg_list_baddr,
                glob_vec=program.glob_vec,
                handler=handler_addr,
            )
            resources = None
            adopted = True
        else:
            # a mount name differing from the partition gets its own node. It
            # reuses the referenced partition's FileSysStartupMsg when the
            # session published one (the DiskSession keeps ownership); only a
            # volume without a partition node builds its own startup.
            startup_bptr = self._partition_startup_bptr(dos_list, spec)
            if startup_bptr:
                resources = None
            else:
                resources = build_startup(
                    self.alloc, spec.unit, spec.device, spec.geometry
                )
                startup_bptr = resources.startup.addr >> 2
            entry = add_device_node(
                dos_list,
                handler.name,
                startup_bptr,
                task=port.addr,
                seg_list=program.seg_list_baddr,
                glob_vec=program.glob_vec,
                handler=handler_addr,
            )
            adopted = False
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
        started = _StartedHandler(
            handler, program, resources, entry, port, bstr_mem, adopted=adopted
        )
        self.started.append(started)
        self.scheduler.add_task(program.sched_task)
        try:
            bptr = (bstr_mem.addr >> 2) if bstr_mem is not None else 0
            # an adopted node (and a created one that reused the partition
            # startup) keeps the DiskSession's FileSysStartupMsg
            if resources is not None:
                startup_bptr = resources.startup.addr >> 2
            else:
                startup_bptr = entry.struct.dol_Startup.val
            alt_port = handler.send_startup(bptr, startup_bptr, entry.baddr)
            if not alt_port:
                # a handler may move its action port by updating the device
                # node's ``dol_Task`` (SFS starts a second process for it)
                # instead of returning one in ``dp_Arg4``
                alt_port = entry.struct.dol_Task.aptr
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
        if err == ERROR_ACTION_NOT_KNOWN:
            # the handler does not implement ACTION_DIE at all (e.g. SFS
            # 1.279 replies ERROR_ACTION_NOT_KNOWN), so it cannot be asked to
            # exit; there is nothing to retry, tear it down anyway
            log_handler.warning(
                "native handler '%s' does not support ACTION_DIE; forcing teardown",
                handler.name,
            )
            return
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
        # the device node: an adopted ``--disk`` node is owned by the
        # DiskSession, so only the handler fields are cleared; a node the
        # manager created is removed and freed here (step 24c)
        try:
            dos_list = self.dos_impl.dos_list
            if started.adopted:
                dos_list.fill_device(started.entry)
            else:
                dos_list.remove_entry(started.entry)
                dos_list.free_entry(started.entry)
            self.dos_impl.update_dos_list_head()
        except Exception as e:  # noqa: BLE001
            log_handler.warning("native handler '%s' device node: %s", handler.name, e)
        if started.resources is not None:
            started.resources.free()
            started.resources = None
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

    def _make_program(self, handler, spec):
        if self.task_factory is not None:
            return self.task_factory(self, handler)
        return self._load_program(handler, spec)

    def _load_program(self, handler, spec):
        config = handler.config
        binary = handler.binary
        if binary:
            baddr = self._load_seglist(binary)
            glob_vec = config.globvec
        else:
            # no explicit binary: mount the driver the RDB stores for the
            # partition's DOS type (step 24d)
            baddr = self._load_rdb_driver(handler, spec)
            glob_vec = self._driver_globvec(config, spec)
        if baddr == 0:
            source = binary if binary else "RDB driver"
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND, "can't load native handler '%s'" % source
            )
        info = self.seg_loader.get_info(baddr)
        seglist = info.seglist
        proc = DosProcess(
            self.machine,
            self.alloc,
            "%s_handler" % handler.name,
            stack_size=config.stack,
            start_pc=seglist.get_start_pc(),
        )
        # a handler process carries its priority in the task node, exactly like
        # CreateProc/CreateNewProc do (dos/Cli.py)
        proc.proc.task.node.pri.val = config.priority
        return HandlerProgram(
            proc.get_sched_task(),
            proc.get_ami_task(),
            proc.proc.msg_port,
            seg_list_baddr=baddr,
            glob_vec=glob_vec,
            owner=_ProcessOwner(self, proc, baddr),
        )

    def _load_rdb_driver(self, handler, spec):
        """load the RDB driver seglist stored for the partition (step 24d)"""
        data = spec.driver_data
        if not data:
            raise HandlerError(
                ERROR_OBJECT_NOT_FOUND,
                "native handler '%s' has no binary configured and no RDB driver"
                % handler.name,
            )
        fobj = StreamFileObj(io.BytesIO(data))
        try:
            return self.seg_loader.load_seglist(fobj, name=handler.name)
        finally:
            fobj.close()

    @staticmethod
    def _driver_globvec(config, spec):
        """the ``dol_GlobVec`` for an RDB driver: explicit ``?globvec=`` wins"""
        if "globvec" in config.raw:
            return config.globvec
        if spec.driver_globvec is not None:
            return spec.driver_globvec
        return config.globvec

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

    @staticmethod
    def _partition_startup_bptr(dos_list, spec):
        """the ``dol_Startup`` BPTR of the partition's DOS device node (or 0)

        A ``--disk`` partition the ``DiskSession`` published carries the
        ``FileSysStartupMsg`` the handler needs, so a node created for a
        differing mount name reuses it instead of duplicating the ``DosEnvec``
        (step 24c).
        """
        if not spec.partition_name:
            return 0
        node = dos_list.get_device_by_name(spec.partition_name)
        if node is None:
            return 0
        return node.struct.dol_Startup.val


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


def build_native_manager(
    machine,
    alloc,
    scheduler,
    seg_loader,
    exec_impl,
    dos_impl,
    handler_mgr=None,
    disk_session=None,
    task_factory=None,
):
    """create a :class:`NativeHandlerManager` from live exec/dos resources

    The caller must have the base libraries open (``exec_impl``/``dos_impl``).
    """
    return NativeHandlerManager(
        machine,
        alloc,
        scheduler,
        seg_loader,
        exec_impl,
        dos_impl,
        handler_mgr=handler_mgr,
        disk_session=disk_session,
        task_factory=task_factory,
    )
