from amitools.vamos.handler import build_handler_manager
from amitools.vamos.lib.dos.DosLibCtx import DosLibCtx
from amitools.vamos.lib.lexec.ExecLibCtx import ExecLibCtx
from amitools.vamos.lib.LibList import vamos_libs
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
        display_scale=(1, 1),
        display_aspect="square",
        display_backend="sdl",
        display_output="vamos-frames",
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
        self.display_scale = display_scale
        self.display_aspect = display_aspect
        from amitools.vamos.display import create_display

        self.display = create_display(display_backend, display_output)
        # state
        self.seg_loader = None
        self.exec_ctx = None
        self.dos_ctx = None
        self.lib_mgr = None
        # the disk session backing native handlers (set by ``main`` before the
        # base libraries are opened)
        self.disk_session = None
        # strict-LVO audit (step 23h); must be set before the libs are opened
        self._strict_lvo = False
        # optional lifecycle hooks; the top-level wiring uses them to attach
        # and detach resources (e.g. the handler transports) that need the open
        # base libraries, without the lib manager having to know about them
        self._post_setup_callbacks = []
        self._pre_shutdown_callbacks = []

    def parse_config(self, cfg):
        if not cfg:
            return True
        self.lib_mgr_cfg = LibMgrCfg.from_dict(cfg)
        return True

    def set_strict_lvo(self, flag):
        """enable the strict-LVO audit (call before :meth:`setup`)"""
        self._strict_lvo = bool(flag)
        if self.lib_mgr is not None:
            self.lib_mgr.set_strict_lvo(self._strict_lvo)

    def add_post_setup_callback(self, callback):
        """register a callback run once the base libraries are open

        The callback is invoked with this setup manager at the end of
        :meth:`open_base_libs`, when exec/dos and their helpers are live.
        """
        self._post_setup_callbacks.append(callback)

    def add_pre_shutdown_callback(self, callback):
        """register a callback run before the base libraries close

        The callback is invoked with this setup manager at the start of
        :meth:`close_base_libs` (and again from :meth:`cleanup` if the base
        libraries were not closed), while exec/dos are still alive. It must be
        idempotent.
        """
        self._pre_shutdown_callbacks.append(callback)

    def _run_callbacks(self, callbacks):
        for callback in callbacks:
            callback(self)

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
        self.lib_mgr.set_strict_lvo(self._strict_lvo)
        self.lib_mgr.vlib_mgr.set_ctx_extra_attr("scheduler", self.scheduler)
        self.lib_mgr.vlib_mgr.set_ctx_extra_attr("display", self.display)
        # setup special lib contexts for exec and dos
        self.exec_ctx = ExecLibCtx(
            self.machine,
            self.alloc,
            self.runner,
            self.seg_loader,
            self.path_mgr,
            self.lib_mgr,
        )
        self.exec_ctx.scheduler = self.scheduler
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
        self.dos_ctx.lib_mgr = self.lib_mgr
        for name in ("asl", "diskfont", "iffparse", "icon", "datatypes"):
            self.lib_mgr.add_ctx(name + ".library", self.dos_ctx)
        self.exec_ctx.display_scale = self.display_scale
        self.exec_ctx.display_aspect = self.display_aspect
        self.lib_mgr.add_ctx("exec.library", self.exec_ctx)
        self.lib_mgr.add_ctx("bsdsocket.library", self.exec_ctx)
        self.lib_mgr.add_ctx("keymap.library", self.exec_ctx)
        self.lib_mgr.add_ctx("gadtools.library", self.exec_ctx)
        self.lib_mgr.add_ctx("layers.library", self.exec_ctx)
        self.lib_mgr.add_ctx("intuition.library", self.exec_ctx)
        self.lib_mgr.add_ctx("graphics.library", self.exec_ctx)
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
        # detach any resource that was not detached by close_base_libs here,
        # before the base libraries are torn down (the hooks are idempotent)
        self._run_callbacks(self._pre_shutdown_callbacks)
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
        # the base libraries are live now: run the post-setup hooks. The
        # top-level wiring attaches the handler transports here.
        self._run_callbacks(self._post_setup_callbacks)

    def close_base_libs(self):
        log_libmgr.info("closing base libs...")
        # run the pre-shutdown hooks (the top-level wiring detaches the handler
        # transports here) while exec/dos are still alive
        self._run_callbacks(self._pre_shutdown_callbacks)
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
