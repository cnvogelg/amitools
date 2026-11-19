from amitools.vamos.handler import build_handler_manager
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.LibList import vamos_libs
from amitools.vamos.libtypes import Message, MsgPort
from amitools.vamos.loader import SegmentLoader
from amitools.vamos.log import log_libmgr
from amitools.vamos.schedule import SchedulerEvent, TaskState
from amitools.vamos.task import ExecScheduler, ExecTask

from .cfg import LibMgrCfg
from .mgr import LibManager


class SetupLibManager(object):
    def __init__(
        self,
        machine,
        mem_map,
        runner,
        scheduler,
        path_mgr,
        lib_cfg=None,
        main_profiler=None,
        handler_mgr=None,
    ):
        self.machine = machine
        self.mem_map = mem_map
        self.runner = runner
        self.path_mgr = path_mgr
        self.scheduler = scheduler
        self.alloc = mem_map.get_alloc()
        self.lib_mgr_cfg = lib_cfg
        self.main_profiler = main_profiler
        # if no handler manager is passed in, build one from the path manager
        # and take ownership of it
        self.handler_mgr = handler_mgr
        self._own_handler_mgr = handler_mgr is None
        # state
        self.seg_loader = None
        self.exec_ctx = None
        self.dos_ctx = None
        self.lib_mgr = None

    def parse_config(self, cfg):
        if not cfg:
            return True
        self.lib_mgr_cfg = LibMgrCfg.from_dict(cfg)
        return True

    def setup(self):
        # create def cfg
        if self.lib_mgr_cfg is None:
            self.lib_mgr_cfg = LibMgrCfg()
        # create segment loader
        self.seg_loader = SegmentLoader(self.alloc)
        # build handlers for the configured volumes if the caller did not
        if self.handler_mgr is None:
            self.handler_mgr = build_handler_manager(self.path_mgr)
        # setup contexts
        odg_base = self.mem_map.get_old_dos_guard_base()
        # create lib mgr
        self.lib_mgr = LibManager(
            self.machine,
            self.alloc,
            self.runner,
            self.seg_loader,
            self.lib_mgr_cfg,
            main_profiler=self.main_profiler,
        )
        # setup special lib contexts for exec and dos
        self.exec_ctx = ExecLibCtx(
            self.machine,
            self.alloc,
            self.runner,
            self.seg_loader,
            self.path_mgr,
            self.lib_mgr,
        )
        self.dos_ctx = DosLibCtx(
            self.machine,
            self.alloc,
            self.runner,
            self.seg_loader,
            self.path_mgr,
            self.scheduler,
            odg_base,
            handler_mgr=self.handler_mgr,
        )
        self.lib_mgr.add_ctx("exec.library", self.exec_ctx)
        self.lib_mgr.add_ctx("bsdsocket.library", self.exec_ctx)
        self.lib_mgr.add_ctx("dos.library", self.dos_ctx)
        # add all vamos libs
        for name in vamos_libs:
            cls = vamos_libs[name]
            self.lib_mgr.add_impl_cls(name, cls)
        # setup scheduler call back
        self.scheduler.set_event_callback(self.scheduler_event_callback)
        # return lib_mgr
        return self.lib_mgr

    def cleanup(self):
        # shutdown of libmgr needs temp stack
        sp = self.machine.get_ram_begin() - 4
        native_shutdown = None
        if self.scheduler.get_num_tasks():
            native_shutdown = self._shutdown_native_with_tasks
        self.lib_mgr.shutdown(run_sp=sp, native_shutdown=native_shutdown)
        # only release handlers we built ourselves
        if self._own_handler_mgr and self.handler_mgr is not None:
            self.handler_mgr.shutdown()
            self.handler_mgr = None

    def _shutdown_native_with_tasks(self):
        """Let native expunge functions exchange messages with helper tasks."""
        # Expunging in a standalone Runtime cannot yield at WaitPort().
        # Native class libraries commonly stop a clipboard/helper process
        # by sending it a message and waiting for its acknowledgement.
        cleanup = ExecTask(
            self.machine,
            self.alloc,
            "Library cleanup",
            stack_size=65536,
            func=lambda task: self.lib_mgr.alib_mgr.shutdown(),
        )
        task = cleanup.get_sched_task()
        self.scheduler.add_task(task)
        try:
            self.scheduler.run_until_idle()
            error = task.get_error()
            if error:
                raise error
            if task.get_state() != TaskState.TS_REMOVED:
                raise RuntimeError(
                    "native library cleanup is waiting without a runnable helper"
                )
            return task.get_exit_code()
        finally:
            if task.get_state() != TaskState.TS_REMOVED:
                self.scheduler.rem_task(task)
            cleanup.free()

    def open_base_libs(self):
        log_libmgr.info("opening base libs...")
        # first bootstrap exec
        self.lib_mgr.bootstrap_exec()
        # open exec lib
        self.exec_addr = self.lib_mgr.open_lib("exec.library", 0)
        self.exec_vlib = self.lib_mgr.get_vlib_by_addr(self.exec_addr)
        self.exec_impl = self.exec_vlib.get_impl()
        log_libmgr.info("open base lib: exec: @%06x", self.exec_addr)
        # setup exec scheduler
        self.exec_scheduler = ExecScheduler(self.scheduler, self.exec_impl.exec_lib)
        # link exec to dos
        self.dos_ctx.set_exec_lib(self.exec_impl)
        # open dos lib
        self.dos_addr = self.lib_mgr.open_lib("dos.library", 0)
        self.dos_vlib = self.lib_mgr.get_vlib_by_addr(self.dos_addr)
        self.dos_impl = self.dos_vlib.get_impl()
        self.dos_ctx.set_dos_lib(self.dos_impl)
        log_libmgr.info("open base lib: dos:  @%06x", self.dos_addr)
        # now that exec/dos (and the port manager) exist, hand the live machine
        # to any detached packet handler (``?handler=packet``)
        self._attach_packet_handlers()

    def _attach_packet_handlers(self):
        if self.handler_mgr is None:
            return
        exec_impl = self.exec_impl
        port_list = exec_impl.exec_lib.port_list
        mem = exec_impl.mem

        def put_msg(port_addr, msg_addr):
            # as PutMsg(): queue the packet and signal the handler's task
            exec_impl.msg_func.put_msg(MsgPort(mem, port_addr), Message(mem, msg_addr))

        self.handler_mgr.attach_packet_transport(
            self.alloc,
            exec_impl.port_mgr,
            mem,
            find_port=lambda name: port_list.find_name(name, promote=True),
            put_msg=put_msg,
        )

    def close_base_libs(self):
        log_libmgr.info("closing base libs...")
        # close dos
        self.lib_mgr.close_lib(self.dos_addr)
        log_libmgr.info("closed dos")
        # close exec
        self.lib_mgr.close_lib(self.exec_addr)
        log_libmgr.info("closed exec")

    def get_lib_proxy_mgr(self):
        return self.lib_mgr.get_lib_proxy_mgr()

    def scheduler_event_callback(self, event):
        if event.type != SchedulerEvent.Type.ACTIVE_TASK:
            return
        sched_task = event.task
        if sched_task:
            map_task = sched_task.map_task
            log_libmgr.info("current task: %s", map_task)
        else:
            map_task = None
            log_libmgr.info("current task: none")

        # is the map task a process?
        if map_task and map_task.ami_proc:
            process = map_task
        else:
            process = None

        self.exec_ctx.set_cur_task_process(map_task, process)
        self.dos_ctx.set_cur_process(process)
