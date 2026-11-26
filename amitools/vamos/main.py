import cProfile
import io
import pstats

from .cfg import VamosMainParser
from .cmdcore import CommandManager
from .cmdcore.resident import ResidentCommands
from .command import get_command_dir
from .machine import Machine, MemoryMap, Runtime
from .log import log_main, log_setup, log_help
from .path import VamosPathManager, SysPathResolver
from .handler import build_handler_manager
from .trace import TraceManager
from .libmgr import SetupLibManager
from .schedule import Scheduler
from .profiler import MainProfiler
from .mode import ModeContext, ModeSetup, ProcArgs
from .disk import DiskSession

RET_CODE_CONFIG_ERROR = 1000


class _DiskDosSetupError(RuntimeError):
    """the ``--disk`` partitions could not be published in the DOS list"""


def wire_handler_transports(slm, handler_mgr, machine, scheduler, disk_session=None):
    """connect the handler transports to the lib manager lifecycle

    The handler transports need the live machine (exec/dos), so they cannot be
    attached when the handlers are bound. This registers the attach and detach
    steps as ``post_setup``/``pre_shutdown`` callbacks on ``slm``, which keeps
    the lib manager itself unaware of handlers.
    """
    if handler_mgr is None:
        return

    def attach(lib_mgr):
        exec_impl = lib_mgr.exec_impl
        port_list = exec_impl.exec_lib.port_list
        handler_mgr.attach_packet_transport(
            lib_mgr.alloc,
            exec_impl.port_mgr,
            exec_impl.mem,
            find_port=lambda name: port_list.find_name(name, promote=True),
        )
        handler_mgr.attach_native_transport(
            machine,
            lib_mgr.alloc,
            scheduler,
            lib_mgr.seg_loader,
            exec_impl,
            lib_mgr.dos_impl,
            disk_session=disk_session,
        )

    def detach(lib_mgr):
        handler_mgr.stop_native_transport()

    slm.add_post_setup_callback(attach)
    slm.add_pre_shutdown_callback(detach)


