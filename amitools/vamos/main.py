import cProfile
import io
import pstats

from .cfg import VamosMainParser
from .machine import Machine, MemoryMap
from .machine.regs import REG_D0
from .log import log_main, log_setup, log_help
from .path import VamosPathManager
from .trace import TraceManager
from .libmgr import SetupLibManager
from .schedule import Scheduler
from .profiler import MainProfiler
from .lib.dos.Process import Process

RET_CODE_CONFIG_ERROR = 1000


def main(cfg_files=None, args=None, cfg_dict=None, profile=False):
    """vamos main entry point.

    setup a vamos session and run it.
    return the error code of the executed Amiga process.

    cfg_files(opt): list/tuple of config files. first found will be read
    args(opt): None=read sys.argv, []=no args, list/tuple=args
    cfg_dict(opt): pass options directly as a dictionary

    if an internal error occurred then return:
      RET_CODE_CONFIG_ERROR (1000): config error
    """
    # --- parse config ---
    mp = VamosMainParser()
    if not mp.parse(cfg_files, args, cfg_dict):
        return RET_CODE_CONFIG_ERROR

    # --- init logging ---
    log_cfg = mp.get_log_dict().logging
    if not log_setup(log_cfg):
        log_help()
        return RET_CODE_CONFIG_ERROR

    # setup main profiler
    main_profiler = MainProfiler()
    prof_cfg = mp.get_profile_dict().profile
    main_profiler.parse_config(prof_cfg)

    # setup machine
    machine_cfg = mp.get_machine_dict().machine
    use_labels = mp.get_trace_dict().trace.labels
    machine = Machine.from_cfg(machine_cfg, use_labels)
    if not machine:
        return RET_CODE_CONFIG_ERROR

    # setup memory map
    mem_map_cfg = mp.get_machine_dict().memmap
    mem_map = MemoryMap(machine)
    if not mem_map.parse_config(mem_map_cfg):
        log_main.error("memory map setup failed!")
        return RET_CODE_CONFIG_ERROR

    # setup trace manager
    trace_mgr_cfg = mp.get_trace_dict().trace
    trace_mgr = TraceManager(machine)
    if not trace_mgr.parse_config(trace_mgr_cfg):
        log_main.error("tracing setup failed!")
        return RET_CODE_CONFIG_ERROR

    # setup path manager
    path_mgr = VamosPathManager()
    try:
        if not path_mgr.parse_config(mp.get_path_dict()):
            log_main.error("path config failed!")
            return RET_CODE_CONFIG_ERROR
        if not path_mgr.setup():
            log_main.error("path setup failed!")
            return RET_CODE_CONFIG_ERROR

        # setup scheduler
        scheduler = Scheduler(machine)

        # setup lib mgr
        lib_cfg = mp.get_libs_dict()
        slm = SetupLibManager(
            machine, mem_map, scheduler, path_mgr, main_profiler=main_profiler
        )
        if not slm.parse_config(lib_cfg):
            log_main.error("lib manager setup failed!")
            return RET_CODE_CONFIG_ERROR
        slm.setup()

        # setup profiler
        main_profiler.setup()

        # open base libs
        slm.open_base_libs()

        # setup main proc
        proc_cfg = mp.get_proc_dict().process
        main_proc = Process.create_main_proc(proc_cfg, path_mgr, slm.dos_ctx)
        if not main_proc:
            log_main.error("main proc setup failed!")
            return RET_CODE_CONFIG_ERROR

        # main loop
        task = main_proc.get_task()
        scheduler.add_task(task)
        scheduler.schedule()

        # check proc result
        ok = False
        run_state = task.get_run_state()
        if run_state.done:
            if run_state.error:
                log_main.error("vamos failed!")
                exit_code = 1
            else:
                ok = True
                # return code is limited to 0-255
                exit_code = run_state.regs[REG_D0] & 0xFF
                log_main.info("done. exit code=%d", exit_code)
                log_main.info("total cycles: %d", run_state.cycles)
        else:
            log_main.info(
                "vamos was stopped after %d cycles. ignoring result",
                machine_cfg.max_cycles,
            )
            exit_code = 0

        # shutdown main proc
        if ok:
            main_proc.free()

        # libs shutdown
        slm.close_base_libs()
        main_profiler.shutdown()
        slm.cleanup()

    finally:
        # always shutdown path manager to ensure that
        # external resources are cleaned up properly
        path_mgr.shutdown()

    # mem_map and machine shutdown
    if ok:
        mem_map.cleanup()
    machine.cleanup()

    # exit
    log_main.info("vamos is exiting: code=%d", exit_code)
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
