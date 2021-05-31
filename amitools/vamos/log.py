import logging
import logging.config
from .cfgcore import log_cfg

# --- vamos loggers ---

log_main = logging.getLogger("main")

log_mem = logging.getLogger("mem")
log_mem_map = logging.getLogger("mem_map")
log_mem_alloc = logging.getLogger("mem_alloc")
log_mem_int = logging.getLogger("mem_int")
log_instr = logging.getLogger("instr")
log_machine = logging.getLogger("machine")

log_lib = logging.getLogger("lib")
log_libmgr = logging.getLogger("libmgr")
log_segload = logging.getLogger("segload")

log_path = logging.getLogger("path")
log_file = logging.getLogger("file")
log_lock = logging.getLogger("lock")
log_doslist = logging.getLogger("doslist")

log_dos = logging.getLogger("dos")
log_exec = logging.getLogger("exec")
log_utility = logging.getLogger("utility")
log_math = logging.getLogger("math")

log_proc = logging.getLogger("proc")
log_prof = logging.getLogger("prof")

log_tp = logging.getLogger("tp")
log_hw = logging.getLogger("hw")

loggers = [
    log_main,
    log_mem,
    log_mem_map,
    log_mem_alloc,
    log_mem_int,
    log_instr,
    log_lib,
    log_libmgr,
    log_path,
    log_file,
    log_lock,
    log_doslist,
    log_segload,
    log_dos,
    log_exec,
    log_proc,
    log_prof,
    log_tp,
    log_utility,
    log_hw,
    log_math,
    log_machine,
]

preset = {log_prof: logging.INFO}

# --- end ---

OFF = 100
levels = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARN,
    "error": logging.ERROR,
    "fatal": logging.FATAL,
    "off": OFF,
}
levels_str = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARN: "warn",
    logging.ERROR: "error",
    logging.FATAL: "fatal",
    OFF: "off",
}


def log_parse_level(name):
    if name in levels:
        return levels[name]
    else:
        return None


def log_help():
    print("logging channels:")
    names = [x.name for x in loggers]
    for n in sorted(names):
        print("  %s" % n)
    print()
    print("logging levels:")
    for l in levels:
        print("  %s" % l)


def log_setup(cfg):
    # setup handler
    if cfg.file != None:
        ch = logging.FileHandler(cfg.file, mode="w")
    else:
        ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # and formatter
    if cfg.timestamps:
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d %(name)10s:%(levelname)7s:  %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        formatter = logging.Formatter("%(name)10s:%(levelname)7s:  %(message)s")
    ch.setFormatter(formatter)
    for l in loggers:
        l.addHandler(ch)

    # setup default
    level = logging.WARN
    if cfg.quiet:
        log_cfg.info("log: quiet!")
        level = logging.ERROR
    for l in loggers:
        log_cfg.info("log: %s -> %s", l.name, levels_str[level])
        if l in preset:
            l.setLevel(preset[l])
        else:
            l.setLevel(level)

    # is verbose enabled?
    if cfg.verbose:
        log_cfg.info("log: verbose: set main to INFO")
        log_main.setLevel(logging.INFO)

    # parse args
    levels = cfg.levels
    if levels:
        return _setup_levels(levels)
    else:
        return True


def log_shutdown():
    logging.shutdown()


def _setup_levels(levels):
    for name in levels:
        # get and parse level
        lvl = levels[name]
        level = log_parse_level(lvl)
        if level == None:
            log_cfg.error("invalid log level: %s", lvl)
            return False
        # find logger
        if name == "all":
            for l in loggers:
                l.setLevel(level)
        else:
            found = False
            for l in loggers:
                if l.name == name:
                    l.setLevel(level)
                    found = True
                    break
            if not found:
                log_cfg.error("invalid logger: %s", name)
                return False

    return True
