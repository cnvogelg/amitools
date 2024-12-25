import cProfile
import io
import pstats

from .cfg import VamosMainParser
from .machine import Machine, MemoryMap, Runtime
from .log import log_main, log_setup, log_help
from .path import VamosPathManager
from .trace import TraceManager
from .libmgr import SetupLibManager
from .schedule import Scheduler
from .profiler import MainProfiler
from .mode import ModeContext, ModeSetup

RET_CODE_CONFIG_ERROR = 1000


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
    single_return_code: if true then return only one int error code otherwise None or list

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

    # setup memory map
    mem_map_cfg = mp.get_machine_dict().memmap
    mem_map = MemoryMap(machine)
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
    try:
        if not path_mgr.parse_config(mp.get_path_dict()):
            log_main.error("path config failed!")
            return error_code
        if not path_mgr.setup():
            log_main.error("path setup failed!")
            return error_code

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
        slm = SetupLibManager(
            machine,
            mem_map,
            runner,
            scheduler,
            path_mgr,
            main_profiler=main_profiler,
        )
        if not slm.parse_config(lib_cfg):
            log_main.error("lib manager setup failed!")
            return error_code
        slm.setup()

        # setup profiler
        main_profiler.setup()

        # open base libs
        slm.open_base_libs()

        # prepare mode context
        proc_cfg = mp.get_proc_dict().process
        exec_ctx = slm.exec_ctx
        dos_ctx = slm.dos_ctx
        mode_ctx = ModeContext(proc_cfg, exec_ctx, dos_ctx, scheduler, default_runtime)

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

        # libs shutdown
        slm.close_base_libs()
        main_profiler.shutdown()
        slm.cleanup()

    finally:
        # always shutdown path manager to ensure that
        # external resources are cleaned up properly
        path_mgr.shutdown()

    # mem_map and machine shutdown
    mem_map.cleanup()
    machine.cleanup()

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
