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
from .lib.dos.Process import Process
from .maptask import TaskCtx

RET_CODE_CONFIG_ERROR = 1000


def main(cfg_files=None, args=None, cfg_dict=None, profile=False):
    def gen_task_list(cfg, task_ctx):
        # setup main proc
        proc_cfg = cfg.get_proc_dict().process
        main_proc = Process.create_main_proc(proc_cfg, task_ctx.dos_ctx)
        if not main_proc:
            log_main.error("main proc setup failed!")
            return None
        return [main_proc]

    exit_codes = main_run(gen_task_list, cfg_files, args, cfg_dict, profile)
    if exit_codes is None:
        return RET_CODE_CONFIG_ERROR

    # exit
    exit_code = exit_codes[0]
    log_main.info("vamos is exiting: code=%d", exit_code)
    return exit_code


def main_run(task_list_gen, cfg_files=None, args=None, cfg_dict=None, profile=False):
    """vamos main entry point.

    setup a vamos session and run it.
    return the error code of the executed Amiga process.

    task_list_gen: return list of tasks to run task_list_gen(cfg, task_ctx) -> [Task]

    cfg_files(opt): list/tuple of config files. first found will be read
    args(opt): None=read sys.argv, []=no args, list/tuple=args
    cfg_dict(opt): pass options directly as a dictionary

    if an internal error occurred then return: None
    otherwise and array with exit codes for each added task
    """
    # --- parse config ---
    mp = VamosMainParser()
    if not mp.parse(cfg_files, args, cfg_dict):
        return None

    # --- init logging ---
    log_cfg = mp.get_log_dict().logging
    if not log_setup(log_cfg):
        log_help()
        return None

    # setup main profiler
    main_profiler = MainProfiler()
    prof_cfg = mp.get_profile_dict().profile
    main_profiler.parse_config(prof_cfg)

    # setup machine
    machine_cfg = mp.get_machine_dict().machine
    use_labels = mp.get_trace_dict().trace.labels
    machine = Machine.from_cfg(machine_cfg, use_labels)
    if not machine:
        return None

    # setup memory map
    mem_map_cfg = mp.get_machine_dict().memmap
    mem_map = MemoryMap(machine)
    if not mem_map.parse_config(mem_map_cfg):
        log_main.error("memory map setup failed!")
        return None

    # setup trace manager
    trace_mgr_cfg = mp.get_trace_dict().trace
    trace_mgr = TraceManager(machine)
    if not trace_mgr.parse_config(trace_mgr_cfg):
        log_main.error("tracing setup failed!")
        return None

    # setup path manager
    path_mgr = VamosPathManager()
    try:
        if not path_mgr.parse_config(mp.get_path_dict()):
            log_main.error("path config failed!")
            return None
        if not path_mgr.setup():
            log_main.error("path setup failed!")
            return None

        # setup scheduler
        schedule_cfg = mp.get_schedule_dict().schedule
        scheduler = Scheduler.from_cfg(machine, schedule_cfg)

        # a default runtime for m68k code execution after scheduling
        default_runtime = Runtime(machine, machine.scratch_end)

        # setup default runner
        def runner(*args, **kw_args):
            task = scheduler.get_cur_task()
            if task:
                return task.sub_run(*args, **kw_args)
            else:
                return default_runtime.run(*args, **kw_args)

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
            return RET_CODE_CONFIG_ERROR
        slm.setup()

        # setup profiler
        main_profiler.setup()

        # open base libs
        slm.open_base_libs()

        # setup context for all tasks
        proxy_mgr = slm.get_lib_proxy_mgr()
        task_ctx = TaskCtx(machine, mem_map.get_alloc(), proxy_mgr)
        # hack for old Process
        task_ctx.dos_ctx = slm.dos_ctx

        # generate tasks
        task_list = task_list_gen(mp, task_ctx)
        if task_list:
            # add tasks to scheduler
            for task in task_list:
                sched_task = task.get_sched_task()
                log_main.info("add task '%s'", sched_task.get_name())
                scheduler.add_task(sched_task)

            # --- main loop ---
            # schedule tasks...
            scheduler.schedule()

            # pick up exit codes and free task
            exit_codes = []
            for task in task_list:
                # return code is limited to 0-255
                sched_task = task.get_sched_task()
                exit_code = sched_task.get_exit_code() & 0xFF
                log_main.info(
                    "done task '%s''. exit code=%d", sched_task.get_name(), exit_code
                )
                exit_codes.append(exit_code)

                run_state = sched_task.get_run_result()
                log_main.debug("run result: %r", run_state)

                # free task
                task.free()
        else:
            exit_codes = None

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

    return exit_codes


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