def main(
    cfg_files=None,
    args=None,
    cfg_dict=None,
    profile=False,
    mode=None,
    single_return_code=True,
):
    """vamos main entry point.

    setup a vamos session and run it.
    return the error code of the executed Amiga process.

    cfg_files(opt): list/tuple of config files. first found will be read
    args(opt): None=read sys.argv, []=no args, list/tuple=args
    cfg_dict(opt): pass options directly as a dictionary

    mode: give the vamos run mode or auto select by config
    single_return_code: if true then return only one int error code otherwise
    None or list

    if an internal error occurred then return: None
    otherwise and array with exit codes for each added task
    """
    error_code = RET_CODE_CONFIG_ERROR if single_return_code else None

    # --- parse config ---
    mp = VamosMainParser()
    if not mp.parse(cfg_files, args, cfg_dict):
        return error_code

    # --- init logging ---
    log_cfg = mp.get_log_dict().logging
    if not log_setup(log_cfg):
        log_help()
        return error_code

    # A disk session is a separate resource from host-directory volumes.
    # It stays empty unless at least one --disk option was supplied.
    disk_session = DiskSession.from_config(mp.get_disk_dict())

    # setup main profiler
    main_profiler = MainProfiler()
    prof_cfg = mp.get_profile_dict().profile
    main_profiler.parse_config(prof_cfg)

    # setup machine
    machine_cfg = mp.get_machine_dict().machine
    use_labels = mp.get_trace_dict().trace.labels
    machine = Machine.from_cfg(machine_cfg, use_labels)
    if not machine:
        return error_code

    mem_map = MemoryMap(machine)
    path_mgr = None
    handler_mgr = None
    slm = None
    slm_is_setup = False
    base_libs_are_open = False
    profiler_is_setup = False
    exit_code = error_code
    cleanup_errors = []
    execution_error = None

    def cleanup_step(name, func):
        try:
            func()
        except Exception as exc:
            cleanup_errors.append(exc)
            log_main.error("%s shutdown failed: %s", name, exc)

    try:
        # setup memory map
        mem_map_cfg = mp.get_machine_dict().memmap
        if not mem_map.parse_config(mem_map_cfg):
            log_main.error("memory map setup failed!")
            return error_code

        # setup trace manager
        trace_mgr_cfg = mp.get_trace_dict().trace
        trace_mgr = TraceManager(machine)
        if not trace_mgr.parse_config(trace_mgr_cfg):
            log_main.error("tracing setup failed!")
            return error_code

        # setup path manager
        path_mgr = VamosPathManager()
        if not path_mgr.parse_config(mp.get_path_dict()):
            log_main.error("path config failed!")
            return error_code
        if not path_mgr.setup():
            log_main.error("path setup failed!")
            return error_code

        # build file system handlers for the configured volumes
        handler_mgr = build_handler_manager(path_mgr)

        # setup scheduler
        schedule_cfg = mp.get_schedule_dict().schedule
        scheduler = Scheduler.from_cfg(machine, schedule_cfg)

        # a default runtime for m68k code execution after scheduling
        default_runtime = Runtime(machine, machine.scratch_end)

        # setup default runner
        def runner(code, name=None):
            task = scheduler.get_cur_task()
            if task:
                return task.sub_run(code, name=name)
            else:
                return default_runtime.run(code, name=name)

        # setup lib mgr
        lib_cfg = mp.get_libs_dict()
        try:
            disk_session.open()
        except (IOError, OSError, ValueError) as exc:
            log_main.error("disk setup failed: %s", exc)
            return error_code
        from .cfg.display import parse_display_scale

        try:
            display_scale = parse_display_scale(mp.get_display_dict().display.scale)
        except ValueError as exc:
            log_main.error("display setup failed: %s", exc)
            return error_code
        slm = SetupLibManager(
            machine,
            mem_map,
            runner,
            scheduler,
            path_mgr,
            main_profiler=main_profiler,
            handler_mgr=handler_mgr,
            display_scale=display_scale,
            display_aspect=mp.get_display_dict().display.aspect,
            display_backend=mp.get_display_dict().display.backend,
            display_output=mp.get_display_dict().display.output,
        )
        if not slm.parse_config(lib_cfg):
            log_main.error("lib manager setup failed!")
            return error_code
        # native handlers resolve their block device through the disk session
        slm.disk_session = disk_session
        slm.setup()
        slm_is_setup = True

        # one command manager per run: the segment loader uses it to build a
        # stub for a Python command, so both proc mode (a directly loaded
        # ``*.py``) and shell mode (RunCommand/LoadSeg) resolve commands
        # through the same registry, traps and module cache
        cmd_mgr = CommandManager(
            machine, slm.alloc, runner, proxies=slm.get_lib_proxy_mgr()
        )
        slm.seg_loader.set_command_manager(cmd_mgr)

        # publish --resident-dir commands in the DOS resident list once the
        # base libraries are open; the shell resolves them via FindSegment
        cmd_cfg = mp.get_command_dict().command
        resident = ResidentCommands(cmd_mgr)

        def register_resident_commands(lib_mgr):
            resident.setup(lib_mgr.dos_impl, lib_mgr.dos_ctx)
            # built-in commands first: a --resident-dir (or command path)
            # command with the same name is registered later and wins
            if not cmd_cfg.no_internal_commands:
                resident.add_dir(get_command_dir())
            for host_dir in cmd_cfg.resident_dir or []:
                resident.add_dir(host_dir)

        slm.add_post_setup_callback(register_resident_commands)
        # unlink the resident nodes before cmd_mgr frees the stub seglists and
        # before DosLibrary.finish_lib walks the resident list
        slm.add_pre_shutdown_callback(lambda lib_mgr: resident.shutdown())
        # free the command stubs and traps while exec/dos are still alive
        slm.add_pre_shutdown_callback(lambda lib_mgr: cmd_mgr.shutdown())

        if disk_session.get_units():
            disk_session.install_devices(slm)

            # publish the RDB partitions before the native handler transports
            # start, so a native volume whose mount name matches its partition
            # adopts that node instead of creating a duplicate (HANDLER.md 24c)
            def install_disk_dos(lib_mgr):
                try:
                    disk_session.install_dos(lib_mgr.dos_impl)
                except (RuntimeError, ValueError) as exc:
                    raise _DiskDosSetupError(str(exc)) from exc

            slm.add_post_setup_callback(install_disk_dos)
        # connect the handler transports to the lib manager lifecycle
        wire_handler_transports(slm, handler_mgr, machine, scheduler, disk_session)

        # setup profiler
        main_profiler.setup()
        profiler_is_setup = True

        # open base libs (this runs the disk DOS install, then the handlers)
        try:
            slm.open_base_libs()
        except _DiskDosSetupError as exc:
            log_main.error("DOS disk setup failed: %s", exc)
            return error_code
        base_libs_are_open = True

        # prepare mode context
        proc_cfg = mp.get_proc_dict().process
        exec_ctx = slm.exec_ctx
        dos_ctx = slm.dos_ctx
        sys_path = SysPathResolver(path_mgr)
        proc_args = ProcArgs(sys_path.file_system, sys_path.from_sys_path)
        mode_ctx = ModeContext(
            proc_cfg, exec_ctx, dos_ctx, scheduler, default_runtime, proc_args
        )

        # select mode via ModeSetup
        if mode is None:
            cmd_cfg = proc_cfg.command
            mode = ModeSetup.select(cmd_cfg)

        # run mode
        if mode is None:
            exit_code = error_code
        else:
            exit_code = mode.run(mode_ctx)
            if single_return_code:
                exit_code = exit_code[0]

    except BaseException as exc:
        execution_error = exc
        raise
    finally:
        # Keep an execution exception as the primary failure, while still
        # attempting every shutdown step and reporting cleanup failures.
        # Remove disk nodes before dos.library frees its maintained list.
        if base_libs_are_open:
            # stop the native handlers first: an adopted --disk node is owned
            # by the DiskSession and must not be freed under a running handler
            if handler_mgr is not None:
                cleanup_step("native handlers", handler_mgr.stop_native_transport)
            cleanup_step(
                "DOS disk",
                lambda: disk_session.release_dos(slm.dos_impl),
            )
            cleanup_step("base library", slm.close_base_libs)
        if profiler_is_setup:
            cleanup_step("profiler", main_profiler.shutdown)
        if slm_is_setup:
            cleanup_step("library manager", slm.cleanup)
        cleanup_step("disk", disk_session.close)
        if handler_mgr is not None:
            cleanup_step("handler manager", handler_mgr.shutdown)
        if path_mgr is not None:
            cleanup_step("path manager", path_mgr.shutdown)
        cleanup_step("memory map", mem_map.cleanup)
        cleanup_step("machine", machine.cleanup)
        if cleanup_errors and execution_error is None:
            raise cleanup_errors[0]

    # exit
    log_main.info("vamos is exiting: code=%r", exit_code)
    return exit_code


def main_profile(
    cfg_files=None, args=None, cfg_dict=None, profile_file=None, dump_profile=True
):
    """Run vamos main with profiling enabled.

    Either dump profile after run or write a profile file.
    """
    # profile run
    cpr = cProfile.Profile()
    cpr.enable()
    ret_code = main(cfg_files, args, cfg_dict)
    cpr.disable()
    # write file
    if profile_file is not None:
        cpr.dump_stats(profile_file)
    # show profile?
    if dump_profile:
        sio = io.StringIO()
        sortby = "cumulative"
        ps = pstats.Stats(cpr, stream=sio).sort_stats(sortby)
        ps.strip_dirs()
        ps.print_stats()
        txt = sio.getvalue()
        lines = txt.split("\n")
        for i in range(min(25, len(lines))):
            print((lines[i]))
    return ret_code
